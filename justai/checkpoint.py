#!/usr/bin/env python3
"""
JustAi — Checkpoint
====================
Human-in-the-loop gate logic. Implements R0-R3 risk levels.

Design principle (from spec): default posture is AUTONOMOUS.
Bother the human only when genuinely necessary. R2 and R3 are rare.

  R0 — no gate, proceed immediately
  R1 — notify only, auto-proceed after 60s unless vetoed via Discord
  R2 — hard gate, wait for explicit approval (Discord or dashboard)
  R3 — blocked, operator must manually unlock before anything proceeds

AUTO MODE (JUSTAI_AUTO_MODE=1 or --auto):
  R0 → proceed immediately (no change)
  R1 → proceed immediately (skip the 60s wait)
  R2 → still requires explicit approval
  R3 → still blocked

Discord integration: posts to DISCORD_RELAY_CHANNEL_ID if token is set.
If Discord is not configured, R1 auto-proceeds silently, R2/R3 block
until a local signal file is written by the operator.
"""
from __future__ import annotations

import os
import sys
import time
import json
from pathlib import Path

from justai.scope_planner import RiskLevel, Task

DISCORD_BOT_TOKEN = os.environ.get("RELAY_COORDINATOR_TOKEN", "")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_RELAY_CHANNEL_ID", "1491134768077865090")
R1_TIMEOUT_SECONDS = int(os.environ.get("JUSTAI_R1_TIMEOUT", "60"))
GATE_SIGNAL_DIR = Path(os.environ.get("JUSTAI_RUNTIME_ROOT", "/tmp/justai")) / "gates"


def _is_auto_mode() -> bool:
    """Check if auto mode is enabled (skip R1 waits)."""
    return os.environ.get("JUSTAI_AUTO_MODE", "").lower() in ("1", "true", "yes")


def _discord_notify(message: str) -> bool:
    """Post a message to Discord. Returns True if successful."""
    if not DISCORD_BOT_TOKEN:
        return False
    try:
        import urllib.request
        payload = json.dumps({"content": message}).encode()
        req = urllib.request.Request(
            f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages",
            data=payload,
            headers={
                "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
                "Content-Type": "application/json",
                "User-Agent": "DiscordBot (JustAi, 1.0)",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception:
        return False


def _gate_file(task_id: str) -> Path:
    GATE_SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    return GATE_SIGNAL_DIR / f"gate_{task_id}.json"


def _write_gate(task_id: str, status: str, reason: str = "") -> None:
    _gate_file(task_id).write_text(json.dumps({
        "task_id": task_id,
        "status": status,
        "reason": reason,
        "ts": time.time(),
    }))


def _read_gate(task_id: str) -> dict | None:
    gf = _gate_file(task_id)
    if gf.exists():
        try:
            return json.loads(gf.read_text())
        except Exception:
            return None
    return None


def evaluate(task: Task, task_id: str = "unknown") -> tuple[bool, str]:
    """
    Evaluate whether a task should proceed given its risk level.

    Returns (proceed: bool, reason: str).

    R0 → (True, "auto-approved")
    R1 → notify, wait up to 60s for veto, then (True, "auto-approved after timeout")
         In auto mode: (True, "R1 auto-approved (auto mode)") — no wait
    R2 → block until gate file written with status=approved
    R3 → always (False, "blocked — operator must manually unlock")
    """
    risk = task.risk

    # R0: no gate
    if risk == RiskLevel.R0:
        return True, "R0 auto-approved"

    # R1: notify and auto-proceed after timeout (or immediately in auto mode)
    if risk == RiskLevel.R1:
        if _is_auto_mode():
            return True, "R1 auto-approved (auto mode)"

        msg = (
            f"[JustAi R1] Task starting in {R1_TIMEOUT_SECONDS}s — veto to stop:\n"
            f"  **{task.title}**\n"
            f"  Risk: R1 (low — modifying existing code)\n"
            f"  To veto: write `{{\"status\": \"vetoed\"}}` to {_gate_file(task_id)}"
        )
        notified = _discord_notify(msg)
        if not notified:
            print(f"[checkpoint] R1: {task.title} — proceeding in {R1_TIMEOUT_SECONDS}s (Discord not configured)")

        deadline = time.time() + R1_TIMEOUT_SECONDS
        while time.time() < deadline:
            gate = _read_gate(task_id)
            if gate and gate.get("status") == "vetoed":
                return False, f"R1 vetoed: {gate.get('reason', 'no reason given')}"
            if gate and gate.get("status") == "approved":
                return True, "R1 manually approved"
            time.sleep(2)

        return True, f"R1 auto-approved after {R1_TIMEOUT_SECONDS}s"

    # R2: hard gate — wait indefinitely for approval
    if risk == RiskLevel.R2:
        msg = (
            f"[JustAi R2] **APPROVAL REQUIRED** before task executes:\n"
            f"  **{task.title}**\n"
            f"  Risk: R2 (interface/schema change)\n"
            f"  To approve: write `{{\"status\": \"approved\"}}` to {_gate_file(task_id)}\n"
            f"  To reject: write `{{\"status\": \"rejected\"}}`"
        )
        notified = _discord_notify(msg)
        if not notified:
            print(f"[checkpoint] R2 GATE: {task.title}")
            print(f"  Waiting for approval. Write to: {_gate_file(task_id)}")
            print(f'  Approve: echo \'{{"status":"approved"}}\' > {_gate_file(task_id)}')

        _write_gate(task_id, "pending")
        while True:
            gate = _read_gate(task_id)
            if gate and gate.get("status") == "approved":
                return True, "R2 approved by operator"
            if gate and gate.get("status") in ("rejected", "vetoed"):
                return False, f"R2 rejected: {gate.get('reason', 'no reason given')}"
            time.sleep(3)

    # R3: always blocked
    if risk == RiskLevel.R3:
        msg = (
            f"[JustAi R3] **BLOCKED** — task requires manual unlock:\n"
            f"  **{task.title}**\n"
            f"  R3 tasks never proceed automatically."
        )
        _discord_notify(msg)
        print(f"[checkpoint] R3 BLOCKED: {task.title}")
        print(f"  This task requires manual operator intervention.")
        return False, "R3 blocked — operator must manually unlock"

    return True, "unknown risk level — defaulting to proceed"
