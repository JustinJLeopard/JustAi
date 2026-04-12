#!/usr/bin/env python3
"""
JustAi — Dashboard API Server
===============================
Lightweight HTTP API for the dashboard. No framework dependencies.

Endpoints:
  GET  /api/health   — service health (LiteLLM, SpacetimeDB, MCP)
  GET  /api/runs     — recent run history from memory
  GET  /api/config   — current config
  POST /api/run      — trigger orchestrator run (async)
  GET  /api/observability/cost     — cost metrics from LangFuse traces
  GET  /api/observability/latency  — latency metrics + percentiles
  GET  /api/observability/quality  — success rates + failure categories
  GET  /api/observability/summary  — aggregate summary for dashboard cards

Usage:
  python3 -m justai.api              # starts on :3002
  python3 -m justai.api --port 8080  # custom port
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from justai.health import preflight
from justai.memory import Memory
from justai.tracing import get_aggregated_metrics
from justai.trajectory import analyze_trajectory, get_patterns, get_audit_data
from justai.discord import is_configured as discord_configured, notify as discord_notify


API_PORT = int(os.environ.get("JUSTAI_API_PORT", "3002"))
_memory = Memory()

# Track active run (only one at a time)
_active_run: dict | None = None
_run_lock = threading.Lock()


def _get_health() -> dict:
    statuses = preflight()
    return {
        "services": [
            {"name": s.name, "url": s.url, "ok": s.ok, "detail": s.detail}
            for s in statuses
        ],
        "all_ok": all(s.ok for s in statuses),
        "timestamp": time.time(),
    }


def _get_runs(limit: int = 20) -> list[dict]:
    try:
        keys = _memory.list_keys()
    except Exception:
        return []

    run_keys = sorted(
        [k for k in keys if k.startswith("justai/runs/")],
        reverse=True,
    )

    runs = []
    for key in run_keys[:limit]:
        try:
            value = _memory.retrieve(key)
            if value:
                # Parse "key=val | key=val" format
                entry = {"key": key}
                for part in value.split("|"):
                    part = part.strip()
                    if "=" in part:
                        k, _, v = part.partition("=")
                        entry[k.strip()] = v.strip()
                runs.append(entry)
        except Exception:
            pass
    return runs


def _get_config() -> dict:
    return {
        "version": "1.0.0",
        "session_ref": os.environ.get("JUSTAI_SESSION_REF", ""),
        "auto_mode": os.environ.get("JUSTAI_AUTO_MODE", "") in ("1", "true"),
        "litellm_url": os.environ.get("LITELLM_BASE_URL", "http://localhost:4000"),
        "planner_model": os.environ.get("JUSTAI_PLANNER_MODEL", "openai/claude-opus-4-6"),
        "spacetimedb_url": os.environ.get("SPACETIMEDB_URL", "http://127.0.0.1:3000"),
    }


def _start_run(goal: str, auto: bool = False, session: str = "") -> dict:
    global _active_run
    with _run_lock:
        if _active_run and _active_run.get("status") == "running":
            return {"error": "A run is already in progress", "run": _active_run}

        run_id = f"dashboard-{int(time.time())}"
        _active_run = {
            "id": run_id,
            "goal": goal,
            "status": "running",
            "started_at": time.time(),
        }

    def _run_thread():
        global _active_run
        try:
            from justai.orchestrator import run
            result = run(goal, session_ref=session or run_id, auto=auto)
            with _run_lock:
                _active_run = {
                    "id": run_id,
                    "goal": goal,
                    "status": result.status,
                    "task_count": result.task_count,
                    "duration": result.duration_seconds,
                    "finished_at": time.time(),
                }
        except Exception as e:
            with _run_lock:
                _active_run = {
                    "id": run_id,
                    "goal": goal,
                    "status": "error",
                    "error": str(e)[:200],
                    "finished_at": time.time(),
                }

    t = threading.Thread(target=_run_thread, daemon=True)
    t.start()
    return {"started": True, "run_id": run_id}


def _get_observability(section: str, days: int = 7) -> dict | list:
    """Fetch observability metrics from LangFuse traces.

    Args:
        section: "cost", "latency", "quality", or "summary"
        days: lookback window
    """
    metrics = get_aggregated_metrics(days=days)
    if section in metrics:
        return metrics[section]
    return {"error": f"unknown section: {section}"}


class APIHandler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, data: dict | list, status: int = 200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        if path == "/api/health":
            self._json(_get_health())
        elif path == "/api/runs":
            limit = int(params.get("limit", ["20"])[0])
            self._json(_get_runs(limit))
        elif path == "/api/config":
            self._json(_get_config())
        elif path == "/api/run/status":
            with _run_lock:
                self._json(_active_run or {"status": "idle"})
        elif path.startswith("/api/observability"):
            section = path.replace("/api/observability/", "").replace("/api/observability", "")
            if not section:
                section = "summary"
            days = int(params.get("days", ["7"])[0])
            self._json(_get_observability(section, days=days))
        elif path == "/api/trajectory/patterns":
            limit = int(params.get("limit", ["50"])[0])
            self._json(get_patterns(limit=limit))
        elif path.startswith("/api/trajectory/") and path.endswith("/analysis"):
            # /api/trajectory/<filename>/analysis
            filename = path.replace("/api/trajectory/", "").replace("/analysis", "")
            force = params.get("force", [""])[0] == "1"
            self._json(analyze_trajectory(filename, force=force))
        elif path.startswith("/api/trajectory/") and path.endswith("/audit"):
            # /api/trajectory/<filename>/audit
            filename = path.replace("/api/trajectory/", "").replace("/audit", "")
            self._json(get_audit_data(filename))
        elif path == "/api/discord/status":
            self._json({"configured": discord_configured()})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            goal = body.get("goal", "")
            if not goal:
                self._json({"error": "goal is required"}, 400)
                return
            result = _start_run(
                goal,
                auto=body.get("auto", False),
                session=body.get("session", ""),
            )
            self._json(result, 200 if result.get("started") else 409)
        elif path == "/api/discord/test":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            msg = body.get("message", "Test notification from JustAi dashboard")
            sent = discord_notify(msg, title="Test Notification")
            self._json({"sent": sent, "configured": discord_configured()})
        else:
            self._json({"error": "not found"}, 404)

    def log_message(self, format, *args):
        # Quieter logging
        pass


def serve(port: int = API_PORT):
    """Start the API server."""
    server = HTTPServer(("0.0.0.0", port), APIHandler)
    print(f"JustAi API server on http://0.0.0.0:{port}")
    print(f"  GET  /api/health")
    print(f"  GET  /api/runs")
    print(f"  GET  /api/config")
    print(f"  POST /api/run")
    print(f"  GET  /api/observability/cost")
    print(f"  GET  /api/observability/latency")
    print(f"  GET  /api/observability/quality")
    print(f"  GET  /api/observability/summary")
    print(f"  GET  /api/trajectory/:name/analysis")
    print(f"  GET  /api/trajectory/:name/audit")
    print(f"  GET  /api/trajectory/patterns")
    server.serve_forever()


if __name__ == "__main__":
    port = API_PORT
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--port" and i + 2 < len(sys.argv):
            port = int(sys.argv[i + 2])
    serve(port)
