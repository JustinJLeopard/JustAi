#!/usr/bin/env python3
"""
Tests for JustAi Orchestrator Core (Sprint 2)

Covers: intent_gate, planner, reviewer, checkpoint
Uses mocking for LiteLLM calls so tests run offline without API access.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

# Ensure justai package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))


def _http_response(status: int, body: dict | str, content_type: str = "application/json"):
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.status = status
    resp.headers = {"Content-Type": content_type}
    payload = json.dumps(body).encode() if isinstance(body, dict) else body.encode()
    resp.read.return_value = payload
    return resp


def _http_error(status: int, body: dict | str, content_type: str = "application/json"):
    payload = json.dumps(body).encode() if isinstance(body, dict) else body.encode()
    return HTTPError(
        url="http://example.test",
        code=status,
        msg="mock",
        hdrs={"Content-Type": content_type},
        fp=BytesIO(payload),
    )


# ── Service Health ───────────────────────────────────────────────────────────


class ServiceHealthTests(unittest.TestCase):
    def test_litellm_accepts_models_data_signature(self):
        from justai.health import check_litellm

        with patch("urllib.request.urlopen", return_value=_http_response(200, {"data": []})):
            status = check_litellm()
        self.assertTrue(status.ok)
        self.assertIn("models API", status.detail)

    def test_litellm_accepts_auth_required_signature(self):
        from justai.health import check_litellm

        err = _http_error(401, {"error": {"message": "Missing API key"}})
        with patch("urllib.request.urlopen", side_effect=err):
            status = check_litellm()
        self.assertTrue(status.ok)
        self.assertIn("http 401", status.detail)

    def test_safe_mini_protocol_stub_is_not_a_healthy_runner(self):
        from justai.health import check_safe_mini_boundary

        status = check_safe_mini_boundary()
        self.assertFalse(status.ok)
        self.assertEqual(status.name, "safe-mini boundary")
        self.assertIn("not integrated", status.detail)

    def test_memory_requires_health_ok_signature(self):
        from justai.health import check_memory

        with patch("urllib.request.urlopen", return_value=_http_response(200, {"status": "ok"})):
            status = check_memory()
        self.assertTrue(status.ok)


# ── Intent Gate ───────────────────────────────────────────────────────────────


class IntentGateTests(unittest.TestCase):
    def test_heuristic_classifies_short_specific_goal_as_execution(self):
        from justai.intent_gate import Intent, _heuristic_classify

        result = _heuristic_classify("add a /health endpoint to health_server.py")
        self.assertEqual(result.intent, Intent.EXECUTION)
        self.assertGreater(result.confidence, 0.5)

    def test_heuristic_classifies_research_keywords(self):
        from justai.intent_gate import Intent, _heuristic_classify

        result = _heuristic_classify("what are the tradeoffs of safe-mini executor policies")
        self.assertEqual(result.intent, Intent.RESEARCH)

    def test_heuristic_classifies_empty_goal_as_ambiguous(self):
        from justai.intent_gate import Intent, _heuristic_classify

        result = _heuristic_classify("build")
        self.assertEqual(result.intent, Intent.AMBIGUOUS)
        self.assertNotEqual(result.clarifying_question, "")

    def test_heuristic_classifies_long_goal_as_multistep(self):
        from justai.intent_gate import Intent, _heuristic_classify

        goal = (
            "Build a FastAPI webhook endpoint that accepts GitHub push events, "
            "parses the payload, and posts a summary to Discord channel #dev-updates"
        )
        result = _heuristic_classify(goal)
        self.assertEqual(result.intent, Intent.MULTI_STEP)

    def test_classify_empty_string_returns_ambiguous(self):
        from justai.intent_gate import Intent, classify

        result = classify("")
        self.assertEqual(result.intent, Intent.AMBIGUOUS)
        self.assertNotEqual(result.clarifying_question, "")

    def test_classify_falls_back_to_heuristic_on_litellm_failure(self):
        from justai.intent_gate import Intent, classify

        with patch("justai.intent_gate._call_litellm", side_effect=Exception("connection refused")):
            result = classify("add a /health endpoint to health_server.py")
        self.assertEqual(result.intent, Intent.EXECUTION)
        self.assertIn("heuristic", result.reasoning)

    def test_classify_uses_litellm_response_when_available(self):
        from justai.intent_gate import Intent, classify

        mock_response = {
            "intent": "multi-step",
            "confidence": 0.92,
            "reasoning": "Goal spans multiple components.",
            "clarifying_question": "",
        }
        with patch("justai.intent_gate._call_litellm", return_value=mock_response):
            result = classify("build a webhook that posts to Discord")
        self.assertEqual(result.intent, Intent.MULTI_STEP)
        self.assertAlmostEqual(result.confidence, 0.92)

    def test_intent_result_has_no_clarifying_question_for_non_ambiguous(self):
        from justai.intent_gate import classify

        mock_response = {
            "intent": "execution",
            "confidence": 0.95,
            "reasoning": "Single file, single concern.",
            "clarifying_question": "",
        }
        with patch("justai.intent_gate._call_litellm", return_value=mock_response):
            result = classify("fix the import error in relay_dispatch.sh")
        self.assertEqual(result.clarifying_question, "")


# ── Planner ───────────────────────────────────────────────────────────────────


class PlannerTests(unittest.TestCase):
    def _mock_plan_response(self):
        return {
            "tasks": [
                {
                    "title": "Explore health_server.py",
                    "description": "Read scripts/health_server.py and understand current endpoint structure.",
                    "agent": "mini",
                    "risk": "R0",
                    "success_criteria": "cat scripts/health_server.py && echo DONE",
                    "depends_on": [],
                },
                {
                    "title": "Add /health/agents endpoint",
                    "description": "In scripts/health_server.py add a /health/agents route returning registered agents as JSON.",
                    "agent": "mini",
                    "risk": "R1",
                    "success_criteria": "grep -q '/health/agents' scripts/health_server.py && echo DONE",
                    "depends_on": [0],
                },
            ]
        }

    def test_decompose_returns_plan_with_tasks(self):
        from justai.scope_planner import decompose

        with patch("justai.scope_planner._call_litellm", return_value=self._mock_plan_response()):
            plan = decompose("add /health/agents endpoint", session_ref="test")
        self.assertEqual(len(plan.tasks), 2)
        self.assertEqual(plan.session_ref, "test")

    def test_decompose_preserves_dependency_order(self):
        from justai.scope_planner import decompose

        with patch("justai.scope_planner._call_litellm", return_value=self._mock_plan_response()):
            plan = decompose("add /health/agents endpoint")
        self.assertEqual(plan.tasks[1].depends_on, [0])

    def test_decompose_first_task_is_read_not_write(self):
        from justai.scope_planner import RiskLevel, decompose

        with patch("justai.scope_planner._call_litellm", return_value=self._mock_plan_response()):
            plan = decompose("add /health/agents endpoint")
        self.assertEqual(plan.tasks[0].risk, RiskLevel.R0)

    def test_decompose_falls_back_to_single_task_on_litellm_failure(self):
        from justai.scope_planner import decompose

        with patch("justai.scope_planner._call_litellm", side_effect=Exception("timeout")):
            plan = decompose("add /health/agents endpoint")
        # Heuristic fallback: explore + execute + verify (Sprint 7)
        self.assertGreaterEqual(len(plan.tasks), 2)
        self.assertEqual(plan.goal, "add /health/agents endpoint")

    def test_format_plan_includes_all_tasks(self):
        from justai.scope_planner import decompose, format_plan

        with patch("justai.scope_planner._call_litellm", return_value=self._mock_plan_response()):
            plan = decompose("add /health/agents endpoint")
        output = format_plan(plan)
        self.assertIn("Explore health_server.py", output)
        self.assertIn("Add /health/agents endpoint", output)

    def test_task_risk_levels_parsed_correctly(self):
        from justai.scope_planner import RiskLevel, decompose

        with patch("justai.scope_planner._call_litellm", return_value=self._mock_plan_response()):
            plan = decompose("add /health/agents endpoint")
        self.assertEqual(plan.tasks[0].risk, RiskLevel.R0)
        self.assertEqual(plan.tasks[1].risk, RiskLevel.R1)


# ── Reviewer ──────────────────────────────────────────────────────────────────


class ReviewerTests(unittest.TestCase):
    def _make_plan(self, tasks_override=None):
        from justai.scope_planner import AgentType, Plan, RiskLevel, Task

        tasks = tasks_override or [
            Task(
                title="Explore health_server.py",
                description="Read scripts/health_server.py and understand current endpoint structure.",
                agent=AgentType.MINI,
                risk=RiskLevel.R0,
                success_criteria="cat scripts/health_server.py && echo DONE",
                depends_on=[],
            ),
            Task(
                title="Add /health/agents endpoint",
                description="Add route to scripts/health_server.py.",
                agent=AgentType.MINI,
                risk=RiskLevel.R1,
                success_criteria="grep -q '/health/agents' scripts/health_server.py",
                depends_on=[0],
            ),
        ]
        return Plan(goal="add /health/agents endpoint", tasks=tasks)

    def test_heuristic_approves_valid_plan(self):
        from justai.reviewer import _heuristic_review

        plan = self._make_plan()
        result = _heuristic_review(plan)
        self.assertTrue(result.approved)
        self.assertEqual(result.feedback, [])

    def test_heuristic_rejects_placeholder_success_criteria(self):
        from justai.reviewer import _heuristic_review
        from justai.scope_planner import AgentType, RiskLevel, Task

        bad_task = Task(
            title="Do something",
            description="Do something vague.",
            agent=AgentType.MINI,
            risk=RiskLevel.R1,
            success_criteria="echo 'verify manually'",
            depends_on=[],
        )
        from justai.scope_planner import Plan

        plan = Plan(goal="do something", tasks=[bad_task])
        result = _heuristic_review(plan)
        self.assertFalse(result.approved)
        self.assertTrue(any("success criteria" in issue for issue in result.feedback))

    def test_heuristic_rejects_bad_dependency_ordering(self):
        from justai.reviewer import _heuristic_review
        from justai.scope_planner import AgentType, Plan, RiskLevel, Task

        task0 = Task(
            "First", "Do first.", AgentType.MINI, RiskLevel.R1, "echo done", depends_on=[1]
        )  # depends on task that comes AFTER
        task1 = Task(
            "Second", "Do second.", AgentType.MINI, RiskLevel.R1, "echo done", depends_on=[]
        )
        plan = Plan(goal="bad order", tasks=[task0, task1])
        result = _heuristic_review(plan)
        self.assertFalse(result.approved)

    def test_review_empty_plan_is_rejected(self):
        from justai.reviewer import review
        from justai.scope_planner import Plan

        plan = Plan(goal="nothing", tasks=[])
        result = review(plan)
        self.assertFalse(result.approved)

    def test_review_uses_litellm_when_available(self):
        from justai.reviewer import review

        mock_response = {"approved": True, "feedback": [], "suggestions": []}
        with patch("justai.reviewer._call_litellm", return_value=mock_response):
            result = review(self._make_plan())
        self.assertTrue(result.approved)

    def test_review_falls_back_to_heuristic_on_litellm_failure(self):
        from justai.reviewer import review

        with patch("justai.reviewer._call_litellm", side_effect=Exception("timeout")):
            result = review(self._make_plan())
        # Valid plan should still pass heuristic review
        self.assertTrue(result.approved)


# ── Checkpoint ────────────────────────────────────────────────────────────────


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        """Give every check its own gate directory.

        These used to write into the shared runtime root, so a checkpoint test
        and a real run on the same machine dropped files in one place. A
        per-test directory costs nothing and makes the isolation explicit.
        """
        import justai.checkpoint as cp

        self._gate_root = tempfile.TemporaryDirectory(prefix="justai-gates-")
        self.addCleanup(self._gate_root.cleanup)
        patcher = patch.object(cp, "GATE_SIGNAL_DIR", Path(self._gate_root.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _a_gate(self, label: str):
        """A gate identity for one task in one run, with a fresh run id."""
        from justai.checkpoint import GateIdentity
        from justai.run_identity import new_run_id

        return GateIdentity(run_id=new_run_id(), index=0, session_ref=label)

    def _make_task(self, risk_str: str, title: str = "Test task"):
        from justai.scope_planner import AgentType, RiskLevel, Task

        return Task(
            title=title,
            description="Test description.",
            agent=AgentType.MINI,
            risk=RiskLevel(risk_str),
            success_criteria="echo done",
            depends_on=[],
        )

    def test_r0_always_proceeds(self):
        from justai.checkpoint import evaluate

        task = self._make_task("R0")
        proceed, reason = evaluate(task, self._a_gate("r0"))
        self.assertTrue(proceed)
        self.assertIn("R0", reason)

    def test_r3_always_blocked(self):
        from justai.checkpoint import evaluate

        with patch("justai.checkpoint._discord_notify", return_value=False):
            task = self._make_task("R3")
            proceed, reason = evaluate(task, self._a_gate("r3"))
        self.assertFalse(proceed)
        self.assertIn("blocked", reason.lower())

    def test_r1_auto_proceeds_after_timeout(self):
        import justai.checkpoint as cp
        from justai.checkpoint import evaluate

        original_timeout = cp.R1_TIMEOUT_SECONDS
        cp.R1_TIMEOUT_SECONDS = 0  # instant timeout for test
        try:
            with patch("justai.checkpoint._discord_notify", return_value=False):
                task = self._make_task("R1")
                proceed, reason = evaluate(task, self._a_gate("r1-timeout"))
            self.assertTrue(proceed)
            self.assertIn("auto-approved", reason)
        finally:
            cp.R1_TIMEOUT_SECONDS = original_timeout

    def test_r1_can_be_vetoed_via_gate_file(self):
        import threading
        import time

        import justai.checkpoint as cp
        from justai.checkpoint import cleanup_run, evaluate, gate_path

        original_timeout = cp.R1_TIMEOUT_SECONDS
        cp.R1_TIMEOUT_SECONDS = 5

        gate = self._a_gate("r1-veto")

        def veto_after_delay():
            # Written the way the operator is told to write it, to the path the
            # checkpoint announced — not through an internal helper.
            time.sleep(0.3)
            gate_path(gate).write_text(json.dumps({"status": "vetoed", "reason": "test veto"}))

        try:
            with patch("justai.checkpoint._discord_notify", return_value=False):
                t = threading.Thread(target=veto_after_delay, daemon=True)
                t.start()
                task = self._make_task("R1")
                proceed, reason = evaluate(task, gate)
            self.assertFalse(proceed)
            self.assertIn("vetoed", reason.lower())
        finally:
            cp.R1_TIMEOUT_SECONDS = original_timeout
            cleanup_run(gate.run_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
