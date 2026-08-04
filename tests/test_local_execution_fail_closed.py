"""Regression coverage for the local runner's completion-integrity boundary."""

from __future__ import annotations

from justai.agent_dispatch import escalate_plan
from justai.scope_planner import AgentType, RiskLevel, Task


def test_local_mode_cannot_mark_an_unperformed_mutation_done(tmp_path):
    """Restoring verification-only execution as completion must fail this test."""
    requested_artifact = tmp_path / "greeting.py"
    task = Task(
        title="Create greeting.py",
        description="Create greeting.py with greet(name) returning exactly Hello, name!",
        agent=AgentType.MINI,
        risk=RiskLevel.R1,
        success_criteria=f"touch {requested_artifact}",
    )

    [result] = escalate_plan([task], session_ref="fail-closed", mode="local")

    assert result.status == "error"
    assert "unavailable" in result.result.lower()
    assert not requested_artifact.exists()
