#!/usr/bin/env python3
"""Tests for S4-3: Stale agent watchdog in health_server.py.

Tests heartbeat parsing, stale detection, restart logic, and escalation
without requiring actual Discord bots or network access.
"""
import os
import signal
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

# Add scripts dir to path so we can import health_server
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import health_server as hs


class TestParseLastHeartbeat(unittest.TestCase):
    """Test _parse_last_heartbeat reads timestamps from bot log files."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self._orig_prefix = "/tmp/relay_bot_"  # used in function

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_log(self, agent, lines):
        path = f"/tmp/relay_bot_{agent}.log"
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
        self.addCleanup(lambda p=path: os.unlink(p) if os.path.exists(p) else None)
        return path

    def test_no_log_file_returns_none(self):
        result = hs._parse_last_heartbeat("nonexistent_agent_xyz")
        self.assertIsNone(result)

    def test_log_with_heartbeat_returns_datetime(self):
        self._write_log("testagent1", [
            "some random line",
            "[HEARTBEAT] testagent1 | alive | listening | 2025-07-12T10:30:00Z",
            "another line",
        ])
        result = hs._parse_last_heartbeat("testagent1")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 7)
        self.assertEqual(result.hour, 10)
        self.assertEqual(result.minute, 30)

    def test_returns_most_recent_heartbeat(self):
        self._write_log("testagent2", [
            "[HEARTBEAT] testagent2 | alive | listening | 2025-07-12T08:00:00Z",
            "[HEARTBEAT] testagent2 | alive | listening | 2025-07-12T09:00:00Z",
            "[HEARTBEAT] testagent2 | alive | listening | 2025-07-12T10:00:00Z",
        ])
        result = hs._parse_last_heartbeat("testagent2")
        self.assertIsNotNone(result)
        self.assertEqual(result.hour, 10)

    def test_log_without_heartbeat_returns_none(self):
        self._write_log("testagent3", [
            "INFO: Bot started",
            "Connected to gateway",
        ])
        result = hs._parse_last_heartbeat("testagent3")
        self.assertIsNone(result)


class TestIsAgentStale(unittest.TestCase):
    """Test _is_agent_stale combining PID check + heartbeat freshness."""

    def _write_log(self, agent, lines):
        path = f"/tmp/relay_bot_{agent}.log"
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
        self.addCleanup(lambda p=path: os.unlink(p) if os.path.exists(p) else None)

    def _write_pid(self, agent, pid):
        path = f"/tmp/relay_discord_{agent}.pid"
        with open(path, "w") as f:
            f.write(str(pid))
        self.addCleanup(lambda p=path: os.unlink(p) if os.path.exists(p) else None)

    def test_no_pid_file_is_stale(self):
        """Agent with no PID file should be detected as stale."""
        stale, reason = hs._is_agent_stale("ghost_agent_xyz")
        self.assertTrue(stale)
        self.assertIn("pid_dead", reason)

    def test_dead_pid_is_stale(self):
        """Agent with PID file pointing to dead process is stale."""
        self._write_pid("deadbot", 999999)  # very unlikely to be running
        stale, reason = hs._is_agent_stale("deadbot")
        self.assertTrue(stale)

    def test_alive_pid_fresh_heartbeat_not_stale(self):
        """Agent with running process and fresh heartbeat is healthy."""
        my_pid = os.getpid()
        self._write_pid("livebot", my_pid)
        fresh_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._write_log("livebot", [
            f"[HEARTBEAT] livebot | alive | listening | {fresh_ts}",
        ])
        stale, reason = hs._is_agent_stale("livebot")
        self.assertFalse(stale)
        self.assertIn("healthy", reason)

    def test_alive_pid_stale_heartbeat_is_stale(self):
        """Agent with running process but old heartbeat is stale."""
        my_pid = os.getpid()
        self._write_pid("stalebot", my_pid)
        old_ts = (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        self._write_log("stalebot", [
            f"[HEARTBEAT] stalebot | alive | listening | {old_ts}",
        ])
        stale, reason = hs._is_agent_stale("stalebot")
        self.assertTrue(stale)
        self.assertIn("heartbeat_stale", reason)


class TestWatchdogCheck(unittest.TestCase):
    """Test watchdog_check orchestration: alerts, restarts, escalation."""

    def setUp(self):
        # Reset watchdog state
        for agent in hs.BOT_AGENTS:
            hs._restart_counts[agent] = 0
            hs._last_healthy.pop(agent, None)

        # Mock _discord_post and _attempt_restart to capture calls
        self.discord_posts = []
        self.restart_calls = []

        self._patch_discord = mock.patch.object(
            hs, "_discord_post",
            side_effect=lambda ch, msg: self.discord_posts.append((ch, msg)),
        )
        self._patch_restart = mock.patch.object(
            hs, "_attempt_restart",
            side_effect=lambda agent: (self.restart_calls.append(agent), True)[1],
        )
        self._patch_discord.start()
        self._patch_restart.start()

    def tearDown(self):
        self._patch_discord.stop()
        self._patch_restart.stop()
        # Clean up any PID/log files
        for agent in hs.BOT_AGENTS:
            for pattern in [f"/tmp/relay_discord_{agent}.pid", f"/tmp/relay_bot_{agent}.log"]:
                if os.path.exists(pattern):
                    os.unlink(pattern)

    def _make_agent_stale(self, agent):
        """Write a PID file with a dead PID to simulate stale agent."""
        pid_file = f"/tmp/relay_discord_{agent}.pid"
        with open(pid_file, "w") as f:
            f.write("999999")  # dead PID

    def _make_agent_healthy(self, agent):
        """Write PID file with own PID + fresh heartbeat."""
        pid_file = f"/tmp/relay_discord_{agent}.pid"
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
        log_file = f"/tmp/relay_bot_{agent}.log"
        fresh_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(log_file, "w") as f:
            f.write(f"[HEARTBEAT] {agent} | alive | listening | {fresh_ts}\n")

    def test_stale_agent_triggers_alert_and_restart(self):
        """A stale agent should post to #alerts and attempt restart."""
        # Make all agents healthy except one
        for agent in hs.BOT_AGENTS:
            self._make_agent_healthy(agent)
        target = hs.BOT_AGENTS[0]
        self._make_agent_stale(target)

        hs.watchdog_check()

        # Should have posted to alerts
        alert_posts = [p for p in self.discord_posts if p[0] == "alerts"]
        self.assertTrue(len(alert_posts) >= 1, f"Expected alert post, got: {self.discord_posts}")
        self.assertIn(target, alert_posts[0][1])

        # Should have attempted restart
        self.assertIn(target, self.restart_calls)

        # Restart count should be 1
        self.assertEqual(hs._restart_counts[target], 1)

    def test_escalation_after_max_failures(self):
        """After MAX_RESTART_ATTEMPTS failures, escalate to #bugs-and-blockers."""
        target = hs.BOT_AGENTS[1]
        # Make all agents healthy except target
        for agent in hs.BOT_AGENTS:
            self._make_agent_healthy(agent)
        self._make_agent_stale(target)

        # Set restart count to max
        hs._restart_counts[target] = hs.MAX_RESTART_ATTEMPTS

        hs.watchdog_check()

        # Should have posted to bugs-and-blockers
        escalation_posts = [p for p in self.discord_posts if p[0] == "bugs-and-blockers"]
        self.assertTrue(
            len(escalation_posts) >= 1,
            f"Expected escalation post, got: {self.discord_posts}",
        )
        self.assertIn("ESCALATION", escalation_posts[0][1])
        self.assertIn(target, escalation_posts[0][1])

        # Should NOT have attempted restart
        self.assertNotIn(target, self.restart_calls)

    def test_healthy_agent_resets_counter(self):
        """A healthy agent should reset its restart count to 0."""
        target = hs.BOT_AGENTS[2]
        hs._restart_counts[target] = 2  # simulate prior failures
        self._make_agent_healthy(target)
        # Make others healthy too
        for agent in hs.BOT_AGENTS:
            if agent != target:
                self._make_agent_healthy(agent)

        hs.watchdog_check()

        self.assertEqual(hs._restart_counts[target], 0)

    def test_consecutive_failures_increment(self):
        """Each watchdog_check increments failure count for stale agents."""
        target = hs.BOT_AGENTS[0]
        for agent in hs.BOT_AGENTS:
            self._make_agent_healthy(agent)
        self._make_agent_stale(target)

        hs.watchdog_check()
        self.assertEqual(hs._restart_counts[target], 1)

        hs.watchdog_check()
        self.assertEqual(hs._restart_counts[target], 2)

        hs.watchdog_check()
        self.assertEqual(hs._restart_counts[target], 3)

        # Next check should escalate, not increment
        self.discord_posts.clear()
        hs.watchdog_check()
        escalation_posts = [p for p in self.discord_posts if p[0] == "bugs-and-blockers"]
        self.assertTrue(len(escalation_posts) >= 1)


class TestWatchdogEndpoint(unittest.TestCase):
    """Test that /health includes watchdog status for bot agents."""

    def test_health_check_includes_bot_agents(self):
        """run_all_checks should include discord bot checks."""
        result = hs.run_all_checks()
        names = {c["name"] for c in result["checks"]}
        for agent in hs.BOT_AGENTS:
            self.assertIn(f"discord_bot_{agent}", names)


if __name__ == "__main__":
    unittest.main()


class TestWatchdogStatusTracking(unittest.TestCase):
    """Test that watchdog_check populates _last_check_results for /health/watchdog."""

    def setUp(self):
        for agent in hs.BOT_AGENTS:
            hs._restart_counts[agent] = 0
        hs._last_healthy.clear()
        hs._last_check_results.clear()
        self.discord_posts = []
        self.restart_calls = []
        self._patch_discord = mock.patch.object(
            hs, "_discord_post",
            side_effect=lambda ch, msg: self.discord_posts.append((ch, msg)),
        )
        self._patch_restart = mock.patch.object(
            hs, "_attempt_restart",
            side_effect=lambda agent: (self.restart_calls.append(agent), True)[1],
        )
        self._patch_discord.start()
        self._patch_restart.start()

    def tearDown(self):
        self._patch_discord.stop()
        self._patch_restart.stop()
        for agent in hs.BOT_AGENTS:
            for pattern in [f"/tmp/relay_discord_{agent}.pid", f"/tmp/relay_bot_{agent}.log"]:
                if os.path.exists(pattern):
                    os.unlink(pattern)

    def _make_agent_healthy(self, agent):
        pid_file = f"/tmp/relay_discord_{agent}.pid"
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
        log_file = f"/tmp/relay_bot_{agent}.log"
        fresh_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(log_file, "w") as f:
            f.write(f"[HEARTBEAT] {agent} | alive | listening | {fresh_ts}\n")

    def test_last_check_results_populated(self):
        """After watchdog_check, _last_check_results should have entries for all agents."""
        for agent in hs.BOT_AGENTS:
            self._make_agent_healthy(agent)

        hs.watchdog_check()

        for agent in hs.BOT_AGENTS:
            self.assertIn(agent, hs._last_check_results)
            result = hs._last_check_results[agent]
            self.assertIn("stale", result)
            self.assertIn("reason", result)
            self.assertIn("last_heartbeat", result)
            self.assertIn("restart_count", result)
            self.assertIn("timestamp", result)

    def test_healthy_agents_show_not_stale(self):
        """Healthy agents should show stale=False in results."""
        for agent in hs.BOT_AGENTS:
            self._make_agent_healthy(agent)

        hs.watchdog_check()

        for agent in hs.BOT_AGENTS:
            self.assertFalse(hs._last_check_results[agent]["stale"])

    def test_stale_agent_recorded_in_results(self):
        """Stale agents should show stale=True in results."""
        for agent in hs.BOT_AGENTS:
            self._make_agent_healthy(agent)
        # Make first agent stale
        target = hs.BOT_AGENTS[0]
        with open(f"/tmp/relay_discord_{target}.pid", "w") as f:
            f.write("999999")

        hs.watchdog_check()

        self.assertTrue(hs._last_check_results[target]["stale"])

    def test_last_heartbeat_in_results(self):
        """Results should include last_heartbeat ISO timestamp when available."""
        for agent in hs.BOT_AGENTS:
            self._make_agent_healthy(agent)

        hs.watchdog_check()

        target = hs.BOT_AGENTS[0]
        self.assertIsNotNone(hs._last_check_results[target]["last_heartbeat"])


class TestDiscordPostFunction(unittest.TestCase):
    """Test _discord_post with and without token."""

    @mock.patch.dict(os.environ, {"RELAY_COORDINATOR_TOKEN": ""}, clear=False)
    def test_no_token_skips_post(self):
        """Without token, _discord_post should not raise and just skip."""
        # Should not raise
        hs._discord_post("alerts", "test message")

    @mock.patch("urllib.request.urlopen")
    @mock.patch.dict(os.environ, {"RELAY_COORDINATOR_TOKEN": "fake-token-123"}, clear=False)
    def test_with_token_makes_request(self, mock_urlopen):
        """With token, _discord_post should attempt a REST call."""
        mock_resp = mock.MagicMock()
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)
        mock_resp.read.return_value = b"{}"
        mock_urlopen.return_value = mock_resp

        hs._discord_post("alerts", "test alert message")

        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertIn("discord.com", req.full_url)
        self.assertEqual(req.get_header("Authorization"), "Bot fake-token-123")
