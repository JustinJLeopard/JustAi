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


# ── Slice 2: result / synthesis / learning vocabulary + tally ────────────────
# One shared vocabulary (justai.results.tally) that the synthesizer and the
# learning layer both read, so they cannot disagree about what a result set
# means. Empty and unknown-status runs must never read as success. (Finding 4 +
# the tally unit of Finding 7b. The orchestrator fail-closed integration —
# Finding 7 whole-run + Finding 8 stage tally — is the next slice.)

import pytest as _pytest
from types import SimpleNamespace as _SNS

from justai.results import DelegationResult as _DR


def _result(status: str = "done", title: str = "task") -> _DR:
    return _DR(task_id="t", title=title, status=status, result="ok", duration_seconds=1.0)


def test_synthesize_refuses_to_call_an_empty_run_complete():
    from justai.synthesizer import synthesize

    summary = synthesize("goal", "execution", [], "test", 1.0)

    assert summary.total_tasks == 0
    assert summary.status != "complete"


def test_synthesize_rejects_an_unknown_result_status():
    from justai.synthesizer import synthesize

    with _pytest.raises(ValueError, match="unknown result status"):
        synthesize("goal", "execution", [_result("mission-accomplished")], "test", 1.0)


def test_synthesize_counts_blocked_results_without_calling_them_complete():
    from justai.synthesizer import synthesize

    summary = synthesize("goal", "execution", [_result("blocked"), _result("done")], "test", 1.0)

    assert summary.blocked == 1
    assert summary.status == "partial"


def test_synthesize_unverified_run_is_partial_not_complete():
    """JustAi's honest 3-state: an executed-but-unverified task is not done."""
    from justai.synthesizer import synthesize

    summary = synthesize("goal", "execution", [_result("unverified")], "test", 1.0)

    assert summary.status == "partial"


def test_learning_does_not_record_an_empty_run_as_successful():
    from justai.learning import record_run

    with patch("justai.learning._store") as store:
        store.store.return_value = True
        recorded = record_run("goal", [], duration=1.0)

    assert recorded is False
    store.store.assert_not_called()


def test_learning_does_not_call_a_fully_skipped_run_successful():
    from justai.learning import record_run

    with patch("justai.learning._store") as store:
        store.store.return_value = True
        record_run("goal", [_result("skipped"), _result("blocked")], duration=1.0)

    assert store.store.call_args.kwargs["outcome"] != "success"


def test_learning_rejects_an_unknown_result_status_instead_of_storing_success():
    from justai.learning import record_run

    with patch("justai.learning._store") as store:
        store.store.return_value = True
        recorded = record_run("goal", [_result("mission-accomplished")], duration=1.0)

    assert recorded is False
    store.store.assert_not_called()


def test_synthesizer_and_learning_agree_on_what_counts_as_success():
    """The two surfaces must not disagree about the same result set."""
    from justai.learning import record_run
    from justai.synthesizer import synthesize

    cases = [
        [],
        [_result("done")],
        [_result("done"), _result("skipped")],
        [_result("failed")],
        [_result("blocked")],
    ]
    for results in cases:
        summary = synthesize("goal", "execution", results, "test", 1.0)
        with patch("justai.learning._store") as store:
            store.store.return_value = True
            record_run("goal", results, duration=1.0)
            outcome = (
                store.store.call_args.kwargs["outcome"] if store.store.call_args else "not-recorded"
            )
        assert (summary.status == "complete") == (outcome == "success"), (
            f"disagreement for {[r.status for r in results]}: "
            f"synthesizer={summary.status} learning={outcome}"
        )


def test_tally_rejects_a_non_numeric_duration():
    from justai.results import tally

    with _pytest.raises(ValueError, match="'duration_seconds' must be a number"):
        tally(
            [
                _SNS(
                    task_id="t", title="Task 0", status="done", result="ok", duration_seconds="fast"
                )
            ]
        )


def test_tally_rejects_a_result_set_that_is_not_a_sequence():
    from justai.results import tally

    with _pytest.raises(ValueError, match="must be a sequence of results"):
        tally(None)


def test_a_result_without_a_duration_is_still_countable():
    """Guarding the opposite error: only what a surface reads may be required."""
    from justai.results import tally

    counts = tally([_SNS(task_id="t", title="Task 0", status="done", result="ok")])

    assert counts.done == 1


# ── Finding 7: unusable results fail the run closed (not a traceback) ─────────
# The orchestrator must turn an unusable executor result set into a FAILED run
# that still flushes traces, files a record, and tells the operator what was
# wrong — never a traceback that loses the evidence, never a silent success.
# Bounded to the three named result-set regressions (unknown status, malformed
# shape, non-sequence). Rejected-blocked-index (needs dependency indexing) and
# stage-tally are later slices.

import os as _os
from contextlib import contextmanager as _contextmanager

from justai.exit_codes import for_run_status as _for_run_status
from justai.scope_planner import AgentType as _AgentType
from justai.scope_planner import Plan as _Plan
from justai.scope_planner import RiskLevel as _RiskLevel
from justai.scope_planner import Task as _Task


def _task(title: str) -> _Task:
    return _Task(
        title=title,
        description=f"Do {title}.",
        agent=_AgentType.MINI,
        risk=_RiskLevel.R0,
        success_criteria="echo ok",
        depends_on=[],
    )


def _trace_ctx7():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.end = MagicMock()
    return ctx


def _execution_intent7():
    from justai.intent_gate import Intent, IntentResult

    return IntentResult(
        intent=Intent("execution"), confidence=0.9, reasoning="test", clarifying_question=""
    )


def _approved_review7():
    from justai.reviewer import ReviewResult

    return ReviewResult(approved=True, feedback=[])


@_contextmanager
def _orchestrated_run(plan, **overrides):
    """Stub every stage but the one under test; keep memory writes local."""
    stubs = {
        "classify": MagicMock(return_value=_execution_intent7()),
        "decompose": MagicMock(return_value=plan),
        "review": MagicMock(return_value=_approved_review7()),
        "evaluate": MagicMock(return_value=(True, "auto")),
        "preflight": MagicMock(return_value=[]),
        "print_preflight": MagicMock(return_value=True),
        "flush_traces": MagicMock(),
        "trace_generation": MagicMock(side_effect=lambda *a, **k: _trace_ctx7()),
        "trace_event": MagicMock(),
        "record_run": MagicMock(),
        "enrich_context": MagicMock(return_value=""),
        "_memory": MagicMock(),
        "_ledger": MagicMock(),
        "OrchestratorHook": MagicMock(),
    }
    stubs.update(overrides)
    # Isolate os.environ: orchestrator.run(auto=True) sets JUSTAI_AUTO_MODE=1
    # globally (pre-existing; flagged to Codex). patch.dict snapshots + restores
    # so these tests stay hermetic and cannot leak auto-mode into later tests.
    with patch.dict(_os.environ), patch.multiple(
        "justai.orchestrator", **stubs
    ), patch("justai.synthesizer._memory", MagicMock()):
        yield stubs


def test_an_unknown_result_status_fails_the_run_closed_instead_of_raising(capsys):
    from justai.orchestrator import run

    plan = _Plan(goal="g", tasks=[_task("Task 0")], session_ref="t")
    unusable = [_result("mission-accomplished", title="Task 0")]

    with _orchestrated_run(plan, escalate_plan=MagicMock(return_value=unusable)) as stubs:
        result = run("goal", session_ref="t", auto=True, local=True)

    assert result.status == "failed"
    assert _for_run_status(result.status) != 0, "an uncountable run must not exit 0"

    out = capsys.readouterr().out
    assert "mission-accomplished" in out, "the operator must be told which status was unusable"
    assert "Task 0" in out, "and which task carried it"

    stubs["flush_traces"].assert_called_once()
    stubs["record_run"].assert_called_once()
    stubs["OrchestratorHook"].return_value.on_error.assert_called_once()


@_pytest.mark.parametrize(
    "malformed",
    [
        _pytest.param(_SNS(title="Task 0", status="done", result="ok"), id="missing-task-id"),
        _pytest.param(_SNS(task_id="t", status="done", result="ok"), id="missing-title"),
        _pytest.param(_SNS(task_id="t", title="Task 0", result="ok"), id="missing-status"),
        _pytest.param(_SNS(task_id="t", title="Task 0", status="done"), id="missing-result"),
        _pytest.param(_SNS(task_id="t", title=7, status="done", result="ok"), id="non-string-title"),
        _pytest.param(
            _SNS(task_id="t", title="Task 0", status=["done"], result="ok"), id="non-string-status"
        ),
        _pytest.param(
            _SNS(task_id="t", title="Task 0", status="done", result=7), id="non-string-result"
        ),
    ],
)
def test_a_malformed_result_still_preserves_the_failed_run(malformed):
    from justai.orchestrator import run

    plan = _Plan(goal="g", tasks=[_task("Task 0")], session_ref="t")

    with _orchestrated_run(plan, escalate_plan=MagicMock(return_value=[malformed])) as stubs:
        result = run("goal", session_ref="t", auto=True, local=True)

    assert result.status == "failed"
    assert _for_run_status(result.status) != 0
    stubs["OrchestratorHook"].return_value.on_error.assert_called_once()
    stubs["_ledger"].record.assert_called()
    stubs["record_run"].assert_called_once()
    stubs["flush_traces"].assert_called_once()


def test_a_non_numeric_duration_preserves_the_failed_run():
    from justai.orchestrator import run

    plan = _Plan(goal="g", tasks=[_task("Task 0")], session_ref="t")
    malformed = _SNS(
        task_id="t", title="Task 0", status="done", result="ok", duration_seconds="fast"
    )

    with _orchestrated_run(plan, escalate_plan=MagicMock(return_value=[malformed])) as stubs:
        result = run("goal", session_ref="t", auto=True, local=True)

    assert result.status == "failed"
    assert _for_run_status(result.status) != 0
    stubs["OrchestratorHook"].return_value.on_error.assert_called_once()
    stubs["_ledger"].record.assert_called()
    stubs["record_run"].assert_called_once()
    stubs["flush_traces"].assert_called_once()


@_pytest.mark.parametrize("returned", [None, {"0": "done"}, "done"])
def test_an_executor_that_returns_no_sequence_preserves_the_failed_run(returned):
    from justai.orchestrator import run

    plan = _Plan(goal="g", tasks=[_task("Task 0")], session_ref="t")

    with _orchestrated_run(plan, escalate_plan=MagicMock(return_value=returned)) as stubs:
        result = run("goal", session_ref="t", auto=True, local=True)

    assert result.status == "failed"
    assert result.results == [], "nothing countable was produced, so nothing may be reported"
    stubs["OrchestratorHook"].return_value.on_error.assert_called_once()
    stubs["_ledger"].record.assert_called()
    stubs["record_run"].assert_called_once()
    stubs["flush_traces"].assert_called_once()
