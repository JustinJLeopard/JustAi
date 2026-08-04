"""Regression coverage for the local runner's completion-integrity boundary."""

from __future__ import annotations

from justai import agent_dispatch
from justai.agent_dispatch import escalate_plan, escalate_task
from justai.results import DelegationResult
from justai.scope_planner import AgentType, RiskLevel, Task


def _mutation_task(requested_artifact) -> Task:
    return Task(
        title="Create greeting.py",
        description="Create greeting.py with greet(name) returning exactly Hello, name!",
        agent=AgentType.MINI,
        risk=RiskLevel.R1,
        success_criteria=f"touch {requested_artifact}",
    )


def test_local_mode_cannot_mark_an_unperformed_mutation_done(tmp_path):
    """Restoring verification-only execution as completion must fail this test."""
    requested_artifact = tmp_path / "greeting.py"

    [result] = escalate_plan([_mutation_task(requested_artifact)], session_ref="fc", mode="local")

    assert result.status == "error"
    assert "unavailable" in result.result.lower()
    assert not requested_artifact.exists()


def test_unavailable_backend_reports_once_without_claiming_an_escalation(tmp_path, capsys):
    """No model runs, so nothing may narrate a failed attempt or a model escalation."""
    requested_artifact = tmp_path / "greeting.py"

    [result] = escalate_plan([_mutation_task(requested_artifact)], session_ref="fc", mode="local")
    out = capsys.readouterr().out

    # The fictitious "failed on <mini>, escalating to <expensive>" notice must be gone,
    # along with any other reference to the models that were never invoked.
    assert "escalating to" not in out
    assert "failed on" not in out
    assert agent_dispatch.MINI_MODEL not in out
    assert agent_dispatch.ESCALATION_MODEL not in out

    # Exactly one dispatch line for the single task: no second attempt is counted.
    assert out.count("[escalation]") == 1
    assert out.count("[escalation] task [0]") == 1

    assert result.status == "error"
    assert not requested_artifact.exists()


def test_unavailable_backend_runner_is_invoked_exactly_once(monkeypatch):
    """A second dispatch would repeat the same error while implying a real retry."""
    calls: list[str] = []

    def counting_unavailable_runner(task: Task, session_ref: str = "") -> DelegationResult:
        calls.append(task.description)
        return agent_dispatch._execute_local_unavailable(task, session_ref=session_ref)

    monkeypatch.setattr(
        agent_dispatch,
        "_NON_DISPATCHING_RUNNERS",
        agent_dispatch._NON_DISPATCHING_RUNNERS | {counting_unavailable_runner},
    )
    task = _mutation_task("/nonexistent/greeting.py")

    result = escalate_task(task, session_ref="fc", runner=counting_unavailable_runner)

    assert len(calls) == 1
    # The escalation path rewrites the description with a "previous attempt failed"
    # note; seeing the description unchanged proves that path was never entered.
    assert calls[0] == task.description
    assert result.status == "error"


def test_real_local_runner_is_registered_as_non_dispatching():
    """Wiring guard: the end-to-end short-circuit depends on this membership."""
    assert not agent_dispatch._dispatches_to_model(agent_dispatch._execute_local_unavailable)
    assert not agent_dispatch._dispatches_to_model(agent_dispatch._execute_removed_backend)


def test_escalation_ladder_still_applies_to_a_model_dispatching_runner():
    """The short-circuit must not silently disable escalation for real backends."""
    attempts: list[str] = []

    def failing_model_runner(task: Task, session_ref: str = "") -> DelegationResult:
        attempts.append(task.description)
        return DelegationResult(
            task_id="t0",
            title=task.title,
            status="failed",
            result="model attempt failed",
            duration_seconds=0.0,
        )

    assert agent_dispatch._dispatches_to_model(failing_model_runner)
    task = _mutation_task("/nonexistent/greeting.py")

    escalate_task(task, session_ref="fc", runner=failing_model_runner)

    assert len(attempts) == 2
    assert "Take a different approach." in attempts[1]
