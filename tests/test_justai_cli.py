import os
import tempfile
import unittest
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import justai_cli


class JustAiCliTests(unittest.TestCase):
    def test_repo_root_defaults_to_workspace(self):
        root = justai_cli.repo_root()
        self.assertTrue(str(root).endswith("/JustAi"))

    def test_base_env_contains_justai_paths(self):
        env = justai_cli.base_env()
        self.assertEqual(env["JUSTAI_ROOT"], str(justai_cli.repo_root()))
        self.assertIn("JUSTAI_LOCALMANUS_ROOT", env)
        self.assertIn("JUSTAI_RELAY_ROOT", env)

    def test_task_command_invokes_localmanus_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "LocalManus" / "tools").mkdir(parents=True)
            ml_cli = root / "LocalManus" / "tools" / "ml_cli.py"
            ml_cli.write_text("print('ok')\n")
            with mock.patch.object(justai_cli, "repo_root", return_value=root), \
                 mock.patch.object(justai_cli, "localmanus_root", return_value=root / "LocalManus"), \
                 mock.patch.object(justai_cli, "run", return_value=0) as run_mock:
                code = justai_cli.task_cmd(mock.Mock(description="hello"))
                self.assertEqual(code, 0)
                run_mock.assert_called_once()

    def test_relay_command_uses_relay_controller(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            relay = root / "relay-room" / "scripts"
            relay.mkdir(parents=True)
            (relay / "daemon_ctl.sh").write_text("#!/usr/bin/env bash\n")
            with mock.patch.object(justai_cli, "repo_root", return_value=root), \
                 mock.patch.object(justai_cli, "relay_root", return_value=root / "relay-room"), \
                 mock.patch.object(justai_cli, "run", return_value=0) as run_mock:
                code = justai_cli.relay_cmd(mock.Mock(action="status"))
                self.assertEqual(code, 0)
                run_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
