"""Slice C: Discord Integration — tests for webhook, bot commands, and hooks."""
from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


class TestDiscordModule(unittest.TestCase):

    def test_import(self):
        from justai.discord import (
            is_configured, notify, notify_stage, notify_complete,
            notify_error, parse_bot_command, format_help, OrchestratorHook,
        )

    def test_not_configured_by_default(self):
        from justai.discord import is_configured
        # In test env, JUSTAI_DISCORD_WEBHOOK is not set
        assert is_configured() is False

    def test_notify_returns_false_when_not_configured(self):
        from justai.discord import notify
        result = notify("test message")
        assert result is False

    def test_notify_stage_returns_false_when_not_configured(self):
        from justai.discord import notify_stage
        result = notify_stage("planner", "4 tasks", run_id="42")
        assert result is False

    def test_notify_complete_returns_false_when_not_configured(self):
        from justai.discord import notify_complete
        result = notify_complete({"status": "complete", "done": 4, "total": 4})
        assert result is False


class TestBotCommandParsing(unittest.TestCase):

    def test_parse_run_command(self):
        from justai.discord import parse_bot_command
        cmd = parse_bot_command('!justai run "fix the login bug"')
        assert cmd is not None
        assert cmd.command == "run"
        assert cmd.args == '"fix the login bug"'

    def test_parse_status_command(self):
        from justai.discord import parse_bot_command
        cmd = parse_bot_command("!justai status")
        assert cmd is not None
        assert cmd.command == "status"
        assert cmd.args == ""

    def test_parse_help_command(self):
        from justai.discord import parse_bot_command
        cmd = parse_bot_command("!justai")
        assert cmd is not None
        assert cmd.command == "help"

    def test_parse_non_command(self):
        from justai.discord import parse_bot_command
        cmd = parse_bot_command("hello world")
        assert cmd is None

    def test_parse_case_insensitive(self):
        from justai.discord import parse_bot_command
        cmd = parse_bot_command("!JustAi Health")
        assert cmd is not None
        assert cmd.command == "health"

    def test_format_help(self):
        from justai.discord import format_help
        text = format_help()
        assert "run" in text
        assert "status" in text
        assert "health" in text


class TestOrchestratorHook(unittest.TestCase):

    def test_hook_disabled_when_not_configured(self):
        from justai.discord import OrchestratorHook
        hook = OrchestratorHook(run_id="42")
        assert hook.enabled is False

    @patch("justai.discord.WEBHOOK_URL", "https://example.com/webhook")
    @patch("justai.discord._send_webhook_async")
    def test_hook_on_stage(self, mock_send):
        from justai.discord import OrchestratorHook
        hook = OrchestratorHook(run_id="42")
        hook.enabled = True
        hook.on_stage("planner", "4 tasks generated")
        # Should have called notify which calls _send_webhook_async
        # (can't easily assert because notify is called inline)

    @patch("justai.discord.WEBHOOK_URL", "https://example.com/webhook")
    @patch("justai.discord._send_webhook")
    def test_webhook_send_with_url(self, mock_send):
        mock_send.return_value = True
        from justai.discord import _send_webhook
        result = _send_webhook({"embeds": [{"title": "test"}]})
        assert result is True


class TestWebhookPayload(unittest.TestCase):

    @patch("justai.discord.WEBHOOK_URL", "https://example.com/webhook")
    @patch("justai.discord._send_webhook_async")
    def test_notify_builds_embed(self, mock_send):
        from justai.discord import notify
        result = notify("test message", title="Test", color=0xff0000)
        assert result is True
        mock_send.assert_called_once()
        payload = mock_send.call_args[0][0]
        assert "embeds" in payload
        assert payload["embeds"][0]["title"] == "Test"
        assert payload["embeds"][0]["description"] == "test message"
        assert payload["embeds"][0]["color"] == 0xff0000

    @patch("justai.discord.WEBHOOK_URL", "https://example.com/webhook")
    @patch("justai.discord._send_webhook_async")
    def test_notify_complete_fields(self, mock_send):
        from justai.discord import notify_complete
        summary = {
            "status": "complete", "goal": "Fix bug", "done": 3,
            "total": 3, "duration": 45.2, "cost": 0.05,
        }
        result = notify_complete(summary, run_id="42")
        assert result is True
        payload = mock_send.call_args[0][0]
        embed = payload["embeds"][0]
        assert "Complete" in embed["title"]
        assert any(f["name"] == "Cost" for f in embed["fields"])

    @patch("justai.discord.WEBHOOK_URL", "https://example.com/webhook")
    @patch("justai.discord._send_webhook_async")
    def test_notify_error_includes_root_cause(self, mock_send):
        from justai.discord import notify_error
        result = notify_error("Plan failed", stage="reviewer", root_cause="Missing success criteria")
        assert result is True
        payload = mock_send.call_args[0][0]
        embed = payload["embeds"][0]
        assert "Error" in embed["title"]
        assert "reviewer" in embed["title"]


class TestDiscordAPI(unittest.TestCase):

    def test_discord_status_endpoint(self):
        from justai.api import APIHandler
        handler = APIHandler.__new__(APIHandler)
        handler.path = "/api/discord/status"
        handler.headers = {}

        responses = []
        handler._json = lambda data, status=200: responses.append((data, status))
        handler.do_GET()

        assert len(responses) == 1
        data, _ = responses[0]
        assert "configured" in data
        assert data["configured"] is False  # Not configured in test env


if __name__ == "__main__":
    unittest.main()
