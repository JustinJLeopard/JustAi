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
        "version": "0.8.0",
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
    server.serve_forever()


if __name__ == "__main__":
    port = API_PORT
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--port" and i + 2 < len(sys.argv):
            port = int(sys.argv[i + 2])
    serve(port)
