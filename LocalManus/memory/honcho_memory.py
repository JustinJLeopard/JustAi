#!/usr/bin/env python3
"""
JustAi — Memory Integration (claude-flow bridge)
=================================================
Replaces Honcho with claude-flow memory for pre-task context injection
and post-task memory storage. Drop-in compatible with the original
honcho_memory.py interface used by mini_local.sh and mini_local_cloud.sh.

Usage:
    # Before running mini (get context to inject into system prompt):
    python3 memory/honcho_memory.py --pre-task --task "create a leapfrog game"

    # After running mini (store the completed task in memory):
    python3 memory/honcho_memory.py --post-task --task "create a leapfrog game" \
        --traj logs/last_mini_run.traj.json

    # Query what JustAi remembers:
    python3 memory/honcho_memory.py --query "what tech stack does Justin prefer?"
"""

import os
import sys
import json
import argparse
import datetime
import subprocess


# ---------------------------------------------------------------------------
# claude-flow memory bridge
# ---------------------------------------------------------------------------
MEMORY_DB = os.path.expanduser("~/projects/ruv-research")


def cf_search(query: str) -> str:
    """Search claude-flow memory semantically."""
    try:
        result = subprocess.run(
            ["claude-flow", "memory", "search", "-q", query],
            capture_output=True, text=True, cwd=MEMORY_DB, timeout=10
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"[memory] Warning: search failed: {e}", file=sys.stderr)
        return ""


def cf_store(key: str, value: str) -> bool:
    """Store a value in claude-flow memory."""
    try:
        result = subprocess.run(
            ["claude-flow", "memory", "store", "-k", key, "-v", value],
            capture_output=True, text=True, cwd=MEMORY_DB, timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[memory] Warning: store failed: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Pre-task: build context string to inject into system prompt
# ---------------------------------------------------------------------------
def pre_task_context(task: str) -> str:
    """
    Query claude-flow memory for relevant context about past tasks and preferences.
    Returns a formatted string ready to inject into the mini-swe-agent system prompt.
    """
    if not task:
        return ""

    try:
        lines = ["[MEMORY — from previous sessions]"]

        # Search for task-relevant prior context
        results = cf_search(task)
        if results and len(results.strip()) > 20:
            # Extract just the value lines from cf output
            value_lines = []
            in_value = False
            for line in results.splitlines():
                if "Value:" in line:
                    in_value = True
                    continue
                if in_value and line.strip().startswith("|"):
                    val = line.strip().strip("|").strip()
                    if val and not val.startswith("-"):
                        value_lines.append(val)
                    else:
                        in_value = False
            if value_lines:
                lines.append("Relevant prior context: " + " | ".join(value_lines[:3]))

        # Search specifically for preferences
        prefs = cf_search("Justin preferences tech stack")
        if prefs and len(prefs.strip()) > 20:
            lines.append("Justin's preferences: see claude-flow memory for details")

        if len(lines) == 1:
            return ""  # No meaningful context

        return "\n".join(lines)

    except Exception as e:
        print(f"[memory] Warning: could not load pre-task context: {e}", file=sys.stderr)
        return ""


# ---------------------------------------------------------------------------
# Post-task: store completed task in claude-flow memory
# ---------------------------------------------------------------------------
def post_task_store(task: str, traj_path: str = None, success: bool = True):
    """
    Store the completed task and learnings in claude-flow memory.
    """
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        status = "completed" if success else "failed"

        summary_parts = [
            f"task={task[:100]}",
            f"status={status}",
            f"ts={ts}",
        ]

        # Parse trajectory if available
        if traj_path and os.path.exists(traj_path):
            try:
                with open(traj_path) as f:
                    traj = json.load(f)
                msgs = traj.get("messages", [])
                model = traj.get("info", {}).get("config", {}).get("model", {}).get("model_name", "unknown")
                summary_parts.append(f"model={model}")
                summary_parts.append(f"steps={len(msgs)}")
            except Exception:
                pass

        summary = " | ".join(summary_parts)
        key = f"justai/tasks/{ts}"

        ok = cf_store(key, summary)
        if ok:
            print(f"[memory] Stored task in claude-flow: {key}")
            print(f"[memory] Summary: {summary}")
        else:
            print(f"[memory] Warning: store failed, task not persisted", file=sys.stderr)

        return key

    except Exception as e:
        print(f"[memory] Warning: could not store post-task memory: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Store a preference
# ---------------------------------------------------------------------------
def store_preference(preference: str):
    """Store an observed preference or fact."""
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    key = f"justai/preferences/{ts}"
    ok = cf_store(key, preference)
    if ok:
        print(f"[memory] Stored preference: {preference[:80]}")
    else:
        print(f"[memory] Warning: could not store preference", file=sys.stderr)


# ---------------------------------------------------------------------------
# Query memory
# ---------------------------------------------------------------------------
def query_memory(query: str):
    """Search claude-flow memory with a natural language query."""
    results = cf_search(query)
    if results:
        print(f"\n[JustAi memory]\n{results}")
    else:
        print("[memory] No results found.")


# ---------------------------------------------------------------------------
# CLI — drop-in compatible with original honcho_memory.py interface
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JustAi Memory (claude-flow bridge)")
    parser.add_argument("--pre-task", action="store_true", help="Get context to inject before a task")
    parser.add_argument("--post-task", action="store_true", help="Store completed task in memory")
    parser.add_argument("--query", type=str, help="Query memory with natural language")
    parser.add_argument("--store-pref", type=str, help="Store a preference or fact")
    parser.add_argument("--task", type=str, default="", help="Task description")
    parser.add_argument("--traj", type=str, default="", help="Path to trajectory JSON file")
    parser.add_argument("--failed", action="store_true", help="Mark task as failed")

    args = parser.parse_args()

    if args.pre_task:
        ctx = pre_task_context(args.task)
        print(ctx)

    elif args.post_task:
        post_task_store(args.task, args.traj or None, success=not args.failed)

    elif args.query:
        query_memory(args.query)

    elif args.store_pref:
        store_preference(args.store_pref)

    else:
        parser.print_help()
