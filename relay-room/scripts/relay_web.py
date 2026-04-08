#!/usr/bin/env python3
"""Relay Room Web UI v2 — enhanced dashboard with health, tasks API, and detail views.

HTTP endpoints served:

    GET /              — Dashboard HTML (auto-refreshing task board)
    GET /index.html    — Alias for /
    GET /tasks          — JSON array of current tasks
    GET /health/status  — Proxied health-check JSON from the relay server
    GET /task/<id>      — Task detail HTML page for a given numeric task ID
"""

from __future__ import annotations

import html as html_mod
import json
import os
import re
import signal
import subprocess
import sys
import threading
import urllib.request
import urllib.error
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
HOST = os.environ.get("RELAY_WEB_HOST", "127.0.0.1")
PORT = int(os.environ.get("RELAY_WEB_PORT", "8765"))
REFRESH_SECONDS = int(os.environ.get("RELAY_WEB_REFRESH", "3"))
HEALTH_URL = os.environ.get("RELAY_HEALTH_URL", "http://127.0.0.1:8080/health")


def _relay_env() -> dict:
    env = os.environ.copy()
    path_entries = env.get("PATH", "").split(":") if env.get("PATH") else []
    for extra in (str(Path.home() / ".local" / "bin"), str(Path.home() / ".cargo" / "bin")):
        if extra not in path_entries:
            path_entries.append(extra)
    env["PATH"] = ":".join(path_entries)
    env.setdefault("RELAY_SERVER", "local-server")
    if not env.get("RELAY_DB_NAME"):
        target_file = ROOT / ".relay-db-target"
        if target_file.exists():
            env["RELAY_DB_NAME"] = target_file.read_text(encoding="utf-8").strip()
        else:
            env["RELAY_DB_NAME"] = "relay-room-dev"
    return env


def load_tasks_text() -> str:
    proc = subprocess.run(
        ["relay", "tasks"], cwd=ROOT, env=_relay_env(),
        capture_output=True, text=True, check=False,
    )
    return ((proc.stdout or "") + (proc.stderr or "")).strip()


def load_task_detail(task_id: str) -> str:
    proc = subprocess.run(
        ["relay", "show", task_id], cwd=ROOT, env=_relay_env(),
        capture_output=True, text=True, check=False,
    )
    return ((proc.stdout or "") + (proc.stderr or "")).strip()


def parse_pipe_table(text: str) -> Tuple[List[str], List[Dict[str, str]]]:
    rows: List[List[str]] = []
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


def fetch_health() -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def tasks_json(text: str) -> List[Dict[str, str]]:
    _, data = parse_pipe_table(text)
    for row in data:
        row.setdefault("session_ref", "")
        row.setdefault("retry_count", "0")
    return data



# -- backward-compat shims (used by tests/test_relay_web.py) --

def load_board_text() -> str:
    """Legacy: calls relay board instead of relay tasks."""
    proc = subprocess.run(
        ["relay", "board"], cwd=ROOT, env=_relay_env(),
        capture_output=True, text=True, check=False,
    )
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise RuntimeError(output or f"relay board exited with status {proc.returncode}")
    return output


def parse_board(text: str):
    """Legacy: splits board text into (agents_table, tasks_table) tuples."""
    sections = {"Agents": [], "Tasks": []}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in sections:
            current = stripped
            continue
        if stripped == "Events":
            current = None
            continue
        if current is not None:
            sections[current].append(line)

    def _lp(lines):
        rows = []
        for raw in lines:
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
        return rows[0], rows[1:]

    return _lp(sections["Agents"]), _lp(sections["Tasks"])


def render_table(title: str, headers, rows, wanted) -> str:
    """Legacy: renders a single HTML section with a filtered table."""
    if not headers:
        return f"<section><h2>{html_mod.escape(title)}</h2><p class='empty'>No data available.</p></section>"
    indexes = [headers.index(name) for name in wanted if name in headers]
    display_headers = [headers[i] for i in indexes]
    colspan = max(len(display_headers), 1)
    body_rows = []
    for row in rows:
        cells = []
        for idx in indexes:
            value = row[idx] if idx < len(row) else ""
            cells.append(f"<td>{html_mod.escape(value)}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        f"<section><h2>{html_mod.escape(title)}</h2>"
        "<div class='table-wrap'><table><thead><tr>"
        + "".join(f"<th>{html_mod.escape(c)}</th>" for c in display_headers)
        + "</tr></thead><tbody>"
        + ("".join(body_rows) if body_rows else f"<tr><td colspan='{colspan}' class='empty'>No rows.</td></tr>")
        + "</tbody></table></div></section>"
    )


def render_page(board_text: str) -> str:
    """Legacy: renders full HTML page from board text."""
    (ah, ar), (th, tr) = parse_board(board_text)
    at = render_table("Agents", ah, ar, ["name", "status", "last_seen"])
    tt = render_table("Tasks", th, tr, ["id", "title", "from_agent", "to_agent", "status", "priority", "created_at"])
    raw = html_mod.escape(board_text)
    return (
        "<!doctype html>\n"
        "<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Relay Room Board</title></head>\n"
        "<body><main>\n"
        "<h1>Relay Room</h1>\n"
        f"<p class=\"meta\">Auto-refreshing every {REFRESH_SECONDS}s on {HOST}:{PORT}</p>\n"
        f"{tt}\n"
        f"{at}\n"
        f"<section><h2>Raw Board</h2><pre>{raw}</pre></section>\n"
        "</main></body></html>"
    )

# -- end backward-compat shims --

STATUS_COLORS = {
    "pending": "#e2b714",
    "in_progress": "#4fc3f7",
    "done": "#66bb6a",
    "failed": "#ef5350",
}
HEALTH_COLORS = {"ok": "#66bb6a", "fail": "#ef5350"}


def render_dashboard(task_text: str, health: Optional[Dict]) -> str:
    _, tasks = parse_pipe_table(task_text)

    # Agent summary
    agent_counts: Dict[str, Dict[str, int]] = {}
    for t in tasks:
        agent = t.get("to_agent", "unknown")
        status = t.get("status", "unknown")
        agent_counts.setdefault(agent, {})
        agent_counts[agent][status] = agent_counts[agent].get(status, 0) + 1

    agent_html = ""
    for agent, counts in sorted(agent_counts.items()):
        badges = " ".join(
            f'<span class="badge" style="background:{STATUS_COLORS.get(s,"#888")}">{s}: {c}</span>'
            for s, c in sorted(counts.items())
        )
        agent_html += f'<div class="agent-card"><strong>{html_mod.escape(agent)}</strong> {badges}</div>'

    # Health panel
    health_html = '<div class="health-panel"><h2>Health</h2>'
    if health and "checks" in health:
        overall = health.get("status", "unknown")
        oc = "#66bb6a" if overall == "healthy" else "#e2b714" if overall == "degraded" else "#ef5350"
        health_html += f'<div class="health-overall" style="color:{oc}">{html_mod.escape(overall.upper())}</div>'
        for chk in health["checks"]:
            color = HEALTH_COLORS.get(chk.get("status", ""), "#888")
            name = html_mod.escape(chk.get("name", ""))
            detail = html_mod.escape(chk.get("detail", ""))
            health_html += f'<div class="health-item"><span class="dot" style="background:{color}"></span> {name} <span class="health-detail">{detail}</span></div>'
    else:
        health_html += '<div class="health-item" style="color:#ef5350">Health server unreachable</div>'
    health_html += '</div>'

    # Task rows
    task_rows = ""
    for t in tasks:
        tid = html_mod.escape(t.get("id", ""))
        title = html_mod.escape(t.get("title", ""))
        fr = html_mod.escape(t.get("from_agent", ""))
        to = html_mod.escape(t.get("to_agent", ""))
        st = t.get("status", "")
        sc = STATUS_COLORS.get(st, "#888")
        badge = f'<span class="badge" style="background:{sc}">{html_mod.escape(st)}</span>'
        task_rows += f'<tr><td><a href="/task/{tid}">{tid}</a></td><td>{title}</td><td>{fr}</td><td>{to}</td><td>{badge}</td></tr>'

    return f'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Relay Room v2</title>
<style>
:root {{ color-scheme:dark; --bg:#0a0f0d; --panel:#111a15; --text:#b8f0c8; --muted:#5fa676; --grid:#1e3328; --accent:#d7ffd7; }}
*{{ box-sizing:border-box; margin:0; padding:0; }}
body{{ font-family:"JetBrains Mono",Consolas,monospace; background:var(--bg); color:var(--text); }}
main{{ max-width:1400px; margin:0 auto; padding:24px 16px; }}
h1{{ color:var(--accent); margin-bottom:6px; font-size:1.4rem; }}
h2{{ color:var(--accent); font-size:1.1rem; margin-bottom:10px; }}
.meta{{ color:var(--muted); margin-bottom:16px; font-size:0.85rem; }}
.grid{{ display:grid; grid-template-columns:1fr 300px; gap:16px; margin-bottom:16px; }}
@media(max-width:900px){{ .grid{{ grid-template-columns:1fr; }} }}
section,.health-panel{{ background:var(--panel); border:1px solid var(--grid); border-radius:10px; padding:14px; }}
table{{ width:100%; border-collapse:collapse; }}
th,td{{ padding:8px 10px; border-bottom:1px solid var(--grid); text-align:left; font-size:0.88rem; }}
th{{ color:var(--accent); }}
a{{ color:#4fc3f7; text-decoration:none; }}
a:hover{{ text-decoration:underline; }}
.badge{{ display:inline-block; padding:2px 8px; border-radius:4px; color:#000; font-size:0.8rem; font-weight:bold; }}
.agent-card{{ margin-bottom:6px; }}
.health-overall{{ font-size:1.2rem; font-weight:bold; margin-bottom:8px; }}
.health-item{{ margin-bottom:4px; font-size:0.85rem; }}
.health-detail{{ color:var(--muted); font-size:0.78rem; }}
.dot{{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:4px; }}
#status{{ color:var(--muted); font-size:0.78rem; float:right; }}
</style>
</head><body><main>
<h1>Relay Room <span id="status">live</span></h1>
<p class="meta">Auto-refresh {REFRESH_SECONDS}s &middot; {HOST}:{PORT}</p>
<div class="grid">
<section><h2>Tasks</h2>
<table><thead><tr><th>ID</th><th>Title</th><th>From</th><th>To</th><th>Status</th></tr></thead>
<tbody id="task-body">{task_rows}</tbody></table></section>
{health_html}
</div>
<section><h2>Agents</h2>{agent_html if agent_html else '<div class="muted">No agents yet</div>'}</section>
<script>
async function refresh(){{
  try{{
    const r=await fetch("/tasks");const tasks=await r.json();
    let html="";const colors={{pending:"#e2b714",in_progress:"#4fc3f7",done:"#66bb6a",failed:"#ef5350"}};
    tasks.forEach(t=>{{
      const c=colors[t.status]||"#888";
      html+=`<tr><td><a href="/task/${{t.id}}">${{t.id}}</a></td><td>${{t.title||""}}</td><td>${{t.from_agent||""}}</td><td>${{t.to_agent||""}}</td><td><span class="badge" style="background:${{c}}">${{t.status||""}}</span></td></tr>`;
    }});
    document.getElementById("task-body").innerHTML=html;
    document.getElementById("status").textContent="updated "+new Date().toLocaleTimeString();
  }}catch(e){{ document.getElementById("status").textContent="fetch error"; }}
}}
setInterval(refresh,{REFRESH_SECONDS}*1000);
</script>
</main></body></html>'''


def render_task_detail(task_id: str) -> str:
    text = load_task_detail(task_id)
    _, rows = parse_pipe_table(text)
    if not rows:
        return f'<html><body><h1>Task {html_mod.escape(task_id)} not found</h1><a href="/">Back</a></body></html>'
    t = rows[0]
    t.setdefault("session_ref", "")
    t.setdefault("retry_count", "0")
    session_ref = t.get("session_ref", "")
    retry_count = t.get("retry_count", "0")
    sprint_tag = ""
    if session_ref:
        sprint_tag = f'<span class="sprint-tag">{html_mod.escape(session_ref)}</span>'
    else:
        sprint_tag = '<span class="sprint-tag none">no sprint</span>'
    retry_badge = ""
    if retry_count.isdigit() and int(retry_count) > 0:
        retry_badge = f'<span class="sprint-tag retry">Retries: {html_mod.escape(retry_count)}</span>'
    fields = "".join(f'<tr><td><strong>{html_mod.escape(k)}</strong></td><td>{html_mod.escape(v)}</td></tr>' for k, v in t.items())
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Task {html_mod.escape(task_id)}</title>
<style>:root{{color-scheme:dark;--bg:#0a0f0d;--text:#b8f0c8;--accent:#d7ffd7;--grid:#1e3328;}}
body{{font-family:monospace;background:var(--bg);color:var(--text);padding:24px;}}
table{{border-collapse:collapse;}} td{{padding:6px 12px;border-bottom:1px solid var(--grid);vertical-align:top;}}
a{{color:#4fc3f7;}}
.sprint-tag{{display:inline-block;padding:4px 12px;border-radius:4px;background:#1b5e20;color:#a5d6a7;font-size:0.95rem;margin-left:12px;vertical-align:middle;}}
.sprint-tag.none{{background:#333;color:#888;}} .sprint-tag.retry{{background:#5d4037;color:#ffccbc;}}</style>
</head><body><h1>Task {html_mod.escape(task_id)} {sprint_tag}{retry_badge}</h1><a href="/">Back to dashboard</a>
<table>{fields}</table></body></html>'''


class RelayHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, content_type: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, data: Any):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json")

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            try:
                text = load_tasks_text()
                health = fetch_health()
                body = render_dashboard(text, health).encode("utf-8")
                self._send(200, body)
            except Exception as exc:
                self._send(500, f"<pre>{html_mod.escape(str(exc))}</pre>".encode())
            return

        if self.path == "/tasks":
            try:
                text = load_tasks_text()
                self._send_json(200, tasks_json(text))
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if self.path == "/health/status":
            health = fetch_health()
            if health:
                self._send_json(200, health)
            else:
                self._send_json(503, {"error": "health server unreachable"})
            return

        m = re.match(r"^/task/(\d+)$", self.path)
        if m:
            try:
                body = render_task_detail(m.group(1)).encode("utf-8")
                self._send(200, body)
            except Exception as exc:
                self._send(500, f"<pre>{html_mod.escape(str(exc))}</pre>".encode())
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(f"[relay_web] {self.address_string()} - {fmt % args}\n")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), RelayHandler)
    shutdown_event = threading.Event()

    def handle_signal(signum, _frame):
        if not shutdown_event.is_set():
            shutdown_event.set()
            print(f"[relay_web] Signal {signum}, shutting down...", flush=True)
            threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    print(f"[relay_web] Relay Room v2 listening on http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        print("[relay_web] Server stopped", flush=True)


if __name__ == "__main__":
    main()
