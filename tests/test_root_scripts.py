import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = ROOT / "scripts" / "start_justai.sh"
CHECK_SCRIPT = ROOT / "scripts" / "check_justai.sh"


class RootScriptTests(unittest.TestCase):
    def _make_workspace(self, tmp: str) -> tuple[Path, Path]:
        root = Path(tmp)
        localmanus = root / "LocalManus" / "scripts"
        relay = root / "relay-room" / "scripts"
        localmanus.mkdir(parents=True)
        relay.mkdir(parents=True)
        (root / "bin").mkdir(parents=True)

        return root, root / "bin"

    def _write_fake_commands(self, bindir: Path) -> None:
        tmux = bindir / "tmux"
        tmux.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "logfile=\"${JUSTAI_TEST_LOG:?}\"\n"
            "printf 'tmux %s\\n' \"$*\" >> \"$logfile\"\n"
            "if [[ \"$1\" == \"new-session\" ]]; then\n"
            "  touch \"${JUSTAI_TEST_SPACETIME_READY:?}\"\n"
            "fi\n"
            "if [[ \"$1\" == \"has-session\" ]]; then\n"
            "  exit 1\n"
            "fi\n",
            encoding="utf-8",
        )
        tmux.chmod(0o755)

        timeout_cmd = bindir / "timeout"
        timeout_cmd.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "if [[ -f \"${JUSTAI_TEST_SPACETIME_READY:-}\" ]]; then\n"
            "  exit 0\n"
            "fi\n"
            "exit 1\n",
            encoding="utf-8",
        )
        timeout_cmd.chmod(0o755)

        python_cmd = bindir / "python3"
        python_cmd.write_text(
            "#!/usr/bin/env bash\n"
            "exec /usr/bin/python3 \"$@\"\n",
            encoding="utf-8",
        )
        python_cmd.chmod(0o755)

        curl_cmd = bindir / "curl"
        curl_cmd.write_text(
            "#!/usr/bin/env bash\n"
            "exit 1\n",
            encoding="utf-8",
        )
        curl_cmd.chmod(0o755)

    def test_start_script_delegates_with_justai_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, bindir = self._make_workspace(tmp)
            self._write_fake_commands(bindir)
            log = root / "calls.log"

            (root / "LocalManus" / "scripts" / "start_manuslocal.sh").write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "printf 'start_localmanus root=%s local=%s relay=%s args=%s\\n' "
                "\"${JUSTAI_ROOT:-}\" \"${JUSTAI_LOCALMANUS_ROOT:-}\" \"${JUSTAI_RELAY_ROOT:-}\" \"$*\" "
                ">> \"${JUSTAI_TEST_LOG:?}\"\n",
                encoding="utf-8",
            )
            (root / "LocalManus" / "scripts" / "start_manuslocal.sh").chmod(0o755)

            (root / "relay-room" / "scripts" / "start_relay_room.sh").write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "printf 'bootstrap_relay cwd=%s root=%s relay=%s\\n' \"$PWD\" \"${JUSTAI_ROOT:-}\" \"${JUSTAI_RELAY_ROOT:-}\" "
                ">> \"${JUSTAI_TEST_LOG:?}\"\n",
                encoding="utf-8",
            )
            (root / "relay-room" / "scripts" / "start_relay_room.sh").chmod(0o755)

            (root / "relay-room" / "scripts" / "daemon_ctl.sh").write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "printf 'daemon_ctl cwd=%s args=%s local=%s relay=%s\\n' \"$PWD\" \"$*\" "
                "\"${LOCALMANUS_ROOT:-}\" \"${RELAY_ROOT:-}\" >> \"${JUSTAI_TEST_LOG:?}\"\n",
                encoding="utf-8",
            )
            (root / "relay-room" / "scripts" / "daemon_ctl.sh").chmod(0o755)

            env = os.environ.copy()
            env["JUSTAI_ROOT"] = str(root)
            env["JUSTAI_LOCALMANUS_ROOT"] = str(root / "LocalManus")
            env["JUSTAI_RELAY_ROOT"] = str(root / "relay-room")
            env["JUSTAI_TEST_LOG"] = str(log)
            env["JUSTAI_TEST_SPACETIME_READY"] = str(root / ".spacetime-ready")
            env["JUSTAI_PATH"] = f"{bindir}:{env.get('PATH', '')}"

            subprocess.run(["bash", str(START_SCRIPT)], check=True, env=env, cwd=root)

            data = log.read_text(encoding="utf-8")
            self.assertIn("tmux new-session -d -s spacetime spacetime start", data)
            self.assertIn(f"start_localmanus root={root}", data)
            self.assertIn(f"local={root / 'LocalManus'}", data)
            self.assertIn(f"relay={root / 'relay-room'}", data)
            self.assertIn(f"bootstrap_relay cwd={root / 'relay-room'}", data)
            self.assertIn("daemon_ctl cwd=", data)
            self.assertIn("args=restart --with-bots --with-codex", data)

    def test_check_script_runs_status_and_health_from_root_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, bindir = self._make_workspace(tmp)
            self._write_fake_commands(bindir)
            log = root / "calls.log"

            (root / "LocalManus" / "tools").mkdir(parents=True)
            (root / "LocalManus" / "tools" / "ml_cli.py").write_text(
                "#!/usr/bin/env python3\n"
                "import os\n"
                "from pathlib import Path\n"
                "log = Path(os.environ['JUSTAI_TEST_LOG'])\n"
                "with log.open('a', encoding='utf-8') as f:\n"
                "    f.write(f\"ml_cli argv={' '.join(__import__('sys').argv[1:])} root={os.environ.get('JUSTAI_ROOT','')}\\n\")\n",
                encoding="utf-8",
            )
            (root / "LocalManus" / "tools" / "ml_cli.py").chmod(0o755)

            (root / "relay-room" / "scripts" / "daemon_ctl.sh").write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "printf 'daemon_ctl cwd=%s args=%s local=%s relay=%s\\n' \"$PWD\" \"$*\" "
                "\"${LOCALMANUS_ROOT:-}\" \"${RELAY_ROOT:-}\" >> \"${JUSTAI_TEST_LOG:?}\"\n",
                encoding="utf-8",
            )
            (root / "relay-room" / "scripts" / "daemon_ctl.sh").chmod(0o755)

            env = os.environ.copy()
            env["JUSTAI_ROOT"] = str(root)
            env["JUSTAI_LOCALMANUS_ROOT"] = str(root / "LocalManus")
            env["JUSTAI_RELAY_ROOT"] = str(root / "relay-room")
            env["JUSTAI_TEST_LOG"] = str(log)
            env["JUSTAI_TEST_SPACETIME_READY"] = str(root / ".spacetime-ready")
            env["JUSTAI_PATH"] = f"{bindir}:{env.get('PATH', '')}"

            subprocess.run(["bash", str(CHECK_SCRIPT)], check=True, env=env, cwd=root)

            data = log.read_text(encoding="utf-8")
            self.assertIn("ml_cli argv=status", data)
            self.assertIn(f"root={root}", data)
            self.assertIn(f"daemon_ctl cwd={root / 'relay-room'} args=status --with-bots --with-codex", data)
            self.assertIn(f"local={root / 'LocalManus'}", data)
            self.assertIn(f"relay={root / 'relay-room'}", data)
            self.assertIn(f"daemon_ctl cwd={root / 'relay-room'} args=health", data)


if __name__ == "__main__":
    unittest.main()
