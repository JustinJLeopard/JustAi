"""Shared harness for the approval-gate identity tests.

Stubs every orchestration stage except the checkpoint and the dispatch that
follows it. ``evaluate``, the gate directory, and the files it reads and writes
stay real — they are what is under test.

Lives outside a ``test_*.py`` module so both the in-process tests and the
subprocess child in :mod:`tests.gate_collision_child` describe the same run.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch


def single_task_plan(risk: str, goal: str = "gate identity", title: str = "Change an interface"):
    """A one-task plan at the given risk level.

    R2 is the hard gate that waits for an approval; R1 is the one an operator
    can veto. Both are decided per task per run, which is the point.
    """
    from justai.scope_planner import AgentType, Plan, RiskLevel, Task

    return Plan(
        goal=goal,
        tasks=[
            Task(
                title=title,
                description="A gated task.",
                agent=AgentType.MINI,
                risk=RiskLevel(risk),
                success_criteria="echo ok",
            )
        ],
    )


def _trace_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.end = MagicMock()
    return ctx


def _execution_intent():
    from justai.intent_gate import Intent, IntentResult

    return IntentResult(
        intent=Intent("execution"),
        confidence=0.9,
        reasoning="harness",
        clarifying_question="",
    )


def _approved_review():
    from justai.reviewer import ReviewResult

    return ReviewResult(approved=True, feedback=[])


@contextmanager
def orchestrator_stubs(plan):
    """Run the pipeline offline, with the checkpoint stage left real."""
    with (
        patch.multiple(
            "justai.orchestrator",
            classify=MagicMock(return_value=_execution_intent()),
            decompose=MagicMock(return_value=plan),
            review=MagicMock(return_value=_approved_review()),
            preflight=MagicMock(return_value=[]),
            print_preflight=MagicMock(return_value=True),
            flush_traces=MagicMock(),
            trace_generation=MagicMock(side_effect=lambda *a, **k: _trace_ctx()),
            trace_event=MagicMock(),
            record_run=MagicMock(),
            enrich_context=MagicMock(return_value=""),
            _memory=MagicMock(),
            _ledger=MagicMock(),
            OrchestratorHook=MagicMock(),
        ),
        patch("justai.synthesizer._memory", MagicMock()),
        # Keep the gate decision local: a configured relay token would send the
        # operator to Discord instead of printing the path these tests read.
        patch("justai.checkpoint._discord_notify", return_value=False),
    ):
        yield
