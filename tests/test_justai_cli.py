import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import justai_runtime

from tools import justai_cli


class JustAiCliTests(unittest.TestCase):
    def test_runtime_env_populates_current_control_plane_settings(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {"SENTINEL": "kept"}, clear=True),
        ):
            root = Path(tmp)
            with mock.patch.object(justai_runtime, "repo_root", return_value=root):
                env = justai_cli.runtime_env()

        self.assertEqual(env["JUSTAI_ROOT"], str(root))
        self.assertEqual(env["JUSTAI_RUNTIME_ROOT"], "/tmp/justai")
        self.assertEqual(env["JUSTAI_SAFE_MINI_MODE"], "stub")
        self.assertEqual(env["SENTINEL"], "kept")

    def test_run_passes_computed_env_to_subprocess_call(self):
        env = {"JUSTAI_ROOT": "/tmp/justai-root"}
        with (
            mock.patch.object(justai_cli, "runtime_env", return_value=env),
            mock.patch.object(justai_cli.subprocess, "call", return_value=17) as call_mock,
        ):
            rc = justai_cli.run(["bash", "/tmp/script.sh"])

        self.assertEqual(rc, 17)
        call_mock.assert_called_once_with(["bash", "/tmp/script.sh"], env=env)

    def test_root_command_dispatches_to_expected_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            calls: list[list[str]] = []

            def fake_run(cmd: list[str]) -> int:
                calls.append(cmd)
                return 0

            with (
                mock.patch.object(justai_cli, "repo_root", return_value=root),
                mock.patch.object(justai_cli, "run", side_effect=fake_run),
            ):
                self.assertEqual(justai_cli.start_cmd(SimpleNamespace()), 0)
                self.assertEqual(justai_cli.status_cmd(SimpleNamespace(mode="status")), 0)
                self.assertEqual(justai_cli.health_cmd(SimpleNamespace(mode="health")), 0)
                self.assertEqual(justai_cli.check_cmd(SimpleNamespace(mode="all")), 0)

        self.assertEqual(
            calls,
            [
                ["bash", str(root / "scripts" / "start_justai.sh")],
                ["bash", str(root / "scripts" / "check_justai.sh"), "--status-only"],
                ["bash", str(root / "scripts" / "check_justai.sh"), "--health-only"],
                ["bash", str(root / "scripts" / "check_justai.sh")],
            ],
        )

    def test_parser_exposes_current_commands(self):
        parser = justai_cli.build_parser()
        args = parser.parse_args(["run", "ship it", "--session-ref", "test-session"])
        self.assertEqual(args.goal, "ship it")
        self.assertEqual(args.session_ref, "test-session")


if __name__ == "__main__":
    unittest.main()
