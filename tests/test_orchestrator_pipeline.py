"""Focused orchestrator and CLI pipeline tests kept after backend amputation."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from justai.results import DelegationResult


def _trace_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.end = MagicMock()
    return ctx


def _intent(intent_type: str = "execution", confidence: float = 0.9):
    from justai.intent_gate import Intent, IntentResult

    return IntentResult(
        intent=Intent(intent_type),
        confidence=confidence,
        reasoning="test reasoning",
        clarifying_question="" if intent_type != "ambiguous" else "What do you mean?",
    )


def _plan(n_tasks: int = 1):
    from justai.scope_planner import AgentType, Plan, RiskLevel, Task

    return Plan(
        goal="test goal",
        tasks=[
            Task(
                title=f"Task {i}",
                description=f"Do thing {i}.",
                agent=AgentType.MINI,
                risk=RiskLevel.R0,
                success_criteria="echo ok",
                depends_on=[i - 1] if i > 0 else [],
            )
            for i in range(n_tasks)
        ],
        session_ref="test",
    )


def _review(approved: bool = True):
    from justai.reviewer import ReviewResult

    return ReviewResult(approved=approved, feedback=[] if approved else ["Task too large"])


def _result(status: str = "done", title: str = "Task 0") -> DelegationResult:
    return DelegationResult(
        task_id="1",
        title=title,
        status=status,
        result="completed ok" if status == "done" else "error",
        duration_seconds=1.0,
    )


def _patch_pipeline(*, intent=None, plan=None, review=None, results=None):
    return patch.multiple(
        "justai.orchestrator",
        classify=MagicMock(return_value=intent or _intent()),
        decompose=MagicMock(return_value=plan or _plan()),
        review=MagicMock(return_value=review or _review()),
        evaluate=MagicMock(return_value=(True, "auto")),
        preflight=MagicMock(return_value=[]),
        print_preflight=MagicMock(return_value=True),
        flush_traces=MagicMock(),
        _memory=MagicMock(),
        _ledger=MagicMock(),
        OrchestratorHook=MagicMock(),
        trace_generation=MagicMock(return_value=_trace_ctx()),
        trace_event=MagicMock(),
        escalate_plan=MagicMock(return_value=results or [_result()]),
    )


def test_run_returns_ambiguous_status_when_intent_is_ambiguous():
    from justai.orchestrator import run

    with patch("justai.orchestrator.classify", return_value=_intent("ambiguous")), \
         patch("justai.orchestrator.preflight", return_value=[]), \
         patch("justai.orchestrator.print_preflight", return_value=True), \
         patch("justai.orchestrator.OrchestratorHook"), \
         patch("justai.orchestrator.trace_generation", return_value=_trace_ctx()), \
         patch("justai.orchestrator._ledger"):
        result = run("do something vague", session_ref="test")

    assert result.status == "ambiguous"
    assert result.task_count == 0


def test_run_returns_blocked_when_plan_cannot_be_approved():
    from justai.orchestrator import run

    with _patch_pipeline(review=_review(False)):
        result = run("some goal", session_ref="test")

    assert result.status == "blocked"


def test_run_returns_complete_when_all_tasks_succeed():
    from justai.orchestrator import run

    with _patch_pipeline(results=[_result("done")]):
        result = run("add endpoint", session_ref="test")

    assert result.status == "complete"
    assert result.task_count == 1


def test_run_returns_partial_when_some_tasks_fail():
    from justai.orchestrator import run

    with _patch_pipeline(plan=_plan(2), results=[_result("done", "Task 0"), _result("failed", "Task 1")]):
        result = run("multi-task goal", session_ref="test")

    assert result.status == "partial"


def test_run_replans_on_review_rejection_then_succeeds():
    from justai.orchestrator import run
    from justai.reviewer import ReviewResult

    review_mock = MagicMock(
        side_effect=[
            ReviewResult(approved=False, feedback=["Task too large"]),
            ReviewResult(approved=True, feedback=[]),
        ]
    )
    with _patch_pipeline():
        with patch("justai.orchestrator.review", review_mock):
            result = run("some goal", session_ref="test")

    assert result.status == "complete"
    assert review_mock.call_count == 2


def test_run_with_swarm_flag_passes_swarm_mode_to_escalate_plan():
    from justai.orchestrator import run

    escalate_mock = MagicMock(return_value=[_result()])
    with _patch_pipeline():
        with patch("justai.orchestrator.escalate_plan", escalate_mock):
            result = run("test goal", auto=True, swarm=True)

    assert result.status == "complete"
    assert escalate_mock.call_args.kwargs["mode"] == "swarm"


def test_parse_args_local_and_auto_flags():
    from justai.orchestrator import _parse_args

    goal, auto, local, swarm = _parse_args(["--local", "--auto", "do", "it"])

    assert goal == "do it"
    assert auto is True
    assert local is True
    assert swarm is False


def test_cli_run_cmd_exit_codes():
    from justai.orchestrator import OrchestrationResult
    from tools.justai_cli import run_cmd

    complete = OrchestrationResult("goal", "execution", 1, [], 1.0, "complete")
    partial = OrchestrationResult("goal", "execution", 2, [], 1.0, "partial")

    with patch("justai.orchestrator.run", return_value=complete):
        assert run_cmd(SimpleNamespace(goal="goal", session_ref="test", auto=False, local=False, swarm=False)) == 0
    with patch("justai.orchestrator.run", return_value=partial):
        assert run_cmd(SimpleNamespace(goal="goal", session_ref="test", auto=False, local=False, swarm=False)) == 1
