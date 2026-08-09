"""Completion-integrity contracts — B1 slice 1: readiness + exit codes.

Every test here pins one rule: JustAi must never signal success for work it
did not verify. This file is ported from the main lineage in bounded slices
(Desktop Codex 1916 scope guidance). Slice 1 covers the two surfaces that can
leak a false success via a process/readiness signal:

  Finding 1 — readiness semantics must agree across CLI and API, and an empty
              or partially-down probe set is not "ok".
  Finding 2 — an ambiguous run with no tasks must not exit 0.

Later slices add: result/synthesis/learning vocabulary + tally (slice 2) and
dependency-index preservation (separate claim). Gate-run ownership is deferred
(B2 architecture decision).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# tools/justai_cli.py imports its sibling as a top-level module, so `tools/`
# has to be importable before this file's legacy-CLI test can load it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from justai.health import ServiceStatus


def _statuses(*, litellm: bool = True, safe_mini: bool = False, memory: bool = True):
    return [
        ServiceStatus("LiteLLM", "http://localhost:4000", litellm, "probe"),
        ServiceStatus("safe-mini boundary", "justai.runner_protocol", safe_mini, "probe"),
        ServiceStatus("claude-flow MCP", "http://127.0.0.1:3100", memory, "probe"),
    ]


# ── Finding 1: readiness semantics disagree across CLI and API ───────────────


def test_status_exit_code_does_not_contradict_api_all_ok():
    """`justai status` must not exit 0 while the API reports all_ok false."""
    from justai.api import _get_health
    from justai.cli import cmd_status

    statuses = _statuses(safe_mini=False)
    with (
        patch("justai.health.preflight", return_value=statuses),
        patch("justai.api.preflight", return_value=statuses),
        patch("justai.memory.Memory", MagicMock()),
    ):
        health = _get_health()
        code = cmd_status(argparse.Namespace())

    assert health["all_ok"] is False
    assert code != 0, "status exited 0 while the API reported the control plane not ok"


def test_status_reports_planning_and_execution_readiness_separately():
    """Readiness must name which capability is available, not collapse to one bit."""
    from justai.health import readiness

    r = readiness(_statuses(litellm=True, safe_mini=False))

    assert r.planning_ready is True, "model-backed planning is available and must say so"
    assert r.execution_ready is False, "no concrete runner is integrated"
    assert r.all_ok is False


def test_api_health_exposes_the_same_readiness_fields_as_the_cli():
    from justai.api import _get_health

    with patch("justai.api.preflight", return_value=_statuses()):
        health = _get_health()

    assert health["planning_ready"] is True
    assert health["execution_ready"] is False
    assert health["all_ok"] is False


def test_readiness_of_an_empty_probe_set_is_not_ok():
    """No evidence is not evidence of health."""
    from justai.health import readiness

    assert readiness([]).all_ok is False


def test_status_exits_zero_only_when_every_probe_is_ok():
    from justai.cli import cmd_status
    from justai.exit_codes import OK

    statuses = _statuses(litellm=True, safe_mini=True, memory=True)
    with (
        patch("justai.health.preflight", return_value=statuses),
        patch("justai.memory.Memory", MagicMock()),
    ):
        assert cmd_status(argparse.Namespace()) == OK


# ── Finding 2: an ambiguous run with no tasks exits 0 ────────────────────────


def test_ambiguous_run_does_not_exit_zero():
    """Exit 0 is reserved for verified completion; a question is not completion."""
    from justai.cli import cmd_run
    from justai.exit_codes import CLARIFICATION_REQUIRED
    from justai.orchestrator import OrchestrationResult

    ambiguous = OrchestrationResult(
        goal="do something vague",
        intent="ambiguous",
        task_count=0,
        results=[],
        duration_seconds=0.1,
        status="ambiguous",
    )
    args = argparse.Namespace(goal=["do", "something"], session="", auto=True, local=True)
    with patch("justai.orchestrator.run", return_value=ambiguous):
        code = cmd_run(args)

    assert code == CLARIFICATION_REQUIRED
    assert code != 0


def test_legacy_tools_cli_also_refuses_to_exit_zero_when_ambiguous():
    from types import SimpleNamespace

    from justai.exit_codes import CLARIFICATION_REQUIRED
    from justai.orchestrator import OrchestrationResult
    from tools.justai_cli import run_cmd

    ambiguous = OrchestrationResult("goal", "ambiguous", 0, [], 1.0, "ambiguous")
    with patch("justai.orchestrator.run", return_value=ambiguous):
        code = run_cmd(SimpleNamespace(goal="goal", session_ref="test"))

    assert code == CLARIFICATION_REQUIRED


def test_exit_zero_requires_a_complete_run_with_at_least_one_task():
    from justai.exit_codes import FAILED, OK, for_run_status

    assert for_run_status("complete") == OK
    assert for_run_status("partial") == FAILED
    assert for_run_status("blocked") == FAILED
    assert for_run_status("failed") == FAILED


# ── Slice 1 follow-up (Desktop Codex 1951 exact review) ──────────────────────
# Three functional misses inside the readiness/exit slice: the direct module
# entrypoint still exited 0 on ambiguous; execution readiness was true from a
# mere Protocol stub; an unauthorized (401/403) planning endpoint read healthy.


def test_direct_orchestrator_module_does_not_exit_zero_when_ambiguous():
    """`python -m justai.orchestrator` must route its exit through the shared
    mapping, not its own `complete/ambiguous -> 0` shortcut."""
    from justai.exit_codes import CLARIFICATION_REQUIRED, OK
    from justai.orchestrator import OrchestrationResult, _run_cli

    ambiguous = OrchestrationResult("g", "ambiguous", 0, [], 0.1, "ambiguous")
    with patch("justai.orchestrator.run", return_value=ambiguous):
        assert _run_cli(["do", "something"]) == CLARIFICATION_REQUIRED

    complete = OrchestrationResult("g", "execution", 1, [], 0.1, "complete")
    with patch("justai.orchestrator.run", return_value=complete):
        assert _run_cli(["do", "something"]) == OK


def test_execution_readiness_is_not_true_from_a_mere_protocol_stub():
    """A Protocol stub import is not a usable runner."""
    from justai.health import check_safe_mini_boundary

    assert check_safe_mini_boundary().ok is False


def test_planning_readiness_is_not_true_when_unauthorized():
    """An unauthorized (401/403) planning endpoint cannot plan -> not ok, and
    readiness must not surface planning_ready/all_ok true off it."""
    import urllib.error

    from justai.health import check_litellm, readiness

    err = urllib.error.HTTPError(
        "http://localhost:4000/v1/models",
        401,
        "Unauthorized",
        {"Content-Type": "application/json"},
        None,
    )
    err.read = lambda: b'{"error": {"message": "litellm: invalid api key"}}'
    with patch("urllib.request.urlopen", side_effect=err):
        status = check_litellm()
        assert status.ok is False
        r = readiness([status])
        assert r.planning_ready is False
        assert r.all_ok is False
