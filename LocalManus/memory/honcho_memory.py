#!/usr/bin/env python3
"""
ManusLocal — Honcho Memory Integration
=======================================
Provides pre-task context injection and post-task memory storage for
mini-swe-agent runs. Called by the mini-local and mini-local-cloud wrappers.

Usage:
    # Before running mini (get context to inject into system prompt):
    python3 memory/honcho_memory.py --pre-task --task "create a leapfrog game"

    # After running mini (store the completed task in memory):
    python3 memory/honcho_memory.py --post-task --task "create a leapfrog game" \
        --traj logs/last_mini_run.traj.json

    # Query what ManusLocal remembers:
    python3 memory/honcho_memory.py --query "what tech stack does Justin prefer?"
"""

import os
import sys
import json
import argparse
import datetime

# Auto-load .env
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(_env_path, override=False)
except ImportError:
    pass

from honcho import Honcho
from honcho.api_types import PeerConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WORKSPACE = "dev"
PEER_DEVELOPER = "developer"
PEER_MANUS_LOCAL = "manus-local"
PEER_SESSION_STATE = "session-state"
SESSION_TASKS = "manus-local-tasks"
SESSION_PREFERENCES = "manus-local-preferences"
MAX_CONTEXT_TOKENS = 1500


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
def get_honcho():
    api_key = os.environ.get("HONCHO_API_KEY")
    if not api_key:
        print("[honcho] ERROR: HONCHO_API_KEY not set.", file=sys.stderr)
        sys.exit(1)
    return Honcho(api_key=api_key, workspace_id=WORKSPACE)


# ---------------------------------------------------------------------------
# Pre-task: build context string to inject into system prompt
# ---------------------------------------------------------------------------
def pre_task_context(task: str) -> str:
    """
    Query Honcho for relevant context about Justin's preferences and past tasks.
    Returns a formatted string ready to inject into the mini-swe-agent system prompt.
    """
    try:
        h = get_honcho()
        developer = h.peer(PEER_DEVELOPER)
        ml_agent = h.peer(PEER_MANUS_LOCAL, configuration=PeerConfig(observe_me=False))

        lines = ["[MEMORY — from previous sessions]"]

        # 1. Query developer preferences relevant to this task
        pref_query = f"What are Justin's preferences, tech stack choices, and coding style relevant to: {task}"
        prefs = developer.chat(pref_query)
        if prefs and len(str(prefs).strip()) > 10:
            lines.append(f"Justin's preferences: {prefs}")

        # 2. Query past similar tasks
        task_query = f"Have I done a similar task before? What was the outcome and what should I do differently? Task: {task}"
        past = ml_agent.chat(task_query)
        if past and len(str(past).strip()) > 10:
            lines.append(f"Past similar tasks: {past}")

        # 3. Get session state (active plans, pending items)
        state_peer = h.peer(PEER_SESSION_STATE)
        state = state_peer.chat("What is the current active plan, any pending items, or important context I should know?")
        if state and len(str(state).strip()) > 10:
            lines.append(f"Session state: {state}")

        if len(lines) == 1:
            return ""  # No meaningful context yet

        return "\n".join(lines)

    except Exception as e:
        print(f"[honcho] Warning: could not load pre-task context: {e}", file=sys.stderr)
        return ""


# ---------------------------------------------------------------------------
# Post-task: store completed task in Honcho
# ---------------------------------------------------------------------------
def post_task_store(task: str, traj_path: str = None, success: bool = True):
    """
    Store the completed task and any learnings in Honcho.
    Reads the trajectory file if provided to extract what was actually done.
    """
    try:
        h = get_honcho()
        developer = h.peer(PEER_DEVELOPER)
        ml_agent = h.peer(PEER_MANUS_LOCAL, configuration=PeerConfig(observe_me=False))

        session_id = f"task-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
        session = h.session(session_id)
        session.add_peers([developer, ml_agent])

        # Build summary of what was done
        summary_parts = [f"Task: {task}", f"Status: {'completed' if success else 'failed'}",
                         f"Timestamp: {datetime.datetime.now().isoformat()}"]

        # Parse trajectory if available
        if traj_path and os.path.exists(traj_path):
            try:
                with open(traj_path) as f:
                    traj = json.load(f)
                steps = traj.get("trajectory", [])
                commands_run = [
                    s.get("action", {}).get("bash_command", "")
                    for s in steps
                    if s.get("action", {}).get("bash_command")
                ]
                if commands_run:
                    summary_parts.append(f"Commands executed: {'; '.join(commands_run[:10])}")
                files_created = []
                for s in steps:
                    output = s.get("observation", {}).get("output", "")
                    if "Writing" in output or "created" in output.lower():
                        files_created.append(output[:100])
                if files_created:
                    summary_parts.append(f"Files/artifacts: {'; '.join(files_created[:5])}")
            except Exception:
                pass

        summary = "\n".join(summary_parts)

        session.add_messages([
            developer.message(f"ManusLocal completed a task: {task}"),
            ml_agent.message(summary),
        ])

        compact_summary = summary.replace("\n", " | ")
        print(f"[honcho] Stored task in session '{session_id}'")
        print(f"[honcho] Summary: {compact_summary}")
        return session_id

    except Exception as e:
        print(f"[honcho] Warning: could not store post-task memory: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Store Justin's preferences observed during a task
# ---------------------------------------------------------------------------
def store_preference(preference: str):
    """Store an observed preference or fact about Justin."""
    try:
        h = get_honcho()
        developer = h.peer(PEER_DEVELOPER)
        ml_agent = h.peer(PEER_MANUS_LOCAL, configuration=PeerConfig(observe_me=False))

        session = h.session(f"pref-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}")
        session.add_peers([developer, ml_agent])
        session.add_messages([
            developer.message(preference),
            ml_agent.message("Noted and stored in memory."),
        ])
        print(f"[honcho] Stored preference: {preference[:80]}...")
    except Exception as e:
        print(f"[honcho] Warning: could not store preference: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Query memory
# ---------------------------------------------------------------------------
def query_memory(query: str):
    """Ask Honcho a natural language question about what it knows."""
    try:
        h = get_honcho()
        developer = h.peer(PEER_DEVELOPER)
        ml_agent = h.peer(PEER_MANUS_LOCAL, configuration=PeerConfig(observe_me=False))

        print(f"\n[Developer memory] {developer.chat(query)}")
        print(f"\n[ManusLocal memory] {ml_agent.chat(query)}")
    except Exception as e:
        print(f"[honcho] Query failed: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ManusLocal Honcho Memory")
    parser.add_argument("--pre-task", action="store_true", help="Get context to inject before a task")
    parser.add_argument("--post-task", action="store_true", help="Store completed task in memory")
    parser.add_argument("--query", type=str, help="Query memory with natural language")
    parser.add_argument("--store-pref", type=str, help="Store a preference or fact about Justin")
    parser.add_argument("--task", type=str, default="", help="Task description")
    parser.add_argument("--traj", type=str, default="", help="Path to trajectory JSON file")
    parser.add_argument("--failed", action="store_true", help="Mark task as failed")

    args = parser.parse_args()

    if args.pre_task:
        ctx = pre_task_context(args.task)
        print(ctx)  # Captured by wrapper and injected into system prompt

    elif args.post_task:
        post_task_store(args.task, args.traj or None, success=not args.failed)

    elif args.query:
        query_memory(args.query)

    elif args.store_pref:
        store_preference(args.store_pref)

    else:
        parser.print_help()
