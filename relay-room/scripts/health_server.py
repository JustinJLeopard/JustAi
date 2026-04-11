#!/usr/bin/env python3
# This module defines 6 check functions: check_tcp_port, check_litellm, check_daemon_pid, check_relay_cli, check_mini_binary, check_discord_bot
import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SPACETIMEDB_PORT = 3000
LITELLM_PORT = 4000
RELAY_PID_FILE = os.environ.get(
    "JUSTAI_RELAY_DISPATCH_PID_FILE",
    os.environ.get("RELAY_PID_FILE", "/tmp/relay_dispatch.pid"),
)
MINI_BIN = "/home/justinleopard/.local/bin/mini"
DEFAULT_PORT = 8080
RELAY_WEB_PORT = int(os.environ.get("RELAY_WEB_PORT", "8765"))


# Sprint 3 Task 4: Watchdog configuration
DEFAULT_BOT_AGENTS = ["relay-coordinator", "codex", "manuslocal", "coworkclaude", "claudecli"]
BOT_AGENTS = [
    agent.strip()
    for agent in os.environ.get("JUSTAI_BOT_AGENTS", ",".join(DEFAULT_BOT_AGENTS)).split(",")
    if agent.strip()
]
HEARTBEAT_INTERVAL = 300       # 5 minutes
STALE_THRESHOLD = 900          # 15 minutes
WATCHDOG_INTERVAL = 30         # Check every 30 seconds
MAX_RESTART_ATTEMPTS = 3
_restart_counts = {a: 0 for a in BOT_AGENTS}
_last_healthy = {}

CRITICAL_CHECK_NAMES = {"spacetimedb", "litellm", "relay_dispatch_daemon"}

# ── /metrics helpers ──────────────────────────────────────────────────
RELAY_ROOT = Path(__file__).resolve().parents[1]
TASK_STATUSES = ("pending", "in_progress", "done", "failed")


def _relay_env():
    """Build env dict with PATH and RELAY vars for the relay CLI."""
    env = os.environ.copy()
    path_entries = env.get("PATH", "").split(":") if env.get("PATH") else []
    for extra in (str(Path.home() / ".local" / "bin"), str(Path.home() / ".cargo" / "bin")):
        if extra not in path_entries:
            path_entries.append(extra)
    env["PATH"] = ":".join(path_entries)
    env.setdefault("RELAY_SERVER", "local-server")
    if not env.get("RELAY_DB_NAME"):
        target_file = RELAY_ROOT / ".relay-db-target"
        if target_file.exists():
            env["RELAY_DB_NAME"] = target_file.read_text(encoding="utf-8").strip()
        else:
            env["RELAY_DB_NAME"] = "relay-room-dev"
    return env


def _parse_pipe_table(text):
    """Parse a pipe-delimited CLI table into (headers, rows) where rows are list of dicts."""
    rows = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("WARNING:") or "|" not in line:
            continue
        stripped = line.replace("+", "").replace("-", "").strip()
        if not stripped:
            continue
        parts = [cell.strip().strip('"') for cell in line.split("|")]
        rows.append(parts)
    if not rows:
        return [], []
    headers = [h.strip() for h in rows[0]]
    data = []
    for row in rows[1:]:
        d = {}
        for i, h in enumerate(headers):
            if h:
                d[h] = row[i].strip() if i < len(row) else ""
        data.append(d)
    return headers, data


def fetch_task_counts():
    """Run `relay tasks`, parse output, and return counts by status."""
    try:
        proc = subprocess.run(
            ["relay", "tasks"],
            cwd=str(RELAY_ROOT),
            env=_relay_env(),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        raw = ((proc.stdout or "") + (proc.stderr or "")).strip()
        if proc.returncode != 0:
            return None, f"relay tasks exited with status {proc.returncode}: {raw[:200]}"
    except FileNotFoundError:
        return None, "relay command not found in PATH"
    except subprocess.TimeoutExpired:
        return None, "relay tasks timed out after 10s"
    except Exception as exc:
        return None, f"relay tasks failed: {exc}"

    _, data = _parse_pipe_table(raw)
    counts = {s: 0 for s in TASK_STATUSES}
    for row in data:
        status = row.get("status", "").strip().lower()
        if status in counts:
            counts[status] += 1
        elif status:
            counts.setdefault(status, 0)
            counts[status] += 1
    return {"total": len(data), "by_status": counts}, None



def now_iso():
    return datetime.now(timezone.utc).isoformat()


def check_tcp_port(name, host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        code = sock.connect_ex((host, port))
        if code == 0:
            return {"name": name, "status": "ok", "detail": f"{host}:{port} reachable"}
        return {"name": name, "status": "fail", "detail": f"{host}:{port} unreachable (connect_ex={code})"}
    except Exception as exc:
        return {"name": name, "status": "fail", "detail": f"{host}:{port} check error: {exc}"}
    finally:
        sock.close()


def check_litellm():
    result = check_tcp_port("litellm", "127.0.0.1", LITELLM_PORT)
    if result["status"] == "fail":
        result["detail"] += "; claudecli will degrade to manuslocal"
    return result


def check_daemon_pid(pid_file):
    if not os.path.exists(pid_file):
        return {"name": "relay_dispatch_daemon", "status": "fail", "detail": f"PID file missing: {pid_file}"}

    try:
        with open(pid_file, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return {"name": "relay_dispatch_daemon", "status": "fail", "detail": f"PID file empty: {pid_file}"}
        pid = int(raw)
    except ValueError:
        return {"name": "relay_dispatch_daemon", "status": "fail", "detail": f"Invalid PID in file: {pid_file}"}
    except Exception as exc:
        return {"name": "relay_dispatch_daemon", "status": "fail", "detail": f"Could not read PID file: {exc}"}

    try:
        os.kill(pid, 0)
        return {"name": "relay_dispatch_daemon", "status": "ok", "detail": f"Process {pid} is running"}
    except ProcessLookupError:
        return {"name": "relay_dispatch_daemon", "status": "fail", "detail": f"Process {pid} not found"}
    except PermissionError:
        return {"name": "relay_dispatch_daemon", "status": "ok", "detail": f"Process {pid} exists (permission denied to signal)"}
    except Exception as exc:
        return {"name": "relay_dispatch_daemon", "status": "fail", "detail": f"PID check error for {pid}: {exc}"}


def check_relay_cli():
    relay_path = shutil.which("relay")
    if not relay_path:
        return {"name": "relay_cli", "status": "fail", "detail": "relay command not found in PATH"}

    for args in (["relay", "--version"], ["relay", "--help"]):
        try:
            proc = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3,
                check=False,
            )
            if proc.returncode == 0:
                return {"name": "relay_cli", "status": "ok", "detail": f"relay available at {relay_path}"}
        except Exception:
            continue

    return {"name": "relay_cli", "status": "fail", "detail": f"relay found at {relay_path} but command invocation failed"}


def check_mini_binary(path):
    if not os.path.exists(path):
        return {"name": "mini_binary", "status": "fail", "detail": f"Missing binary: {path}"}
    if not os.access(path, os.X_OK):
        return {"name": "mini_binary", "status": "fail", "detail": f"Not executable: {path}"}

    try:
        proc = subprocess.run(
            [path, "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
            check=False,
        )
        if proc.returncode in (0, 1, 2):
            return {"name": "mini_binary", "status": "ok", "detail": f"Executable and invocable: {path}"}
        return {"name": "mini_binary", "status": "fail", "detail": f"Executable but returned {proc.returncode}: {path}"}
    except Exception as exc:
        return {"name": "mini_binary", "status": "fail", "detail": f"Execution failed for {path}: {exc}"}


DISCORD_BOT_TOKENS = {
    "relay-coordinator": os.getenv("RELAY_COORDINATOR_TOKEN", ""),
    "codex":             os.getenv("CODEX_TOKEN", ""),
    "manuslocal":        os.getenv("MANUSLOCAL_TOKEN", ""),
    "coworkclaude":      os.getenv("COWORKCLAUDE_TOKEN", ""),
    "claudecli":         os.getenv("CLAUDECLI_TOKEN", ""),
}
DISCORD_BOT_PID_DIR = os.environ.get("JUSTAI_RELAY_BOT_PID_DIR", "/tmp")
DISCORD_BOT_LOG_DIR = os.environ.get("JUSTAI_RELAY_BOT_LOG_DIR", "/tmp")


def check_discord_bot(agent_name: str) -> dict:
    """Check if a Discord bot listener process is running via its PID file."""
    pid_file = os.path.join(DISCORD_BOT_PID_DIR, f"relay_discord_{agent_name}.pid")
    if not os.path.exists(pid_file):
        return {"name": f"discord_bot_{agent_name}", "status": "warn",
                "detail": f"No PID file (bot may not be started): {pid_file}"}
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return {"name": f"discord_bot_{agent_name}", "status": "ok",
                "detail": f"PID {pid} running"}
    except ProcessLookupError:
        return {"name": f"discord_bot_{agent_name}", "status": "fail",
                "detail": f"PID file present but process not running"}
    except Exception as exc:
        return {"name": f"discord_bot_{agent_name}", "status": "warn",
                "detail": str(exc)}



# ── Sprint 4 Task 3: Stale Agent Watchdog ────────────────────────────────────
# Polls PID files every 30s, parses heartbeat timestamps from bot logs,
# posts to #alerts if no heartbeat in 15min, auto-restarts if PID gone,
# escalates to #bugs-and-blockers after 3 consecutive failures.

import re as _re
import time as _time


def _parse_last_heartbeat(agent: str) -> "datetime | None":
    """Read last heartbeat timestamp from /tmp/relay_bot_{agent}.log.

    Scans for lines matching:
      [HEARTBEAT] <agent> | alive | ... | 2025-07-12T10:00:00Z
    Returns the most recent datetime found, or None.
    """
    log_path = os.path.join(DISCORD_BOT_LOG_DIR, f"relay_bot_{agent}.log")
    if not os.path.exists(log_path):
        return None
    # Read last 200 lines to avoid scanning huge files
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-200:]
    except Exception:
        return None

    pattern = _re.compile(
        r"\[HEARTBEAT\].*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)"
    )
    last_ts = None
    for line in lines:
        m = pattern.search(line)
        if m:
            try:
                last_ts = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue
    return last_ts


def _is_agent_stale(agent: str) -> "tuple[bool, str]":
    """Return (is_stale, reason) for an agent.

    An agent is considered stale if:
      1. Its PID file is missing or process is dead, OR
      2. Its process is alive but no heartbeat within STALE_THRESHOLD seconds.
    """
    result = check_discord_bot(agent)

    if result["status"] != "ok":
        return True, f"pid_dead: {result['detail']}"

    # Process alive — check heartbeat freshness
    last_hb = _parse_last_heartbeat(agent)
    if last_hb is None:
        # No heartbeat log yet — give benefit of doubt if recently started
        if agent in _last_healthy:
            return False, "running, no heartbeat log yet"
        return True, "no_heartbeat_ever"

    age = (datetime.now(timezone.utc) - last_hb).total_seconds()
    if age > STALE_THRESHOLD:
        return True, f"heartbeat_stale ({int(age)}s old, threshold={STALE_THRESHOLD}s)"

    return False, f"healthy (heartbeat {int(age)}s ago)"


# Discord channel IDs for watchdog alerts
DISCORD_ALERTS_CHANNEL_ID = os.getenv("DISCORD_ALERTS_CHANNEL_ID", "1491134780589342770")
DISCORD_BUGS_CHANNEL_ID = os.getenv("DISCORD_BUGS_CHANNEL_ID", "1491134770439258285")
DISCORD_RELAY_CHANNEL_ID = os.getenv("DISCORD_RELAY_CHANNEL_ID", "1491134768077865090")
DISCORD_BOT_USER_AGENT = "DiscordBot (relay-room, 0.1)"

# Track last watchdog check results for the /health/watchdog endpoint
_last_check_results = {}     # agent -> {stale, reason, last_heartbeat, restart_count, timestamp}
_watchdog_lock = threading.Lock()


def _discord_post(channel: str, message: str):
    """Post a message to a Discord channel via the Discord REST API.

    channel: 'alerts' or 'bugs-and-blockers'
    Uses RELAY_COORDINATOR_TOKEN for authentication.
    Falls back to relay CLI if available.
    """
    token = os.getenv("RELAY_COORDINATOR_TOKEN", "")
    if not token:
        print(f"[watchdog] No RELAY_COORDINATOR_TOKEN set, skipping Discord post to #{channel}", flush=True)
        return

    channel_map = {
        "alerts": DISCORD_ALERTS_CHANNEL_ID,
        "bugs-and-blockers": DISCORD_BUGS_CHANNEL_ID or DISCORD_ALERTS_CHANNEL_ID,
        "relay-room": DISCORD_RELAY_CHANNEL_ID,
    }
    channel_id = channel_map.get(channel, DISCORD_ALERTS_CHANNEL_ID)
    if not channel_id:
        print(f"[watchdog] No channel ID for #{channel}, skipping", flush=True)
        return

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    try:
        import urllib.request
        import urllib.error
        payload = json.dumps({"content": message}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, method="POST",
            headers={
                "Authorization": f"Bot {token}",
                "Content-Type": "application/json",
                "User-Agent": DISCORD_BOT_USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        print(f"[watchdog] Posted to #{channel} (channel_id={channel_id})", flush=True)
    except Exception as e:
        # Fallback: try relay CLI send_message
        print(f"[watchdog] Discord REST post to #{channel} failed: {e}", flush=True)
        _discord_post_fallback(channel, message)


def _discord_post_fallback(channel: str, message: str):
    """Fallback: post via relay CLI if REST API fails."""
    try:
        relay_path = shutil.which("relay")
        if relay_path:
            subprocess.run(
                [relay_path, "send_message", "--channel", channel, "--content", message],
                timeout=10, capture_output=True, check=False,
            )
    except Exception as e2:
        print(f"[watchdog] Fallback relay CLI also failed: {e2}", flush=True)


def _agent_snapshot(agent: str) -> dict:
    """Capture the current runtime health for a single agent."""
    pid_info = check_discord_bot(agent)
    stale, reason = _is_agent_stale(agent)
    last_hb = _parse_last_heartbeat(agent)
    if pid_info["status"] == "ok" and not stale:
        status = "online"
    elif pid_info["status"] == "ok":
        status = "stale"
    else:
        status = "offline"
    snapshot = {
        "agent": agent,
        "status": status,
        "pid_status": pid_info["status"],
        "pid_detail": pid_info["detail"],
        "stale": stale,
        "reason": reason,
        "restart_count": _restart_counts[agent],
        "last_heartbeat": last_hb.isoformat() if last_hb else None,
        "last_healthy": _last_healthy.get(agent),
    }
    if last_hb is not None:
        snapshot["heartbeat_age_s"] = int((datetime.now(timezone.utc) - last_hb).total_seconds())
    return snapshot


def _attempt_restart(agent: str):
    """Kill stale process if any, then restart bot_listener.py for agent."""
    pid_file = os.path.join(DISCORD_BOT_PID_DIR, f"relay_discord_{agent}.pid")

    # Kill stale process
    if os.path.exists(pid_file):
        try:
            pid = int(open(pid_file).read().strip())
            os.kill(pid, signal.SIGTERM)
            _time.sleep(2)
        except Exception:
            pass
        try:
            os.unlink(pid_file)
        except Exception:
            pass

    # Restart bot
    try:
        bot_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_listener.py")
        log_file = os.path.join(DISCORD_BOT_LOG_DIR, f"relay_bot_{agent}.log")
        os.makedirs(DISCORD_BOT_LOG_DIR, exist_ok=True)
        with open(log_file, "a") as lf:
            proc = subprocess.Popen(
                ["python3", bot_script, "--agent", agent],
                stdout=lf, stderr=lf,
            )
        with open(pid_file, "w", encoding="utf-8") as pf:
            pf.write(str(proc.pid))
        print(f"[watchdog] Restart initiated for {agent}", flush=True)
        return True
    except Exception as e:
        print(f"[watchdog] Restart failed for {agent}: {e}", flush=True)
        return False


def watchdog_check():
    """Single watchdog iteration: check all bot agents for staleness."""
    for agent in BOT_AGENTS:
        stale, reason = _is_agent_stale(agent)
        last_hb = _parse_last_heartbeat(agent)

        # Record check result for /health/watchdog endpoint
        with _watchdog_lock:
            _last_check_results[agent] = {
                "stale": stale,
                "reason": reason,
                "last_heartbeat": last_hb.isoformat() if last_hb else None,
                "restart_count": _restart_counts[agent],
                "timestamp": now_iso(),
            }

        if not stale:
            _restart_counts[agent] = 0
            _last_healthy[agent] = datetime.now(timezone.utc).isoformat()
            continue

        # Agent is stale
        print(f"[watchdog] Agent {agent} stale: {reason}", flush=True)

        # Already at max retries → escalate to #bugs-and-blockers
        if _restart_counts[agent] >= MAX_RESTART_ATTEMPTS:
            msg = (
                f"🚨 **ESCALATION** Agent `{agent}` failed "
                f"{MAX_RESTART_ATTEMPTS} consecutive restart attempts. "
                f"Reason: {reason}. Manual intervention required."
            )
            print(f"[watchdog] ESCALATION: {msg}", flush=True)
            _discord_post("bugs-and-blockers", msg)
            continue

        # Increment failure count and alert
        _restart_counts[agent] += 1
        attempt = _restart_counts[agent]
        alert_msg = (
            f"⚠️ Agent `{agent}` stale ({reason}). "
            f"Attempting auto-restart ({attempt}/{MAX_RESTART_ATTEMPTS})."
        )
        print(f"[watchdog] {alert_msg}", flush=True)
        _discord_post("alerts", alert_msg)

        # Attempt restart
        success = _attempt_restart(agent)
        if not success:
            fail_msg = f"❌ Auto-restart of `{agent}` failed (attempt {attempt})."
            _discord_post("alerts", fail_msg)


def watchdog_loop(interval=WATCHDOG_INTERVAL):
    """Background watchdog thread."""
    print(f"[watchdog] Started (interval={interval}s, stale={STALE_THRESHOLD}s)", flush=True)
    while True:
        try:
            watchdog_check()
        except Exception as e:
            print(f"[watchdog] Error: {e}", flush=True)
        _time.sleep(interval)


def run_all_checks():
    checks = [
        check_tcp_port("spacetimedb", "127.0.0.1", SPACETIMEDB_PORT),
        check_litellm(),
        check_tcp_port("relay_web", "127.0.0.1", RELAY_WEB_PORT),
        check_daemon_pid(RELAY_PID_FILE),
        check_relay_cli(),
        check_mini_binary(MINI_BIN),
        check_discord_bot("relay-coordinator"),
        check_discord_bot("codex"),
        check_discord_bot("manuslocal"),
        check_discord_bot("coworkclaude"),
        check_discord_bot("claudecli"),
    ]

    failed = [c for c in checks if c["status"] == "fail"]
    failed_names = {c["name"] for c in failed}
    critical_failed = bool(failed_names.intersection(CRITICAL_CHECK_NAMES))

    if not failed:
        overall = "healthy"
    elif critical_failed:
        overall = "unhealthy"
    else:
        overall = "degraded"

    return {
        "status": overall,
        "checks": checks,
        "timestamp": now_iso(),
    }


def run_ready_checks():
    critical = [
        check_tcp_port("spacetimedb", "127.0.0.1", SPACETIMEDB_PORT),
        check_litellm(),
        check_daemon_pid(RELAY_PID_FILE),
    ]
    ok = all(c["status"] == "ok" for c in critical)
    return ok, critical


class HealthHandler(BaseHTTPRequestHandler):
    server_version = "relay-health/1.0"

    def _send_json(self, code, payload):
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            payload = run_all_checks()
            code = 200 if payload["status"] in ("healthy", "degraded") else 503
            self._send_json(code, payload)
            return

        if self.path == "/health/ready":
            ready, checks = run_ready_checks()
            payload = {
                "status": "ready" if ready else "not_ready",
                "checks": checks,
                "timestamp": now_iso(),
            }
            self._send_json(200 if ready else 503, payload)
            return

        if self.path == "/health/live":
            self._send_json(200, {"status": "alive", "timestamp": now_iso()})
            return

        if self.path == "/health/watchdog":
            with _watchdog_lock:
                agent_status = dict(_last_check_results)
            payload = {
                "status": "ok" if all(not v.get("stale") for v in agent_status.values()) else "degraded",
                "agents": agent_status,
                "restart_counts": dict(_restart_counts),
                "last_healthy": dict(_last_healthy),
                "config": {
                    "stale_threshold_s": STALE_THRESHOLD,
                    "watchdog_interval_s": WATCHDOG_INTERVAL,
                    "max_restart_attempts": MAX_RESTART_ATTEMPTS,
                },
                "timestamp": now_iso(),
            }
            self._send_json(200, payload)
            return

        if self.path == "/health/agents":
            agents = [_agent_snapshot(agent) for agent in BOT_AGENTS]
            summary = {
                "online": sum(1 for agent in agents if agent["status"] == "online"),
                "stale": sum(1 for agent in agents if agent["status"] == "stale"),
                "offline": sum(1 for agent in agents if agent["status"] == "offline"),
            }
            payload = {
                "status": "ok" if all(not agent["stale"] for agent in agents) else "degraded",
                "agents": agents,
                "summary": summary,
                "timestamp": now_iso(),
            }
            self._send_json(200, payload)
            return

        if self.path == "/metrics":
            counts, error = fetch_task_counts()
            if error:
                payload = {"error": error, "timestamp": now_iso()}
                self._send_json(503, payload)
            else:
                payload = {
                    "tasks": counts,
                    "timestamp": now_iso(),
                }
                self._send_json(200, payload)
            return

        self._send_json(404, {"error": "not_found", "path": self.path, "timestamp": now_iso()})

    def log_message(self, fmt, *args):
        return


def parse_args():
    parser = argparse.ArgumentParser(description="Relay room health endpoint server")
    parser.add_argument("--port", type=int, default=None, help="Port for health server (default from HEALTH_PORT or 8080)")
    return parser.parse_args()


def resolve_port(cli_port):
    if cli_port is not None:
        return cli_port
    env_port = os.getenv("HEALTH_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass
    return DEFAULT_PORT


def main():
    args = parse_args()
    port = resolve_port(args.port)
    # Sprint 3 Task 4: Start watchdog thread
    watchdog_thread = threading.Thread(target=watchdog_loop, daemon=True)
    watchdog_thread.start()

    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)

    shutdown_event = threading.Event()

    def handle_signal(signum, _frame):
        if not shutdown_event.is_set():
            shutdown_event.set()
            print(f"[health_server] Received signal {signum}; shutting down...", flush=True)
            threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    print(f"[health_server] Starting relay-room health server on port {port}", flush=True)

    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        print("[health_server] Server stopped", flush=True)


if __name__ == "__main__":
    main()
