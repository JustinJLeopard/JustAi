#!/usr/bin/env python3
"""
JustAi — Discord Integration
==============================
Sends pipeline notifications to Discord via webhooks. Optionally listens
for commands via a bot token.

Two modes:
  1. Webhook-only (no bot token required) — push notifications
  2. Bot mode — listens for !justai commands in a channel

Setup:
    export JUSTAI_DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
    export JUSTAI_DISCORD_TOKEN=...       # optional, enables bot commands
    export JUSTAI_DISCORD_CHANNEL_ID=...  # required for bot mode

Usage:
    from justai.discord import notify, notify_stage, notify_complete

    notify("Pipeline started", title="Run #42")
    notify_stage("planner", "4 tasks generated", run_id="42")
    notify_complete(summary_dict)
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any, Optional

# ── Config ───────────────────────────────────────────────────────────────────

WEBHOOK_URL = os.environ.get("JUSTAI_DISCORD_WEBHOOK", "")
BOT_TOKEN = os.environ.get("JUSTAI_DISCORD_TOKEN", "")
CHANNEL_ID = os.environ.get("JUSTAI_DISCORD_CHANNEL_ID", "")
BOT_PREFIX = "!justai"

# Stage emoji mapping
STAGE_EMOJI = {
    "intent-gate": "\U0001f50d",   # 🔍
    "planner": "\U0001f4cb",       # 📋
    "reviewer": "\u2705",          # ✅
    "executor": "\u2699\ufe0f",    # ⚙️
    "delegator": "\U0001f4e4",     # 📤
    "synthesizer": "\U0001f4ca",   # 📊
    "checkpoint": "\U0001f6d1",    # 🛑
}

STATUS_EMOJI = {
    "complete": "\u2705",          # ✅
    "partial": "\u26a0\ufe0f",     # ⚠️
    "failed": "\u274c",            # ❌
    "blocked": "\U0001f6ab",       # 🚫
    "ambiguous": "\u2753",         # ❓
}


# ── Public API ───────────────────────────────────────────────────────────────

def is_configured() -> bool:
    """Check if Discord notifications are configured."""
    return bool(WEBHOOK_URL)


def notify(
    message: str,
    title: Optional[str] = None,
    color: int = 0xf43f5e,  # rose-500
    fields: Optional[list[dict]] = None,
) -> bool:
    """
    Send a Discord embed notification via webhook.

    Non-blocking — fires and forgets in a background thread.
    Returns True if the webhook URL is configured (not whether delivery succeeded).
    """
    if not WEBHOOK_URL:
        return False

    embed: dict[str, Any] = {
        "description": message,
        "color": color,
        "timestamp": _iso_now(),
        "footer": {"text": "JustAi Orchestrator"},
    }
    if title:
        embed["title"] = title
    if fields:
        embed["fields"] = fields

    _send_webhook_async({"embeds": [embed]})
    return True


def notify_stage(
    stage: str,
    detail: str,
    run_id: str = "",
    color: int = 0x94a3b8,  # text-secondary
) -> bool:
    """Send a stage transition notification."""
    emoji = STAGE_EMOJI.get(stage, "\u25b6\ufe0f")
    title = f"{emoji} {stage.replace('-', ' ').title()}"
    if run_id:
        title += f" — Run {run_id}"
    return notify(detail, title=title, color=color)


def notify_complete(
    summary: dict,
    run_id: str = "",
) -> bool:
    """Send a run completion notification with summary."""
    status = summary.get("status", "unknown")
    emoji = STATUS_EMOJI.get(status, "\u2754")
    color = {
        "complete": 0x10b981,   # emerald
        "partial": 0xf59e0b,    # amber
        "failed": 0xef4444,     # red
    }.get(status, 0x94a3b8)

    title = f"{emoji} Run {'#' + run_id if run_id else ''} — {status.title()}"

    fields = [
        {"name": "Goal", "value": summary.get("goal", "—")[:100], "inline": False},
        {"name": "Tasks", "value": f"{summary.get('done', 0)}/{summary.get('total', 0)} done", "inline": True},
        {"name": "Duration", "value": f"{summary.get('duration', 0):.1f}s", "inline": True},
    ]

    if summary.get("cost"):
        fields.append({"name": "Cost", "value": f"${summary['cost']:.4f}", "inline": True})

    return notify("", title=title, color=color, fields=fields)


def notify_error(
    message: str,
    stage: str = "",
    run_id: str = "",
    root_cause: str = "",
) -> bool:
    """Send a failure alert."""
    title = "\u274c Pipeline Error"
    if stage:
        title += f" at {stage}"
    if run_id:
        title += f" — Run {run_id}"

    fields = []
    if root_cause:
        fields.append({"name": "Root Cause", "value": root_cause[:200], "inline": False})

    return notify(message, title=title, color=0xef4444, fields=fields)


# ── Webhook Transport ────────────────────────────────────────────────────────

def _send_webhook(payload: dict) -> bool:
    """Send a payload to the Discord webhook. Blocking."""
    if not WEBHOOK_URL:
        return False
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)
    except Exception:
        return False


def _send_webhook_async(payload: dict) -> None:
    """Send webhook in background thread — non-blocking."""
    t = threading.Thread(target=_send_webhook, args=(payload,), daemon=True)
    t.start()


# ── Bot Listener (optional) ─────────────────────────────────────────────────

@dataclass
class BotCommand:
    command: str       # "run", "status", "health"
    args: str          # everything after the command
    channel_id: str
    author: str


def parse_bot_command(content: str) -> BotCommand | None:
    """Parse a Discord message into a BotCommand if it matches the prefix."""
    content = content.strip()
    if not content.lower().startswith(BOT_PREFIX):
        return None
    rest = content[len(BOT_PREFIX):].strip()
    if not rest:
        return BotCommand(command="help", args="", channel_id="", author="")
    parts = rest.split(None, 1)
    return BotCommand(
        command=parts[0].lower(),
        args=parts[1] if len(parts) > 1 else "",
        channel_id="",
        author="",
    )


def format_help() -> str:
    """Return the bot help message."""
    return (
        "**JustAi Bot Commands**\n"
        f"`{BOT_PREFIX} run \"goal\"` — Start a pipeline run\n"
        f"`{BOT_PREFIX} status` — Current pipeline status\n"
        f"`{BOT_PREFIX} health` — Service health check\n"
        f"`{BOT_PREFIX} help` — Show this message"
    )


# ── Orchestrator Hooks ──────────────────────────────────────────────────────

class OrchestratorHook:
    """
    Mixin for orchestrator to emit Discord notifications at each stage.

    Usage:
        hook = OrchestratorHook(run_id="42")
        hook.on_stage("planner", "4 tasks generated")
        hook.on_complete(summary_dict)
        hook.on_error("Plan rejected", stage="reviewer")
    """

    def __init__(self, run_id: str = ""):
        self.run_id = run_id
        self.enabled = is_configured()

    def on_stage(self, stage: str, detail: str) -> None:
        if self.enabled:
            notify_stage(stage, detail, run_id=self.run_id)

    def on_complete(self, summary: dict) -> None:
        if self.enabled:
            notify_complete(summary, run_id=self.run_id)

    def on_error(self, message: str, stage: str = "", root_cause: str = "") -> None:
        if self.enabled:
            notify_error(message, stage=stage, run_id=self.run_id, root_cause=root_cause)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
