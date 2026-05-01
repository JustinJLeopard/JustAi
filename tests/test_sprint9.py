#!/usr/bin/env python3
"""Sprint 9 tests — API server, dashboard integration."""

import json
import sys
import threading
import time
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestAPIEndpoints(unittest.TestCase):
    """Test API handler logic without starting HTTP server."""

    def test_get_health_returns_dict(self):
        from justai.api import _get_health

        result = _get_health()
        self.assertIsInstance(result, dict)
        self.assertIn("services", result)
        self.assertIn("all_ok", result)
        self.assertIn("timestamp", result)

    def test_get_health_has_three_services(self):
        from justai.api import _get_health

        result = _get_health()
        self.assertEqual(len(result["services"]), 3)

    def test_get_health_service_structure(self):
        from justai.api import _get_health

        result = _get_health()
        for svc in result["services"]:
            self.assertIn("name", svc)
            self.assertIn("url", svc)
            self.assertIn("ok", svc)
            self.assertIn("detail", svc)

    def test_get_runs_returns_list(self):
        from justai.api import _get_runs

        result = _get_runs()
        self.assertIsInstance(result, list)

    def test_get_runs_with_limit(self):
        from justai.api import _get_runs

        result = _get_runs(limit=5)
        self.assertLessEqual(len(result), 5)

    def test_get_config_returns_dict(self):
        from justai.api import _get_config

        result = _get_config()
        self.assertIsInstance(result, dict)
        self.assertIn("version", result)
        self.assertEqual(result["version"], "1.0.0")

    def test_get_config_has_required_fields(self):
        from justai.api import _get_config

        result = _get_config()
        for key in (
            "version",
            "session_ref",
            "auto_mode",
            "litellm_url",
            "planner_model",
            "safe_mini_mode",
        ):
            self.assertIn(key, result)


class TestAPIStartRun(unittest.TestCase):
    """Test run trigger logic."""

    def test_start_run_missing_goal(self):
        from justai.api import _start_run

        # Empty goal should still create a run (validation is in handler)
        result = _start_run("")
        self.assertIn("started", result)

    def test_start_run_returns_run_id(self):
        import justai.api
        from justai.api import _start_run

        # Reset active run
        justai.api._active_run = None
        result = _start_run("test goal", auto=True)
        self.assertTrue(result["started"])
        self.assertIn("run_id", result)
        # Clean up — wait for thread to finish or timeout
        time.sleep(0.5)
        justai.api._active_run = None

    def test_concurrent_run_blocked(self):
        import justai.api
        from justai.api import _start_run

        # Simulate active run
        justai.api._active_run = {"status": "running", "id": "test"}
        result = _start_run("another goal")
        self.assertIn("error", result)
        justai.api._active_run = None


class TestAPIRunHistory(unittest.TestCase):
    """Test run history parsing."""

    def test_run_entry_parsing(self):
        """Verify the key=val parsing logic."""
        from justai.api import _get_runs

        # This depends on actual memory content. Just verify it doesn't crash.
        runs = _get_runs(limit=3)
        self.assertIsInstance(runs, list)
        for run in runs:
            self.assertIn("key", run)


class TestAPIServer(unittest.TestCase):
    """Test the actual HTTP server (start, request, stop)."""

    @classmethod
    def setUpClass(cls):
        from http.server import HTTPServer

        from justai.api import APIHandler

        cls.port = 13902  # Use a non-standard port for testing
        cls.server = HTTPServer(("127.0.0.1", cls.port), APIHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.load(resp), resp.status

    def test_health_endpoint(self):
        data, status = self._get("/api/health")
        self.assertEqual(status, 200)
        self.assertIn("services", data)

    def test_runs_endpoint(self):
        data, status = self._get("/api/runs?limit=5")
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)

    def test_config_endpoint(self):
        data, status = self._get("/api/config")
        self.assertEqual(status, 200)
        self.assertIn("version", data)

    def test_run_status_endpoint(self):
        data, status = self._get("/api/run/status")
        self.assertEqual(status, 200)
        self.assertIn("status", data)

    def test_404_endpoint(self):
        try:
            self._get("/api/nonexistent")
            self.fail("Should have raised")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_cors_headers(self):
        url = f"http://127.0.0.1:{self.port}/api/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")


class TestDashboardFiles(unittest.TestCase):
    """Test dashboard file structure."""

    def test_api_client_exists(self):
        p = Path(__file__).resolve().parents[1] / "dashboard" / "src" / "lib" / "api-client.ts"
        self.assertTrue(p.exists())

    def test_run_history_exists(self):
        p = Path(__file__).resolve().parents[1] / "dashboard" / "src" / "views" / "RunHistory.tsx"
        self.assertTrue(p.exists())

    def test_vite_config_has_api_proxy(self):
        p = Path(__file__).resolve().parents[1] / "dashboard" / "vite.config.ts"
        content = p.read_text()
        self.assertIn("/api/health", content)
        self.assertIn("/api/runs", content)
        self.assertIn("3002", content)

    def test_app_tsx_has_runs_view(self):
        p = Path(__file__).resolve().parents[1] / "dashboard" / "src" / "App.tsx"
        content = p.read_text()
        self.assertIn("RunHistory", content)
        self.assertIn("'runs'", content)

    def test_mission_control_has_health_import(self):
        p = (
            Path(__file__).resolve().parents[1]
            / "dashboard"
            / "src"
            / "views"
            / "MissionControl.tsx"
        )
        content = p.read_text()
        self.assertIn("fetchHealth", content)


if __name__ == "__main__":
    unittest.main()
