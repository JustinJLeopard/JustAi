#!/usr/bin/env python3
"""
JustAi — Synthesizer
=====================
Aggregates execution results into a structured summary.
Stores results in claude-flow memory for future sessions.

Also applies the intent-fidelity gate's verdict (computed upstream by
justai.intent_fidelity): a run whose tasks all completed but whose OUTCOME
missed the user's original intent is honestly downgraded from "complete" to
"partial". The fidelity percentile/grade/verdict travel on the summary.
"""

from __future__ import annotations

import time
from contextlib import suppress
from dataclasses import dataclass

from justai.memory import Memory
from justai.results import tally

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
    status: str  # "complete" | "partial" | "failed"
    details: list[dict]
    # Intent-fidelity gate (None when the gate did not run):
    intent_fidelity: float | None = None  # 0-100 percentile
    fidelity_verdict: str | None = None  # met | exceeded | missed
    fidelity_grade: str | None = None  # A+/A/B/C/D/F
    a_or_better: bool | None = None  # cleared the intent bar


def synthesize(
    goal: str,
    intent: str,
    results: list,
    session_ref: str = "",
    duration: float = 0.0,
    fidelity=None,
) -> RunSummary:
    """
    Aggregate results and produce a run summary.

    Args:
        results: list of DelegationResult or ExecResult objects
        fidelity: optional FidelityResult from justai.intent_fidelity. When a
            task-complete run is judged to have MISSED the intent, its status is
            honestly downgraded to "partial".
    """
    # One shared vocabulary: tally() is also what the learning layer reads, so
    # the two surfaces cannot disagree about the same result set. It raises on a
    # status outside the canonical vocabulary rather than bucketing it toward a
    # success path, and on a result set that is not a well-formed sequence.
    counts = tally(results, strict=True)
    done = counts.done
    failed = counts.failed
    skipped = counts.skipped
    blocked = counts.blocked
    total = counts.total
    status = counts.run_status

    # Intent-fidelity gate: a task-complete run that missed the original intent
    # is not honestly "complete" — downgrade it. No effect when fidelity is None
    # or the intent was met/exceeded.
    intent_fidelity = fidelity_verdict = fidelity_grade = a_or_better = None
    if fidelity is not None:
        intent_fidelity = fidelity.fidelity
        fidelity_verdict = (
            fidelity.verdict.value if hasattr(fidelity.verdict, "value") else str(fidelity.verdict)
        )
        fidelity_grade = fidelity.grade
        a_or_better = fidelity.a_or_better
        if status == "complete" and fidelity_verdict == "missed":
            status = "partial"

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
        blocked=blocked,
        duration_seconds=duration,
        session_ref=session_ref,
        status=status,
        details=details,
        intent_fidelity=intent_fidelity,
        fidelity_verdict=fidelity_verdict,
        fidelity_grade=fidelity_grade,
        a_or_better=a_or_better,
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
    if s.intent_fidelity is not None:
        value += f" | fidelity={s.intent_fidelity:.0f}({s.fidelity_grade}/{s.fidelity_verdict})"
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
    if s.intent_fidelity is not None:
        intent_line = (
            f"Intent:  {s.intent_fidelity:.0f}/100 ({s.fidelity_grade}) "
            f"{s.fidelity_verdict} | a-or-better: {s.a_or_better}"
        )
        lines.append(f"|  {intent_line:<48} |")
    lines.append("+" + "=" * 58 + "+")
    return "\n".join(lines)
