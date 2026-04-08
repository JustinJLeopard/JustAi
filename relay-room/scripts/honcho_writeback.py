#!/usr/bin/env python3
"""
honcho_writeback.py — Session-End Write-Back for Cowork-Claude

Cowork-Claude is session-based (not persistent). At the end of every session,
this script captures the current state from Discord and writes it to Honcho
so the next session boots with full context.

What gets written:
  - Last N messages from key channels (decisions, relay-room, standup, bugs)
  - Current active blockers and their status
  - Who was online / last heartbeat timestamps
  - Any unresolved @cowork-claude mentions
  - Session summary (what was accomplished, what's pending)

Usage:
    # Run at the end of a Cowork session:
    python honcho_writeback.py --summary "Designed relay-room architecture, wrote setup scripts"

    # Or with full options:
    python honcho_writeback.py \
        --summary "..." \
        --accomplished "setup_server.py, bot_listener.py" \
        --pending "bot creation, clawhip config" \
        --blockers "none"

Requirements:
    pip install discord.py python-dotenv httpx pyyaml

Architecture:
    ┌──────────────┐    read recent     ┌──────────────┐    write state    ┌─────────┐
    │  Discord      │ ◄────────────────► │  writeback   │ ────────────────► │  Honcho │
    │  #decisions   │                    │  .py         │                   │  (API)  │
    │  #relay-room  │                    │              │                   │         │
    │  #standup     │                    │              │                   │         │
    └──────────────┘                    └──────────────┘                   └─────────┘
"""

import argparse
import asyncio
import json
import os
import sys
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

import discord
import yaml
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
ENV_PATH = SCRIPT_DIR.parent / ".env"
CONFIG_PATH = SCRIPT_DIR / "server_config.yaml"

# Channels to capture for context
CONTEXT_CHANNELS = {
    "decisions":        10,  # last 10 messages
    "relay-room":       20,  # last 20 messages (active work)
    "standup":          10,
    "bugs-and-blockers": 10,
    "alerts":            5,
    "lobby":            10,
    "logs":             15,
}

# Honcho SDK config
HONCHO_WORKSPACE = "relay-room"
HONCHO_PEER = "cowork-claude"


# ─────────────────────────────────────────────────────────────────────────────
# Discord Reader
# ─────────────────────────────────────────────────────────────────────────────

class DiscordReader(discord.Client):
    """
    Read-only Discord client that captures recent channel state
    and disconnects. Does NOT stay connected.
    """

    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.guild_id = guild_id
        self.captured_state: dict = {}
        self._done = asyncio.Event()

    async def on_ready(self):
        guild = self.get_guild(self.guild_id)
        if not guild:
            print(f"✗ Guild {self.guild_id} not found")
            self._done.set()
            return

        print(f"✓ Connected to {guild.name} — capturing state...")

        state = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "guild": guild.name,
            "channels": {},
            "agent_status": {},
            "unresolved_mentions": [],
        }

        # Capture messages from key channels
        for ch_name, limit in CONTEXT_CHANNELS.items():
            ch = discord.utils.get(guild.text_channels, name=ch_name)
            if not ch:
                continue

            messages = []
            try:
                async for msg in ch.history(limit=limit):
                    messages.append({
                        "author": msg.author.display_name,
                        "content": msg.content[:500],
                        "timestamp": msg.created_at.isoformat(),
                        "is_bot": msg.author.bot,
                    })

                    # Check for unresolved @cowork-claude mentions
                    if self.user.mentioned_in(msg):
                        state["unresolved_mentions"].append({
                            "channel": ch_name,
                            "author": msg.author.display_name,
                            "content": msg.content[:300],
                            "timestamp": msg.created_at.isoformat(),
                        })

                messages.reverse()  # chronological order
                state["channels"][ch_name] = messages
                print(f"  ✓ #{ch_name}: {len(messages)} messages captured")

            except discord.Forbidden:
                print(f"  ⚠ #{ch_name}: no access")
            except Exception as e:
                print(f"  ⚠ #{ch_name}: {e}")

        # Parse heartbeats to determine agent status
        hb_channel = discord.utils.get(guild.text_channels, name="heartbeats")
        if hb_channel:
            last_seen = {}
            async for msg in hb_channel.history(limit=50):
                if "[HEARTBEAT]" in msg.content:
                    parts = msg.content.split("|")
                    if len(parts) >= 2:
                        agent = parts[0].replace("[HEARTBEAT]", "").strip()
                        if agent not in last_seen:
                            last_seen[agent] = {
                                "last_heartbeat": msg.created_at.isoformat(),
                                "status": parts[1].strip() if len(parts) > 1 else "unknown",
                                "task": parts[2].strip() if len(parts) > 2 else "unknown",
                            }
            state["agent_status"] = last_seen
            print(f"  ✓ Agent status: {list(last_seen.keys())}")

        self.captured_state = state
        self._done.set()
        await self.close()

    async def wait_for_capture(self):
        await self._done.wait()
        return self.captured_state


# ─────────────────────────────────────────────────────────────────────────────
# Honcho Writer
# ─────────────────────────────────────────────────────────────────────────────

async def write_to_honcho(
    state: dict,
    summary: str,
    accomplished: str,
    pending: str,
    blockers: str,
):
    """Write the captured state to Honcho via the Python SDK."""

    payload = {
        "session_summary": summary,
        "accomplished": accomplished,
        "pending_next_session": pending,
        "active_blockers": blockers,
        "discord_state": state,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "written_by": "cowork-claude/honcho_writeback.py",
    }

    api_key = os.getenv("HONCHO_API_KEY")
    if not api_key:
        print("  ⚠ HONCHO_API_KEY not set — falling back to file")
        await write_to_file(payload)
        return

    try:
        from honcho import Honcho

        honcho = Honcho(
            workspace_id=HONCHO_WORKSPACE,
            api_key=api_key,
            environment="production",
        )

        # Create/get peer for cowork-claude
        peer = honcho.peer(
            HONCHO_PEER,
            metadata={"type": "session_writeback"},
        )

        # Create a session tagged with this writeback
        session_name = f"writeback-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        session = honcho.session(session_name)

        # Store the full state as session metadata
        session.set_metadata(payload)

        # Also write a summary message from the peer
        summary_text = (
            f"Session writeback at {payload['written_at']}.\n"
            f"Summary: {summary}\n"
            f"Accomplished: {accomplished or 'n/a'}\n"
            f"Pending: {pending or 'n/a'}\n"
            f"Blockers: {blockers}\n"
            f"Channels captured: {list(state.get('channels', {}).keys())}\n"
            f"Agents seen: {list(state.get('agent_status', {}).keys())}"
        )
        session.add_messages([peer.message(summary_text)])

        print(f"  ✓ Written to Honcho (session: {session_name})")

    except ImportError:
        print("  ⚠ honcho package not installed — falling back to file")
        await write_to_file(payload)
    except Exception as e:
        print(f"  ⚠ Honcho error: {e} — falling back to file")
        await write_to_file(payload)


async def write_to_file(payload: dict):
    """Fallback: write state to a JSON file that can be loaded on next boot."""
    output_path = SCRIPT_DIR / "last_session_state.json"
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"  ✓ State written to {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def async_main(args):
    load_dotenv(ENV_PATH)

    token = os.getenv("COWORKCLAUDE_TOKEN")
    if not token:
        # Fall back to relay coordinator token for reading
        token = os.getenv("RELAY_COORDINATOR_TOKEN")
    if not token:
        print("✗ No bot token found (COWORKCLAUDE_TOKEN or RELAY_COORDINATOR_TOKEN)")
        sys.exit(1)

    guild_id = int(os.getenv("DISCORD_GUILD_ID", "1491110247299944641"))

    # Capture Discord state
    print("\n── DISCORD STATE CAPTURE ──")
    reader = DiscordReader(guild_id)
    start_task = asyncio.create_task(reader.start(token))
    capture_task = asyncio.create_task(reader.wait_for_capture())
    state = {}

    try:
        done, pending = await asyncio.wait(
            {start_task, capture_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if capture_task in done:
            state = capture_task.result()
            await start_task
        else:
            await start_task
            if not capture_task.done():
                capture_task.cancel()
                with suppress(asyncio.CancelledError):
                    await capture_task
    finally:
        if not reader.is_closed():
            await reader.close()
        if not capture_task.done():
            capture_task.cancel()
            with suppress(asyncio.CancelledError):
                await capture_task
        with suppress(asyncio.CancelledError):
            await start_task

    if not state:
        print("✗ Failed to capture Discord state")
        sys.exit(1)

    print(f"\n── WRITING TO HONCHO ──")
    await write_to_honcho(
        state=state,
        summary=args.summary,
        accomplished=args.accomplished,
        pending=args.pending,
        blockers=args.blockers,
    )

    # Also always write a local copy
    await write_to_file({
        "session_summary": args.summary,
        "accomplished": args.accomplished,
        "pending_next_session": args.pending,
        "active_blockers": args.blockers,
        "discord_state": state,
    })

    print("\n✓ Write-back complete\n")


def main():
    parser = argparse.ArgumentParser(
        description="Capture Discord state and write to Honcho for next Cowork session"
    )
    parser.add_argument(
        "--summary", "-s",
        default="Session ended (no summary provided)",
        help="Brief summary of what was accomplished this session",
    )
    parser.add_argument(
        "--accomplished", "-a",
        default="",
        help="Comma-separated list of completed items",
    )
    parser.add_argument(
        "--pending", "-p",
        default="",
        help="Comma-separated list of items for next session",
    )
    parser.add_argument(
        "--blockers", "-b",
        default="none",
        help="Current blockers",
    )
    args = parser.parse_args()

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
