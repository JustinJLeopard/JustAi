import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import justai_runtime

from tools import justai_cli


class JustAiCliTests(unittest.TestCase):
    def test_runtime_env_populates_root_aliases_and_preserves_existing_runtime_settings(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(
                os.environ,
                {
                    "JUSTAI_RELAY_SERVER": "custom-server",
                    "JUSTAI_SPACETIME_SESSION": "custom-session",
                    "SENTINEL": "kept",
                },
                clear=True,
            ),
        ):
            root = Path(tmp)
            with (
                mock.patch.object(justai_runtime, "repo_root", return_value=root),
                mock.patch.object(
                    justai_runtime, "localmanus_root", return_value=root / "LocalManus"
                ),
                mock.patch.object(justai_runtime, "relay_root", return_value=root / "relay-room"),
            ):
                env = justai_cli.runtime_env()

        self.assertEqual(env["JUSTAI_ROOT"], str(root))
        self.assertEqual(env["JUSTAI_LOCALMANUS_ROOT"], str(root / "LocalManus"))
        self.assertEqual(env["JUSTAI_RELAY_ROOT"], str(root / "relay-room"))
        self.assertEqual(env["LOCALMANUS_ROOT"], str(root / "LocalManus"))
        self.assertEqual(env["RELAY_ROOT"], str(root / "relay-room"))
        self.assertEqual(env["JUSTAI_RELAY_SERVER"], "custom-server")
        self.assertEqual(env["JUSTAI_SPACETIME_SESSION"], "custom-session")
        self.assertEqual(env["SENTINEL"], "kept")

    def test_run_passes_computed_env_to_subprocess_call(self):
        env = {"JUSTAI_ROOT": "/tmp/justai-root", "LOCALMANUS_ROOT": "/tmp/localmanus"}
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
                self.assertEqual(
                    justai_cli.start_cmd(
                        SimpleNamespace(
                            no_bots=True,
                            no_codex=True,
                            force_bootstrap=True,
                            skip_relay_bootstrap=True,
                        )
                    ),
                    0,
                )
                self.assertEqual(justai_cli.status_cmd(SimpleNamespace(mode="status")), 0)
                self.assertEqual(justai_cli.health_cmd(SimpleNamespace(mode="health")), 0)
                self.assertEqual(justai_cli.check_cmd(SimpleNamespace(mode="all")), 0)

        self.assertEqual(
            calls,
            [
                [
                    "bash",
                    str(root / "scripts" / "start_justai.sh"),
                    "--no-bots",
                    "--no-codex",
                    "--force-bootstrap",
                    "--skip-relay-bootstrap",
                ],
                ["bash", str(root / "scripts" / "check_justai.sh"), "--status-only"],
                ["bash", str(root / "scripts" / "check_justai.sh"), "--health-only"],
                ["bash", str(root / "scripts" / "check_justai.sh")],
            ],
        )

    def test_task_and_mini_dispatch_to_localmanus_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ml = root / "LocalManus" / "tools" / "ml_cli.py"
            ml.parent.mkdir(parents=True)
            ml.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            ml.chmod(0o755)
            calls: list[list[str]] = []

            def fake_run(cmd: list[str]) -> int:
                calls.append(cmd)
                return 0

            with (
                mock.patch.object(justai_cli, "repo_root", return_value=root),
                mock.patch.object(justai_cli, "localmanus_root", return_value=root / "LocalManus"),
                mock.patch.object(justai_cli, "run", side_effect=fake_run),
            ):
                self.assertEqual(justai_cli.task_cmd(SimpleNamespace(description="ship this")), 0)
                self.assertEqual(
                    justai_cli.mini_cmd(SimpleNamespace(description="summarize it")), 0
                )

        self.assertEqual(
            calls,
            [
                ["python3", str(ml), "task", "ship this"],
                ["python3", str(ml), "mini", "summarize it"],
            ],
        )

    def test_task_cmd_reports_missing_localmanus_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (
                mock.patch.object(justai_cli, "repo_root", return_value=root),
                mock.patch.object(justai_cli, "localmanus_root", return_value=root / "LocalManus"),
            ):
                err = io.StringIO()
                with redirect_stderr(err):
                    rc = justai_cli.task_cmd(SimpleNamespace(description="anything"))

        self.assertEqual(rc, 1)
        self.assertIn("missing LocalManus CLI", err.getvalue())
        self.assertIn(str(root / "LocalManus" / "tools" / "ml_cli.py"), err.getvalue())

    def test_relay_dispatch_uses_controller_and_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            relay = root / "relay-room"
            controller = relay / "scripts" / "daemon_ctl.sh"
            controller.parent.mkdir(parents=True)
            controller.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            controller.chmod(0o755)
            calls: list[list[str]] = []

            def fake_run(cmd: list[str]) -> int:
                calls.append(cmd)
                return 0

            with (
                mock.patch.object(justai_cli, "repo_root", return_value=root),
                mock.patch.object(justai_cli, "relay_root", return_value=relay),
                mock.patch.object(justai_cli, "run", side_effect=fake_run),
            ):
                self.assertEqual(justai_cli.relay_cmd(SimpleNamespace(action="restart")), 0)

            missing_relay = root / "missing-relay"
            with mock.patch.object(justai_cli, "relay_root", return_value=missing_relay):
                err = io.StringIO()
                with redirect_stderr(err):
                    rc = justai_cli.relay_cmd(SimpleNamespace(action="status"))

        self.assertEqual(calls, [["bash", str(controller), "restart"]])
        self.assertEqual(rc, 1)
        self.assertIn("missing relay daemon controller", err.getvalue())
        self.assertIn(str(missing_relay / "scripts" / "daemon_ctl.sh"), err.getvalue())


if __name__ == "__main__":
    unittest.main()
