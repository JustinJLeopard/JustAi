#!/usr/bin/env python3
"""
bot_listener.py — Generic Agent Bot Listener for The Relay Room

Each agent runs its own instance of this script with its own bot token.
The bot connects to the Discord Gateway, listens for messages, and
dispatches them to the agent's action handler.

Usage:
    python bot_listener.py --agent codex
    python bot_listener.py --agent claudecli
    python bot_listener.py --agent manuslocal

Or via environment:
    AGENT_NAME=codex python bot_listener.py

The bot token is read from .env as <AGENT_NAME>_TOKEN (uppercased).
Example: CODEX_TOKEN=abc123...

Requirements:
    pip install discord.py python-dotenv pyyaml aiohttp

Architecture:
    ┌──────────────┐     Discord Gateway     ┌──────────────────┐
    │  Discord      │ ◄──────────────────────► │  bot_listener.py │
    │  Server       │    (WebSocket)           │  (per agent)     │
    │  #relay-room  │                          │                  │
    │  #standup     │                          │  → action_handler│
    │  #logs        │                          │  → heartbeat     │
    │  ...          │                          │  → lifecycle     │
    └──────────────┘                          └──────────────────┘
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord import app_commands
import yaml
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = SCRIPT_DIR / "server_config.yaml"
ENV_PATH = SCRIPT_DIR.parent / ".env"

RELAY_BIN = "/home/justinleopard/.local/bin/relay"
HEALTH_BASE_URL = os.environ.get("RELAY_HEALTH_BASE_URL", "http://127.0.0.1:8080")
RELAY_WEB_URL = os.environ.get("RELAY_WEB_URL", "http://127.0.0.1:8765")

# Channels this bot posts lifecycle events to
LOGS_CHANNEL = "logs"
HEARTBEAT_CHANNEL = "heartbeats"
ALERTS_CHANNEL = "alerts"
LOBBY_CHANNEL = "lobby"
RELAY_CHANNEL = "relay-room"

# Agent name → token env var mapping overrides (if different from convention)
PID_DIR = "/tmp"

TOKEN_OVERRIDES = {
    "relay-coordinator": "RELAY_COORDINATOR_TOKEN",
    "coworkclaude":     "COWORKCLAUDE_TOKEN",
    "coworkclaude":      "COWORKCLAUDE_TOKEN",
    "manus":             "MANUSLOCAL_TOKEN",
    "manuslocal":        "MANUSLOCAL_TOKEN",
    "claudecli":         "CLAUDECLI_TOKEN",
}

AGENT_METADATA = {
    "relay-coordinator": {
        "handler_type": "discord-bot",
        "capabilities": ["routing", "lifecycle"],
    },
    "codex": {
        "handler_type": "discord-bot",
        "capabilities": ["code-execution", "code-review"],
    },
    "manuslocal": {
        "handler_type": "discord-bot",
        "capabilities": ["task-execution", "file-ops"],
    },
    "coworkclaude": {
        "handler_type": "discord-bot",
        "capabilities": ["architecture", "planning"],
    },
    "claudecli": {
        "handler_type": "discord-bot",
        "capabilities": ["reasoning", "review", "delegation"],
    },
}


def get_token_env_var(agent_name: str) -> str:
    """Get the environment variable name for an agent's bot token."""
    if agent_name.lower() in TOKEN_OVERRIDES:
        return TOKEN_OVERRIDES[agent_name.lower()]
    return f"{agent_name.upper().replace('-', '_')}_TOKEN"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Async helpers
# ─────────────────────────────────────────────────────────────────────────────

async def run_command(*args, timeout: int = 30) -> tuple[str, int]:
    """Run a subprocess command asynchronously, return (output, exit_code)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return f"[timeout after {timeout}s]", 1
        return stdout.decode(errors="replace"), proc.returncode or 0
    except Exception as e:
        return f"[error: {e}]", 1


async def relay(*args, timeout: int = 15) -> tuple[str, int]:
    """Run relay CLI command."""
    env = os.environ.copy()
    env.setdefault("RELAY_SERVER", "local-server")
    target_file = SCRIPT_DIR.parent / ".relay-db-target"
    if "RELAY_DB_NAME" not in env and target_file.exists():
        env["RELAY_DB_NAME"] = target_file.read_text(encoding="utf-8").strip()

    try:
        proc = await asyncio.create_subprocess_exec(
            RELAY_BIN,
            *args,
            cwd=str(SCRIPT_DIR.parent),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return f"[timeout after {timeout}s]", 1
        return stdout.decode(errors="replace"), proc.returncode or 0
    except Exception as e:
        return f"[error: {e}]", 1


async def bash(command: str, timeout: int = 30) -> tuple[str, int]:
    """Run a bash command in WSL."""
    return await run_command("bash", "-c", command, timeout=timeout)


def parse_pipe_table(text: str) -> tuple[list[str], list[dict[str, str]]]:
    rows: list[list[str]] = []
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
    data: list[dict[str, str]] = []
    for row in rows[1:]:
        record: dict[str, str] = {}
        for index, header in enumerate(headers):
            if header:
                record[header] = row[index].strip() if index < len(row) else ""
        data.append(record)
    return headers, data


def extract_section(text: str, start_label: str, end_labels: tuple[str, ...]) -> str:
    lines: list[str] = []
    active = False
    for raw in text.splitlines():
        line = raw.strip()
        if line == start_label:
            active = True
            continue
        if active and line in end_labels:
            break
        if active:
            lines.append(raw)
    return "\n".join(lines)


def truncate(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(limit - 3, 0)] + "..."


def summarize_agent_rows(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "no agents returned"
    lines = []
    for row in rows[:8]:
        name = row.get("name") or row.get("agent") or "unknown"
        status = row.get("status", "unknown")
        current_task = row.get("current_task_id") or row.get("task_id") or "0"
        lines.append(f"{name}: {status} (task {current_task})")
    if len(rows) > 8:
        lines.append(f"and {len(rows) - 8} more...")
    return "\n".join(lines)


def _extract_task_id(text: str) -> str:
    """Extract the first relay task id from command output."""
    match = re.search(r"\bid=(\d+)\b", text)
    if match:
        return match.group(1)
    match = re.search(r"\btask\s+(\d+)\b", text, re.IGNORECASE)
    if match:
        return match.group(1)
    for line in text.splitlines():
        digits = re.findall(r"\b\d+\b", line)
        if digits:
            return digits[0]
    return ""


def _extract_status_row(output: str) -> dict[str, str]:
    """Return the first task row from a relay show/board output."""
    _, rows = parse_pipe_table(output)
    if rows:
        return rows[0]
    return {}


def summarize_task_rows(rows: list[dict[str, str]], limit: int = 10) -> str:
    if not rows:
        return "no rows"
    lines = []
    for row in rows[:limit]:
        task_id = row.get("id", "?")
        status = row.get("status", "unknown")
        assignee = row.get("to_agent", row.get("claimed_by", ""))
        title = truncate(row.get("title", ""), 56)
        lines.append(f"#{task_id} [{status}] {assignee}: {title}")
    if len(rows) > limit:
        lines.append(f"and {len(rows) - limit} more...")
    return "\n".join(lines)


def summarize_board_tasks(rows: list[dict[str, str]], limit: int = 8) -> str:
    if not rows:
        return "no active tasks"
    lines = []
    for row in rows[:limit]:
        task_id = row.get("id", "?")
        status = row.get("status", "unknown")
        to_agent = row.get("to_agent", "unknown")
        title = truncate(row.get("title", ""), 80) or "(untitled)"
        retry_count = str(row.get("retry_count", "0"))
        retry_suffix = ""
        if retry_count.isdigit() and int(retry_count) > 0:
            retry_suffix = f" · retry {retry_count}"
        lines.append(f"#{task_id} [{status}] {to_agent} · {title}{retry_suffix}")
    if len(rows) > limit:
        lines.append(f"+{len(rows) - limit} more task(s) in relay_web")
    return "\n".join(lines)


def parse_status_counts(board_text: str) -> dict[str, int]:
    counts = {"active": 0, "done_failed": 0, "archived": 0}
    for key, pattern in (
        ("active", r"--- Total active tasks: (\d+) ---"),
        ("done_failed", r"--- Total done/failed tasks: (\d+) ---"),
        ("archived", r"--- Total archived tasks: (\d+) ---"),
    ):
        match = re.search(pattern, board_text)
        if match:
            counts[key] = int(match.group(1))
    return counts


# ─────────────────────────────────────────────────────────────────────────────
# Action Handlers — customize per agent
# ─────────────────────────────────────────────────────────────────────────────

class ActionHandler:
    """
    Base action handler. Subclass this for agent-specific behavior.
    """

    def __init__(self, agent_name: str, bot: "AgentBot"):
        self.agent_name = agent_name
        self.bot = bot

    async def handle_message(self, message: discord.Message):
        """Called for every message in channels this agent can see."""
        if message.author == self.bot.user:
            return

        channel = message.channel.name if hasattr(message.channel, 'name') else "DM"
        print(f"  [{channel}] {message.author.display_name}: {message.content[:120]}")

        if self.bot.user.mentioned_in(message):
            await self.handle_mention(message)

        if channel == LOGS_CHANNEL:
            await self.handle_lifecycle_event(message)

    async def handle_mention(self, message: discord.Message):
        """Called when this agent is @mentioned."""
        print(f"  📣 Mentioned by {message.author.display_name}: {message.content[:120]}")

    async def handle_lifecycle_event(self, message: discord.Message):
        """Called for messages in #logs."""
        content = message.content
        if content.startswith("[SESSION]"):
            event_type = content.split("|")[0].strip().replace("[SESSION]", "").strip()
            print(f"  🔄 Lifecycle event: {event_type} from {message.author.display_name}")

    async def on_boot(self):
        pass


def _extract_payload_for_task(tasks_output: str, task_id: str) -> str:
    """Extract payload for a specific task_id from `relay tasks` tabular output."""
    for line in tasks_output.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if parts and parts[0].strip() == task_id and len(parts) >= 7:
            payload = parts[6].strip().strip('"')
            if payload:
                return payload
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# ClaudeHandler — Judgment Layer
# ─────────────────────────────────────────────────────────────────────────────

CLAUDE_SYSTEM_PROMPT = """\
You are claudecli, the judgment and reasoning layer in the relay-room agent pipeline running on WSL Ubuntu.

Your role is NOT to execute code directly. Your role is to be the quality gate throughout the pipeline:

1. INTAKE — When you receive a task, assess whether it is well-specified. If not, clarify it.
2. DECOMPOSE — Break vague or large tasks into precise, scoped subtasks that mini-swe-agent can execute.
3. DELEGATE — Issue relay_post actions to route work to the right agent (manuslocal for mini execution, codex for code writing).
4. REVIEW — When mini completes a task, evaluate whether the output actually solves the problem, not just the literal prompt.
5. CORRECT — If something is wrong, incomplete, or missed the point, issue follow-up tasks. Don't just accept "done".

The other agents:
- localmanus / mini: the executor. Runs code, reads/writes files, runs shell commands. Best for well-scoped tasks.
- codex: code-writing specialist. Called by mini via codex-delegate. For complex coding tasks.
- relay-coordinator: orchestrates relay board. Handles routing.

Your tools (respond ONLY with valid JSON):
{
  "reasoning": "your step-by-step thinking about the task",
  "verdict": "proceed | needs_clarification | reject | review_failed | review_passed",
  "actions": [
    {"type": "relay_post", "to": "manuslocal", "title": "short title", "payload": "full task description for mini"},
    {"type": "relay_done", "task_id": "ID", "result": "summary of what was accomplished"},
    {"type": "relay_fail", "task_id": "ID", "error": "reason"},
    {"type": "bash", "command": "command to run for context gathering only"},
    {"type": "discord_reply", "channel": "relay-room", "message": "what to post in Discord"},
    {"type": "wait_for_completion", "note": "task posted, monitoring for result"}
  ]
}

Be decisive. Be brief in reasoning. Be precise in actions. You are the one agent that should always ask "but is this actually right?"\
"""


class ClaudeHandler(ActionHandler):
    """
    Judgment layer for claudecli.

    - Polls relay inbox every 30s for tasks assigned to claudecli
    - Calls claude-opus-4-6 via LiteLLM for reasoning
    - Executes structured actions (relay_post, bash, discord_reply, etc.)
    - Monitors #relay-room for task completions to trigger post-execution review
    """

    INBOX_POLL_INTERVAL = 30   # seconds between inbox checks
    LITELLM_URL = "http://localhost:4000/v1/chat/completions"
    LITELLM_HEALTH_URL = "http://localhost:4000/health"
    MODEL = "claude-opus-4-6"
    MAX_TOKENS = 2048

    # Task IDs we've dispatched to mini, waiting for completion
    _pending_review: dict  # task_id -> {"original_task": str, "mini_task_id": str}

    def __init__(self, agent_name: str, bot: "AgentBot"):
        super().__init__(agent_name, bot)
        self._pending_review = {}
        self._processing_tasks: set = set()   # avoid double-processing
        self._degraded_mode_announced = False

    async def on_boot(self):
        print("  🧠 Claude handler initialized — ready for reasoning tasks")
        asyncio.ensure_future(self._inbox_poll_loop())

    # ── Inbox polling ─────────────────────────────────────────────────────

    async def _inbox_poll_loop(self):
        await asyncio.sleep(10)  # let bot settle first
        while not self.bot.is_closed():
            try:
                await self._check_inbox()
            except Exception as e:
                print(f"  ⚠ claudecli inbox poll error: {e}")
            await asyncio.sleep(self.INBOX_POLL_INTERVAL)

    async def _check_inbox(self):
        output, code = await relay("tasks", "--to", "claudecli", "--status", "pending")
        task_ids = self._parse_task_ids(output)
        for task_id in task_ids:
            if task_id not in self._processing_tasks:
                self._processing_tasks.add(task_id)
                asyncio.ensure_future(self._handle_relay_task(task_id))

    def _parse_task_ids(self, output: str) -> list[str]:
        ids = []
        for line in output.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if parts and re.match(r"^\d+$", parts[0]):
                ids.append(parts[0])
        return ids

    # ── Task processing ───────────────────────────────────────────────────

    async def _handle_relay_task(self, task_id: str):
        """Claim, reason about, and act on a relay task assigned to claudecli."""
        print(f"  📥 claudecli handling relay task {task_id}")

        # Claim it
        _, code = await relay("claim", task_id, "--as", "claudecli")
        if code != 0:
            self._processing_tasks.discard(task_id)
            return
        await relay("start", task_id, "--as", "claudecli")
        await self.bot.set_relay_status("busy", int(task_id))

        try:
            # Get payload
            show_output, _ = await relay("show", task_id)
            payload = self._extract_payload(show_output)
            if not payload:
                await relay("fail", task_id, "--as", "claudecli", "--error", "empty payload")
                self._processing_tasks.discard(task_id)
                return

            print(f"  🤔 Reasoning about task {task_id}: {payload[:80]}...")

            # Gather context
            context = await self._gather_context(payload)

            # Call Claude
            if not await self._litellm_available():
                await self._degrade_to_manuslocal(task_id, payload, "LiteLLM unreachable")
                self._processing_tasks.discard(task_id)
                return

            response = await self._call_claude(payload, context, task_id)
            if not response:
                await self._degrade_to_manuslocal(task_id, payload, "Claude reasoning unavailable")
                self._processing_tasks.discard(task_id)
                return

            # Execute actions
            await self._execute_response(task_id, payload, response)
            self._processing_tasks.discard(task_id)
        finally:
            await self.bot.set_relay_status("online")

    def _extract_payload(self, show_output: str) -> str:
        """Parse payload from `relay show <id>` output."""
        for line in show_output.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 7 and re.match(r"^\d+$", parts[0]):
                payload = parts[6].strip().strip('"')
                if payload:
                    return payload
        # Fallback: look for Payload: line
        for line in show_output.splitlines():
            if line.strip().lower().startswith("payload"):
                return line.split(":", 1)[-1].strip().strip('"')
        return ""

    # ── Context gathering ─────────────────────────────────────────────────

    async def _gather_context(self, task: str) -> str:
        """Gather lightweight context to help Claude reason about the task."""
        parts = []

        # Recent relay board state
        board_out, _ = await relay("board")
        if board_out.strip():
            parts.append(f"RELAY BOARD:\n{board_out[:500]}")

        # Recent dispatch log
        log_out, _ = await bash("tail -10 /tmp/relay_dispatch.log 2>/dev/null || echo 'no log'")
        if log_out.strip():
            parts.append(f"RECENT DISPATCH:\n{log_out[:300]}")

        return "\n\n".join(parts)

    async def _litellm_available(self) -> bool:
        """Check whether LiteLLM is reachable before attempting reasoning."""
        try:
            import aiohttp
        except ImportError:
            output, code = await bash("curl -s -o /dev/null -w '%{http_code}' http://localhost:4000/health", timeout=5)
            status = (output or "").strip()
            return code == 0 and status in {"200", "401"}

        try:
            timeout = aiohttp.ClientTimeout(total=3)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.LITELLM_HEALTH_URL) as resp:
                    return resp.status in (200, 401)
        except Exception as e:
            print(f"  ⚠ LiteLLM health check failed: {e}")
            return False

    async def _degrade_to_manuslocal(self, task_id: str, payload: str, reason: str):
        """Fallback path when claudecli cannot use its reasoning layer."""
        print(f"  ⚠ claudecli degraded mode: {reason}")
        out, code = await relay(
            "post",
            "--from", "claudecli",
            "--to", "manuslocal",
            "--title", f"claudecli fallback {task_id}",
            "--payload", payload,
        )
        if not self._degraded_mode_announced:
            self._degraded_mode_announced = True
            await self._post_to_channel(
                RELAY_CHANNEL,
                "**[claudecli]** claudecli operating without reasoning layer (LiteLLM unreachable)"
            )

        if code == 0:
            summary = f"Degraded mode: routed task to manuslocal because {reason.lower()}"
            await relay("done", task_id, "--as", "claudecli", "--result", summary)
        else:
            await relay("fail", task_id, "--as", "claudecli", "--error", f"{reason}; fallback relay_post failed: {out[:160]}")

    # ── Claude API call ───────────────────────────────────────────────────

    async def _call_claude(self, task: str, context: str, task_id: str) -> dict | None:
        """Call claude-opus-4-6 via LiteLLM and return parsed JSON response."""
        try:
            import aiohttp
        except ImportError:
            print("  ⚠ aiohttp not installed — falling back to httpx or urllib")
            return await self._call_claude_urllib(task, context, task_id)

        litellm_key = os.getenv("LITELLM_KEY", "")
        user_content = f"TASK ID: {task_id}\n\nTASK:\n{task}"
        if context:
            user_content += f"\n\nCONTEXT:\n{context}"

        payload = {
            "model": self.MODEL,
            "messages": [
                {"role": "system", "content": CLAUDE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": self.MAX_TOKENS,
        }
        headers = {
            "Authorization": f"Bearer {litellm_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.LITELLM_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        print(f"  ⚠ LiteLLM error {resp.status}: {text[:200]}")
                        return None
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return self._parse_json_response(content)
        except Exception as e:
            print(f"  ⚠ Claude API call failed: {e}")
            return None

    async def _call_claude_urllib(self, task: str, context: str, task_id: str) -> dict | None:
        """Fallback: call LiteLLM via subprocess curl."""
        litellm_key = os.getenv("LITELLM_KEY", "")
        user_content = f"TASK ID: {task_id}\n\nTASK:\n{task}"
        if context:
            user_content += f"\n\nCONTEXT:\n{context}"

        payload = {
            "model": self.MODEL,
            "messages": [
                {"role": "system", "content": CLAUDE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": self.MAX_TOKENS,
        }
        payload_json = json.dumps(payload).replace("'", "'\\''")
        cmd = (
            f"curl -s -X POST {self.LITELLM_URL} "
            f"-H 'Authorization: Bearer {litellm_key}' "
            f"-H 'Content-Type: application/json' "
            f"-d '{payload_json}'"
        )
        output, code = await bash(cmd, timeout=60)
        if code != 0:
            print(f"  ⚠ curl Claude call failed: {output[:200]}")
            return None
        try:
            data = json.loads(output)
            content = data["choices"][0]["message"]["content"]
            return self._parse_json_response(content)
        except Exception as e:
            print(f"  ⚠ Failed to parse Claude response: {e}\n{output[:200]}")
            return None

    def _parse_json_response(self, content: str) -> dict | None:
        """Parse Claude's JSON response, tolerating markdown fences."""
        # Strip markdown code fences if present
        content = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.MULTILINE)
        content = re.sub(r"\s*```$", "", content.strip(), flags=re.MULTILINE)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try extracting JSON object from surrounding text
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
            print(f"  ⚠ Could not parse Claude JSON response:\n{content[:300]}")
            return None

    # ── Action execution ──────────────────────────────────────────────────

    async def _execute_response(self, task_id: str, original_task: str, response: dict):
        """Execute the structured actions from Claude's response."""
        reasoning = response.get("reasoning", "")
        verdict = response.get("verdict", "proceed")
        actions = response.get("actions", [])

        print(f"  💭 Verdict: {verdict}")
        print(f"  💭 Reasoning: {reasoning[:200]}")

        task_done = False

        for action in actions:
            action_type = action.get("type", "")

            if action_type == "relay_post":
                to_agent = action.get("to", "manuslocal")
                title = action.get("title", "claudecli subtask")
                payload = action.get("payload", original_task)
                out, code = await relay("post", "--from", "claudecli", "--to", to_agent, "--title", title, "--payload", payload)
                print(f"  📤 relay post → {to_agent}: {title[:60]} (exit {code})")
                if code != 0:
                    print(f"     ⚠ relay post error: {out[:300]}")
                # Extract new task ID for tracking
                new_id = re.search(r"\b(\d{4,})\b", out)
                if new_id:
                    self._pending_review[new_id.group(1)] = {
                        "original_task_id": task_id,
                        "original_task": original_task,
                    }
                    print(f"  👁  Watching mini task {new_id.group(1)} for review")

            elif action_type == "relay_done":
                result = action.get("result", "completed")
                await relay("done", task_id, "--as", "claudecli", "--result", result)
                print(f"  ✅ relay done: {task_id}")
                task_done = True

            elif action_type == "relay_fail":
                error = action.get("error", "unknown")
                await relay("fail", task_id, "--as", "claudecli", "--error", error)
                print(f"  ❌ relay fail: {task_id} — {error}")
                task_done = True

            elif action_type == "bash":
                command = action.get("command", "")
                if command:
                    out, code = await bash(command, timeout=20)
                    print(f"  🔧 bash: {command[:60]} → exit {code}")
                    print(f"     {out[:200]}")

            elif action_type == "discord_reply":
                channel_name = action.get("channel", RELAY_CHANNEL)
                message_text = action.get("message", "")
                if message_text:
                    await self._post_to_channel(channel_name, f"**[claudecli]** {message_text}")

            elif action_type == "wait_for_completion":
                note = action.get("note", "")
                print(f"  ⏳ Waiting for completion: {note}")
                # Don't mark task done yet — will review when mini finishes

        # If Claude didn't explicitly call relay_done/fail but verdict says done
        if not task_done and verdict in ("review_passed", "needs_clarification"):
            result_msg = f"Judgment complete ({verdict}): {reasoning[:150]}"
            await relay("done", task_id, "--as", "claudecli", "--result", result_msg)

        # Always post verdict summary to Discord (unless Claude already posted one via discord_reply action)
        has_discord_action = any(a.get("type") == "discord_reply" for a in actions)
        if not has_discord_action:
            emoji = {"proceed": "▶️", "review_passed": "✅", "review_failed": "❌",
                     "needs_clarification": "❓", "reject": "🚫"}.get(verdict, "🔷")
            auto_msg = f"{emoji} **[claudecli]** Task `{task_id}` → `{verdict}` | {reasoning[:140]}"
            await self._post_to_channel(RELAY_CHANNEL, auto_msg)

    async def _post_to_channel(self, channel_name: str, message: str):
        ch = self.bot.get_channel_by_name(channel_name)
        if ch:
            try:
                await ch.send(message)
                print(f"  💬 Posted to #{channel_name}: {message[:100]}")
            except discord.HTTPException as e:
                print(f"  ⚠ Discord send failed on #{channel_name}: {e}")
        else:
            available = [c.name for c in self.bot.guild.text_channels] if self.bot.guild else []
            print(f"  ⚠ discord_reply: channel #{channel_name} not found")
            print(f"     Available channels: {available}")

    # ── Post-execution review (Discord monitoring) ────────────────────────

    async def handle_message(self, message: discord.Message):
        """Intercept task completion messages for post-execution review."""
        await super().handle_message(message)

        # Watch for relay-coordinator done/fail messages
        content = message.content
        channel = message.channel.name if hasattr(message.channel, 'name') else ""
        if channel != RELAY_CHANNEL:
            return

        # Detect [TASK DONE] or similar patterns from relay-coordinator
        done_match = re.search(r"\[DONE\].*?task[:\s]+(\d+)", content, re.IGNORECASE)
        if not done_match:
            done_match = re.search(r"task\s+(\d+)\s+(?:DONE|completed)", content, re.IGNORECASE)

        if done_match:
            completed_id = done_match.group(1)
            if completed_id in self._pending_review:
                review_info = self._pending_review.pop(completed_id)
                asyncio.ensure_future(
                    self._review_completion(completed_id, content, review_info)
                )

    async def _review_completion(self, mini_task_id: str, completion_msg: str, review_info: dict):
        """Review a mini task completion for correctness."""
        original_task = review_info.get("original_task", "unknown")
        original_task_id = review_info.get("original_task_id", "")
        print(f"  🔍 Reviewing completion of mini task {mini_task_id}...")

        # Get full task result
        show_out, _ = await relay("show", mini_task_id)

        context = f"ORIGINAL TASK:\n{original_task}\n\nCOMPLETION MESSAGE:\n{completion_msg}\n\nTASK DETAIL:\n{show_out[:500]}"

        review_prompt = (
            f"Mini-swe-agent just completed task {mini_task_id}. "
            f"Review whether the result actually satisfies the original requirement. "
            f"If it does, issue relay_done for the parent task. "
            f"If it doesn't or is incomplete, issue relay_post to correct it."
        )

        response = await self._call_claude(review_prompt, context, original_task_id or mini_task_id)
        if response:
            await self._execute_response(original_task_id or mini_task_id, original_task, response)
            await self._post_to_channel(
                RELAY_CHANNEL,
                f"Reviewed task {mini_task_id}: **{response.get('verdict', '?')}** — {response.get('reasoning', '')[:120]}"
            )

    # ── Mention handling ──────────────────────────────────────────────────

    async def handle_mention(self, message: discord.Message):
        """Respond to @claudecli mentions with Claude's reasoning."""
        await super().handle_mention(message)

        # Strip mention tokens
        content = re.sub(r"<@!?\d+>", "", message.content).strip()
        if not content:
            return

        print(f"  💬 Reasoning about mention: {content[:80]}")
        context = f"This is a direct Discord mention in #{message.channel.name if hasattr(message.channel, 'name') else 'DM'}."
        response = await self._call_claude(content, context, f"mention-{message.id}")

        if response:
            reasoning = response.get("reasoning", "")
            verdict = response.get("verdict", "")
            reply = f"**[claudecli]** {reasoning[:400]}"
            if verdict:
                reply += f"\n→ verdict: `{verdict}`"
            try:
                await message.reply(reply)
            except discord.HTTPException:
                await self._post_to_channel(
                    message.channel.name if hasattr(message.channel, 'name') else RELAY_CHANNEL,
                    reply
                )

            # Execute any actions from the mention response
            if response.get("actions"):
                await self._execute_response(
                    f"mention-{message.id}", content, response
                )


# ─────────────────────────────────────────────────────────────────────────────
# Other Agent Handlers
# ─────────────────────────────────────────────────────────────────────────────

class CodexHandler(ActionHandler):
    INBOX_POLL_INTERVAL = 30

    def __init__(self, agent_name: str, bot: "AgentBot"):
        super().__init__(agent_name, bot)
        self._processing_tasks: set = set()

    async def handle_mention(self, message: discord.Message):
        await super().handle_mention(message)

    async def on_boot(self):
        print("  💻 CodexHandler initialized — relay inbox polling via ml mini")
        asyncio.ensure_future(self._inbox_poll_loop())

    async def _inbox_poll_loop(self):
        await asyncio.sleep(20)  # stagger relative to claudecli (10s) and manuslocal (15s)
        while not self.bot.is_closed():
            try:
                await self._check_inbox()
            except Exception as e:
                print(f"  ⚠ codex inbox poll error: {e}")
            await asyncio.sleep(self.INBOX_POLL_INTERVAL)

    async def _check_inbox(self):
        output, code = await relay("tasks", "--to", "codex", "--status", "pending")
        print(f"  📬 codex inbox poll: {output.strip()[:120] or 'no pending tasks'}")
        for task_id in re.findall(r"(\d{4,})", output):
            if task_id not in self._processing_tasks:
                self._processing_tasks.add(task_id)
                asyncio.ensure_future(self._handle_relay_task(task_id))

    async def _handle_relay_task(self, task_id: str):
        print(f"  📥 codex handling relay task {task_id}")
        await relay("claim", task_id, "--as", "codex")
        await relay("start", task_id, "--as", "codex")
        await self.bot.set_relay_status("busy", int(task_id))
        try:
            # Get full task row to extract payload
            out2, _ = await relay("tasks", "--to", "codex", "--status", "claimed")
            payload = _extract_payload_for_task(out2, task_id) or f"relay task {task_id}"
            print(f"  💻 ml mini (codex route): {payload[:80]}...")
            out, code = await run_command("ml", "mini", payload, timeout=600)
            print(f"  {'✅' if code == 0 else '❌'} codex exit {code}: {out[:150]}")
            if code == 0:
                await relay("done", task_id, "--as", "codex", "--result", out.strip()[-200:] or "done")
            else:
                await relay("fail", task_id, "--as", "codex", "--error", out[:200])
            self._processing_tasks.discard(task_id)
        finally:
            await self.bot.set_relay_status("online")


class ManusHandler(ActionHandler):
    INBOX_POLL_INTERVAL = 30

    def __init__(self, agent_name: str, bot: "AgentBot"):
        super().__init__(agent_name, bot)
        self._processing_tasks: set = set()

    async def handle_mention(self, message: discord.Message):
        await super().handle_mention(message)

    async def on_boot(self):
        print("  ⚙  ManusHandler initialized — relay inbox polling via ml mini")
        asyncio.ensure_future(self._inbox_poll_loop())

    async def _inbox_poll_loop(self):
        await asyncio.sleep(15)  # stagger relative to claudecli (10s)
        while not self.bot.is_closed():
            try:
                await self._check_inbox()
            except Exception as e:
                print(f"  ⚠ manuslocal inbox poll error: {e}")
            await asyncio.sleep(self.INBOX_POLL_INTERVAL)

    async def _check_inbox(self):
        output, code = await relay("tasks", "--to", "manuslocal", "--status", "pending")
        print(f"  📬 manuslocal inbox poll: {output.strip()[:120] or 'no pending tasks'}")
        for task_id in re.findall(r"(\d{4,})", output):
            if task_id not in self._processing_tasks:
                self._processing_tasks.add(task_id)
                asyncio.ensure_future(self._handle_relay_task(task_id))

    async def _handle_relay_task(self, task_id: str):
        print(f"  📥 manuslocal handling relay task {task_id}")
        await relay("claim", task_id, "--as", "manuslocal")
        await relay("start", task_id, "--as", "manuslocal")
        await self.bot.set_relay_status("busy", int(task_id))
        try:
            out2, _ = await relay("tasks", "--to", "manuslocal", "--status", "claimed")
            payload = _extract_payload_for_task(out2, task_id) or f"relay task {task_id}"
            print(f"  ⚙  ml mini (manuslocal): {payload[:80]}...")
            out, code = await run_command("ml", "mini", payload, timeout=300)
            print(f"  {'✅' if code == 0 else '❌'} manuslocal exit {code}: {out[:150]}")
            if code == 0:
                await relay("done", task_id, "--as", "manuslocal", "--result", out.strip()[-200:] or "done")
            else:
                await relay("fail", task_id, "--as", "manuslocal", "--error", out[:200])
            self._processing_tasks.discard(task_id)
        finally:
            await self.bot.set_relay_status("online")


class CoworkClaudeHandler(ActionHandler):
    async def handle_mention(self, message: discord.Message):
        await super().handle_mention(message)

    async def on_boot(self):
        print("  🏗️  Cowork-Claude handler initialized — architecture mode")


# Registry of handlers
HANDLERS = {
    "relay-coordinator": ActionHandler,
    "codex":             CodexHandler,
    "manuslocal":        ManusHandler,
    "coworkclaude":      CoworkClaudeHandler,
    "claudecli":         ClaudeHandler,
}


# ─────────────────────────────────────────────────────────────────────────────
# The Bot
# ─────────────────────────────────────────────────────────────────────────────

class AgentBot(discord.Client):
    """
    Discord bot that listens on behalf of a single agent.
    """

    def __init__(self, agent_name: str, guild_id: int, config: dict):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)

        self.agent_name = agent_name
        self.guild_id = guild_id
        self.config = config
        self.guild: discord.Guild | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._relay_post_watch_task: asyncio.Task | None = None
        self._relay_post_watchers: dict[str, dict[str, str]] = {}
        self._boot_time = datetime.now(timezone.utc)
        self.tree = app_commands.CommandTree(self)
        self._relay_slash_commands_synced = False

        handler_cls = HANDLERS.get(agent_name.lower(), ActionHandler)
        self.handler = handler_cls(agent_name, self)
        if self.agent_name.lower() == "relay-coordinator":
            self._register_relay_commands()

    def get_channel_by_name(self, name: str) -> discord.TextChannel | None:
        if not self.guild:
            return None
        for ch in self.guild.text_channels:
            if ch.name == name:
                return ch
        return None

    async def emit_lifecycle(self, event: str, detail: str = ""):
        ch = self.get_channel_by_name(LOGS_CHANNEL)
        if not ch:
            print(f"  ⚠ #{LOGS_CHANNEL} not found, skipping lifecycle emit")
            return
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        msg = f"[SESSION] {event} | {self.agent_name} | {detail} | {ts}"
        await ch.send(msg)
        print(f"  → Emitted: {event}")

    async def register_with_relay(self):
        meta = AGENT_METADATA.get(
            self.agent_name,
            {"handler_type": "discord-bot", "capabilities": []},
        )
        out, code = await relay(
            "register",
            self.agent_name,
            "--handler-type",
            meta["handler_type"],
            "--caps",
            ",".join(meta["capabilities"]),
        )
        if code == 0:
            print(f"  📝 relay register ok: {self.agent_name}")
        else:
            print(f"  ⚠ relay register failed for {self.agent_name}: {out[:200]}")

    async def emit_relay_heartbeat(self):
        out, code = await relay("heartbeat", self.agent_name)
        if code != 0:
            print(f"  ⚠ relay heartbeat failed for {self.agent_name}: {out[:200]}")

    async def set_relay_status(self, status: str, current_task: int = 0):
        out, code = await relay(
            "agent-status",
            self.agent_name,
            "--status",
            status,
            "--task",
            str(current_task),
        )
        if code != 0:
            print(f"  ⚠ relay agent-status failed for {self.agent_name}: {out[:200]}")

    def _register_relay_commands(self):
        relay_group = app_commands.Group(
            name="relay",
            description="Relay Room slash commands",
        )
        self.tree.add_command(relay_group)

        @relay_group.command(name="status", description="Show relay health")
        async def relay_status(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True, ephemeral=True)
            try:
                embed = await self._build_status_embed()
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as exc:
                print(f"  ⚠ /relay status failed: {exc}")
                await interaction.followup.send(
                    embed=self._error_embed("/relay status failed", str(exc)),
                    ephemeral=True,
                )

        @relay_group.command(name="board", description="Show the relay task board")
        @app_commands.rename(all_="all")
        @app_commands.describe(all_="Show completed and archived tasks too")
        async def relay_board(interaction: discord.Interaction, all_: bool = False):
            await interaction.response.defer(thinking=True, ephemeral=True)
            try:
                embed = await self._build_board_embed(include_all=all_)
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as exc:
                print(f"  ⚠ /relay board failed: {exc}")
                await interaction.followup.send(
                    embed=self._error_embed("/relay board failed", str(exc)),
                    ephemeral=True,
                )

        @relay_group.command(name="post", description="Post a relay task from Discord")
        @app_commands.describe(
            title="Short task title",
            body="Optional task details",
            to="Target agent name",
            session="Session tag for scorecard tracking",
        )
        async def relay_post(
            interaction: discord.Interaction,
            title: str,
            body: str = "",
            to: str = "manuslocal",
            session: str = "session-local",
        ):
            await interaction.response.defer(thinking=True, ephemeral=True)
            try:
                clean_title = title.strip()
                if not clean_title:
                    raise RuntimeError("title is required")
                payload = body.strip() or clean_title
                out, code = await relay(
                    "post",
                    "--from",
                    "relay-coordinator",
                    "--to",
                    to,
                    "--title",
                    clean_title,
                    "--payload",
                    payload,
                    "--session",
                    session,
                )
                if code != 0:
                    raise RuntimeError(out.strip() or "relay post failed")

                task_id = _extract_task_id(out)
                if task_id:
                    self._relay_post_watchers[task_id] = {
                        "to": to,
                        "session": session,
                        "task": payload,
                    }

                embed = discord.Embed(
                    title="Relay task posted",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(name="Task ID", value=task_id or "unknown", inline=True)
                embed.add_field(name="Target", value=to, inline=True)
                embed.add_field(name="Session", value=session, inline=True)
                embed.add_field(name="Title", value=truncate(clean_title, 200), inline=False)
                if payload != clean_title:
                    embed.add_field(name="Body", value=truncate(payload, 900) or "empty task", inline=False)
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as exc:
                print(f"  ⚠ /relay post failed: {exc}")
                await interaction.followup.send(
                    embed=self._error_embed("/relay post failed", str(exc)),
                    ephemeral=True,
                )

    def _error_embed(self, title: str, detail: str) -> discord.Embed:
        embed = discord.Embed(title=title, color=discord.Color.red())
        embed.add_field(name="Detail", value=truncate(detail, 900) or "unknown error", inline=False)
        embed.timestamp = datetime.now(timezone.utc)
        return embed

    async def _sync_relay_commands(self):
        if self.agent_name.lower() != "relay-coordinator":
            return
        if self._relay_slash_commands_synced:
            return
        guild_obj = discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild_obj)
        try:
            synced = await self.tree.sync(guild=guild_obj)
            self._relay_slash_commands_synced = True
            print(f"  🔁 Synced {len(synced)} relay slash command(s) to guild {self.guild_id}")
        except Exception as exc:
            print(f"  ⚠ relay slash command sync failed: {exc}")

    def _load_agent_records(self, output: str) -> list[dict[str, str]]:
        try:
            parsed = json.loads(output)
        except Exception:
            _, rows = parse_pipe_table(output)
            return rows

        if isinstance(parsed, list):
            records = parsed
        elif isinstance(parsed, dict):
            for key in ("agents", "rows", "data", "items"):
                value = parsed.get(key)
                if isinstance(value, list):
                    records = value
                    break
            else:
                records = []
        else:
            records = []

        normalized: list[dict[str, str]] = []
        for row in records:
            if isinstance(row, dict):
                normalized.append({str(k): "" if v is None else str(v) for k, v in row.items()})
        return normalized

    def _color_for_health(self, healthy: bool, degraded: bool = False) -> discord.Color:
        if healthy:
            return discord.Color.green()
        if degraded:
            return discord.Color.yellow()
        return discord.Color.red()

    async def _fetch_json(self, url: str) -> dict | list | None:
        def _load() -> dict | list | None:
            request = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            return await asyncio.to_thread(_load)
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            return None

    async def _build_status_embed(self) -> discord.Embed:
        health_payload = await self._fetch_json(f"{HEALTH_BASE_URL}/health")
        agents_payload = await self._fetch_json(f"{HEALTH_BASE_URL}/health/agents")
        metrics_payload = await self._fetch_json(f"{HEALTH_BASE_URL}/metrics")

        # Track which data sources are unavailable for degraded reporting
        unavailable: list[str] = []
        if health_payload is None:
            unavailable.append("health")
        if agents_payload is None:
            unavailable.append("agents")
        if metrics_payload is None:
            unavailable.append("metrics")

        summary = (agents_payload or {}).get("summary", {}) if isinstance(agents_payload, dict) else {}
        agent_rows = (agents_payload or {}).get("agents", []) if isinstance(agents_payload, dict) else []
        task_counts = (metrics_payload or {}).get("tasks", {}) if isinstance(metrics_payload, dict) else {}
        active_tasks = 0
        if isinstance(task_counts, dict):
            by_status = task_counts.get("by_status", {})
            if isinstance(by_status, dict):
                active_tasks = int(by_status.get("pending", 0)) + int(by_status.get("in_progress", 0))

        try:
            dispatch_out, dispatch_code = await bash(
                f"cd {REPO_ROOT} && scripts/daemon_ctl.sh status --with-bots --with-codex",
                timeout=20,
            )
        except Exception:
            dispatch_out, dispatch_code = "", 1
            unavailable.append("dispatch")
        dispatch_match = re.search(r"uptime\s+([0-9A-Za-z: ]+)", dispatch_out)
        dispatch_uptime = dispatch_match.group(1).strip() if dispatch_match else "unavailable" if "dispatch" in unavailable else "unknown"

        overall_status = health_payload.get("status", "unknown") if isinstance(health_payload, dict) else "unknown"
        litellm_ok = bool(
            isinstance(health_payload, dict)
            and any(
                check.get("name") == "litellm" and check.get("status") == "ok"
                for check in health_payload.get("checks", [])
            )
        )

        # Force degraded when any endpoint is unavailable
        if unavailable:
            overall_status = overall_status if overall_status not in {"healthy"} else "degraded"

        healthy = overall_status == "healthy"
        degraded = overall_status in {"degraded", "unknown"}

        embed = discord.Embed(
            title="Relay status",
            color=self._color_for_health(healthy, degraded=degraded and not healthy),
            timestamp=datetime.now(timezone.utc),
        )

        if unavailable:
            embed.description = f"⚠ Unavailable: {', '.join(unavailable)}"

        agents_value = "unavailable" if agents_payload is None else (
            f"online {summary.get('online', 0)}\n"
            f"stale {summary.get('stale', 0)}\n"
            f"offline {summary.get('offline', 0)}"
        )
        embed.add_field(
            name="Agents",
            value=agents_value,
            inline=True,
        )

        tasks_value = "unavailable" if metrics_payload is None else f"active {active_tasks}"
        embed.add_field(
            name="Tasks",
            value=tasks_value,
            inline=True,
        )
        if agent_rows:
            normalized_agent_rows = [
                {str(k): "" if v is None else str(v) for k, v in row.items()}
                for row in agent_rows
                if isinstance(row, dict)
            ]
            embed.add_field(
                name="Agent Detail",
                value=truncate(summarize_agent_rows(normalized_agent_rows), 1000),
                inline=False,
            )
        embed.add_field(name="Dispatch", value=dispatch_uptime, inline=True)
        embed.add_field(name="LiteLLM", value="healthy" if litellm_ok else ("unavailable" if health_payload is None else "degraded"), inline=True)
        embed.add_field(name="Overall", value=overall_status, inline=True)
        embed.set_footer(text="slash command: /relay status")
        return embed

    async def _build_board_embed(self, include_all: bool) -> discord.Embed:
        args = ["board", "--json"]
        if include_all:
            args.insert(1, "--all")
        board_text, code = await relay(*args)
        if code != 0:
            raise RuntimeError(board_text.strip() or "relay board failed")
        board = json.loads(board_text)
        rows = board.get("active_tasks", [])
        summary = board.get("summary", {})
        title = "Relay board (all)" if include_all else "Relay board"
        embed = discord.Embed(
            title=title,
            color=self._color_for_health(code == 0, degraded=code == 0),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(
            name="Counts",
            value=(
                f"active {summary.get('active', 0)}\n"
                f"done/failed {summary.get('done_failed', 0)}\n"
                f"archived {summary.get('archived', 0)}"
            ),
            inline=True,
        )
        embed.add_field(
            name="Tasks",
            value=truncate(summarize_board_tasks(rows, limit=8), 1000),
            inline=False,
        )
        if include_all:
            embed.description = f"Full history available in relay_web: {RELAY_WEB_URL}"
        embed.set_footer(text="slash command: /relay board")
        return embed

    async def _relay_post_watch_loop(self):
        await asyncio.sleep(12)
        while not self.is_closed():
            try:
                await self._poll_relay_post_watchers()
            except Exception as exc:
                print(f"  ⚠ relay post watcher error: {exc}")
            await asyncio.sleep(12)

    async def _poll_relay_post_watchers(self):
        if not self._relay_post_watchers:
            return
        finished: list[str] = []
        for task_id, info in list(self._relay_post_watchers.items()):
            show_out, code = await relay("show", task_id)
            if code != 0:
                continue
            row = _extract_status_row(show_out)
            status = row.get("status", "").lower()
            if status not in {"done", "failed"}:
                continue
            result = truncate(row.get("result", ""), 280) or row.get("result", "") or "no result"
            to_agent = info.get("to", "unknown")
            session = info.get("session", "session-local")
            emoji = "✅" if status == "done" else "❌"
            await self._post_to_channel(
                RELAY_CHANNEL,
                (
                    f"**[relay-coordinator]** {emoji} task `{task_id}` for `{to_agent}` "
                    f"({session}) → `{status}` | {result}"
                ),
            )
            finished.append(task_id)
        for task_id in finished:
            self._relay_post_watchers.pop(task_id, None)

    async def _heartbeat_loop(self):
        hb_config = self.config.get("heartbeat", {})
        interval = hb_config.get("interval_minutes", 5) * 60
        fmt = hb_config.get("format", "[HEARTBEAT] {agent_name} | {status} | {current_task} | {timestamp}")

        await self.wait_until_ready()
        ch = self.get_channel_by_name(HEARTBEAT_CHANNEL)
        if not ch:
            print(f"  ⚠ #{HEARTBEAT_CHANNEL} not found, heartbeat disabled")
            return

        print(f"  💓 Heartbeat started (every {interval}s)")
        while not self.is_closed():
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            msg = fmt.format(
                agent_name=self.agent_name,
                status="alive",
                current_task="listening",
                timestamp=ts,
            )
            try:
                await ch.send(msg)
            except discord.HTTPException as e:
                print(f"  ⚠ Heartbeat send failed: {e}")
            await self.emit_relay_heartbeat()
            await asyncio.sleep(interval)

    async def catchup_on_boot(self):
        print("\n── BOOT CATCHUP ──")
        catchup_channels = ["lobby", "standup", "relay-room", "decisions",
                            "bugs-and-blockers", "alerts", "logs"]

        for ch_name in catchup_channels:
            ch = self.get_channel_by_name(ch_name)
            if not ch:
                continue
            try:
                messages = []
                async for msg in ch.history(limit=20):
                    messages.append(msg)
                if messages:
                    messages.reverse()
                    print(f"\n  #{ch_name} — last {len(messages)} messages:")
                    for msg in messages:
                        ts = msg.created_at.strftime("%H:%M")
                        preview = msg.content[:100].replace("\n", " ")
                        print(f"    [{ts}] {msg.author.display_name}: {preview}")
                        if self.user.mentioned_in(msg):
                            print(f"    ⚡ ^ YOU WERE MENTIONED")
                else:
                    print(f"\n  #{ch_name} — empty")
            except discord.Forbidden:
                print(f"\n  #{ch_name} — no access")
            except Exception as e:
                print(f"\n  #{ch_name} — error: {e}")

        print("\n── END CATCHUP ──\n")

    async def on_ready(self):
        print(f"\n{'═' * 50}")
        print(f"  {self.agent_name.upper()} — ONLINE")
        print(f"  Bot user: {self.user} (id: {self.user.id})")
        print(f"{'═' * 50}\n")

        self.guild = self.get_guild(self.guild_id)
        if not self.guild:
            print(f"✗ Guild {self.guild_id} not found!")
            await self.close()
            return

        await self._sync_relay_commands()
        await self.catchup_on_boot()
        await self.register_with_relay()
        await self.set_relay_status("online")
        await self.handler.on_boot()
        if self.agent_name.lower() == "relay-coordinator":
            self._relay_post_watch_task = asyncio.ensure_future(self._relay_post_watch_loop())
        await self.emit_lifecycle("session.started", "Bot connected and caught up")

        lobby = self.get_channel_by_name(LOBBY_CHANNEL)
        if lobby:
            ts = datetime.now(timezone.utc).strftime("%H:%M UTC")
            await lobby.send(
                f"**{self.agent_name}** is online. "
                f"Boot catchup complete. Ready for work. ({ts})"
            )

        self._heartbeat_task = asyncio.ensure_future(self._heartbeat_loop())

    async def on_message(self, message: discord.Message):
        if message.guild and message.guild.id != self.guild_id:
            return
        await self.handler.handle_message(message)

    async def on_disconnect(self):
        print(f"  ⚠ {self.agent_name} disconnected from Gateway")

    async def on_resumed(self):
        print(f"  ✓ {self.agent_name} resumed Gateway session")

    async def graceful_shutdown(self, reason: str = "shutdown"):
        print(f"\n  Shutting down: {reason}")
        try:
            await self.set_relay_status("offline")
            await self.emit_lifecycle("session.finished", reason)
        except Exception:
            pass
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        await self.close()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Run a Relay Room agent bot listener"
    )
    parser.add_argument(
        "--agent", "-a",
        default=os.getenv("AGENT_NAME", ""),
        help="Agent name (codex, claudecli, manuslocal, coworkclaude)",
    )
    parser.add_argument(
        "--guild", "-g",
        default=os.getenv("DISCORD_GUILD_ID", "1491110247299944641"),
        help="Discord guild (server) ID",
    )
    args = parser.parse_args()

    if not args.agent:
        print("✗ Agent name required: --agent <name> or AGENT_NAME env var")
        sys.exit(1)

    load_dotenv(ENV_PATH)
    # Also load OpenFang env for LITELLM_KEY and other API keys
    openfang_env = Path.home() / ".openfang" / ".env"
    if openfang_env.exists():
        load_dotenv(openfang_env, override=False)

    token_var = get_token_env_var(args.agent)
    token = os.getenv(token_var)
    if not token:
        print(f"✗ Token not found: set {token_var} in .env")
        sys.exit(1)

    config = load_config()
    guild_id = int(args.guild)

    print(f"Agent:    {args.agent}")
    print(f"Token:    {token_var} ({'*' * 8}...{token[-4:]})")
    print(f"Guild:    {guild_id}")
    print(f"Handler:  {HANDLERS.get(args.agent.lower(), ActionHandler).__name__}")

    # Ensure ~/.local/bin is on PATH so relay can find spacetime
    import os as _os
    _local_bin = "/home/justinleopard/.local/bin"
    _cargo_bin = "/home/justinleopard/.cargo/bin"
    _current = _os.environ.get("PATH", "")
    if _local_bin not in _current:
        _os.environ["PATH"] = f"{_local_bin}:{_cargo_bin}:{_current}"
        print(f"  🔧 PATH extended with {_local_bin}")

    bot = AgentBot(args.agent, guild_id, config)

    import signal
    def handle_signal(sig, frame):
        print("\n\nCaught interrupt, shutting down...")
        asyncio.ensure_future(bot.graceful_shutdown("SIGINT"))
    signal.signal(signal.SIGINT, handle_signal)

    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
