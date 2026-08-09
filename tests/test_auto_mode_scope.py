"""run(auto=True) must scope JUSTAI_AUTO_MODE to the run, not leak it.

Before this fix, run(auto=True) set os.environ["JUSTAI_AUTO_MODE"]="1" and never
restored it, so a later run(auto=False) inherited auto approval and skipped its
R1 checkpoint waits — a sticky, cross-run (and cross-test) leak.
"""

from __future__ import annotations

import os

from unittest.mock import MagicMock, patch


def _trace_ctx():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.end = MagicMock()
    return ctx


def _pipeline_stubs():
    """Stub every stage so run() completes fast and hermetically.

    Deliberately does NOT patch os.environ — these tests assert on it. Fidelity
    is forced to skip so no live model endpoint is contacted.
    """
    from justai.intent_gate import Intent, IntentResult
    from justai.results import DelegationResult
    from justai.reviewer import ReviewResult
    from justai.scope_planner import AgentType, Plan, RiskLevel, Task

    plan = Plan(
        goal="g",
        tasks=[Task("Task 0", "do it", AgentType.MINI, RiskLevel.R0, "echo ok", [])],
        session_ref="t",
    )
    done = DelegationResult(task_id="t", title="Task 0", status="done", result="ok", duration_seconds=1.0)
    return {
        "classify": MagicMock(
            return_value=IntentResult(
                intent=Intent("execution"), confidence=0.9, reasoning="t", clarifying_question=""
            )
        ),
        "decompose": MagicMock(return_value=plan),
        "review": MagicMock(return_value=ReviewResult(approved=True, feedback=[])),
        "evaluate": MagicMock(return_value=(True, "auto")),
        "escalate_plan": MagicMock(return_value=[done]),
        "preflight": MagicMock(return_value=[]),
        "print_preflight": MagicMock(return_value=True),
        "flush_traces": MagicMock(),
        "trace_generation": MagicMock(side_effect=lambda *a, **k: _trace_ctx()),
        "trace_event": MagicMock(),
        "record_run": MagicMock(),
        "enrich_context": MagicMock(return_value=""),
        "score_fidelity": MagicMock(side_effect=RuntimeError("skip fidelity")),
        "_memory": MagicMock(),
        "_ledger": MagicMock(),
        "OrchestratorHook": MagicMock(),
    }


def test_auto_run_does_not_leave_auto_mode_set(monkeypatch):
    from justai.orchestrator import run

    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)
    with patch.multiple("justai.orchestrator", **_pipeline_stubs()), patch(
        "justai.synthesizer._memory", MagicMock()
    ):
        run("g", auto=True, local=True)

    assert "JUSTAI_AUTO_MODE" not in os.environ, (
        "auto=True leaked JUSTAI_AUTO_MODE process-wide; a later auto=False run "
        "would inherit auto approval"
    )


def test_auto_run_restores_a_prior_auto_mode_value(monkeypatch):
    from justai.orchestrator import run

    monkeypatch.setenv("JUSTAI_AUTO_MODE", "0")
    with patch.multiple("justai.orchestrator", **_pipeline_stubs()), patch(
        "justai.synthesizer._memory", MagicMock()
    ):
        run("g", auto=True, local=True)

    assert os.environ["JUSTAI_AUTO_MODE"] == "0", "prior JUSTAI_AUTO_MODE value not restored"


def test_non_auto_run_leaves_env_untouched(monkeypatch):
    from justai.orchestrator import run

    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)
    with patch.multiple("justai.orchestrator", **_pipeline_stubs()), patch(
        "justai.synthesizer._memory", MagicMock()
    ):
        run("g", auto=False, local=True)

    assert "JUSTAI_AUTO_MODE" not in os.environ
