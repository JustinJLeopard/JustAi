#!/usr/bin/env python3
"""
session_capture.py — Captures recent relay task activity, generates a session
summary, and persists it via honcho_writeback.py (with local JSON fallback).

Usage:
    python scripts/session_capture.py
    python scripts/session_capture.py --summary "Finished sprint 6 tasks"
    python scripts/session_capture.py --agent manuslocal --last 20 --json

Called by:  relay session-end
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
LOGS_DIR = PROJECT_ROOT / "logs"
HONCHO_WRITEBACK = SCRIPT_DIR / "honcho_writeback.py"


# Regex matching relay CLI warning/info lines that can appear in command output
_WARNING_RE = re.compile(
    r"^\s*(WARNING|WARN|WARNING:|INFO:|ERROR:|DEBUG:|\[WARNING\]|\[WARN\]|\[ERROR\])",
    re.IGNORECASE,
)


def _is_table_line(line: str) -> bool:
    """Return True if *line* looks like a pipe-separated table row."""
    return bool(line) and "|" in line and not _WARNING_RE.match(line)


# ─── Relay board queries ──────────────────────────────────────────────────────

def relay_cmd(*args: str) -> str:
    """Run a relay CLI command, return stdout or empty string on failure."""
    try:
        result = subprocess.run(
            ["relay", *args],
            capture_output=True, text=True, timeout=15,
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"  ⚠ relay command failed: {exc}", file=sys.stderr)
        return ""


def parse_relay_table(raw: str) -> list[dict]:
    """Parse the pipe-separated table output from `relay tasks` into dicts."""
    # Filter out CLI WARNING / INFO / ERROR lines before parsing the table
    lines = [l.strip() for l in raw.splitlines() if _is_table_line(l.strip())]
    if len(lines) < 2:
        return []

    # First line is headers, second is separator (dashes)
    headers = [h.strip().strip('"') for h in lines[0].split("|")]
    rows = []
    for line in lines[2:]:  # skip header + separator
        if line.startswith("---") or not line.strip():
            continue
        cols = [c.strip().strip('"') for c in line.split("|")]
        if len(cols) >= len(headers):
            rows.append(dict(zip(headers, cols)))
        elif cols:
            # partial row — pad with empty strings
            padded = cols + [""] * (len(headers) - len(cols))
            rows.append(dict(zip(headers, padded)))
    return rows


def fetch_tasks(agent: str | None = None, last_n: int = 50) -> list[dict]:
    """Fetch recent tasks from the relay board."""
    args = ["tasks"]
    if agent:
        args += ["--to", agent]
    raw = relay_cmd(*args)
    if not raw:
        return []
    tasks = parse_relay_table(raw)
    # Sort by id descending and take last_n
    try:
        tasks.sort(key=lambda t: int(t.get("id", 0)), reverse=True)
    except (ValueError, TypeError):
        pass
    return tasks[:last_n]


def fetch_agents() -> list[dict]:
    """Fetch registered agents."""
    raw = relay_cmd("agents")
    if not raw:
        return []
    return parse_relay_table(raw)


# ─── Summarization ────────────────────────────────────────────────────────────

def summarize_tasks(tasks: list[dict]) -> dict:
    """Generate a structured summary from a list of task dicts."""
    status_counts: dict[str, int] = {}
    completed: list[str] = []
    failed: list[str] = []
    pending: list[str] = []
    in_progress: list[str] = []

    for t in tasks:
        status = t.get("status", "unknown").strip('"')
        title = t.get("title", "(untitled)").strip('"')
        task_id = t.get("id", "?")

        status_counts[status] = status_counts.get(status, 0) + 1

        brief = f"#{task_id}: {title[:80]}"
        if status == "done":
            completed.append(brief)
        elif status == "failed":
            failed.append(brief)
        elif status in ("pending", "posted"):
            pending.append(brief)
        elif status == "in_progress":
            in_progress.append(brief)

    return {
        "total_tasks": len(tasks),
        "status_counts": status_counts,
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "in_progress": in_progress,
    }


def generate_summary_text(summary: dict, user_summary: str | None = None) -> str:
    """Produce a human-readable summary string."""
    parts = []

    if user_summary:
        parts.append(user_summary)
    else:
        parts.append("Session ended — auto-generated summary.")

    counts = summary["status_counts"]
    counts_str = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    parts.append(f"Task totals ({summary['total_tasks']}): {counts_str}")

    if summary["completed"]:
        parts.append(f"Completed ({len(summary['completed'])}):")
        for item in summary["completed"][:10]:
            parts.append(f"  ✓ {item}")
        if len(summary["completed"]) > 10:
            parts.append(f"  ... and {len(summary['completed']) - 10} more")

    if summary["failed"]:
        parts.append(f"Failed ({len(summary['failed'])}):")
        for item in summary["failed"][:5]:
            parts.append(f"  ✗ {item}")

    if summary["in_progress"]:
        parts.append(f"In progress ({len(summary['in_progress'])}):")
        for item in summary["in_progress"][:5]:
            parts.append(f"  ⟳ {item}")

    if summary["pending"]:
        parts.append(f"Pending ({len(summary['pending'])}):")
        for item in summary["pending"][:5]:
            parts.append(f"  ○ {item}")

    return "\n".join(parts)


# ─── Persistence ──────────────────────────────────────────────────────────────

def write_via_honcho(
    summary_text: str,
    accomplished: str,
    pending: str,
    blockers: str,
) -> bool:
    """Attempt to write the session summary through honcho_writeback.py.

    Returns True on success, False if Honcho is unavailable.
    """
    if not HONCHO_WRITEBACK.exists():
        print("  ⚠ honcho_writeback.py not found", file=sys.stderr)
        return False

    # Check if HONCHO_API_KEY is set — if not, honcho_writeback will fall back
    # to file anyway, so we go straight to our own fallback
    if not os.environ.get("HONCHO_API_KEY"):
        print("  ⚠ HONCHO_API_KEY not set — skipping Honcho writeback", file=sys.stderr)
        return False

    try:
        result = subprocess.run(
            [
                sys.executable, str(HONCHO_WRITEBACK),
                "--summary", summary_text,
                "--accomplished", accomplished,
                "--pending", pending,
                "--blockers", blockers,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            print("  ✓ Written to Honcho via honcho_writeback.py")
            return True
        else:
            print(f"  ⚠ honcho_writeback.py exited {result.returncode}: {result.stderr[:200]}", file=sys.stderr)
            return False
    except subprocess.TimeoutExpired:
        print("  ⚠ honcho_writeback.py timed out", file=sys.stderr)
        return False
    except Exception as exc:
        print(f"  ⚠ honcho_writeback.py error: {exc}", file=sys.stderr)
        return False


def write_fallback_json(payload: dict) -> Path:
    """Write session summary to logs/session_<timestamp>.json."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = LOGS_DIR / f"session_{ts}.json"
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"  ✓ Fallback session log written to {path}")
    return path


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Capture recent relay tasks and persist a session summary",
    )
    parser.add_argument(
        "--summary", "-s",
        default=None,
        help="Optional human-written session summary",
    )
    parser.add_argument(
        "--agent", "-a",
        default=None,
        help="Filter tasks by agent name (e.g., manuslocal)",
    )
    parser.add_argument(
        "--last", "-n",
        type=int, default=50,
        help="Number of recent tasks to include (default: 50)",
    )
    parser.add_argument(
        "--blockers", "-b",
        default="none",
        help="Current blockers",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the summary as JSON to stdout (no persistence)",
    )
    args = parser.parse_args()

    print("\n── SESSION CAPTURE ──")

    # 1. Fetch data from relay board
    print("Fetching tasks from relay board...")
    tasks = fetch_tasks(agent=args.agent, last_n=args.last)
    agents = fetch_agents()
    print(f"  Found {len(tasks)} tasks, {len(agents)} agents")

    # 2. Summarize
    task_summary = summarize_tasks(tasks)
    summary_text = generate_summary_text(task_summary, user_summary=args.summary)

    # Derive accomplished/pending strings
    accomplished = ", ".join(task_summary["completed"][:10]) or "n/a"
    pending_items = ", ".join(task_summary["pending"][:10]) or "n/a"

    # 3. Build full payload
    payload = {
        "session_summary": summary_text,
        "accomplished": accomplished,
        "pending_next_session": pending_items,
        "active_blockers": args.blockers,
        "task_summary": task_summary,
        "agents": agents,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "captured_by": "session_capture.py",
    }

    # JSON-only mode
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
        return

    # 4. Print human-readable summary
    print(f"\n{summary_text}\n")

    # 5. Attempt Honcho writeback, fall back to local JSON
    print("── PERSISTING ──")
    honcho_ok = write_via_honcho(
        summary_text=summary_text,
        accomplished=accomplished,
        pending=pending_items,
        blockers=args.blockers,
    )

    if not honcho_ok:
        write_fallback_json(payload)

    print("\n✓ Session capture complete\n")


if __name__ == "__main__":
    main()
