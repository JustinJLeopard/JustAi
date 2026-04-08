import importlib.util
import pathlib
import tempfile
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "relay_web.py"
SPEC = importlib.util.spec_from_file_location("relay_web", MODULE_PATH)
relay_web = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(relay_web)


SAMPLE_BOARD = """Agents
name            | status   | current_task_id | capabilities     | last_seen
-----------------+----------+-----------------+------------------+--------------
 "codex"         | "online" | 0               | "execution"      | 1775377285779
 "localmanus"    | "online" | 0               | "delegation"     | 1775377285804
WARNING: This command is UNSTABLE and subject to breaking changes.

Tasks
id | task_uuid | from_agent | to_agent | claimed_by | title         | payload       | status    | priority | session_ref | created_at    | updated_at    | claimed_at | completed_at | result
----+-----------+------------+----------+------------+---------------+---------------+-----------+----------+-------------+---------------+---------------+------------+--------------+-------
 2  | "uuid-2"  | "codex"    | "local"  | "codex"    | "Implement"   | "payload"     | "done"    | 7        | "demo"      | 1775377661492 | 1775378118354 | 0          | 0            | "ok"

Events
id | event_type | agent | task_ref | detail | timestamp
"""


class RelayWebTests(unittest.TestCase):
    def test_parse_board_extracts_agents_and_tasks(self):
        (agent_headers, agent_rows), (task_headers, task_rows) = relay_web.parse_board(SAMPLE_BOARD)
        self.assertEqual(agent_headers[:3], ["name", "status", "current_task_id"])
        self.assertEqual(agent_rows[0][0], "codex")
        self.assertEqual(task_headers[:5], ["id", "task_uuid", "from_agent", "to_agent", "claimed_by"])
        self.assertEqual(task_rows[0][0], "2")
        self.assertEqual(task_rows[0][5], "Implement")

    def test_render_page_contains_filtered_tables(self):
        page = relay_web.render_page(SAMPLE_BOARD)
        self.assertIn("<h1>Relay Room</h1>", page)
        self.assertIn("<th>title</th>", page)
        self.assertIn("<td>Implement</td>", page)
        self.assertIn("<th>last_seen</th>", page)
        self.assertIn("Auto-refreshing every", page)

    def test_render_table_handles_empty_headers(self):
        html = relay_web.render_table("Tasks", [], [], ["id"])
        self.assertIn("No data available", html)

    def test_load_board_text_reads_target_file_when_env_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            (root / ".relay-db-target").write_text("relay-room-test\n", encoding="utf-8")
            completed = mock.Mock(returncode=0, stdout="Agents\n", stderr="")
            with mock.patch.object(relay_web, "ROOT", root):
                with mock.patch.object(relay_web.subprocess, "run", return_value=completed) as run_mock:
                    text = relay_web.load_board_text()
        self.assertEqual(text, "Agents")
        self.assertEqual(run_mock.call_args.kwargs["env"]["RELAY_DB_NAME"], "relay-room-test")

    def test_load_board_text_raises_on_subprocess_failure(self):
        failed = mock.Mock(returncode=1, stdout="", stderr="bad relay state")
        with mock.patch.object(relay_web.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "bad relay state"):
                relay_web.load_board_text()


if __name__ == "__main__":
    unittest.main()
