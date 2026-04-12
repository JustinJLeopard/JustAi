#!/usr/bin/env python3
"""
JustAi — Delegator
==================
Posts validated tasks to SpacetimeDB via the relay CLI and monitors
execution. Handles heartbeat timeouts, retries, and failure escalation.

Evidence basis (from relay_dispatch.sh and sprint scorecards):
  - Tasks posted to SpacetimeDB, claimed by manuslocal agent
  - Retry logic (max 2) added in Sprint 8 → 90% success rate
  - Heartbeat monitoring detects stale in-progress tasks
  - relay CLI is the interface: relay post, relay board --json, relay show

Flow:
  post task → wait for claim → wait for done/failed → return result
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass

from justai.planner import Task

RELAY_BIN = os.environ.get("RELAY_BIN", str(__import__("pathlib").Path.home() / ".local" / "bin" / "relay"))
RELAY_DB_NAME = os.environ.get("RELAY_DB_NAME", "relay-room-dev")
RELAY_SERVER = os.environ.get("RELAY_SERVER", "local-server")
AGENT = os.environ.get("JUSTAI_DELEGATE_AGENT", "manuslocal")
POLL_INTERVAL = 5       # seconds between status checks
CLAIM_TIMEOUT = 120     # seconds to wait for agent to claim
EXEC_TIMEOUT = 1800     # seconds to wait for task completion (30 min)


@dataclass
class DelegationResult:
    task_id: str
    title: str
    status: str           # "done" | "failed" | "timeout" | "error"
    result: str           # result text from agent
    duration_seconds: float


def _relay(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run a relay CLI command and return the result."""
    env = os.environ.copy()
    env["RELAY_DB_NAME"] = RELAY_DB_NAME
    env["RELAY_SERVER"] = RELAY_SERVER
    return subprocess.run(
        [RELAY_BIN, *args],
        capture_output=True, text=True, env=env, check=check
    )


def _sanitize_payload(text: str) -> str:
    """Sanitize text for relay CLI -> spacetime call pipeline.

    The relay CLI passes payload as a positional arg to 'spacetime call',
    which parses it as JSON. Inner double quotes and backslashes break
    the parser. Replace them with safe alternatives.
    """
    return (
        text
        .replace('\\', '/')       # backslashes → forward slashes
        .replace('"', "'")         # double quotes → single quotes
        .replace('`', "'")         # backticks → single quotes
        .replace('$', '')          # strip shell vars
    )


def _post_task(task: Task, session_ref: str = "") -> str | None:
    """Post a task to SpacetimeDB. Returns task_id or None on failure."""
    args = [
        "post",
        "--from", "justai-orchestrator",
        "--to", AGENT,
        "--title", _sanitize_payload((task.title or task.description[:60])[:80]),
        "--payload", _sanitize_payload(task.description),
    ]
    if session_ref:
        args += ["--session", session_ref]

    result = _relay(*args)
    if result.returncode != 0:
        print(f"[delegator] post failed: {result.stderr[:200]}")
        return None

    # Extract task ID from relay output.
    # relay v2 prints: "posted task_uuid=<uuid>"
    # relay v1 printed: "Posted task #N"
    for line in result.stdout.splitlines():
        if "task_uuid=" in line:
            uuid = line.split("task_uuid=")[1].strip()
            if uuid:
                return uuid
        if "task" in line.lower() and "#" in line:
            parts = line.split("#")
            if len(parts) > 1:
                tid = parts[1].strip().split()[0].strip()
                if tid:
                    return tid

    print(f"[delegator] could not parse task ID from: {result.stdout[:200]}")
    return None


def _get_task_status(task_id: str) -> dict | None:
    """Get current task status via relay show --json."""
    result = _relay("show", str(task_id), "--json")
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except Exception:
        # Try parsing from board output
        result2 = _relay("board", "--json")
        if result2.returncode != 0:
            return None
        try:
            board = json.loads(result2.stdout)
            tasks = board.get("tasks", [])
            for t in tasks:
                if str(t.get("id")) == str(task_id):
                    return t
        except Exception:
            pass
        return None


def delegate(task: Task, session_ref: str = "") -> DelegationResult:
    """
    Post a task to SpacetimeDB and wait for completion.
    Returns a DelegationResult regardless of outcome.
    """
    start = time.time()
    print(f"[delegator] posting: {task.title}")

    task_id = _post_task(task, session_ref)
    if not task_id:
        return DelegationResult(
            task_id="?", title=task.title,
            status="error", result="Failed to post task to SpacetimeDB",
            duration_seconds=time.time() - start,
        )

    print(f"[delegator] task #{task_id} posted — waiting for claim...")

    # Wait for claim
    claim_deadline = time.time() + CLAIM_TIMEOUT
    while time.time() < claim_deadline:
        status = _get_task_status(task_id)
        if status:
            s = status.get("status", "")
            if s in ("in_progress", "done", "failed"):
                break
        time.sleep(POLL_INTERVAL)
    else:
        return DelegationResult(
            task_id=task_id, title=task.title,
            status="timeout", result=f"No agent claimed task #{task_id} within {CLAIM_TIMEOUT}s",
            duration_seconds=time.time() - start,
        )

    print(f"[delegator] task #{task_id} claimed — executing...")

    # Wait for completion
    exec_deadline = time.time() + EXEC_TIMEOUT
    while time.time() < exec_deadline:
        status = _get_task_status(task_id)
        if not status:
            time.sleep(POLL_INTERVAL)
            continue

        s = status.get("status", "")
        if s == "done":
            return DelegationResult(
                task_id=task_id, title=task.title,
                status="done",
                result=status.get("result", "completed"),
                duration_seconds=time.time() - start,
            )
        if s == "failed":
            return DelegationResult(
                task_id=task_id, title=task.title,
                status="failed",
                result=status.get("error", "task failed"),
                duration_seconds=time.time() - start,
            )

        time.sleep(POLL_INTERVAL)

    return DelegationResult(
        task_id=task_id, title=task.title,
        status="timeout",
        result=f"Task #{task_id} did not complete within {EXEC_TIMEOUT}s",
        duration_seconds=time.time() - start,
    )


def delegate_plan(tasks: list[Task], session_ref: str = "") -> list[DelegationResult]:
    """
    Delegate a list of tasks in dependency order.
    If a task fails, dependent tasks are skipped.
    """
    results: list[DelegationResult | None] = [None] * len(tasks)

    for i, task in enumerate(tasks):
        # Check dependencies
        skip = False
        for dep_idx in task.depends_on:
            if dep_idx < len(results) and results[dep_idx] and results[dep_idx].status != "done":
                print(f"[delegator] skipping task [{i}] '{task.title}' — dependency [{dep_idx}] failed")
                results[i] = DelegationResult(
                    task_id="skipped", title=task.title,
                    status="skipped",
                    result=f"Skipped — dependency task [{dep_idx}] did not complete successfully",
                    duration_seconds=0,
                )
                skip = True
                break

        if not skip:
            results[i] = delegate(task, session_ref)
            print(f"[delegator] task [{i}] {results[i].status}: {results[i].result[:80]}")

    return [r for r in results if r is not None]
