#!/usr/bin/env python3
"""Sprint 7 tests — session memory, auto mode, preflight, planner retry."""

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _a_gate(label: str):
    """A gate identity for one task in one run.

    Each call mints a fresh run id, so these checks never share a gate with
    each other or with a run happening alongside them. The label is only what
    an operator would read.
    """
    from justai.checkpoint import GateIdentity
    from justai.run_identity import new_run_id

    return GateIdentity(run_id=new_run_id(), index=0, session_ref=label)


class TestAutoMode(unittest.TestCase):
    """Test --auto flag skips R1 checkpoint wait."""

    def test_auto_mode_env_detection(self):
        """JUSTAI_AUTO_MODE=1 is detected by checkpoint."""
        from justai.checkpoint import _is_auto_mode

        with patch.dict(os.environ, {"JUSTAI_AUTO_MODE": "1"}):
            self.assertTrue(_is_auto_mode())

    def test_auto_mode_false_by_default(self):
        from justai.checkpoint import _is_auto_mode

        with patch.dict(os.environ, {"JUSTAI_AUTO_MODE": ""}):
            self.assertFalse(_is_auto_mode())

    def test_auto_mode_true_variants(self):
        from justai.checkpoint import _is_auto_mode

        for val in ("1", "true", "yes", "True", "YES"):
            with patch.dict(os.environ, {"JUSTAI_AUTO_MODE": val}):
                self.assertTrue(_is_auto_mode(), f"Expected True for '{val}'")

    def test_r1_auto_mode_immediate_approval(self):
        """R1 tasks approve immediately in auto mode — no 60s wait."""
        from justai.checkpoint import evaluate
        from justai.scope_planner import AgentType, RiskLevel, Task

        task = Task(
            title="test task",
            description="test",
            agent=AgentType.MINI,
            risk=RiskLevel.R1,
            success_criteria="echo ok",
        )
        with patch.dict(os.environ, {"JUSTAI_AUTO_MODE": "1"}):
            start = time.time()
            proceed, reason = evaluate(task, _a_gate("auto-1"))
            elapsed = time.time() - start

        self.assertTrue(proceed)
        self.assertIn("auto mode", reason)
        self.assertLess(elapsed, 2.0, "R1 in auto mode should not wait")

    def test_r0_always_immediate(self):
        """R0 always auto-approves regardless of mode."""
        from justai.checkpoint import evaluate
        from justai.scope_planner import AgentType, RiskLevel, Task

        task = Task(
            title="read only",
            description="explore",
            agent=AgentType.MINI,
            risk=RiskLevel.R0,
            success_criteria="echo ok",
        )
        proceed, reason = evaluate(task, _a_gate("r0-1"))
        self.assertTrue(proceed)
        self.assertIn("R0", reason)

    def test_r3_always_blocked(self):
        """R3 always blocks regardless of mode."""
        from justai.checkpoint import evaluate
        from justai.scope_planner import AgentType, RiskLevel, Task

        task = Task(
            title="dangerous op",
            description="destroy",
            agent=AgentType.MINI,
            risk=RiskLevel.R3,
            success_criteria="echo ok",
        )
        with patch.dict(os.environ, {"JUSTAI_AUTO_MODE": "1"}):
            proceed, reason = evaluate(task, _a_gate("r3-1"))
        self.assertFalse(proceed)
        self.assertIn("blocked", reason)


class TestServicePreflight(unittest.TestCase):
    """Test health.py service preflight checks."""

    def test_check_litellm_structure(self):
        from justai.health import ServiceStatus, check_litellm

        result = check_litellm()
        self.assertIsInstance(result, ServiceStatus)
        self.assertEqual(result.name, "LiteLLM")
        self.assertIsInstance(result.ok, bool)

    def test_check_safe_mini_boundary_structure(self):
        from justai.health import ServiceStatus, check_safe_mini_boundary

        result = check_safe_mini_boundary()
        self.assertIsInstance(result, ServiceStatus)
        self.assertEqual(result.name, "safe-mini boundary")

    def test_check_memory_structure(self):
        from justai.health import ServiceStatus, check_memory

        result = check_memory()
        self.assertIsInstance(result, ServiceStatus)
        self.assertEqual(result.name, "claude-flow MCP")

    def test_preflight_returns_list(self):
        from justai.health import preflight

        results = preflight()
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 3)

    def test_print_preflight_returns_bool(self):
        from justai.health import ServiceStatus, print_preflight

        statuses = [
            ServiceStatus("LiteLLM", "http://localhost:4000", True, "ok"),
            ServiceStatus("safe-mini boundary", "justai.runner_protocol", True, "ok"),
            ServiceStatus("MCP", "http://localhost:3100", True, "ok"),
        ]
        result = print_preflight(statuses)
        self.assertTrue(result)

    def test_print_preflight_false_when_litellm_down(self):
        from justai.health import ServiceStatus, print_preflight

        statuses = [
            ServiceStatus("LiteLLM", "http://localhost:4000", False, "refused"),
            ServiceStatus("safe-mini boundary", "justai.runner_protocol", True, "ok"),
            ServiceStatus("MCP", "http://localhost:3100", True, "ok"),
        ]
        result = print_preflight(statuses)
        self.assertFalse(result)

    def test_preflight_non_critical_service_down(self):
        """Non-critical safe-mini boundary or MCP down should NOT fail preflight."""
        from justai.health import ServiceStatus, print_preflight

        statuses = [
            ServiceStatus("LiteLLM", "http://localhost:4000", True, "ok"),
            ServiceStatus("safe-mini boundary", "justai.runner_protocol", False, "down"),
            ServiceStatus("claude-flow MCP", "http://localhost:3100", False, "down"),
        ]
        result = print_preflight(statuses)
        self.assertTrue(result)


class TestSessionMemory(unittest.TestCase):
    """Test session context load/save in orchestrator."""

    def test_retrieve_memory_returns_none_on_failure(self):
        from justai.orchestrator import _retrieve_memory

        # With no MCP running, should return None gracefully
        result = _retrieve_memory("nonexistent/key")
        self.assertIsNone(result)

    def test_load_session_context_returns_none_on_miss(self):
        import uuid

        from justai.orchestrator import _load_session_context

        result = _load_session_context(f"sprint-never-exists-{uuid.uuid4().hex[:8]}")
        # If MCP is down, returns None. If up, this random ref won't exist.
        # Note: _load_session_context also checks "justai/session/latest"
        # which might exist from prior saves, so we just verify it returns str or None.
        self.assertIsInstance(result, (str, type(None)))

    def test_store_memory_does_not_raise(self):
        """_store_memory should never raise, even with MCP down."""
        from justai.orchestrator import _store_memory

        # Should silently fail — no exception
        _store_memory("test/key", "test value")

    def test_save_session_context_does_not_raise(self):
        from justai.orchestrator import _save_session_context

        _save_session_context("test-ref", "test summary")


class TestPlannerRetry(unittest.TestCase):
    """Test planner retry logic and heuristic fallback."""

    def test_heuristic_plan_has_explore_task(self):
        from justai.scope_planner import _heuristic_plan

        plan = _heuristic_plan("add a /ready endpoint to server.py")
        self.assertGreaterEqual(len(plan.tasks), 2)
        self.assertIn("explore", plan.tasks[0].title.lower())

    def test_heuristic_plan_verify_task(self):
        from justai.scope_planner import _heuristic_plan

        plan = _heuristic_plan("fix the login bug")
        # Should have explore, execute, verify
        self.assertEqual(len(plan.tasks), 3)
        self.assertIn("verify", plan.tasks[2].title.lower())

    def test_heuristic_plan_no_extra_verify_for_test_goal(self):
        from justai.scope_planner import _heuristic_plan

        plan = _heuristic_plan("run the test suite and check results")
        # Test goals don't get extra verify task
        self.assertEqual(len(plan.tasks), 2)

    def test_heuristic_plan_dependencies(self):
        from justai.scope_planner import _heuristic_plan

        plan = _heuristic_plan("add endpoint to app.py")
        # Execute depends on explore
        self.assertEqual(plan.tasks[1].depends_on, [0])
        # Verify depends on execute
        if len(plan.tasks) > 2:
            self.assertEqual(plan.tasks[2].depends_on, [1])

    def test_infer_verify_command_endpoint(self):
        from justai.scope_planner import _infer_verify_command

        cmd = _infer_verify_command("add /api/health endpoint")
        self.assertIn("curl", cmd)

    def test_infer_verify_command_test(self):
        from justai.scope_planner import _infer_verify_command

        cmd = _infer_verify_command("run the test suite")
        self.assertIn("pytest", cmd)

    def test_infer_verify_command_python_file(self):
        from justai.scope_planner import _infer_verify_command

        cmd = _infer_verify_command("update server.py with new handler")
        self.assertIn("python3", cmd)  # check command

    def test_infer_verify_command_generic(self):
        from justai.scope_planner import _infer_verify_command

        cmd = _infer_verify_command("do something abstract")
        self.assertIn("verify manually", cmd)

    def test_decompose_fallback_on_network_error(self):
        """When LLM is unreachable, decompose returns heuristic plan."""
        from justai import scope_planner
        from justai.scope_planner import decompose

        with patch.object(scope_planner, "_call_litellm", side_effect=ConnectionError("refused")):
            plan = decompose("add a feature", session_ref="test")
        self.assertGreaterEqual(len(plan.tasks), 2)
        self.assertEqual(plan.goal, "add a feature")

    def test_llm_retry_attempts_constant(self):
        from justai.scope_planner import LLM_RETRY_ATTEMPTS

        self.assertEqual(LLM_RETRY_ATTEMPTS, 2)


class TestOrchestratorCLIParsing(unittest.TestCase):
    """Test CLI argument parsing."""

    def test_parse_args_basic(self):
        from justai.orchestrator import _parse_args

        goal, auto, local, _swarm = _parse_args(["hello", "world"])
        self.assertEqual(goal, "hello world")
        self.assertFalse(auto)

    def test_parse_args_auto_flag(self):
        from justai.orchestrator import _parse_args

        goal, auto, local, _swarm = _parse_args(["--auto", "do", "something"])
        self.assertEqual(goal, "do something")
        self.assertTrue(auto)

    def test_parse_args_auto_at_end(self):
        from justai.orchestrator import _parse_args

        goal, auto, local, _swarm = _parse_args(["do", "something", "--auto"])
        self.assertEqual(goal, "do something")
        self.assertTrue(auto)

    def test_parse_args_empty(self):
        from justai.orchestrator import _parse_args

        goal, auto, local, _swarm = _parse_args([])
        self.assertEqual(goal, "")
        self.assertFalse(auto)


if __name__ == "__main__":
    unittest.main()
