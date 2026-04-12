#!/usr/bin/env python3
"""Sprint 10 tests — local executor, synthesizer, E2E local pipeline."""
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestLocalExecutor(unittest.TestCase):
    """Test executor.py local task execution."""

    def _task(self, title="test", desc="test", risk="R0", criteria="echo ok"):
        from justai.planner import Task, RiskLevel, AgentType
        return Task(
            title=title, description=desc,
            agent=AgentType.MINI, risk=RiskLevel(risk),
            success_criteria=criteria, depends_on=[],
        )

    def test_execute_r0_passing(self):
        from justai.executor import execute_task
        task = self._task(criteria="echo 'hello'")
        result = execute_task(task, 0)
        self.assertEqual(result.status, "done")
        self.assertIn("hello", result.output)

    def test_execute_r0_failing(self):
        from justai.executor import execute_task
        task = self._task(criteria="exit 1")
        result = execute_task(task, 0)
        self.assertEqual(result.status, "failed")

    def test_execute_r1_verify_passes(self):
        from justai.executor import execute_task
        task = self._task(risk="R1", criteria="echo success")
        result = execute_task(task, 0)
        self.assertEqual(result.status, "done")

    def test_execute_manual_verify(self):
        from justai.executor import execute_task
        task = self._task(risk="R0", criteria="echo 'verify manually'")
        result = execute_task(task, 0)
        self.assertEqual(result.status, "done")

    def test_execute_plan_dependency_skip(self):
        from justai.executor import execute_plan
        from justai.planner import Task, RiskLevel, AgentType
        tasks = [
            Task("failing", "fail", AgentType.MINI, RiskLevel.R0, "exit 1", []),
            Task("dependent", "dep", AgentType.MINI, RiskLevel.R0, "echo ok", [0]),
        ]
        results = execute_plan(tasks)
        self.assertEqual(results[0].status, "failed")
        self.assertEqual(results[1].status, "skipped")

    def test_execute_plan_all_pass(self):
        from justai.executor import execute_plan
        from justai.planner import Task, RiskLevel, AgentType
        tasks = [
            Task("t0", "first", AgentType.MINI, RiskLevel.R0, "echo ok", []),
            Task("t1", "second", AgentType.MINI, RiskLevel.R0, "echo ok", [0]),
        ]
        results = execute_plan(tasks)
        self.assertTrue(all(r.status == "done" for r in results))

    def test_exec_result_has_duration(self):
        from justai.executor import execute_task
        task = self._task(criteria="echo fast")
        result = execute_task(task, 0)
        self.assertGreaterEqual(result.duration_seconds, 0)


class TestSynthesizer(unittest.TestCase):
    """Test synthesizer.py result aggregation."""

    def _result(self, status="done", title="task"):
        from justai.delegator import DelegationResult
        return DelegationResult(
            task_id="t1", title=title, status=status,
            result="ok", duration_seconds=1.0,
        )

    def test_synthesize_all_done(self):
        from justai.synthesizer import synthesize
        results = [self._result("done"), self._result("done")]
        s = synthesize("goal", "execution", results, "test", 5.0)
        self.assertEqual(s.status, "complete")
        self.assertEqual(s.done, 2)
        self.assertEqual(s.failed, 0)

    def test_synthesize_partial(self):
        from justai.synthesizer import synthesize
        results = [self._result("done"), self._result("failed")]
        s = synthesize("goal", "execution", results, "test", 5.0)
        self.assertEqual(s.status, "partial")

    def test_synthesize_all_failed(self):
        from justai.synthesizer import synthesize
        results = [self._result("failed")]
        s = synthesize("goal", "execution", results, "test", 5.0)
        self.assertEqual(s.status, "failed")

    def test_synthesize_with_skipped(self):
        from justai.synthesizer import synthesize
        results = [self._result("done"), self._result("skipped")]
        s = synthesize("goal", "execution", results, "test", 5.0)
        self.assertEqual(s.skipped, 1)
        self.assertEqual(s.status, "partial")

    def test_format_summary(self):
        from justai.synthesizer import synthesize, format_summary
        results = [self._result("done", "Add endpoint")]
        s = synthesize("goal", "execution", results, "test", 5.0)
        text = format_summary(s)
        self.assertIn("Run Summary", text)
        self.assertIn("Add endpoint", text)

    def test_synthesize_details(self):
        from justai.synthesizer import synthesize
        results = [self._result("done", "task A"), self._result("failed", "task B")]
        s = synthesize("goal", "exec", results, "test", 3.0)
        self.assertEqual(len(s.details), 2)
        self.assertEqual(s.details[0]["title"], "task A")


class TestOrchestratorLocalMode(unittest.TestCase):
    """Test orchestrator with local execution mode."""

    def test_parse_args_local_flag(self):
        from justai.orchestrator import _parse_args
        goal, auto, local = _parse_args(["--local", "--auto", "do", "it"])
        self.assertEqual(goal, "do it")
        self.assertTrue(auto)
        self.assertTrue(local)

    def test_parse_args_no_local(self):
        from justai.orchestrator import _parse_args
        goal, auto, local = _parse_args(["do", "something"])
        self.assertFalse(local)

    def test_local_exec_env_var(self):
        from justai.orchestrator import LOCAL_EXEC
        # Default is false
        self.assertIsInstance(LOCAL_EXEC, bool)

    def test_run_local_e2e(self):
        """Full pipeline with local execution."""
        from justai.orchestrator import run
        from justai.planner import Plan, Task, RiskLevel, AgentType
        from justai.intent_gate import IntentResult, Intent
        from justai.reviewer import ReviewResult

        mock_intent = IntentResult(
            intent=Intent.EXECUTION,
            confidence=0.95,
            reasoning="test",
            clarifying_question=None,
        )
        mock_plan = Plan(goal="test", tasks=[
            Task("check", "echo test", AgentType.MINI, RiskLevel.R0, "echo ok", []),
        ])
        mock_review = ReviewResult(approved=True, feedback=[])

        with patch("justai.orchestrator.classify", return_value=mock_intent):
            with patch("justai.orchestrator.decompose", return_value=mock_plan):
                with patch("justai.orchestrator.review", return_value=mock_review):
                    result = run("test local", session_ref="test-local", auto=True, local=True)

        self.assertEqual(result.status, "complete")
        self.assertEqual(result.task_count, 1)


class TestCLILocalFlag(unittest.TestCase):
    """Test CLI --local flag."""

    def test_cli_parser_local(self):
        from justai.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["run", "--local", "--auto", "test"])
        self.assertTrue(args.local)
        self.assertTrue(args.auto)


if __name__ == "__main__":
    unittest.main()
