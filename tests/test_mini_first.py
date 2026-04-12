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
