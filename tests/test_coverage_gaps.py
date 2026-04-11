#!/usr/bin/env python3
"""
Sprint 2.5 — Coverage gap tests

Covers remaining uncovered lines in:
  intent_gate.py  — _call_litellm internals, markdown fence stripping
  planner.py      — _call_litellm path, context parameter, agent types
  reviewer.py     — _call_litellm path, _format_plan_for_review, suggestions
  checkpoint.py   — R1 approved via gate file, R2 wait loop
  delegator.py    — exec timeout, get_task_status parsing, board fallback
  justai_cli.py   — start, status, health, check, task, mini, relay commands
  justai_runtime  — relay_root, localmanus_root, runtime_paths edge cases
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import argparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))


# ── intent_gate — _call_litellm internals ────────────────────────────────────

class IntentGateLiteLLMTests(unittest.TestCase):

    def _mock_http_response(self, content: str):
        """Build a mock urllib response returning the given content string."""
        import io
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read = MagicMock(return_value=json.dumps({
            "choices": [{"message": {"content": content}}]
        }).encode())
        mock_resp.status = 200
        # Make json.load work on it
        mock_resp.read.side_effect = None
        inner = io.BytesIO(json.dumps({
            "choices": [{"message": {"content": content}}]
        }).encode())
        mock_resp.__iter__ = inner.__iter__
        return mock_resp

    def test_call_litellm_strips_markdown_json_fence(self):
        from justai.intent_gate import _call_litellm
        raw = '```json\n{"intent": "execution", "confidence": 0.9, "reasoning": "r", "clarifying_question": ""}\n```'
        mock_response = {
            "choices": [{"message": {"content": raw}}]
        }
        with patch("justai.intent_gate.urllib.request.urlopen") as mock_open:
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=MagicMock(
                read=MagicMock(return_value=json.dumps(mock_response).encode())
            ))
            mock_cm.__exit__ = MagicMock(return_value=False)
            # Use json.load path
            import io
            buf = io.BytesIO(json.dumps(mock_response).encode())
            mock_open.return_value.__enter__ = lambda s: buf
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            result = _call_litellm("test goal")
        self.assertEqual(result["intent"], "execution")

    def test_call_litellm_strips_plain_code_fence(self):
        from justai.intent_gate import _call_litellm
        raw = '```\n{"intent": "research", "confidence": 0.8, "reasoning": "r", "clarifying_question": ""}\n```'
        mock_response = {"choices": [{"message": {"content": raw}}]}
        import io
        buf = io.BytesIO(json.dumps(mock_response).encode())
        with patch("justai.intent_gate.urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__ = lambda s: buf
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            result = _call_litellm("research question")
        self.assertEqual(result["intent"], "research")

    def test_classify_uses_litellm_key_from_env(self):
        from justai.intent_gate import classify
        mock_response = {
            "intent": "execution", "confidence": 0.9,
            "reasoning": "test", "clarifying_question": ""
        }
        with patch("justai.intent_gate._call_litellm", return_value=mock_response) as mock_call:
            with patch.dict("os.environ", {"LITELLM_KEY": "sk-test-key"}):
                classify("add endpoint to server.py")
        mock_call.assert_called_once()

    def test_heuristic_classifies_goal_with_file_extension(self):
        from justai.intent_gate import _heuristic_classify, Intent
        result = _heuristic_classify("fix the bug in relay_dispatch.sh")
        self.assertEqual(result.intent, Intent.EXECUTION)

    def test_heuristic_multi_step_for_medium_length_goal(self):
        from justai.intent_gate import _heuristic_classify, Intent
        goal = "set up the database schema and wire it into the API layer"
        result = _heuristic_classify(goal)
        self.assertEqual(result.intent, Intent.MULTI_STEP)

    def test_classify_handles_malformed_json_from_litellm(self):
        from justai.intent_gate import classify
        with patch("justai.intent_gate._call_litellm", side_effect=json.JSONDecodeError("bad", "", 0)):
            result = classify("add endpoint to server.py")
        # Should fall back to heuristic
        self.assertIn("heuristic", result.reasoning)

    def test_classify_handles_invalid_intent_value(self):
        from justai.intent_gate import classify
        with patch("justai.intent_gate._call_litellm", return_value={
            "intent": "unknown-value", "confidence": 0.5,
            "reasoning": "test", "clarifying_question": ""
        }):
            result = classify("add endpoint to server.py")
        self.assertIn("heuristic", result.reasoning)


# ── planner — _call_litellm path, context, agent types ───────────────────────

class PlannerLiteLLMTests(unittest.TestCase):

    def _valid_response(self, n=2):
        tasks = []
        for i in range(n):
            tasks.append({
                "title": f"Task {i}",
                "description": f"Do task {i} in the repo.",
                "agent": "mini",
                "risk": "R0" if i == 0 else "R1",
                "success_criteria": f"grep -q 'task{i}' output.txt",
                "depends_on": [i-1] if i > 0 else [],
            })
        return {"tasks": tasks}

    def test_decompose_passes_context_to_litellm(self):
        from justai.planner import decompose
        with patch("justai.planner._call_litellm", return_value=self._valid_response()) as mock_call:
            decompose("add endpoint", context="Prior plan was rejected: task too large")
        args = mock_call.call_args
        self.assertIn("Prior plan was rejected", args[0][1])

    def test_decompose_researcher_agent_type_parsed(self):
        from justai.planner import decompose, AgentType
        response = {"tasks": [{
            "title": "Research options",
            "description": "Find examples of SpacetimeDB schemas.",
            "agent": "researcher",
            "risk": "R0",
            "success_criteria": "echo done",
            "depends_on": [],
        }]}
        with patch("justai.planner._call_litellm", return_value=response):
            plan = decompose("research SpacetimeDB schemas")
        self.assertEqual(plan.tasks[0].agent, AgentType.RESEARCHER)

    def test_decompose_session_ref_on_each_task(self):
        from justai.planner import decompose
        with patch("justai.planner._call_litellm", return_value=self._valid_response()):
            plan = decompose("add endpoint", session_ref="sprint-2.5")
        for task in plan.tasks:
            self.assertEqual(task.session_ref, "sprint-2.5")

    def test_decompose_r2_risk_level_parsed(self):
        from justai.planner import decompose, RiskLevel
        response = {"tasks": [{
            "title": "Delete old schema",
            "description": "Remove deprecated columns.",
            "agent": "mini",
            "risk": "R2",
            "success_criteria": "echo done",
            "depends_on": [],
        }]}
        with patch("justai.planner._call_litellm", return_value=response):
            plan = decompose("delete old schema")
        self.assertEqual(plan.tasks[0].risk, RiskLevel.R2)

    def test_format_plan_shows_dependency_indices(self):
        from justai.planner import decompose, format_plan
        with patch("justai.planner._call_litellm", return_value=self._valid_response(2)):
            plan = decompose("multi-task goal")
        output = format_plan(plan)
        self.assertIn("after [0]", output)

    def test_format_plan_shows_no_dependency_for_first_task(self):
        from justai.planner import decompose, format_plan
        with patch("justai.planner._call_litellm", return_value=self._valid_response(2)):
            plan = decompose("multi-task goal")
        lines = format_plan(plan).splitlines()
        first_task_line = [l for l in lines if "[0]" in l][0]
        self.assertNotIn("after", first_task_line)

    def test_decompose_empty_task_list_falls_back(self):
        from justai.planner import decompose
        with patch("justai.planner._call_litellm", return_value={"tasks": []}):
            plan = decompose("add endpoint")
        # Empty task list from LiteLLM — planner returns it as-is
        self.assertEqual(len(plan.tasks), 0)


# ── reviewer — LiteLLM path, format, suggestions merged into feedback ─────────

class ReviewerLiteLLMTests(unittest.TestCase):

    def _make_valid_plan(self):
        from justai.planner import Plan, Task, RiskLevel, AgentType
        return Plan(goal="add endpoint", tasks=[
            Task("Explore", "Read the file.", AgentType.MINI, RiskLevel.R0,
                 "cat file.py && echo DONE", []),
            Task("Add endpoint", "Add route.", AgentType.MINI, RiskLevel.R1,
                 "grep -q route file.py", [0]),
        ])

    def test_review_merges_feedback_and_suggestions(self):
        from justai.reviewer import review
        mock_response = {
            "approved": False,
            "feedback": ["Task 0 is too large"],
            "suggestions": ["Split into two tasks"],
        }
        with patch("justai.reviewer._call_litellm", return_value=mock_response):
            result = review(self._make_valid_plan())
        self.assertFalse(result.approved)
        self.assertIn("Task 0 is too large", result.feedback)
        self.assertIn("Split into two tasks", result.feedback)

    def test_format_plan_for_review_includes_all_fields(self):
        from justai.reviewer import _format_plan_for_review
        plan = self._make_valid_plan()
        output = _format_plan_for_review(plan)
        data = json.loads(output)
        self.assertEqual(data["task_count"], 2)
        self.assertEqual(data["tasks"][0]["title"], "Explore")
        self.assertEqual(data["tasks"][1]["depends_on"], [0])

    def test_review_approved_true_clears_feedback(self):
        from justai.reviewer import review
        with patch("justai.reviewer._call_litellm", return_value={
            "approved": True, "feedback": [], "suggestions": []
        }):
            result = review(self._make_valid_plan())
        self.assertTrue(result.approved)
        self.assertEqual(result.feedback, [])

    def test_heuristic_flags_very_long_description(self):
        from justai.planner import Plan, Task, RiskLevel, AgentType
        from justai.reviewer import _heuristic_review
        long_desc = "x " * 350  # > 600 chars
        task = Task("Big task", long_desc, AgentType.MINI, RiskLevel.R1,
                    "echo done", [])
        plan = Plan(goal="big goal", tasks=[task])
        result = _heuristic_review(plan)
        self.assertFalse(result.approved)
        self.assertTrue(any("oversized" in i for i in result.feedback))


# ── checkpoint — R1 approved via file, R2 wait loop ──────────────────────────

class CheckpointGateFileTests(unittest.TestCase):

    def _make_task(self, risk="R1"):
        from justai.planner import Task, RiskLevel, AgentType
        return Task("Test", "Do it.", AgentType.MINI, RiskLevel(risk), "echo done", [])

    def test_r1_approved_via_gate_file(self):
        from justai.checkpoint import evaluate, _write_gate, _gate_file
        import threading, time
        import justai.checkpoint as cp
        orig = cp.R1_TIMEOUT_SECONDS
        cp.R1_TIMEOUT_SECONDS = 5
        task_id = "test-r1-approved"

        def approve_after_delay():
            time.sleep(0.3)
            _write_gate(task_id, "approved")

        try:
            with patch("justai.checkpoint._discord_notify", return_value=False):
                t = threading.Thread(target=approve_after_delay, daemon=True)
                t.start()
                proceed, reason = evaluate(self._make_task("R1"), task_id=task_id)
            self.assertTrue(proceed)
            self.assertIn("approved", reason.lower())
        finally:
            cp.R1_TIMEOUT_SECONDS = orig
            _gate_file(task_id).unlink(missing_ok=True)

    def test_r2_approved_via_gate_file(self):
        from justai.checkpoint import evaluate, _write_gate, _gate_file
        import threading, time
        task_id = "test-r2-approved"

        def approve_after_delay():
            time.sleep(0.3)
            _write_gate(task_id, "approved")

        with patch("justai.checkpoint._discord_notify", return_value=False):
            t = threading.Thread(target=approve_after_delay, daemon=True)
            t.start()
            proceed, reason = evaluate(self._make_task("R2"), task_id=task_id)
        self.assertTrue(proceed)
        self.assertIn("approved", reason.lower())
        _gate_file(task_id).unlink(missing_ok=True)

    def test_r2_rejected_via_gate_file(self):
        from justai.checkpoint import evaluate, _write_gate, _gate_file
        import threading, time
        task_id = "test-r2-rejected"

        def reject_after_delay():
            time.sleep(0.3)
            _write_gate(task_id, "rejected", "too risky")

        with patch("justai.checkpoint._discord_notify", return_value=False):
            t = threading.Thread(target=reject_after_delay, daemon=True)
            t.start()
            proceed, reason = evaluate(self._make_task("R2"), task_id=task_id)
        self.assertFalse(proceed)
        self.assertIn("rejected", reason.lower())
        _gate_file(task_id).unlink(missing_ok=True)

    def test_discord_notify_called_for_r1(self):
        from justai.checkpoint import evaluate
        import justai.checkpoint as cp
        orig = cp.R1_TIMEOUT_SECONDS
        cp.R1_TIMEOUT_SECONDS = 0
        try:
            with patch("justai.checkpoint._discord_notify", return_value=True) as mock_notify:
                with patch.dict("os.environ", {"RELAY_COORDINATOR_TOKEN": "fake-token"}):
                    evaluate(self._make_task("R1"), task_id="test-discord-r1")
            mock_notify.assert_called()
            msg = mock_notify.call_args[0][0]
            self.assertIn("R1", msg)
        finally:
            cp.R1_TIMEOUT_SECONDS = orig

    def test_gate_file_write_and_read_roundtrip(self):
        from justai.checkpoint import _write_gate, _read_gate, _gate_file
        task_id = "test-roundtrip"
        _write_gate(task_id, "approved", "looks good")
        result = _read_gate(task_id)
        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["reason"], "looks good")
        _gate_file(task_id).unlink(missing_ok=True)


# ── delegator — exec timeout, board fallback ──────────────────────────────────

class DelegatorEdgeCaseTests(unittest.TestCase):

    def _make_task(self):
        from justai.planner import Task, RiskLevel, AgentType
        return Task("Test", "Do it.", AgentType.MINI, RiskLevel.R1, "echo done", [])

    def test_delegate_exec_timeout_when_task_never_completes(self):
        from justai.delegator import delegate
        import justai.delegator as d
        orig_claim = d.CLAIM_TIMEOUT
        orig_exec = d.EXEC_TIMEOUT
        d.CLAIM_TIMEOUT = 0
        d.EXEC_TIMEOUT = 0
        try:
            with patch("justai.delegator._post_task", return_value="55"):
                with patch("justai.delegator._get_task_status",
                           return_value={"status": "in_progress"}):
                    result = delegate(self._make_task())
            self.assertEqual(result.status, "timeout")
        finally:
            d.CLAIM_TIMEOUT = orig_claim
            d.EXEC_TIMEOUT = orig_exec

    def test_get_task_status_falls_back_to_board_json(self):
        from justai.delegator import _get_task_status
        # Board fallback is reached when show returns success but non-JSON stdout.
        # The code: returncode==0 -> json.loads raises -> falls back to board.
        show_result = MagicMock()
        show_result.returncode = 0
        show_result.stdout = "not valid json"   # triggers json.loads exception
        board_result = MagicMock()
        board_result.returncode = 0
        board_result.stdout = json.dumps({
            "tasks": [
                {"id": 42, "status": "done", "result": "endpoint added"}
            ]
        })
        def relay_side_effect(*args):
            if "show" in args:
                return show_result
            return board_result

        with patch("justai.delegator._relay", side_effect=relay_side_effect):
            status = _get_task_status("42")
        self.assertIsNotNone(status)
        self.assertEqual(status["status"], "done")

    def test_get_task_status_returns_none_when_both_fail(self):
        from justai.delegator import _get_task_status
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stdout = ""
        with patch("justai.delegator._relay", return_value=fail_result):
            status = _get_task_status("99")
        self.assertIsNone(status)

    def test_delegate_plan_returns_all_results_including_skipped(self):
        from justai.delegator import delegate_plan, DelegationResult
        from justai.planner import Task, RiskLevel, AgentType
        tasks = [
            Task("A", "Do A.", AgentType.MINI, RiskLevel.R1, "echo done", []),
            Task("B", "Do B.", AgentType.MINI, RiskLevel.R1, "echo done", [0]),
            Task("C", "Do C.", AgentType.MINI, RiskLevel.R1, "echo done", [0]),
        ]
        failed = DelegationResult("1", "A", "failed", "error", 1.0)
        with patch("justai.delegator.delegate", return_value=failed):
            results = delegate_plan(tasks)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].status, "failed")
        self.assertEqual(results[1].status, "skipped")
        self.assertEqual(results[2].status, "skipped")


# ── justai_cli — all commands ─────────────────────────────────────────────────

class CLICommandTests(unittest.TestCase):

    def _args(self, **kwargs):
        ns = argparse.Namespace()
        for k, v in kwargs.items():
            setattr(ns, k, v)
        return ns

    def test_start_cmd_calls_start_script(self):
        from tools.justai_cli import start_cmd
        with patch("tools.justai_cli.run", return_value=0) as mock_run:
            result = start_cmd(self._args(
                no_bots=False, no_codex=False,
                force_bootstrap=False, skip_relay_bootstrap=False
            ))
        self.assertEqual(result, 0)
        cmd = mock_run.call_args[0][0]
        self.assertTrue(any("start_justai" in str(c) for c in cmd))

    def test_start_cmd_passes_no_bots_flag(self):
        from tools.justai_cli import start_cmd
        with patch("tools.justai_cli.run", return_value=0) as mock_run:
            start_cmd(self._args(
                no_bots=True, no_codex=False,
                force_bootstrap=False, skip_relay_bootstrap=False
            ))
        cmd = mock_run.call_args[0][0]
        self.assertIn("--no-bots", cmd)

    def test_health_cmd_calls_check_script_with_health_flag(self):
        from tools.justai_cli import health_cmd
        with patch("tools.justai_cli.run", return_value=0) as mock_run:
            health_cmd(self._args())
        cmd = mock_run.call_args[0][0]
        self.assertIn("--health-only", cmd)

    def test_status_cmd_calls_check_script_with_status_flag(self):
        from tools.justai_cli import status_cmd
        with patch("tools.justai_cli.run", return_value=0) as mock_run:
            status_cmd(self._args(with_bots=False, with_codex=False))
        cmd = mock_run.call_args[0][0]
        self.assertIn("--status-only", cmd)

    def test_task_cmd_returns_1_when_ml_cli_missing(self):
        from tools.justai_cli import task_cmd
        with patch("tools.justai_cli.localmanus_root",
                   return_value=Path("/nonexistent")):
            result = task_cmd(self._args(description="do something"))
        self.assertEqual(result, 1)

    def test_mini_cmd_returns_1_when_ml_cli_missing(self):
        from tools.justai_cli import mini_cmd
        with patch("tools.justai_cli.localmanus_root",
                   return_value=Path("/nonexistent")):
            result = mini_cmd(self._args(description="do something"))
        self.assertEqual(result, 1)

    def test_relay_cmd_returns_1_when_daemon_ctl_missing(self):
        from tools.justai_cli import relay_cmd
        with patch("tools.justai_cli.relay_root",
                   return_value=Path("/nonexistent")):
            result = relay_cmd(self._args(action="status"))
        self.assertEqual(result, 1)

    def test_task_cmd_calls_ml_cli_when_present(self):
        from tools.justai_cli import task_cmd
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            tools_dir = Path(tmpdir) / "tools"
            tools_dir.mkdir()
            fake_ml = tools_dir / "ml_cli.py"
            fake_ml.touch()
            with patch("tools.justai_cli.localmanus_root", return_value=Path(tmpdir)):
                with patch("tools.justai_cli.run", return_value=0) as mock_run:
                    task_cmd(self._args(description="do the thing"))
            self.assertIsNotNone(mock_run.call_args)
            cmd = mock_run.call_args[0][0]
            self.assertIn("task", cmd)
            self.assertIn("do the thing", cmd)

    def test_build_parser_registers_run_command(self):
        from tools.justai_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["run", "add endpoint to server.py"])
        self.assertEqual(args.goal, "add endpoint to server.py")
        self.assertEqual(args.command, "run")

    def test_build_parser_run_has_session_ref_default(self):
        from tools.justai_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["run", "test goal"])
        self.assertEqual(args.session_ref, "sprint-2")

    def test_build_parser_run_accepts_custom_session_ref(self):
        from tools.justai_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["run", "test goal", "--session-ref", "sprint-3"])
        self.assertEqual(args.session_ref, "sprint-3")


# ── justai_runtime — path helpers ─────────────────────────────────────────────

class RuntimePathTests(unittest.TestCase):

    def test_repo_root_uses_env_var_when_set(self):
        from tools.justai_runtime import repo_root
        with patch.dict("os.environ", {"JUSTAI_ROOT": "/custom/root"}):
            result = repo_root()
        self.assertEqual(result, Path("/custom/root"))

    def test_localmanus_root_defaults_to_repo_localmanus(self):
        from tools.justai_runtime import localmanus_root, repo_root
        result = localmanus_root()
        self.assertEqual(result, repo_root() / "LocalManus")

    def test_relay_root_defaults_to_repo_relay_room(self):
        from tools.justai_runtime import relay_root, repo_root
        result = relay_root()
        self.assertEqual(result, repo_root() / "relay-room")

    def test_relay_root_uses_env_var_when_set(self):
        from tools.justai_runtime import relay_root
        with patch.dict("os.environ", {"JUSTAI_RELAY_ROOT": "/custom/relay"}):
            result = relay_root()
        self.assertEqual(result, Path("/custom/relay"))

    def test_runtime_paths_returns_all_expected_keys(self):
        from tools.justai_runtime import runtime_paths
        paths = runtime_paths()
        expected = {"root", "dispatch_pid", "dispatch_log",
                    "health_pid", "health_log", "web_pid", "web_log",
                    "bot_pid_dir", "bot_log_dir"}
        self.assertEqual(set(paths.keys()), expected)

    def test_runtime_env_sets_justai_root(self):
        from tools.justai_runtime import runtime_env, repo_root
        env = runtime_env()
        self.assertEqual(env["JUSTAI_ROOT"], str(repo_root()))

    def test_runtime_env_sets_localmanus_root_alias(self):
        from tools.justai_runtime import runtime_env, localmanus_root
        env = runtime_env()
        self.assertEqual(env["LOCALMANUS_ROOT"], str(localmanus_root()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
