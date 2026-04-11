import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = ROOT / "scripts" / "start_justai.sh"
CHECK_SCRIPT = ROOT / "scripts" / "check_justai.sh"


class RootScriptTests(unittest.TestCase):
    def _workspace(self, tmp: str) -> tuple[Path, Path]:
        root = Path(tmp)
        (root / "LocalManus" / "scripts").mkdir(parents=True)
        (root / "LocalManus" / "tools").mkdir(parents=True)
        (root / "relay-room" / "scripts").mkdir(parents=True)
        bindir = root / "bin"
        bindir.mkdir()
        return root, bindir

    def _write_executable(self, path: Path, content: str) -> None:
        path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
        path.chmod(0o755)

    def _write_startup_fakes(self, root: Path, bindir: Path, log: Path) -> None:
        self._write_executable(
            bindir / "tmux",
            f"""
            #!/usr/bin/env bash
            set -euo pipefail
            printf 'tmux %s\\n' "$*" >> "{log}"
            case "${{1:-}}" in
              has-session)
                if [[ "${{JUSTAI_TEST_TMUX_SESSION_PRESENT:-0}}" == "1" ]]; then
                  exit 0
                fi
                exit 1
                ;;
              new-session)
                touch "${{JUSTAI_TEST_SPACETIME_READY:?}}"
                ;;
              kill-session)
                ;;
            esac
            exit 0
            """,
        )
        self._write_executable(
            bindir / "timeout",
            f"""
            #!/usr/bin/env bash
            set -euo pipefail
            printf 'timeout %s\\n' "$*" >> "{log}"
            if [[ "${{JUSTAI_TEST_PORT_OPEN:-0}}" == "1" ]]; then
              exit 0
            fi
            if [[ -n "${{JUSTAI_TEST_SPACETIME_READY:-}}" && -f "${{JUSTAI_TEST_SPACETIME_READY}}" ]]; then
              exit 0
            fi
            exit 1
            """,
        )
        self._write_executable(
            root / "LocalManus" / "scripts" / "start_manuslocal.sh",
            f"""
            #!/usr/bin/env bash
            set -euo pipefail
            printf 'start_manuslocal cwd=%s args=%s root=%s local=%s relay=%s pid=%s log=%s server=%s session=%s\\n' \
              "$PWD" "$*" \
              "${{JUSTAI_ROOT:-}}" "${{JUSTAI_LOCALMANUS_ROOT:-}}" "${{JUSTAI_RELAY_ROOT:-}}" \
              "${{PID_FILE:-}}" "${{LOG_FILE:-}}" \
              "${{JUSTAI_RELAY_SERVER:-}}" "${{JUSTAI_SPACETIME_SESSION:-}}" >> "{log}"
            """,
        )
        self._write_executable(
            root / "relay-room" / "scripts" / "start_relay_room.sh",
            f"""
            #!/usr/bin/env bash
            set -euo pipefail
            printf 'start_relay_room cwd=%s args=%s root=%s local=%s relay=%s pid=%s log=%s server=%s session=%s\\n' \
              "$PWD" "$*" \
              "${{JUSTAI_ROOT:-}}" "${{JUSTAI_LOCALMANUS_ROOT:-}}" "${{JUSTAI_RELAY_ROOT:-}}" \
              "${{PID_FILE:-}}" "${{LOG_FILE:-}}" \
              "${{JUSTAI_RELAY_SERVER:-}}" "${{JUSTAI_SPACETIME_SESSION:-}}" >> "{log}"
            """,
        )
        self._write_executable(
            root / "relay-room" / "scripts" / "daemon_ctl.sh",
            f"""
            #!/usr/bin/env bash
            set -euo pipefail
            printf 'daemon_ctl cwd=%s args=%s root=%s local=%s relay=%s pid=%s log=%s server=%s session=%s\\n' \
              "$PWD" "$*" \
              "${{JUSTAI_ROOT:-}}" "${{JUSTAI_LOCALMANUS_ROOT:-}}" "${{JUSTAI_RELAY_ROOT:-}}" \
              "${{PID_FILE:-}}" "${{LOG_FILE:-}}" \
              "${{JUSTAI_RELAY_SERVER:-}}" "${{JUSTAI_SPACETIME_SESSION:-}}" >> "{log}"
            """,
        )

    def _write_health_fakes(self, root: Path, bindir: Path, log: Path) -> None:
        self._write_executable(
            bindir / "python3",
            f"""
            #!/usr/bin/env bash
            set -euo pipefail
            printf 'python3 %s\\n' "$*" >> "{log}"
            exec /usr/bin/python3 "$@"
            """,
        )
        self._write_executable(
            root / "LocalManus" / "tools" / "ml_cli.py",
            """
            #!/usr/bin/env python3
            import os
            import sys
            from pathlib import Path

            log = Path(os.environ["JUSTAI_TEST_LOG"])
            with log.open("a", encoding="utf-8") as fh:
                fh.write(
                    "ml_cli argv={argv} root={root} local={local} relay={relay} pid={pid} log={log}\\n".format(
                        argv=" ".join(sys.argv[1:]),
                        root=os.environ.get("JUSTAI_ROOT", ""),
                        local=os.environ.get("JUSTAI_LOCALMANUS_ROOT", ""),
                        relay=os.environ.get("JUSTAI_RELAY_ROOT", ""),
                        pid=os.environ.get("PID_FILE", ""),
                        log=os.environ.get("LOG_FILE", ""),
                    )
                )
            raise SystemExit(int(os.environ.get("JUSTAI_TEST_ML_EXIT", "23")))
            """,
        )
        self._write_executable(
            root / "relay-room" / "scripts" / "daemon_ctl.sh",
            f"""
            #!/usr/bin/env bash
            set -euo pipefail
            printf 'daemon_ctl cwd=%s args=%s root=%s local=%s relay=%s pid=%s log=%s server=%s session=%s\\n' \
              "$PWD" "$*" \
              "${{JUSTAI_ROOT:-}}" "${{JUSTAI_LOCALMANUS_ROOT:-}}" "${{JUSTAI_RELAY_ROOT:-}}" \
              "${{PID_FILE:-}}" "${{LOG_FILE:-}}" \
              "${{JUSTAI_RELAY_SERVER:-}}" "${{JUSTAI_SPACETIME_SESSION:-}}" >> "{log}"
            exit "${{JUSTAI_TEST_DAEMON_EXIT:-42}}"
            """,
        )

    def test_start_script_initializes_spacetime_then_bootstraps_relay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, bindir = self._workspace(tmp)
            log = root / "calls.log"
            self._write_startup_fakes(root, bindir, log)

            env = os.environ.copy()
            env.update(
                {
                    "JUSTAI_ROOT": str(root),
                    "JUSTAI_LOCALMANUS_ROOT": str(root / "LocalManus"),
                    "JUSTAI_RELAY_ROOT": str(root / "relay-room"),
                    "JUSTAI_RELAY_SERVER": "local-server",
                    "JUSTAI_SPACETIME_SESSION": "spacetime-root",
                    "JUSTAI_PATH": f"{bindir}:{env.get('PATH', '')}",
                    "JUSTAI_TEST_LOG": str(log),
                    "JUSTAI_TEST_SPACETIME_READY": str(root / ".spacetime-ready"),
                    "PID_FILE": "/tmp/justai.pid",
                    "LOG_FILE": "/tmp/justai.log",
                }
            )

            subprocess.run(["bash", str(START_SCRIPT)], cwd=root, env=env, check=True, text=True)

            data = log.read_text(encoding="utf-8")
            self.assertIn("tmux has-session -t spacetime-root", data)
            self.assertIn("tmux new-session -d -s spacetime-root spacetime start", data)
            self.assertIn("start_manuslocal cwd=", data)
            self.assertIn("args=--background", data)
            self.assertIn("start_relay_room cwd=", data)
            self.assertIn("daemon_ctl cwd=", data)
            self.assertIn("args=restart --with-bots --with-codex", data)
            self.assertIn("pid=/tmp/justai.pid", data)
            self.assertIn("log=/tmp/justai.log", data)
            self.assertLess(data.index("tmux new-session -d -s spacetime-root spacetime start"), data.index("start_manuslocal cwd="))
            self.assertLess(data.index("start_manuslocal cwd="), data.index("start_relay_room cwd="))
            self.assertLess(data.index("start_relay_room cwd="), data.index("daemon_ctl cwd="))

    def test_start_script_skips_tmux_when_spacetime_port_is_already_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, bindir = self._workspace(tmp)
            log = root / "calls.log"
            self._write_startup_fakes(root, bindir, log)

            env = os.environ.copy()
            env.update(
                {
                    "JUSTAI_ROOT": str(root),
                    "JUSTAI_LOCALMANUS_ROOT": str(root / "LocalManus"),
                    "JUSTAI_RELAY_ROOT": str(root / "relay-room"),
                    "JUSTAI_RELAY_SERVER": "local-server",
                    "JUSTAI_SPACETIME_SESSION": "already-up",
                    "JUSTAI_PATH": f"{bindir}:{env.get('PATH', '')}",
                    "JUSTAI_TEST_LOG": str(log),
                    "JUSTAI_TEST_SPACETIME_READY": str(root / ".spacetime-ready"),
                    "JUSTAI_TEST_PORT_OPEN": "1",
                }
            )
            Path(env["JUSTAI_TEST_SPACETIME_READY"]).write_text("ready", encoding="utf-8")

            subprocess.run(["bash", str(START_SCRIPT)], cwd=root, env=env, check=True, text=True)

            data = log.read_text(encoding="utf-8")
            self.assertNotIn("tmux ", data)
            self.assertIn("start_manuslocal cwd=", data)
            self.assertIn("start_relay_room cwd=", data)
            self.assertIn("daemon_ctl cwd=", data)
            self.assertIn("session=already-up", data)

    def test_check_script_reports_root_status_and_child_health_probes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, bindir = self._workspace(tmp)
            log = root / "calls.log"
            self._write_health_fakes(root, bindir, log)

            env = os.environ.copy()
            env.update(
                {
                    "JUSTAI_ROOT": str(root),
                    "JUSTAI_LOCALMANUS_ROOT": str(root / "LocalManus"),
                    "JUSTAI_RELAY_ROOT": str(root / "relay-room"),
                    "JUSTAI_RELAY_SERVER": "local-server",
                    "JUSTAI_SPACETIME_SESSION": "status-session",
                    "JUSTAI_PATH": f"{bindir}:{env.get('PATH', '')}",
                    "JUSTAI_TEST_LOG": str(log),
                    "JUSTAI_TEST_ML_EXIT": "23",
                    "JUSTAI_TEST_DAEMON_EXIT": "42",
                    "PID_FILE": "/tmp/justai.pid",
                    "LOG_FILE": "/tmp/justai.log",
                }
            )

            result = subprocess.run(
                ["bash", str(CHECK_SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertIn(f"[JustAi] root={root}", result.stdout)
            self.assertIn("[JustAi] health check complete", result.stdout)
            data = log.read_text(encoding="utf-8")
            self.assertIn("ml_cli argv=status", data)
            self.assertIn("daemon_ctl cwd=", data)
            self.assertIn("args=status --with-bots --with-codex", data)
            self.assertIn("args=health", data)
            self.assertIn("pid=/tmp/justai.pid", data)
            self.assertIn("log=/tmp/justai.log", data)
            self.assertLess(data.index("ml_cli argv=status"), data.index("args=status --with-bots --with-codex"))
            self.assertLess(data.index("args=status --with-bots --with-codex"), data.index("args=health"))

    def test_check_script_skips_missing_probes_when_executables_are_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, bindir = self._workspace(tmp)
            log = root / "calls.log"

            env = os.environ.copy()
            env.update(
                {
                    "JUSTAI_ROOT": str(root),
                    "JUSTAI_LOCALMANUS_ROOT": str(root / "LocalManus"),
                    "JUSTAI_RELAY_ROOT": str(root / "relay-room"),
                    "JUSTAI_PATH": f"{bindir}:{env.get('PATH', '')}",
                    "JUSTAI_TEST_LOG": str(log),
                }
            )

            result = subprocess.run(
                ["bash", str(CHECK_SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertIn(f"[JustAi] root={root}", result.stdout)
            self.assertIn("[JustAi] health check complete", result.stdout)
            self.assertFalse(log.exists())


if __name__ == "__main__":
    unittest.main()
