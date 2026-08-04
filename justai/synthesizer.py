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
from justai.results import WITHHELD_STATUSES, tally

_memory = Memory()


@dataclass
class RunSummary:
    goal: str
    intent: str
    total_tasks: int
    done: int
    failed: int
    skipped: int
    blocked: int
    duration_seconds: float
    session_ref: str
    status: str  # "complete" | "partial" | "blocked" | "failed"
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

    The verdict comes from :func:`justai.results.tally`, which is also what the
    learning layer reads — the two used to derive success independently and
    disagreed. It raises on a status outside the canonical vocabulary rather
    than letting an unrecognised string fall through to a non-failure bucket.

    Args:
        results: list of DelegationResult or ExecResult objects

    Raises:
        ValueError: a result carries a status the vocabulary does not define.
    """
    counts = tally(results)
    status = counts.run_status

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
        total_tasks=counts.total,
        done=counts.done,
        failed=counts.failed,
        skipped=counts.skipped,
        blocked=counts.blocked,
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
        f"skipped={s.skipped} | blocked={s.blocked} | "
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
        icon = "+" if d["status"] == "done" else "-" if d["status"] in WITHHELD_STATUSES else "x"
        lines.append(f"|  {icon} [{d['task_id']}] {d['title'][:38]:<38}  |")
    lines.append("+" + "-" * 58 + "+")
    counts = (
        f"{s.done}/{s.total_tasks} done | {s.failed} failed | "
        f"{s.skipped} skipped | {s.blocked} blocked | {s.duration_seconds:.0f}s"
    )
    lines.append(f"|  {counts:<56}|")
    lines.append(f"|  Status: {s.status:<48} |")
    lines.append("+" + "=" * 58 + "+")
    return "\n".join(lines)
