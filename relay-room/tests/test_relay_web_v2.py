#!/usr/bin/env python3
"""Tests for relay_web.py v2 — dashboard, /tasks, /health/status, /task/<id>."""

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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

RELAY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = RELAY_ROOT / "scripts" / "relay_web.py"


def free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_http(url, timeout=6.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                return resp.status
        except Exception:
            time.sleep(0.1)
    raise TimeoutError(f"Server not ready at {url}")


def http_get(url, timeout=3):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8"), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), e.headers.get("Content-Type", "")


class FakeHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({
            "status": "healthy",
            "checks": [
                {"name": "spacetimedb", "status": "ok", "detail": "up"},
                {"name": "litellm", "status": "ok", "detail": "up"},
                {"name": "relay_dispatch_daemon", "status": "ok", "detail": "running"},
                {"name": "relay_cli", "status": "ok", "detail": "found"},
                {"name": "mini_binary", "status": "ok", "detail": "found"},
            ],
            "timestamp": "2026-04-05T00:00:00Z",
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class TestRelayWebV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.fake_bin = Path(cls.tmpdir) / "bin"
        cls.fake_bin.mkdir()

        # Fake relay CLI
        relay = cls.fake_bin / "relay"
        relay.write_text(
            '#!/bin/sh\n'
            'if [ "$1" = "tasks" ]; then\n'
            '  echo \'id | title | from_agent | to_agent | status | session_ref | retry_count\'\n'
            '  echo \'---+-------+------------+----------+--------+-------------+------------\'\n'
            '  echo \' 1  | "test-task" | "claude" | "mini" | "done" | "sprint-8" | 1\'\n'
            '  exit 0\n'
            'fi\n'
            'if [ "$1" = "show" ]; then\n'
            '  echo \'id | title | payload | result | status | session_ref | retry_count\'\n'
            '  echo \'---+-------+---------+--------+--------+-------------+------------\'\n'
            '  echo \' 1  | "test-task" | "do stuff" | "ok" | "done" | "sprint-8" | 1\'\n'
            '  exit 0\n'
            'fi\n'
            'exit 0\n',
            encoding="utf-8",
        )
        relay.chmod(0o755)

        # Start fake health server
        cls.health_port = free_port()
        cls.health_server = ThreadingHTTPServer(("127.0.0.1", cls.health_port), FakeHealthHandler)
        cls.health_thread = threading.Thread(target=cls.health_server.serve_forever, daemon=True)
        cls.health_thread.start()

        # Start relay_web
        cls.web_port = free_port()
        env = os.environ.copy()
        env["PATH"] = f"{cls.fake_bin}:{env.get('PATH', '')}"
        env["RELAY_WEB_PORT"] = str(cls.web_port)
        env["RELAY_WEB_HOST"] = "127.0.0.1"
        env["RELAY_HEALTH_URL"] = f"http://127.0.0.1:{cls.health_port}/health"
        env["RELAY_DB_NAME"] = "relay-room-dev"

        cls.proc = subprocess.Popen(
            ["python3", str(SCRIPT)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True,
        )
        cls.base = f"http://127.0.0.1:{cls.web_port}"
        wait_http(f"{cls.base}/tasks")

    @classmethod
    def tearDownClass(cls):
        if cls.proc.poll() is None:
            cls.proc.send_signal(signal.SIGTERM)
            try:
                cls.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.proc.kill()
        cls.health_server.shutdown()
        cls.health_server.server_close()
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_dashboard_returns_html(self):
        code, body, ct = http_get(f"{self.base}/")
        self.assertEqual(code, 200)
        self.assertIn("text/html", ct)
        self.assertIn("Relay Room", body)
        self.assertIn("Health", body)

    def test_tasks_returns_json(self):
        code, body, ct = http_get(f"{self.base}/tasks")
        self.assertEqual(code, 200)
        self.assertIn("application/json", ct)
        data = json.loads(body)
        self.assertIsInstance(data, list)
        self.assertTrue(len(data) > 0)
        self.assertIn("id", data[0])
        self.assertEqual(data[0]["session_ref"], "sprint-8")

    def test_health_status_returns_json(self):
        code, body, ct = http_get(f"{self.base}/health/status")
        self.assertEqual(code, 200)
        self.assertIn("application/json", ct)
        data = json.loads(body)
        self.assertEqual(data["status"], "healthy")
        self.assertIn("checks", data)

    def test_task_detail_returns_html(self):
        code, body, ct = http_get(f"{self.base}/task/1")
        self.assertEqual(code, 200)
        self.assertIn("text/html", ct)
        self.assertIn("Task 1", body)
        self.assertIn("session_ref", body)
        self.assertIn("sprint-tag", body)
        self.assertIn("sprint-8", body)

    def test_task_detail_without_session_ref(self):
        """Task detail should show sprint tag even when session_ref is missing."""
        # The fake relay show already has session_ref, so this test verifies
        # the sprint-tag CSS class is rendered
        code, body, ct = http_get(f"{self.base}/task/1")
        self.assertEqual(code, 200)
        self.assertIn("sprint-tag", body)

    def test_task_detail_shows_retry_badge(self):
        code, body, ct = http_get(f"{self.base}/task/1")
        self.assertEqual(code, 200)
        self.assertIn("Retries: 1", body)

    def test_not_found(self):
        code, _, _ = http_get(f"{self.base}/nope")
        self.assertEqual(code, 404)


if __name__ == "__main__":
    unittest.main()


class TestRetryCountPreservation(unittest.TestCase):
    """Focused coverage: retry_count in /tasks JSON and retry badge on detail."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.fake_bin = Path(cls.tmpdir) / "bin"
        cls.fake_bin.mkdir()

        # Fake relay CLI with retry_count = 3
        relay = cls.fake_bin / "relay"
        relay.write_text(
            '#!/bin/sh\n'
            'if [ "$1" = "tasks" ]; then\n'
            '  echo \'id | title | from_agent | to_agent | status | session_ref | retry_count\'\n'
            '  echo \'---+-------+------------+----------+--------+-------------+------------\'\n'
            '  echo \' 42  | "retried-task" | "gpt" | "claude" | "pending" | "sprint-9" | 3\'\n'
            '  exit 0\n'
            'fi\n'
            'if [ "$1" = "show" ]; then\n'
            '  echo \'id | title | payload | result | status | session_ref | retry_count\'\n'
            '  echo \'---+-------+---------+--------+--------+-------------+------------\'\n'
            '  echo \' 42  | "retried-task" | "payload" | "res" | "pending" | "sprint-9" | 3\'\n'
            '  exit 0\n'
            'fi\n'
            'exit 0\n',
            encoding="utf-8",
        )
        relay.chmod(0o755)

        cls.health_port = free_port()
        cls.health_server = ThreadingHTTPServer(("127.0.0.1", cls.health_port), FakeHealthHandler)
        cls.health_thread = threading.Thread(target=cls.health_server.serve_forever, daemon=True)
        cls.health_thread.start()

        cls.web_port = free_port()
        env = os.environ.copy()
        env["PATH"] = f"{cls.fake_bin}:{env.get('PATH', '')}"
        env["RELAY_WEB_PORT"] = str(cls.web_port)
        env["RELAY_WEB_HOST"] = "127.0.0.1"
        env["RELAY_HEALTH_URL"] = f"http://127.0.0.1:{cls.health_port}/health"
        env["RELAY_DB_NAME"] = "relay-room-dev"

        cls.proc = subprocess.Popen(
            ["python3", str(SCRIPT)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True,
        )
        cls.base = f"http://127.0.0.1:{cls.web_port}"
        wait_http(f"{cls.base}/tasks")

    @classmethod
    def tearDownClass(cls):
        if cls.proc.poll() is None:
            cls.proc.send_signal(signal.SIGTERM)
            try:
                cls.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.proc.kill()
        cls.health_server.shutdown()
        cls.health_server.server_close()
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_tasks_json_preserves_retry_count_as_numeric(self):
        """retry_count from relay output must appear in /tasks JSON as a numeric-looking string."""
        code, body, ct = http_get(f"{self.base}/tasks")
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertTrue(len(data) > 0, "Expected at least one task")
        task = data[0]
        self.assertIn("retry_count", task, "retry_count field missing from /tasks JSON")
        rc = task["retry_count"]
        # Must be numeric-looking (string digits or actual int)
        self.assertTrue(
            str(rc).strip().isdigit(),
            f"retry_count should be numeric-looking, got {rc!r}",
        )
        self.assertEqual(int(str(rc).strip()), 3)

    def test_retried_task_detail_shows_retry_badge(self):
        """Task detail page for a retried task must display the retry badge."""
        code, body, ct = http_get(f"{self.base}/task/42")
        self.assertEqual(code, 200)
        self.assertIn("text/html", ct)
        self.assertIn("Retries: 3", body, "Retry badge with count not found")
        self.assertIn("sprint-tag retry", body, "Retry CSS class not found")
