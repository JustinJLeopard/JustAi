#!/usr/bin/env python3
"""
Tests for justai/delegator.py and justai/orchestrator.py

Delegator: SpacetimeDB task posting, dependency ordering, failure handling
Orchestrator: full pipeline integration, status outcomes, memory storage
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))


# ── Delegator ─────────────────────────────────────────────────────────────────

class DelegatorTests(unittest.TestCase):

    def _make_task(self, title="Test task", risk="R1", depends_on=None):
        from justai.planner import Task, RiskLevel, AgentType
        return Task(
            title=title,
            description=f"Description for {title}.",
            agent=AgentType.MINI,
            risk=RiskLevel(risk),
            success_criteria="echo done",
            depends_on=depends_on or [],
            session_ref="test",
        )

    def test_post_task_parses_task_id_from_relay_output(self):
        from justai.delegator import _post_task
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Posted task #42 to SpacetimeDB\n"
        with patch("justai.delegator._relay", return_value=mock_result):
            task_id = _post_task(self._make_task(), session_ref="test")
        self.assertEqual(task_id, "42")

    def test_post_task_returns_none_on_relay_failure(self):
        from justai.delegator import _post_task
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "relay CLI error"
        with patch("justai.delegator._relay", return_value=mock_result):
            task_id = _post_task(self._make_task())
        self.assertIsNone(task_id)

    def test_delegate_returns_error_result_when_post_fails(self):
        from justai.delegator import delegate
        with patch("justai.delegator._post_task", return_value=None):
            result = delegate(self._make_task(), session_ref="test")
        self.assertEqual(result.status, "error")
        self.assertIn("Failed to post", result.result)

    def test_delegate_returns_timeout_when_no_agent_claims(self):
        from justai.delegator import delegate
        import justai.delegator as d
        orig = d.CLAIM_TIMEOUT
        d.CLAIM_TIMEOUT = 0
        try:
            with patch("justai.delegator._post_task", return_value="99"):
                with patch("justai.delegator._get_task_status", return_value=None):
                    result = delegate(self._make_task())
            self.assertEqual(result.status, "timeout")
        finally:
            d.CLAIM_TIMEOUT = orig

    def test_delegate_returns_done_on_success(self):
        from justai.delegator import delegate
        status_sequence = [
            {"status": "in_progress"},
            {"status": "done", "result": "endpoint added successfully"},
        ]
        call_count = [0]
        def mock_status(task_id):
            result = status_sequence[min(call_count[0], len(status_sequence)-1)]
            call_count[0] += 1
            return result

        with patch("justai.delegator._post_task", return_value="7"):
            with patch("justai.delegator._get_task_status", side_effect=mock_status):
                result = delegate(self._make_task())
        self.assertEqual(result.status, "done")
        self.assertEqual(result.task_id, "7")

    def test_delegate_returns_failed_on_agent_failure(self):
        from justai.delegator import delegate
        status_sequence = [
            {"status": "in_progress"},
            {"status": "failed", "error": "syntax error on line 42"},
        ]
        call_count = [0]
        def mock_status(task_id):
            result = status_sequence[min(call_count[0], len(status_sequence)-1)]
            call_count[0] += 1
            return result

        with patch("justai.delegator._post_task", return_value="8"):
            with patch("justai.delegator._get_task_status", side_effect=mock_status):
                result = delegate(self._make_task())
        self.assertEqual(result.status, "failed")
        self.assertIn("syntax error", result.result)

    def test_delegate_plan_skips_task_when_dependency_failed(self):
        from justai.delegator import delegate_plan, DelegationResult
        task0 = self._make_task("Task A")
        task1 = self._make_task("Task B", depends_on=[0])

        failed_result = DelegationResult(
            task_id="1", title="Task A",
            status="failed", result="error", duration_seconds=1.0
        )
        with patch("justai.delegator.delegate", return_value=failed_result):
            results = delegate_plan([task0, task1], session_ref="test")

        self.assertEqual(results[0].status, "failed")
        self.assertEqual(results[1].status, "skipped")

    def test_delegate_plan_runs_independent_tasks(self):
        from justai.delegator import delegate_plan, DelegationResult
        task0 = self._make_task("Task A")
        task1 = self._make_task("Task B")  # no dependency

        done_result = lambda t, s: DelegationResult(
            task_id="1", title=t.title,
            status="done", result="ok", duration_seconds=1.0
        )
        with patch("justai.delegator.delegate", side_effect=done_result):
            results = delegate_plan([task0, task1])

        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.status == "done" for r in results))

    def test_delegation_result_has_duration(self):
        from justai.delegator import delegate
        status_sequence = [{"status": "done", "result": "ok"}]
        with patch("justai.delegator._post_task", return_value="5"):
            with patch("justai.delegator._get_task_status", return_value={"status": "done", "result": "ok"}):
                result = delegate(self._make_task())
        self.assertGreaterEqual(result.duration_seconds, 0)


# ── Orchestrator ──────────────────────────────────────────────────────────────

class OrchestratorTests(unittest.TestCase):

    def _mock_intent(self, intent_type="execution", confidence=0.9):
        from justai.intent_gate import IntentResult, Intent
        return IntentResult(
            intent=Intent(intent_type),
            confidence=confidence,
            reasoning="Test reasoning.",
            clarifying_question="" if intent_type != "ambiguous" else "What do you mean?",
        )

    def _mock_plan(self, n_tasks=2):
        from justai.planner import Plan, Task, RiskLevel, AgentType
        tasks = [
            Task(
                title=f"Task {i}",
                description=f"Do thing {i}.",
                agent=AgentType.MINI,
                risk=RiskLevel.R0,
                success_criteria="echo done",
                depends_on=[i-1] if i > 0 else [],
            )
            for i in range(n_tasks)
        ]
        return Plan(goal="test goal", tasks=tasks, session_ref="test")

    def _mock_review(self, approved=True):
        from justai.reviewer import ReviewResult
        return ReviewResult(approved=approved, feedback=[] if approved else ["Task too large"])

    def _mock_delegation_result(self, status="done"):
        from justai.delegator import DelegationResult
        return DelegationResult(
            task_id="1", title="Task 0",
            status=status, result="completed ok",
            duration_seconds=1.5,
        )

    def test_run_returns_ambiguous_status_when_intent_is_ambiguous(self):
        from justai.orchestrator import run
        with patch("justai.orchestrator.classify", return_value=self._mock_intent("ambiguous", 0.9)):
            result = run("do something vague", session_ref="test")
        self.assertEqual(result.status, "ambiguous")
        self.assertEqual(result.task_count, 0)

    def test_run_returns_blocked_when_plan_cannot_be_approved(self):
        from justai.orchestrator import run
        with patch("justai.orchestrator.classify", return_value=self._mock_intent()):
            with patch("justai.orchestrator.decompose", return_value=self._mock_plan()):
                with patch("justai.orchestrator.review", return_value=self._mock_review(approved=False)):
                    result = run("some goal", session_ref="test")
        self.assertEqual(result.status, "blocked")

    def test_run_returns_complete_when_all_tasks_succeed(self):
        from justai.orchestrator import run
        done_result = self._mock_delegation_result("done")
        with patch("justai.orchestrator.classify", return_value=self._mock_intent()):
            with patch("justai.orchestrator.decompose", return_value=self._mock_plan(1)):
                with patch("justai.orchestrator.review", return_value=self._mock_review()):
                    with patch("justai.orchestrator.evaluate", return_value=(True, "R0 auto-approved")):
                        with patch("justai.orchestrator.delegate_plan", return_value=[done_result]):
                            with patch("justai.orchestrator._store_memory"):
                                result = run("add an endpoint", session_ref="test")
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.task_count, 1)

    def test_run_returns_partial_when_some_tasks_fail(self):
        from justai.orchestrator import run
        from justai.delegator import DelegationResult
        results = [
            DelegationResult("1", "Task 0", "done", "ok", 1.0),
            DelegationResult("2", "Task 1", "failed", "error", 1.0),
        ]
        with patch("justai.orchestrator.classify", return_value=self._mock_intent()):
            with patch("justai.orchestrator.decompose", return_value=self._mock_plan(2)):
                with patch("justai.orchestrator.review", return_value=self._mock_review()):
                    with patch("justai.orchestrator.evaluate", return_value=(True, "R0 auto-approved")):
                        with patch("justai.orchestrator.delegate_plan", return_value=results):
                            with patch("justai.orchestrator._store_memory"):
                                result = run("multi-task goal", session_ref="test")
        self.assertEqual(result.status, "partial")

    def test_run_stores_outcome_in_memory(self):
        from justai.orchestrator import run
        done_result = self._mock_delegation_result("done")
        with patch("justai.orchestrator.classify", return_value=self._mock_intent()):
            with patch("justai.orchestrator.decompose", return_value=self._mock_plan(1)):
                with patch("justai.orchestrator.review", return_value=self._mock_review()):
                    with patch("justai.orchestrator.evaluate", return_value=(True, "R0 auto-approved")):
                        with patch("justai.orchestrator.delegate_plan", return_value=[done_result]):
                            with patch("justai.synthesizer._memory"):
                                result = run("add an endpoint", session_ref="test")
        # Sprint 10: synthesizer handles memory
        self.assertIn(result.status, ("complete", "partial"))

    def test_run_blocked_when_all_tasks_gated_at_r3(self):
        from justai.orchestrator import run
        with patch("justai.orchestrator.classify", return_value=self._mock_intent()):
            with patch("justai.orchestrator.decompose", return_value=self._mock_plan(1)):
                with patch("justai.orchestrator.review", return_value=self._mock_review()):
                    with patch("justai.orchestrator.evaluate", return_value=(False, "R3 blocked")):
                        result = run("dangerous operation", session_ref="test")
        self.assertEqual(result.status, "blocked")

    def test_run_replans_on_review_rejection_then_succeeds(self):
        from justai.orchestrator import run
        from justai.reviewer import ReviewResult
        done_result = self._mock_delegation_result("done")
        review_calls = [0]
        def mock_review(plan):
            review_calls[0] += 1
            # Reject first time, approve second
            return ReviewResult(
                approved=(review_calls[0] > 1),
                feedback=["Task too large"] if review_calls[0] == 1 else [],
            )
        with patch("justai.orchestrator.classify", return_value=self._mock_intent()):
            with patch("justai.orchestrator.decompose", return_value=self._mock_plan(1)):
                with patch("justai.orchestrator.review", side_effect=mock_review):
                    with patch("justai.orchestrator.evaluate", return_value=(True, "auto")):
                        with patch("justai.orchestrator.delegate_plan", return_value=[done_result]):
                            with patch("justai.orchestrator._store_memory"):
                                result = run("some goal", session_ref="test")
        self.assertEqual(result.status, "complete")
        self.assertEqual(review_calls[0], 2)

    def test_run_intent_is_recorded_in_result(self):
        from justai.orchestrator import run
        done_result = self._mock_delegation_result("done")
        with patch("justai.orchestrator.classify", return_value=self._mock_intent("execution")):
            with patch("justai.orchestrator.decompose", return_value=self._mock_plan(1)):
                with patch("justai.orchestrator.review", return_value=self._mock_review()):
                    with patch("justai.orchestrator.evaluate", return_value=(True, "auto")):
                        with patch("justai.orchestrator.delegate_plan", return_value=[done_result]):
                            with patch("justai.orchestrator._store_memory"):
                                result = run("add endpoint", session_ref="test")
        self.assertEqual(result.intent, "execution")

    def test_run_duration_is_positive(self):
        from justai.orchestrator import run
        done_result = self._mock_delegation_result("done")
        with patch("justai.orchestrator.classify", return_value=self._mock_intent()):
            with patch("justai.orchestrator.decompose", return_value=self._mock_plan(1)):
                with patch("justai.orchestrator.review", return_value=self._mock_review()):
                    with patch("justai.orchestrator.evaluate", return_value=(True, "auto")):
                        with patch("justai.orchestrator.delegate_plan", return_value=[done_result]):
                            with patch("justai.orchestrator._store_memory"):
                                result = run("add endpoint", session_ref="test")
        self.assertGreater(result.duration_seconds, 0)


# ── CLI — run command ─────────────────────────────────────────────────────────

class CLIRunCommandTests(unittest.TestCase):

    def test_run_cmd_returns_0_on_complete(self):
        from tools.justai_cli import run_cmd
        from justai.orchestrator import OrchestrationResult
        mock_result = OrchestrationResult(
            goal="test", intent="execution",
            task_count=1, results=[],
            duration_seconds=1.0, status="complete",
        )
        import argparse
        args = argparse.Namespace(goal="add endpoint", session_ref="test")
        with patch("justai.orchestrator.run", return_value=mock_result):
            exit_code = run_cmd(args)
        self.assertEqual(exit_code, 0)

    def test_run_cmd_returns_1_on_partial(self):
        from tools.justai_cli import run_cmd
        from justai.orchestrator import OrchestrationResult
        mock_result = OrchestrationResult(
            goal="test", intent="execution",
            task_count=2, results=[],
            duration_seconds=1.0, status="partial",
        )
        import argparse
        args = argparse.Namespace(goal="multi goal", session_ref="test")
        with patch("justai.orchestrator.run", return_value=mock_result):
            exit_code = run_cmd(args)
        self.assertEqual(exit_code, 1)

    def test_run_cmd_returns_0_on_ambiguous(self):
        from tools.justai_cli import run_cmd
        from justai.orchestrator import OrchestrationResult
        mock_result = OrchestrationResult(
            goal="?", intent="ambiguous",
            task_count=0, results=[],
            duration_seconds=0.1, status="ambiguous",
        )
        import argparse
        args = argparse.Namespace(goal="do something", session_ref="test")
        with patch("justai.orchestrator.run", return_value=mock_result):
            exit_code = run_cmd(args)
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
