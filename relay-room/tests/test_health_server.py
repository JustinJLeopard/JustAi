#!/usr/bin/env python3
import json
import os
import signal
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

RELAY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = RELAY_ROOT / "scripts" / "health_server.py"


def free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_http(url, timeout=5.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                return resp.status
        except Exception:
            time.sleep(0.1)
    raise TimeoutError(f"Server did not become ready at {url}")


def http_json(url, timeout=2):
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return e.code, parsed


class TestHealthServer(unittest.TestCase):
    def _close_proc_streams(self):
        proc = getattr(self, "proc", None)
        if not proc:
            return
        for stream_name in ("stdout", "stderr"):
            stream = getattr(proc, stream_name, None)
            if stream:
                stream.close()

    def setUp(self):
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.tmpdir = tempfile.TemporaryDirectory()
        self.fake_bin = Path(self.tmpdir.name) / "bin"
        self.fake_bin.mkdir(parents=True, exist_ok=True)

        relay = self.fake_bin / "relay"
        relay.write_text("#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo relay 0.0.0; exit 0; fi\nexit 0\n", encoding="utf-8")
        relay.chmod(0o755)

        mini_dir = Path.home() / ".venv" / "hermes" / "bin"
        mini_dir.mkdir(parents=True, exist_ok=True)
        mini = mini_dir / "mini"
        self.mini_original = None
        if mini.exists():
            self.mini_original = mini.read_bytes()
        mini.write_text("#!/bin/sh\necho mini\nexit 0\n", encoding="utf-8")
        mini.chmod(0o755)

        self.env = os.environ.copy()
        self.env["PATH"] = f"{self.fake_bin}:{self.env.get('PATH','')}"

        self.proc = subprocess.Popen(
            ["python3", str(SCRIPT_PATH), "--port", str(self.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=self.env,
            text=True,
        )
        wait_http(f"{self.base}/health/live", timeout=6)

    def tearDown(self):
        if getattr(self, "proc", None) and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self._close_proc_streams()
        if hasattr(self, "tmpdir"):
            self.tmpdir.cleanup()

        mini = Path.home() / ".venv" / "hermes" / "bin" / "mini"
        if hasattr(self, "mini_original"):
            if self.mini_original is None:
                if mini.exists():
                    mini.unlink()
            else:
                mini.write_bytes(self.mini_original)
                mini.chmod(0o755)

    def test_live_always_200(self):
        status, body = http_json(f"{self.base}/health/live")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "alive")
        self.assertIn("timestamp", body)

    def test_health_schema_and_values(self):
        status, body = http_json(f"{self.base}/health")
        self.assertIn(status, (200, 503))
        self.assertIn(body.get("status"), ("healthy", "degraded", "unhealthy"))
        self.assertIn("checks", body)
        self.assertIn("timestamp", body)
        self.assertIsInstance(body["checks"], list)

        expected_names = {"spacetimedb", "litellm", "relay_web", "relay_dispatch_daemon", "relay_cli", "mini_binary"}
        names = {c.get("name") for c in body["checks"]}
        self.assertTrue(expected_names.issubset(names))

        for check in body["checks"]:
            self.assertIn("name", check)
            self.assertIn("status", check)
            self.assertIn("detail", check)
            self.assertIn(check["status"], ("ok", "fail"))

    def test_ready_endpoint_code_and_schema(self):
        status, body = http_json(f"{self.base}/health/ready")
        self.assertIn(status, (200, 503))
        self.assertIn(body.get("status"), ("ready", "not_ready"))
        self.assertIn("checks", body)
        self.assertIn("timestamp", body)
        self.assertEqual(len(body["checks"]), 3)
        names = {c.get("name") for c in body["checks"]}
        self.assertEqual(names, {"spacetimedb", "litellm", "relay_dispatch_daemon"})
        for check in body["checks"]:
            self.assertIn(check["status"], ("ok", "fail"))

    def test_agents_endpoint_returns_agent_snapshot(self):
        status, body = http_json(f"{self.base}/health/agents")
        self.assertEqual(status, 200)
        self.assertIn(body.get("status"), ("ok", "degraded"))
        self.assertIn("agents", body)
        self.assertIn("timestamp", body)
        self.assertEqual(len(body["agents"]), 5)
        names = {agent["agent"] for agent in body["agents"]}
        self.assertEqual(names, {"relay-coordinator", "codex", "manuslocal", "coworkclaude", "claudecli"})
        self.assertIn("summary", body)
        self.assertIn("online", body["summary"])
        self.assertIn("stale", body["summary"])
        self.assertIn("offline", body["summary"])
        for agent in body["agents"]:
            self.assertIn(agent["status"], ("online", "stale", "offline"))
            self.assertIn("pid_status", agent)
            self.assertIn("pid_detail", agent)
            self.assertIn("stale", agent)
            self.assertIn("reason", agent)
            self.assertIn("restart_count", agent)

    def test_not_found(self):
        status, body = http_json(f"{self.base}/nope")
        self.assertEqual(status, 404)
        self.assertEqual(body.get("error"), "not_found")
        self.assertEqual(body.get("path"), "/nope")
        self.assertIn("timestamp", body)


if __name__ == "__main__":
    unittest.main()


class TestMetricsEndpoint(unittest.TestCase):
    """Tests for the /metrics endpoint."""

    def _close_proc_streams(self):
        proc = getattr(self, "proc", None)
        if not proc:
            return
        for stream_name in ("stdout", "stderr"):
            stream = getattr(proc, stream_name, None)
            if stream:
                stream.close()

    def setUp(self):
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.tmpdir = tempfile.TemporaryDirectory()
        self.fake_bin = Path(self.tmpdir.name) / "bin"
        self.fake_bin.mkdir(parents=True, exist_ok=True)

        mini_dir = Path.home() / ".venv" / "hermes" / "bin"
        mini_dir.mkdir(parents=True, exist_ok=True)
        mini = mini_dir / "mini"
        self.mini_original = None
        if mini.exists():
            self.mini_original = mini.read_bytes()
        mini.write_text("#!/bin/sh\necho mini\nexit 0\n", encoding="utf-8")
        mini.chmod(0o755)

    def tearDown(self):
        if getattr(self, "proc", None) and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self._close_proc_streams()
        if hasattr(self, "tmpdir"):
            self.tmpdir.cleanup()
        mini = Path.home() / ".venv" / "hermes" / "bin" / "mini"
        if hasattr(self, "mini_original"):
            if self.mini_original is None:
                if mini.exists():
                    mini.unlink()
            else:
                mini.write_bytes(self.mini_original)
                mini.chmod(0o755)

    def _start_server(self, relay_script_body):
        relay = self.fake_bin / "relay"
        relay.write_text(relay_script_body, encoding="utf-8")
        relay.chmod(0o755)

        env = os.environ.copy()
        env["PATH"] = f"{self.fake_bin}:{env.get('PATH', '')}"

        self.proc = subprocess.Popen(
            ["python3", str(SCRIPT_PATH), "--port", str(self.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            text=True,
        )
        wait_http(f"{self.base}/health/live", timeout=6)

    def test_metrics_empty_tasks(self):
        """When relay tasks returns no output, metrics should return zero counts."""
        self._start_server('#!/bin/sh\nexit 0\n')
        status, body = http_json(f"{self.base}/metrics")
        self.assertEqual(status, 200)
        self.assertIn("tasks", body)
        self.assertIn("timestamp", body)
        self.assertEqual(body["tasks"]["total"], 0)
        for s in ("pending", "in_progress", "done", "failed"):
            self.assertEqual(body["tasks"]["by_status"][s], 0)

    def test_metrics_with_tasks(self):
        """When relay tasks returns a pipe table, metrics counts by status."""
        table = (
            "| id | title        | from_agent | to_agent | status      |\\n"
            "|  1 | task-alpha   | alice      | bob      | pending     |\\n"
            "|  2 | task-beta    | alice      | carol    | in_progress |\\n"
            "|  3 | task-gamma   | bob        | dave     | done        |\\n"
            "|  4 | task-delta   | carol      | alice    | failed      |\\n"
            "|  5 | task-epsilon | dave       | alice    | pending     |\\n"
        )
        script = f'#!/bin/sh\nif [ "$1" = "tasks" ]; then printf "{table}"; exit 0; fi\nif [ "$1" = "--version" ]; then echo relay 0.0.0; exit 0; fi\nexit 0\n'
        self._start_server(script)
        status, body = http_json(f"{self.base}/metrics")
        self.assertEqual(status, 200)
        self.assertEqual(body["tasks"]["total"], 5)
        self.assertEqual(body["tasks"]["by_status"]["pending"], 2)
        self.assertEqual(body["tasks"]["by_status"]["in_progress"], 1)
        self.assertEqual(body["tasks"]["by_status"]["done"], 1)
        self.assertEqual(body["tasks"]["by_status"]["failed"], 1)

    def test_metrics_relay_failure(self):
        """When relay tasks fails, /metrics returns 503 with error."""
        script = (
            '#!/bin/sh\n'
            'if [ "$1" = "tasks" ]; then echo "error: connection refused" >&2; exit 1; fi\n'
            'if [ "$1" = "--version" ]; then echo relay 0.0.0; exit 0; fi\n'
            'exit 0\n'
        )
        self._start_server(script)
        status, body = http_json(f"{self.base}/metrics")
        self.assertEqual(status, 503)
        self.assertIn("error", body)

if __name__ == "__main__":
    unittest.main()
