"""Tests for mini-first workflow — escalation pipeline."""
from __future__ import annotations
import json
import pytest
from unittest.mock import patch, MagicMock
from justai.planner import Task, RiskLevel, AgentType


def _make_task(title: str, desc: str = "") -> Task:
    return Task(
        title=title,
        description=desc or f"Do {title}",
        agent=AgentType.MINI,
        risk=RiskLevel.R0,
        success_criteria="echo ok",
    )


class TestMiniFirstPipeline:
    def test_phase_sequence(self):
        """Pipeline should have 5 phases in order."""
        from justai.mini_first import PHASES
        assert PHASES == ["pseudocode", "write_tests", "write_code", "iterate", "escalate"]

    def test_iteration_config_defaults(self):
        from justai.mini_first import MiniFirstConfig
        cfg = MiniFirstConfig()
        assert cfg.max_mini_iterations == 3
        assert cfg.escalation_model == "claude-opus-4-6"
        assert cfg.mini_model == "gpt-5.3-codex"

    def test_phase_result_dataclass(self):
        from justai.mini_first import PhaseResult
        r = PhaseResult(phase="write_tests", status="done", output="5 tests written", iterations=1)
        assert r.phase == "write_tests"
        assert r.status == "done"

    def test_run_pipeline_all_mini_succeeds(self):
        """When mini succeeds at every phase, escalation never triggers."""
        from justai.mini_first import MiniFirstPipeline, MiniFirstConfig, PhaseResult

        cfg = MiniFirstConfig(max_mini_iterations=2)

        # Mock the LLM call to return success at each phase
        mock_responses = {
            "pseudocode": "def add(a, b): return a + b",
            "write_tests": "def test_add(): assert add(1,2) == 3",
            "write_code": "def add(a, b): return a + b",
            "iterate": "All tests pass.",
        }

        with patch("justai.mini_first._llm_call") as mock_llm:
            mock_llm.side_effect = lambda model, prompt, system="": mock_responses.get(
                next((p for p in mock_responses if p in prompt), ""), "ok"
            )
            with patch("justai.mini_first._run_tests", return_value=(True, "5 passed")):
                pipeline = MiniFirstPipeline(cfg)
                result = pipeline.run("implement an add function", spec="add(a,b) returns a+b")

        assert result.escalated is False
        assert result.total_iterations <= cfg.max_mini_iterations
        assert len(result.phases) >= 3  # pseudocode, write_tests, write_code at minimum

    def test_run_pipeline_mini_fails_escalates(self):
        """When mini fails after max iterations, pipeline escalates."""
        from justai.mini_first import MiniFirstPipeline, MiniFirstConfig

        cfg = MiniFirstConfig(max_mini_iterations=2)

        call_count = 0
        def mock_llm(model, prompt, system=""):
            nonlocal call_count
            call_count += 1
            return "attempted but incomplete"

        with patch("justai.mini_first._llm_call", side_effect=mock_llm):
            with patch("justai.mini_first._run_tests", return_value=(False, "3 failed")):
                pipeline = MiniFirstPipeline(cfg)
                result = pipeline.run("implement something complex", spec="complex spec")

        assert result.escalated is True
        assert result.total_iterations == cfg.max_mini_iterations

    def test_run_pipeline_records_phase_history(self):
        """Pipeline should record every phase attempt."""
        from justai.mini_first import MiniFirstPipeline, MiniFirstConfig

        cfg = MiniFirstConfig(max_mini_iterations=1)

        with patch("justai.mini_first._llm_call", return_value="code output"):
            with patch("justai.mini_first._run_tests", return_value=(True, "ok")):
                pipeline = MiniFirstPipeline(cfg)
                result = pipeline.run("simple task", spec="spec")

        assert len(result.phases) > 0
        assert all(hasattr(p, 'phase') and hasattr(p, 'status') for p in result.phases)

    def test_cost_tracking(self):
        """Pipeline should track total model calls."""
        from justai.mini_first import MiniFirstPipeline, MiniFirstConfig

        cfg = MiniFirstConfig(max_mini_iterations=1)

        with patch("justai.mini_first._llm_call", return_value="output"):
            with patch("justai.mini_first._run_tests", return_value=(True, "pass")):
                pipeline = MiniFirstPipeline(cfg)
                result = pipeline.run("task", spec="spec")

        assert result.model_calls > 0
        assert result.mini_calls > 0


# ── Escalation Strategy Tests ────────────────────────────────────────────────

class TestEscalateTask:
    def test_succeeds_first_try_no_escalation(self):
        """When executor returns done, no escalation happens."""
        from justai.mini_first import escalate_task
        from justai.delegator import DelegationResult

        task = _make_task("add endpoint")
        executor = MagicMock(return_value=DelegationResult(
            task_id="t1", title="add endpoint", status="done",
            result="completed", duration_seconds=2.0,
        ))
        result = escalate_task(task, session_ref="test", executor=executor)
        assert result.status == "done"
        assert executor.call_count == 1  # no escalation call

    def test_fails_then_escalates_successfully(self):
        """When first attempt fails, escalation succeeds."""
        from justai.mini_first import escalate_task
        from justai.delegator import DelegationResult

        task = _make_task("fix bug")
        first_result = DelegationResult(
            task_id="t1", title="fix bug", status="failed",
            result="syntax error on line 42", duration_seconds=1.0,
        )
        escalation_result = DelegationResult(
            task_id="t1-esc", title="fix bug", status="done",
            result="fixed", duration_seconds=3.0,
        )
        executor = MagicMock(side_effect=[first_result, escalation_result])
        result = escalate_task(task, session_ref="test", executor=executor)
        assert result.status == "done"
        assert executor.call_count == 2

    def test_both_attempts_fail(self):
        """When both cheap and escalation fail, returns failed."""
        from justai.mini_first import escalate_task
        from justai.delegator import DelegationResult

        task = _make_task("impossible task")
        fail = DelegationResult(
            task_id="t1", title="impossible task", status="failed",
            result="cannot do", duration_seconds=1.0,
        )
        executor = MagicMock(return_value=fail)
        result = escalate_task(task, session_ref="test", executor=executor)
        assert result.status == "failed"
        assert executor.call_count == 2  # cheap + escalation

    def test_escalation_sets_model_env(self):
        """escalate_task sets JUSTAI_ACTIVE_MODEL env var for each attempt."""
        from justai.mini_first import escalate_task, MINI_MODEL, ESCALATION_MODEL
        from justai.delegator import DelegationResult
        import os

        captured_models = []
        def capture_executor(task, session_ref=""):
            captured_models.append(os.environ.get("JUSTAI_ACTIVE_MODEL", ""))
            return DelegationResult(
                task_id="t1", title=task.title, status="failed",
                result="fail", duration_seconds=1.0,
            )

        task = _make_task("test model routing")
        escalate_task(task, session_ref="test", executor=capture_executor)
        assert captured_models[0] == MINI_MODEL
        assert captured_models[1] == ESCALATION_MODEL


class TestEscalatePlan:
    def test_dependency_skip_after_escalation_failure(self):
        """If task 0 fails after escalation, task 1 (depends on 0) is skipped."""
        from justai.mini_first import escalate_plan
        from justai.delegator import DelegationResult

        task0 = _make_task("setup db")
        task1 = _make_task("add tables")
        task1.depends_on = [0]

        fail = DelegationResult(
            task_id="t0", title="setup db", status="failed",
            result="db unreachable", duration_seconds=1.0,
        )
        with patch("justai.mini_first.escalate_task", return_value=fail):
            results = escalate_plan([task0, task1], session_ref="test", mode="local")
        assert results[0].status == "failed"
        assert results[1].status == "skipped"

    def test_routes_to_correct_executor(self):
        """escalate_plan passes the right executor for each mode."""
        from justai.mini_first import escalate_plan
        from justai.delegator import DelegationResult

        task = _make_task("single task")
        done = DelegationResult(
            task_id="t0", title="single task", status="done",
            result="ok", duration_seconds=1.0,
        )
        with patch("justai.mini_first.escalate_task", return_value=done) as mock_esc:
            escalate_plan([task], session_ref="test", mode="delegated")
            executor_arg = mock_esc.call_args.kwargs.get("executor") or mock_esc.call_args[0][2]
            # The executor should be delegator.delegate for "delegated" mode
            from justai.delegator import delegate
            assert executor_arg == delegate

    def test_all_three_modes_accepted(self):
        """escalate_plan accepts 'local', 'delegated', and 'swarm' modes."""
        from justai.mini_first import escalate_plan
        from justai.delegator import DelegationResult

        task = _make_task("test")
        done = DelegationResult(
            task_id="t0", title="test", status="done",
            result="ok", duration_seconds=1.0,
        )
        with patch("justai.mini_first.escalate_task", return_value=done):
            for mode in ("local", "delegated", "swarm"):
                results = escalate_plan([task], session_ref="test", mode=mode)
                assert len(results) == 1
                assert results[0].status == "done"
