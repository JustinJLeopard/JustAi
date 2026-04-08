#!/usr/bin/env python3
"""Real unit tests for relay Discord slash commands."""

import importlib.util
import json
import pathlib
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "bot_listener.py"
SPEC = importlib.util.spec_from_file_location("relay_bot_listener", MODULE_PATH)
bot_listener = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(bot_listener)


def load_group(bot: "bot_listener.AgentBot"):
    groups = [cmd for cmd in bot.tree.get_commands() if getattr(cmd, "name", "") == "relay"]
    if not groups:
        raise AssertionError("relay slash command group not registered")
    return groups[0]


def load_command(bot: "bot_listener.AgentBot", name: str):
    group = load_group(bot)
    for cmd in group.commands:
        if cmd.name == name:
            return cmd
    raise AssertionError(f"slash command '{name}' not registered")


class TestRelaySlashCommands(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = bot_listener.AgentBot("relay-coordinator", 1491110247299944641, {})

    async def test_relay_status_returns_health_embed(self):
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        with (
            mock.patch.object(
                self.bot,
                "_fetch_json",
                side_effect=[
                    {"status": "healthy", "checks": [{"name": "litellm", "status": "ok"}]},
                    {
                        "summary": {"online": 5, "stale": 0, "offline": 0},
                        "agents": [
                            {"name": "relay-dispatch", "status": "online"},
                            {"name": "manuslocal", "status": "online"},
                        ],
                    },
                    {"tasks": {"by_status": {"pending": 1, "in_progress": 2}}},
                ],
            ),
            mock.patch.object(bot_listener, "bash", new=mock.AsyncMock(return_value=("Daemon running (PID 1, uptime 02:34)", 0))),
        ):
            command = load_command(self.bot, "status")
            await command.callback(interaction)

        interaction.response.defer.assert_awaited_once_with(thinking=True, ephemeral=True)
        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "Relay status")
        fields = {field.name: field.value for field in embed.fields}
        self.assertIn("online 5", fields["Agents"])
        self.assertEqual(fields["Tasks"], "active 3")
        self.assertEqual(fields["LiteLLM"], "healthy")
        self.assertEqual(fields["Overall"], "healthy")
        self.assertEqual(embed.footer.text, "slash command: /relay status")
        self.assertIn("relay-dispatch: online", fields["Agent Detail"])
        self.assertIn("manuslocal: online", fields["Agent Detail"])

    async def test_relay_board_respects_all_flag_and_summary_counts(self):
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        board_json = {
            "active_tasks": [
                {
                    "id": 7,
                    "title": "Review slash command coverage",
                    "status": "in_progress",
                    "to_agent": "manuslocal",
                    "retry_count": 1,
                }
            ],
            "summary": {"active": 1, "done_failed": 3, "archived": 5},
        }

        relay_mock = mock.AsyncMock(return_value=(json.dumps(board_json), 0))
        with mock.patch.object(bot_listener, "relay", new=relay_mock):
            command = load_command(self.bot, "board")
            await command.callback(interaction, all_=True)

        relay_mock.assert_awaited_once_with("board", "--all", "--json")
        embed = interaction.followup.send.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "Relay board (all)")
        counts = {field.name: field.value for field in embed.fields}["Counts"]
        self.assertIn("active 1", counts)
        self.assertIn("done/failed 3", counts)
        self.assertIn("archived 5", counts)
        self.assertIn("relay_web", embed.description)
        self.assertEqual(embed.footer.text, "slash command: /relay board")

    async def test_relay_post_rejects_blank_title(self):
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        relay_mock = mock.AsyncMock()
        with mock.patch.object(bot_listener, "relay", new=relay_mock):
            command = load_command(self.bot, "post")
            await command.callback(interaction, title="   ", body="", to="manuslocal", session="sprint-9")

        relay_mock.assert_not_called()
        embed = interaction.followup.send.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "/relay post failed")
        detail_field = embed.fields[0]
        self.assertEqual(detail_field.name, "Detail")
        self.assertIn("title is required", detail_field.value)

    async def test_relay_post_tracks_created_task(self):
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        relay_mock = mock.AsyncMock(return_value=("queued relay task for manuslocal id=12 task_uuid=abc", 0))
        with mock.patch.object(bot_listener, "relay", new=relay_mock):
            command = load_command(self.bot, "post")
            await command.callback(
                interaction,
                title="Ship retry proof",
                body="Confirm retry counter survives slash-command post flow",
                to="manuslocal",
                session="sprint-9",
            )

        relay_mock.assert_awaited_once_with(
            "post",
            "--from",
            "relay-coordinator",
            "--to",
            "manuslocal",
            "--title",
            "Ship retry proof",
            "--payload",
            "Confirm retry counter survives slash-command post flow",
            "--session",
            "sprint-9",
        )
        self.assertIn("12", self.bot._relay_post_watchers)
        self.assertEqual(self.bot._relay_post_watchers["12"]["to"], "manuslocal")
        self.assertEqual(self.bot._relay_post_watchers["12"]["session"], "sprint-9")
        embed = interaction.followup.send.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "Relay task posted")
        fields = {field.name: field.value for field in embed.fields}
        self.assertEqual(fields["Task ID"], "12")
        self.assertEqual(fields["Target"], "manuslocal")
        self.assertEqual(fields["Session"], "sprint-9")
        self.assertEqual(fields["Title"], "Ship retry proof")


if __name__ == "__main__":
    unittest.main()


class TestRelayBoardRetryAnnotation(unittest.IsolatedAsyncioTestCase):
    """Focused test: /relay board includes a retry annotation when retry_count > 0."""

    def setUp(self):
        self.bot = bot_listener.AgentBot("relay-coordinator", 1491110247299944641, {})

    async def test_relay_board_shows_retry_annotation_when_retry_count_positive(self):
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        board_json = {
            "active_tasks": [
                {
                    "id": 42,
                    "title": "Flaky deployment",
                    "status": "in_progress",
                    "to_agent": "manuslocal",
                    "retry_count": 3,
                },
                {
                    "id": 43,
                    "title": "Stable task",
                    "status": "pending",
                    "to_agent": "claudecli",
                    "retry_count": 0,
                },
            ],
            "summary": {"active": 2, "done_failed": 0, "archived": 0},
        }

        relay_mock = mock.AsyncMock(return_value=(json.dumps(board_json), 0))
        with mock.patch.object(bot_listener, "relay", new=relay_mock):
            command = load_command(self.bot, "board")
            await command.callback(interaction)

        embed = interaction.followup.send.await_args.kwargs["embed"]
        tasks_field = {f.name: f.value for f in embed.fields}["Tasks"]

        # Task with retry_count=3 must show the retry annotation
        self.assertIn("retry 3", tasks_field)
        # Task with retry_count=0 must NOT show any retry annotation
        self.assertNotIn("retry 0", tasks_field)




class TestRelayPostBodyOmitted(unittest.IsolatedAsyncioTestCase):
    """Focused test: /relay post with body omitted uses title as payload,
    does not add a Body embed field, and still records watcher metadata."""

    def setUp(self):
        self.bot = bot_listener.AgentBot("relay-coordinator", 1491110247299944641, {})

    async def test_relay_post_body_omitted_uses_title_as_payload(self):
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        relay_mock = mock.AsyncMock(
            return_value=("queued relay task for manuslocal id=55 task_uuid=xyz", 0)
        )
        with mock.patch.object(bot_listener, "relay", new=relay_mock):
            command = load_command(self.bot, "post")
            await command.callback(
                interaction,
                title="Deploy the new config",
                body="",
                to="manuslocal",
                session="sprint-10",
            )

        # 1) payload argument should be the title itself (body was empty)
        relay_mock.assert_awaited_once_with(
            "post",
            "--from",
            "relay-coordinator",
            "--to",
            "manuslocal",
            "--title",
            "Deploy the new config",
            "--payload",
            "Deploy the new config",
            "--session",
            "sprint-10",
        )

        embed = interaction.followup.send.await_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]

        # 2) No "Body" embed field when body is omitted
        self.assertNotIn("Body", field_names)

        # 3) Watcher metadata is still recorded
        self.assertIn("55", self.bot._relay_post_watchers)
        watcher = self.bot._relay_post_watchers["55"]
        self.assertEqual(watcher["to"], "manuslocal")
        self.assertEqual(watcher["session"], "sprint-10")
        self.assertEqual(watcher["task"], "Deploy the new config")


class TestRelayStatusDegraded(unittest.IsolatedAsyncioTestCase):
    """Focused test: /relay status when health endpoints return degraded data."""

    def setUp(self):
        self.bot = bot_listener.AgentBot("relay-coordinator", 1491110247299944641, {})

    async def test_relay_status_marks_litellm_and_overall_degraded(self):
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        with (
            mock.patch.object(
                self.bot,
                "_fetch_json",
                side_effect=[
                    # /health – overall degraded, litellm check NOT ok
                    {
                        "status": "degraded",
                        "checks": [{"name": "litellm", "status": "degraded"}],
                    },
                    # /health/agents
                    {
                        "summary": {"online": 3, "stale": 1, "offline": 1},
                        "agents": [
                            {"name": "relay-dispatch", "status": "online"},
                            {"name": "manuslocal", "status": "stale"},
                        ],
                    },
                    # /metrics
                    {"tasks": {"by_status": {"pending": 0, "in_progress": 1}}},
                ],
            ),
            mock.patch.object(
                bot_listener,
                "bash",
                new=mock.AsyncMock(return_value=("Daemon running (PID 99, uptime 01:00)", 0)),
            ),
        ):
            command = load_command(self.bot, "status")
            await command.callback(interaction)

        embed = interaction.followup.send.await_args.kwargs["embed"]
        fields = {field.name: field.value for field in embed.fields}

        # LiteLLM should be marked degraded (litellm check status != "ok")
        self.assertEqual(fields["LiteLLM"], "degraded")
        # Overall should reflect the degraded status from the health endpoint
        self.assertEqual(fields["Overall"], "degraded")


class TestRelayBoardAllWithArchivedAndDoneFailed(unittest.IsolatedAsyncioTestCase):
    """Focused test: /relay board all:true when archived and done_failed counts are present."""

    def setUp(self):
        self.bot = bot_listener.AgentBot("relay-coordinator", 1491110247299944641, {})

    async def test_board_all_true_with_archived_and_done_failed(self):
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        board_json = {
            "active_tasks": [
                {
                    "id": 10,
                    "title": "Migrate database schema",
                    "status": "in_progress",
                    "to_agent": "manuslocal",
                    "retry_count": 0,
                },
                {
                    "id": 11,
                    "title": "Validate migration output",
                    "status": "pending",
                    "to_agent": "claudecli",
                    "retry_count": 0,
                },
            ],
            "summary": {"active": 2, "done_failed": 7, "archived": 12},
        }

        relay_mock = mock.AsyncMock(return_value=(json.dumps(board_json), 0))
        with mock.patch.object(bot_listener, "relay", new=relay_mock):
            command = load_command(self.bot, "board")
            await command.callback(interaction, all_=True)

        relay_mock.assert_awaited_once_with("board", "--all", "--json")
        embed = interaction.followup.send.await_args.kwargs["embed"]

        # Title switches to "Relay board (all)" when all_=True
        self.assertEqual(embed.title, "Relay board (all)")

        # Description references relay_web
        self.assertIn("relay_web", embed.description)

        # Counts field includes active, done_failed, and archived totals
        fields = {f.name: f.value for f in embed.fields}
        counts = fields["Counts"]
        self.assertIn("active 2", counts)
        self.assertIn("done/failed 7", counts)
        self.assertIn("archived 12", counts)


class TestRelayPostNonzeroExit(unittest.IsolatedAsyncioTestCase):
    """Focused test: /relay post when relay CLI returns a nonzero exit code."""

    def setUp(self):
        self.bot = bot_listener.AgentBot("relay-coordinator", 1491110247299944641, {})

    async def test_relay_post_cli_error_returns_error_embed_with_relay_text(self):
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        relay_error_msg = "Error: database connection refused on port 5432"
        relay_mock = mock.AsyncMock(return_value=(relay_error_msg, 1))

        with mock.patch.object(bot_listener, "relay", new=relay_mock):
            command = load_command(self.bot, "post")
            await command.callback(
                interaction,
                title="Deploy hotfix",
                body="Roll out the hotfix to prod",
                to="manuslocal",
                session="sprint-11",
            )

        # relay CLI was called
        relay_mock.assert_awaited_once()

        # The handler should return an error embed
        embed = interaction.followup.send.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "/relay post failed")

        # The Detail field must contain the relay CLI error text
        detail_field = next(f for f in embed.fields if f.name == "Detail")
        self.assertIn("database connection refused on port 5432", detail_field.value)


class TestRelayStatusAgentKeyPayload(unittest.IsolatedAsyncioTestCase):
    """/relay status must render real agent names when /health/agents uses
    ``"agent"`` keys (the real payload shape) instead of ``"name"`` keys.

    The production /health/agents endpoint returns rows like::

        {"agent": "manuslocal", "status": "online", "current_task_id": 42}

    ``summarize_agent_rows`` should resolve the agent identity from the
    ``"agent"`` key so that the Agent Detail embed field shows actual names
    rather than "unknown".
    """

    def setUp(self):
        self.bot = bot_listener.AgentBot("relay-coordinator", 1491110247299944641, {})

    async def test_agent_detail_renders_names_from_agent_key(self):
        """Agent Detail must show real names when rows use 'agent' key."""
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        # Mimic the *real* /health/agents payload shape — note "agent", not "name"
        health_agents_payload = {
            "summary": {"online": 3, "stale": 0, "offline": 0},
            "agents": [
                {"agent": "relay-dispatch", "status": "online", "current_task_id": 1},
                {"agent": "manuslocal", "status": "online", "current_task_id": 42},
                {"agent": "claudecli", "status": "online", "current_task_id": 7},
            ],
        }

        with (
            mock.patch.object(
                self.bot,
                "_fetch_json",
                side_effect=[
                    # /health
                    {"status": "healthy", "checks": [{"name": "litellm", "status": "ok"}]},
                    # /health/agents — real shape with "agent" keys
                    health_agents_payload,
                    # /metrics
                    {"tasks": {"by_status": {"pending": 2, "in_progress": 1}}},
                ],
            ),
            mock.patch.object(
                bot_listener,
                "bash",
                new=mock.AsyncMock(return_value=("Daemon running (PID 1, uptime 05:00)", 0)),
            ),
        ):
            command = load_command(self.bot, "status")
            await command.callback(interaction)

        embed = interaction.followup.send.await_args.kwargs["embed"]
        fields = {f.name: f.value for f in embed.fields}

        # Agent Detail field must exist
        self.assertIn("Agent Detail", fields)
        detail = fields["Agent Detail"]

        # Each agent name must appear — NOT "unknown"
        self.assertIn("relay-dispatch", detail)
        self.assertIn("manuslocal", detail)
        self.assertIn("claudecli", detail)
        self.assertNotIn("unknown", detail)

        # Each agent should have its status rendered
        self.assertIn("relay-dispatch: online", detail)
        self.assertIn("manuslocal: online", detail)
        self.assertIn("claudecli: online", detail)

        # current_task_id should be reflected
        self.assertIn("task 42", detail)
        self.assertIn("task 7", detail)


class TestRelayStatusDegradedUnavailable(unittest.IsolatedAsyncioTestCase):
    """Regression: /relay status returns a useful degraded embed when one or
    more health endpoints are unavailable (return None from _fetch_json)."""

    def setUp(self):
        self.bot = bot_listener.AgentBot("relay-coordinator", 1491110247299944641, {})

    async def test_all_endpoints_unavailable_returns_degraded_embed(self):
        """When every _fetch_json call returns None the embed must still render
        with all expected fields and an 'unavailable' description."""
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        with (
            mock.patch.object(
                self.bot,
                "_fetch_json",
                side_effect=[None, None, None],  # health, agents, metrics all down
            ),
            mock.patch.object(
                bot_listener,
                "bash",
                new=mock.AsyncMock(return_value=("", 1)),  # dispatch also fails
            ),
        ):
            command = load_command(self.bot, "status")
            await command.callback(interaction)

        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "Relay status")
        self.assertEqual(embed.footer.text, "slash command: /relay status")

        fields = {f.name: f.value for f in embed.fields}

        # All standard fields must still be present
        self.assertIn("Agents", fields)
        self.assertIn("Tasks", fields)
        self.assertIn("Dispatch", fields)
        self.assertIn("LiteLLM", fields)
        self.assertIn("Overall", fields)

        # Values should indicate unavailability
        self.assertEqual(fields["Agents"], "unavailable")
        self.assertEqual(fields["Tasks"], "unavailable")
        self.assertEqual(fields["LiteLLM"], "unavailable")

        # Overall should not claim healthy
        self.assertNotEqual(fields["Overall"], "healthy")

        # Description should list unavailable sources
        self.assertIn("Unavailable", embed.description)
        self.assertIn("health", embed.description)
        self.assertIn("agents", embed.description)
        self.assertIn("metrics", embed.description)

    async def test_partial_unavailability_still_shows_available_data(self):
        """When only the metrics endpoint is down, agents data should still
        render normally while tasks shows 'unavailable'."""
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        with (
            mock.patch.object(
                self.bot,
                "_fetch_json",
                side_effect=[
                    {"status": "healthy", "checks": [{"name": "litellm", "status": "ok"}]},
                    {
                        "summary": {"online": 2, "stale": 1, "offline": 0},
                        "agents": [
                            {"name": "relay-dispatch", "status": "online"},
                        ],
                    },
                    None,  # metrics endpoint unavailable
                ],
            ),
            mock.patch.object(
                bot_listener,
                "bash",
                new=mock.AsyncMock(return_value=("Daemon running (PID 1, uptime 01:23)", 0)),
            ),
        ):
            command = load_command(self.bot, "status")
            await command.callback(interaction)

        embed = interaction.followup.send.await_args.kwargs["embed"]
        fields = {f.name: f.value for f in embed.fields}

        # Agents data should render normally
        self.assertIn("online 2", fields["Agents"])
        self.assertIn("stale 1", fields["Agents"])

        # Tasks should show unavailable
        self.assertEqual(fields["Tasks"], "unavailable")

        # LiteLLM healthy since /health was ok
        self.assertEqual(fields["LiteLLM"], "healthy")

        # Overall should be degraded (was healthy but metrics is down)
        self.assertEqual(fields["Overall"], "degraded")

        # Description should mention metrics
        self.assertIn("metrics", embed.description)

    async def test_agents_endpoint_down_omits_agent_detail(self):
        """When /health/agents is down, Agent Detail field should not appear
        but other fields still render."""
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        with (
            mock.patch.object(
                self.bot,
                "_fetch_json",
                side_effect=[
                    {"status": "healthy", "checks": [{"name": "litellm", "status": "ok"}]},
                    None,  # agents endpoint unavailable
                    {"tasks": {"by_status": {"pending": 3, "in_progress": 1}}},
                ],
            ),
            mock.patch.object(
                bot_listener,
                "bash",
                new=mock.AsyncMock(return_value=("Daemon running (PID 1, uptime 00:45)", 0)),
            ),
        ):
            command = load_command(self.bot, "status")
            await command.callback(interaction)

        embed = interaction.followup.send.await_args.kwargs["embed"]
        fields = {f.name: f.value for f in embed.fields}

        # Agents field should show unavailable
        self.assertEqual(fields["Agents"], "unavailable")

        # Agent Detail should NOT appear (no agent rows)
        self.assertNotIn("Agent Detail", fields)

        # Tasks should still work
        self.assertEqual(fields["Tasks"], "active 4")

        # Overall degraded because agents endpoint is down
        self.assertEqual(fields["Overall"], "degraded")


class TestRelayBoardCLIFailure(unittest.IsolatedAsyncioTestCase):
    """Focused test: /relay board returns an error embed when the relay CLI fails."""

    def setUp(self):
        self.bot = bot_listener.AgentBot("relay-coordinator", 1491110247299944641, {})

    async def test_board_cli_nonzero_exit_returns_error_embed(self):
        """When `relay board --json` exits non-zero the slash handler should
        return an error embed whose Detail field contains the relay failure
        text, instead of timing out or rendering a broken embed."""
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        error_text = "Error: board.json not found at /tmp/relay/board.json"
        relay_mock = mock.AsyncMock(return_value=(error_text, 1))

        with mock.patch.object(bot_listener, "relay", new=relay_mock):
            command = load_command(self.bot, "board")
            await command.callback(interaction, all_=False)

        # Should have deferred and then followed up (no timeout)
        interaction.response.defer.assert_awaited_once_with(thinking=True, ephemeral=True)
        interaction.followup.send.assert_awaited_once()

        embed = interaction.followup.send.await_args.kwargs["embed"]

        # Title must indicate failure
        self.assertEqual(embed.title, "/relay board failed")

        # The Detail field must contain the relay CLI error text
        fields = {f.name: f.value for f in embed.fields}
        self.assertIn("Detail", fields)
        self.assertIn(error_text, fields["Detail"])

    async def test_board_cli_nonzero_exit_with_empty_stderr(self):
        """When relay CLI fails with empty output, the error embed should
        still render with a fallback detail message."""
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        relay_mock = mock.AsyncMock(return_value=("", 1))

        with mock.patch.object(bot_listener, "relay", new=relay_mock):
            command = load_command(self.bot, "board")
            await command.callback(interaction, all_=False)

        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "/relay board failed")

        fields = {f.name: f.value for f in embed.fields}
        self.assertIn("Detail", fields)
        # Should have some fallback text, not empty
        self.assertTrue(len(fields["Detail"]) > 0)

    async def test_board_invalid_json_returns_error_embed(self):
        """When relay CLI returns success but invalid JSON, the handler
        should catch the parse error and return an error embed."""
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        relay_mock = mock.AsyncMock(return_value=("not valid json {{{", 0))

        with mock.patch.object(bot_listener, "relay", new=relay_mock):
            command = load_command(self.bot, "board")
            await command.callback(interaction, all_=False)

        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "/relay board failed")

        fields = {f.name: f.value for f in embed.fields}
        self.assertIn("Detail", fields)
