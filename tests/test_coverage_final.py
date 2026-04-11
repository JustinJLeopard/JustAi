#!/usr/bin/env python3
"""
Sprint 2.5 — Final coverage push

Covers remaining gaps:
  planner._call_litellm    — HTTP request construction and response parsing
  reviewer._call_litellm   — HTTP request construction and response parsing
  checkpoint               — Discord notify HTTP path, R1 post-notify flow
  delegator                — _relay env setup, board ID mismatch, timeout branches
"""
from __future__ import annotations

import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))


def _make_http_mock(response_dict: dict):
    """Return a context-manager mock that json.load can read."""
    buf = io.BytesIO(json.dumps(response_dict).encode())
    cm = MagicMock()
    cm.__enter__ = lambda s: buf
    cm.__exit__ = MagicMock(return_value=False)
    return cm


# ── planner._call_litellm ─────────────────────────────────────────────────────

class PlannerCallLiteLLMTests(unittest.TestCase):

    def _litellm_response(self, tasks):
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({"tasks": tasks})
                }
            }]
        }

    def test_call_litellm_sends_correct_model(self):
        from justai.planner import _call_litellm
        response = self._litellm_response([{
            "title": "T", "description": "D", "agent": "mini",
            "risk": "R0", "success_criteria": "echo done", "depends_on": []
        }])
        with patch("justai.planner.urllib.request.urlopen",
                   return_value=_make_http_mock(response)) as mock_open:
            _call_litellm("add endpoint")
        request = mock_open.call_args[0][0]
        payload = json.loads(request.data)
        self.assertIn("claude-opus", payload["model"])

    def test_call_litellm_includes_goal_in_user_message(self):
        from justai.planner import _call_litellm
        response = self._litellm_response([{
            "title": "T", "description": "D", "agent": "mini",
            "risk": "R1", "success_criteria": "echo done", "depends_on": []
        }])
        with patch("justai.planner.urllib.request.urlopen",
                   return_value=_make_http_mock(response)) as mock_open:
            _call_litellm("add /health endpoint to server.py")
        request = mock_open.call_args[0][0]
        payload = json.loads(request.data)
        user_content = payload["messages"][-1]["content"]
        self.assertIn("add /health endpoint", user_content)

    def test_call_litellm_includes_context_when_provided(self):
        from justai.planner import _call_litellm
        response = self._litellm_response([{
            "title": "T", "description": "D", "agent": "mini",
            "risk": "R0", "success_criteria": "echo done", "depends_on": []
        }])
        with patch("justai.planner.urllib.request.urlopen",
                   return_value=_make_http_mock(response)) as mock_open:
            _call_litellm("add endpoint", context="Prior attempt failed: task too large")
        request = mock_open.call_args[0][0]
        payload = json.loads(request.data)
        user_content = payload["messages"][-1]["content"]
        self.assertIn("Prior attempt failed", user_content)

    def test_call_litellm_strips_json_fence_from_response(self):
        from justai.planner import _call_litellm
        fenced = '```json\n' + json.dumps({"tasks": []}) + '\n```'
        response = {"choices": [{"message": {"content": fenced}}]}
        with patch("justai.planner.urllib.request.urlopen",
                   return_value=_make_http_mock(response)):
            result = _call_litellm("some goal")
        self.assertIn("tasks", result)

    def test_call_litellm_uses_temperature_zero(self):
        from justai.planner import _call_litellm
        response = self._litellm_response([])
        with patch("justai.planner.urllib.request.urlopen",
                   return_value=_make_http_mock(response)) as mock_open:
            _call_litellm("test goal")
        payload = json.loads(mock_open.call_args[0][0].data)
        self.assertEqual(payload["temperature"], 0.0)


# ── reviewer._call_litellm ────────────────────────────────────────────────────

class ReviewerCallLiteLLMTests(unittest.TestCase):

    def _litellm_response(self, approved, feedback=None, suggestions=None):
        content = json.dumps({
            "approved": approved,
            "feedback": feedback or [],
            "suggestions": suggestions or [],
        })
        return {"choices": [{"message": {"content": content}}]}

    def _make_plan(self):
        from justai.planner import Plan, Task, RiskLevel, AgentType
        return Plan(goal="add endpoint", tasks=[
            Task("Explore", "Read.", AgentType.MINI, RiskLevel.R0, "echo done", []),
        ])

    def test_call_litellm_sends_plan_json_in_user_message(self):
        from justai.reviewer import _call_litellm
        response = self._litellm_response(True)
        with patch("justai.reviewer.urllib.request.urlopen",
                   return_value=_make_http_mock(response)) as mock_open:
            _call_litellm('{"goal": "test", "task_count": 1, "tasks": []}')
        request = mock_open.call_args[0][0]
        payload = json.loads(request.data)
        user_content = payload["messages"][-1]["content"]
        self.assertIn("task_count", user_content)

    def test_call_litellm_uses_temperature_zero(self):
        from justai.reviewer import _call_litellm
        response = self._litellm_response(True)
        with patch("justai.reviewer.urllib.request.urlopen",
                   return_value=_make_http_mock(response)) as mock_open:
            _call_litellm("{}")
        payload = json.loads(mock_open.call_args[0][0].data)
        self.assertEqual(payload["temperature"], 0.0)

    def test_review_via_litellm_rejected_with_combined_feedback(self):
        from justai.reviewer import review
        response = self._litellm_response(
            False,
            feedback=["Task 0 too large"],
            suggestions=["Split into read then write"]
        )
        with patch("justai.reviewer.urllib.request.urlopen",
                   return_value=_make_http_mock(response)):
            result = review(self._make_plan())
        self.assertFalse(result.approved)
        self.assertIn("Task 0 too large", result.feedback)
        self.assertIn("Split into read then write", result.feedback)

    def test_review_strips_json_fence_from_litellm_response(self):
        from justai.reviewer import review
        fenced = '```json\n' + json.dumps({
            "approved": True, "feedback": [], "suggestions": []
        }) + '\n```'
        response = {"choices": [{"message": {"content": fenced}}]}
        with patch("justai.reviewer.urllib.request.urlopen",
                   return_value=_make_http_mock(response)):
            result = review(self._make_plan())
        self.assertTrue(result.approved)


# ── checkpoint — Discord HTTP path ────────────────────────────────────────────

class CheckpointDiscordTests(unittest.TestCase):

    def test_discord_notify_sends_post_request(self):
        from justai.checkpoint import _discord_notify
        with patch("urllib.request.urlopen",
                   return_value=_make_http_mock({})) as mock_open:
            with patch("justai.checkpoint.DISCORD_BOT_TOKEN", "fake-token"):
                import justai.checkpoint as cp
                orig_token = cp.DISCORD_BOT_TOKEN
                cp.DISCORD_BOT_TOKEN = "fake-token"
                try:
                    result = _discord_notify("Test message")
                finally:
                    cp.DISCORD_BOT_TOKEN = orig_token
        # urlopen was called — message was sent
        mock_open.assert_called_once()

    def test_discord_notify_returns_false_when_no_token(self):
        from justai.checkpoint import _discord_notify
        import justai.checkpoint as cp
        orig = cp.DISCORD_BOT_TOKEN
        cp.DISCORD_BOT_TOKEN = ""
        try:
            result = _discord_notify("Test message")
        finally:
            cp.DISCORD_BOT_TOKEN = orig
        self.assertFalse(result)

    def test_discord_notify_returns_false_on_http_error(self):
        from justai.checkpoint import _discord_notify
        import justai.checkpoint as cp
        orig = cp.DISCORD_BOT_TOKEN
        cp.DISCORD_BOT_TOKEN = "fake-token"
        try:
            with patch("urllib.request.urlopen",
                       side_effect=Exception("connection refused")):
                result = _discord_notify("Test message")
        finally:
            cp.DISCORD_BOT_TOKEN = orig
        self.assertFalse(result)

    def test_r1_notifies_discord_when_token_set(self):
        from justai.checkpoint import evaluate
        from justai.planner import Task, RiskLevel, AgentType
        import justai.checkpoint as cp
        orig_timeout = cp.R1_TIMEOUT_SECONDS
        orig_token = cp.DISCORD_BOT_TOKEN
        cp.R1_TIMEOUT_SECONDS = 0
        cp.DISCORD_BOT_TOKEN = "fake-token"
        task = Task("Test", "Do it.", AgentType.MINI, RiskLevel.R1, "echo done", [])
        try:
            with patch("justai.checkpoint._discord_notify", return_value=True) as mock_notify:
                evaluate(task, task_id="test-discord-notify")
            mock_notify.assert_called_once()
            self.assertIn("R1", mock_notify.call_args[0][0])
        finally:
            cp.R1_TIMEOUT_SECONDS = orig_timeout
            cp.DISCORD_BOT_TOKEN = orig_token


# ── delegator — remaining edge cases ─────────────────────────────────────────

class DelegatorFinalTests(unittest.TestCase):

    def _make_task(self):
        from justai.planner import Task, RiskLevel, AgentType
        return Task("T", "D.", AgentType.MINI, RiskLevel.R1, "echo done", [])

    def test_relay_sets_relay_db_name_in_env(self):
        from justai.delegator import _relay
        with patch("justai.delegator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            _relay("board", "--json")
        env = mock_run.call_args[1]["env"]
        self.assertIn("RELAY_DB_NAME", env)

    def test_relay_sets_relay_server_in_env(self):
        from justai.delegator import _relay
        with patch("justai.delegator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            _relay("board", "--json")
        env = mock_run.call_args[1]["env"]
        self.assertIn("RELAY_SERVER", env)

    def test_get_task_status_returns_none_when_id_not_in_board(self):
        from justai.delegator import _get_task_status
        # show returns non-JSON, board returns JSON but task ID not found
        show_result = MagicMock()
        show_result.returncode = 0
        show_result.stdout = "not json"
        board_result = MagicMock()
        board_result.returncode = 0
        board_result.stdout = json.dumps({"tasks": [{"id": 99, "status": "done"}]})

        def side_effect(*args):
            return show_result if "show" in args else board_result

        with patch("justai.delegator._relay", side_effect=side_effect):
            result = _get_task_status("42")  # 42 not in board
        self.assertIsNone(result)

    def test_post_task_handles_numeric_id_with_trailing_text(self):
        from justai.delegator import _post_task
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Posted task #123 successfully to the relay board\n"
        with patch("justai.delegator._relay", return_value=mock_result):
            task_id = _post_task(self._make_task())
        self.assertEqual(task_id, "123")

    def test_post_task_returns_none_when_no_id_in_output(self):
        from justai.delegator import _post_task
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Task submitted successfully (no ID in output)\n"
        with patch("justai.delegator._relay", return_value=mock_result):
            task_id = _post_task(self._make_task())
        self.assertIsNone(task_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
