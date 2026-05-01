#!/usr/bin/env python3
"""
JustAi — Synthesizer
=====================
Aggregates execution results into a structured summary.
Stores results in claude-flow memory for future sessions.
"""

from __future__ import annotations

import time
from contextlib import suppress
from dataclasses import dataclass

from justai.memory import Memory

_memory = Memory()


@dataclass
class RunSummary:
    goal: str
    intent: str
    total_tasks: int
    done: int
    failed: int
    skipped: int
    duration_seconds: float
    session_ref: str
    status: str  # "complete" | "partial" | "failed"
    details: list[dict]


def synthesize(
    goal: str,
    intent: str,
    results: list,
    session_ref: str = "",
    duration: float = 0.0,
) -> RunSummary:
    """
    Aggregate results and produce a run summary.

    Args:
        results: list of DelegationResult or ExecResult objects
    """
    done = sum(1 for r in results if r.status == "done")
    failed = sum(1 for r in results if r.status in ("failed", "error", "timeout"))
    skipped = sum(1 for r in results if r.status == "skipped")
    total = len(results)

    if failed == 0 and skipped == 0:
        status = "complete"
    elif done > 0:
        status = "partial"
    else:
        status = "failed"

    details = []
    for r in results:
        entry = {
            "task_id": r.task_id,
            "title": r.title,
            "status": r.status,
            "result": r.result[:200] if hasattr(r, "result") else "",
        }
        if hasattr(r, "duration_seconds"):
            entry["duration"] = round(r.duration_seconds, 1)
        details.append(entry)

    summary = RunSummary(
        goal=goal,
        intent=intent,
        total_tasks=total,
        done=done,
        failed=failed,
        skipped=skipped,
        duration_seconds=duration,
        session_ref=session_ref,
        status=status,
        details=details,
    )

    # Store in memory
    _store_summary(summary)

    return summary


def _store_summary(s: RunSummary) -> None:
    """Persist run summary to claude-flow memory."""
    key = f"justai/runs/{s.session_ref}-{int(time.time())}"
    value = (
        f"goal={s.goal[:80]} | intent={s.intent} | "
        f"tasks={s.total_tasks} | done={s.done} | failed={s.failed} | "
        f"duration={s.duration_seconds:.0f}s | session={s.session_ref} | "
        f"status={s.status}"
    )
    with suppress(Exception):
        _memory.store(key, value)

    # Also update session context
    with suppress(Exception):
        _memory.store(f"justai/session/{s.session_ref}", value)
        _memory.store("justai/session/latest", value)


def format_summary(s: RunSummary) -> str:
    """Format summary for terminal output."""
    lines = []
    lines.append("")
    lines.append("+" + "=" * 58 + "+")
    lines.append("|  Run Summary" + " " * 45 + "|")
    lines.append("+" + "=" * 58 + "+")
    for d in s.details:
        icon = "+" if d["status"] == "done" else "-" if d["status"] == "skipped" else "x"
        lines.append(f"|  {icon} [{d['task_id']}] {d['title'][:38]:<38}  |")
    lines.append("+" + "-" * 58 + "+")
    lines.append(
        f"|  {s.done}/{s.total_tasks} done | {s.failed} failed | {s.skipped} skipped | {s.duration_seconds:.0f}s"
        + " " * 10
        + "|"
    )
    lines.append(f"|  Status: {s.status:<48} |")
    lines.append("+" + "=" * 58 + "+")
    return "\n".join(lines)
