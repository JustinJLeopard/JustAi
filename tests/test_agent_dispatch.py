"""Tests for agent dispatch workflow — escalation pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from justai.scope_planner import AgentType, RiskLevel, Task


def _make_task(title: str, desc: str = "") -> Task:
    return Task(
        title=title,
        description=desc or f"Do {title}",
        agent=AgentType.MINI,
        risk=RiskLevel.R0,
        success_criteria="echo ok",
    )


class TestAgentDispatchPipeline:
    """The pipeline is quarantined — see justai/agent_dispatch.py's module docstring.

    Its phases only ever produced strings, and the removed iterate/escalate
    loop closed over a `pytest` run against the launching checkout, which the
    pipeline had not written to. These tests pin the quarantine; completion
    behaviour is covered in tests/test_completion_integrity.py.
    """

    def test_phase_sequence(self):
        """Only the generation phases remain; iterate/escalate needed test results."""
        from justai.agent_dispatch import PHASES

        assert PHASES == ["pseudocode", "write_tests", "write_code"]

    def test_iteration_config_defaults(self):
        from justai.agent_dispatch import AgentDispatchConfig

        cfg = AgentDispatchConfig()
        assert cfg.max_mini_iterations == 3
        assert cfg.escalation_model == "claude-opus-4-6"
        assert cfg.mini_model == "gpt-5.3-codex"

    def test_phase_result_dataclass(self):
        from justai.agent_dispatch import PhaseResult

        r = PhaseResult(phase="write_tests", status="done", output="5 tests written", iterations=1)
        assert r.phase == "write_tests"
        assert r.status == "done"

    def test_run_refuses_before_spending_a_model_call(self):
        """Generating three phases and then admitting nothing was written is waste."""
        import pytest

        from justai.agent_dispatch import AgentDispatchConfig, AgentDispatchPipeline

        with patch("justai.agent_dispatch._llm_call") as mock_llm:
            with pytest.raises(NotImplementedError, match="materiali"):
                AgentDispatchPipeline(AgentDispatchConfig()).run("task", spec="spec")

        mock_llm.assert_not_called()

    def test_pipeline_result_type_is_gone(self):
        """It carried `escalated` / `total_iterations` — verdicts about unwritten code."""
        from justai import agent_dispatch

        assert not hasattr(agent_dispatch, "PipelineResult")


# ── Escalation Strategy Tests ────────────────────────────────────────────────


class TestEscalateTask:
    def test_succeeds_first_try_no_escalation(self):
        """When runner returns done, no escalation happens."""
        from justai.agent_dispatch import escalate_task
        from justai.results import DelegationResult

        task = _make_task("add endpoint")
        runner = MagicMock(
            return_value=DelegationResult(
                task_id="t1",
                title="add endpoint",
                status="done",
                result="completed",
                duration_seconds=2.0,
            )
        )
        result = escalate_task(task, session_ref="test", runner=runner)
        assert result.status == "done"
        assert runner.call_count == 1  # no escalation call

    def test_fails_then_escalates_successfully(self):
        """When first attempt fails, escalation succeeds."""
        from justai.agent_dispatch import escalate_task
        from justai.results import DelegationResult

        task = _make_task("fix bug")
        first_result = DelegationResult(
            task_id="t1",
            title="fix bug",
            status="failed",
            result="syntax error on line 42",
            duration_seconds=1.0,
        )
        escalation_result = DelegationResult(
            task_id="t1-esc",
            title="fix bug",
            status="done",
            result="fixed",
            duration_seconds=3.0,
        )
        runner = MagicMock(side_effect=[first_result, escalation_result])
        result = escalate_task(task, session_ref="test", runner=runner)
        assert result.status == "done"
        assert runner.call_count == 2

    def test_both_attempts_fail(self):
        """When both cheap and escalation fail, returns failed."""
        from justai.agent_dispatch import escalate_task
        from justai.results import DelegationResult

        task = _make_task("impossible task")
        fail = DelegationResult(
            task_id="t1",
            title="impossible task",
            status="failed",
            result="cannot do",
            duration_seconds=1.0,
        )
        runner = MagicMock(return_value=fail)
        result = escalate_task(task, session_ref="test", runner=runner)
        assert result.status == "failed"
        assert runner.call_count == 2  # cheap + escalation

    def test_escalation_sets_model_env(self):
        """escalate_task sets JUSTAI_ACTIVE_MODEL env var for each attempt."""
        import os

        from justai.agent_dispatch import ESCALATION_MODEL, MINI_MODEL, escalate_task
        from justai.results import DelegationResult

        captured_models = []

        def capture_runner(task, session_ref=""):
            captured_models.append(os.environ.get("JUSTAI_ACTIVE_MODEL", ""))
            return DelegationResult(
                task_id="t1",
                title=task.title,
                status="failed",
                result="fail",
                duration_seconds=1.0,
            )

        task = _make_task("test model routing")
        escalate_task(task, session_ref="test", runner=capture_runner)
        assert captured_models[0] == MINI_MODEL
        assert captured_models[1] == ESCALATION_MODEL


class TestEscalatePlan:
    def test_dependency_skip_after_escalation_failure(self):
        """If task 0 fails after escalation, task 1 (depends on 0) is skipped."""
        from justai.agent_dispatch import escalate_plan
        from justai.results import DelegationResult

        task0 = _make_task("setup db")
        task1 = _make_task("add tables")
        task1.depends_on = [0]

        fail = DelegationResult(
            task_id="t0",
            title="setup db",
            status="failed",
            result="db unreachable",
            duration_seconds=1.0,
        )
        with patch("justai.agent_dispatch.escalate_task", return_value=fail):
            results = escalate_plan([task0, task1], session_ref="test", mode="local")
        assert results[0].status == "failed"
        assert results[1].status == "skipped"

    def test_routes_to_correct_runner(self):
        """escalate_plan passes the right runner for each mode."""
        from justai.agent_dispatch import escalate_plan
        from justai.results import DelegationResult

        task = _make_task("single task")
        done = DelegationResult(
            task_id="t0",
            title="single task",
            status="done",
            result="ok",
            duration_seconds=1.0,
        )
        with patch("justai.agent_dispatch.escalate_task", return_value=done) as mock_esc:
            escalate_plan([task], session_ref="test", mode="delegated")
            runner_arg = mock_esc.call_args.kwargs.get("runner") or mock_esc.call_args[0][2]
            from justai.agent_dispatch import _execute_removed_backend

            assert runner_arg == _execute_removed_backend

    def test_all_three_modes_accepted(self):
        """escalate_plan accepts 'local', 'delegated', and 'swarm' modes."""
        from justai.agent_dispatch import escalate_plan
        from justai.results import DelegationResult

        task = _make_task("test")
        done = DelegationResult(
            task_id="t0",
            title="test",
            status="done",
            result="ok",
            duration_seconds=1.0,
        )
        with patch("justai.agent_dispatch.escalate_task", return_value=done):
            for mode in ("local", "delegated", "swarm"):
                results = escalate_plan([task], session_ref="test", mode=mode)
                assert len(results) == 1
                assert results[0].status == "done"
