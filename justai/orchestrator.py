#!/usr/bin/env python3
"""
JustAi — Orchestrator
======================
Main pipeline: intake → intent → plan → review → checkpoint → delegate → synthesize

Usage:
    python3 -m justai.orchestrator "your goal here"
    python3 -m justai.orchestrator --auto "your goal here"   # skip R1 wait
    # or via CLI:
    justai run "your goal here"

Evidence-based design:
  - Intent gate classifies the goal first
  - Planner decomposes into mini-sized tasks (evidence: ~35 steps each)
  - Reviewer validates plan quality before any execution (evidence: planning
    quality was #1 driver of 80->90->100% sprint success improvement)
  - Checkpoint enforces R0-R3 gates (default: autonomous)
  - Delegator posts to SpacetimeDB and monitors via relay CLI
  - Synthesizer aggregates results and stores in claude-flow memory
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass

from justai.intent_gate import classify, Intent, IntentResult
from justai.planner import decompose, Plan, format_plan
from justai.reviewer import review, ReviewResult
from justai.checkpoint import evaluate
from justai.delegator import delegate_plan, DelegationResult
from justai.memory import Memory
from justai.tracing import trace_generation, trace_event, flush_traces
from justai.health import preflight, print_preflight

MAX_REPLAN_ATTEMPTS = 2
SESSION_REF = os.environ.get("JUSTAI_SESSION_REF", "sprint-2")
AUTO_MODE = os.environ.get("JUSTAI_AUTO_MODE", "").lower() in ("1", "true", "yes")


@dataclass
class OrchestrationResult:
    goal: str
    intent: str
    task_count: int
    results: list[DelegationResult]
    duration_seconds: float
    status: str   # "complete" | "partial" | "blocked" | "ambiguous"


# Shared memory client — talks to MCP HTTP at :3100 (~5ms vs ~300ms CLI)
_memory = Memory()


def _store_memory(key: str, value: str) -> None:
    """Store outcome in claude-flow memory via MCP HTTP."""
    try:
        _memory.store(key, value)
    except Exception:
        pass


def _retrieve_memory(key: str) -> str | None:
    """Retrieve a value from claude-flow memory. Returns None on failure."""
    try:
        return _memory.retrieve(key)
    except Exception:
        return None


def _load_session_context(session_ref: str) -> str | None:
    """Load prior session context from memory, if available."""
    # Try session-specific key first, then generic last-run
    for key in [f"justai/session/{session_ref}", "justai/session/latest"]:
        ctx = _retrieve_memory(key)
        if ctx:
            return ctx
    return None


def _save_session_context(session_ref: str, summary: str) -> None:
    """Persist session context for future runs."""
    _store_memory(f"justai/session/{session_ref}", summary)
    _store_memory("justai/session/latest", summary)


def _print_header(goal: str, auto: bool = False) -> None:
    print()
    print("╔══════════════════════════════════════════════════════╗")
    mode = " [AUTO]" if auto else ""
    print(f"║  JustAi Orchestrator{mode:<36}║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  Goal: {goal[:70]}")
    print()


def run(
    goal: str,
    session_ref: str = SESSION_REF,
    auto: bool = AUTO_MODE,
) -> OrchestrationResult:
    """
    Full orchestration pipeline for a given goal.

    Args:
        goal: The task to accomplish.
        session_ref: Session identifier for tracing and memory.
        auto: If True, R1 checkpoints auto-approve immediately (no 60s wait).
    """
    start = time.time()
    _print_header(goal, auto=auto)

    # Export auto mode so checkpoint.py can read it
    if auto:
        os.environ["JUSTAI_AUTO_MODE"] = "1"

    # ── Preflight: service health ─────────────────────────────────────────────
    statuses = preflight()
    litellm_ok = print_preflight(statuses)

    if not litellm_ok:
        print("  ⚠ LiteLLM unreachable — pipeline will use heuristic fallbacks")
        print()

    # ── Session context: load prior run ───────────────────────────────────────
    prior_context = _load_session_context(session_ref)
    if prior_context:
        print(f"  Session context loaded ({len(prior_context)} chars)")
        print(f"    {prior_context[:120]}...")
        print()

    # ── Stage 1: Intent Classification ───────────────────────────────────────
    print("[1/5] Classifying intent...")
    with trace_generation("intent-gate", input_text=goal,
                          session_id=session_ref, tags=["intent"]) as _t1:
        intent_result: IntentResult = classify(goal)
        _t1.end(output_text=f"{intent_result.intent.value} ({intent_result.confidence:.2f})")
    print(f"      Intent: {intent_result.intent.value} (confidence: {intent_result.confidence:.2f})")
    print(f"      Reason: {intent_result.reasoning}")

    if intent_result.intent == Intent.AMBIGUOUS:
        print(f"\n  Question: {intent_result.clarifying_question}")
        return OrchestrationResult(
            goal=goal, intent=intent_result.intent.value,
            task_count=0, results=[],
            duration_seconds=time.time() - start,
            status="ambiguous",
        )

    # ── Stage 2: Plan Decomposition ───────────────────────────────────────────
    print("\n[2/5] Decomposing into tasks...")
    extra_context = ""
    if prior_context:
        extra_context += f"Prior session context:\n{prior_context}\n\n"

    plan: Plan = decompose(goal, session_ref=session_ref, context=extra_context)
    print(f"      {len(plan.tasks)} task(s) generated")
    print()
    print(format_plan(plan))

    # ── Stage 3: Plan Review ──────────────────────────────────────────────────
    print("[3/5] Reviewing plan quality...")
    review_result: ReviewResult = review(plan)

    attempts = 0
    while not review_result.approved and attempts < MAX_REPLAN_ATTEMPTS:
        print(f"      Plan rejected (attempt {attempts + 1}/{MAX_REPLAN_ATTEMPTS}):")
        for issue in review_result.feedback:
            print(f"        ! {issue}")

        # Replan with feedback as context
        context = "Previous plan was rejected. Issues to fix:\n" + "\n".join(review_result.feedback)
        plan = decompose(goal, session_ref=session_ref, context=context)
        review_result = review(plan)
        attempts += 1

    if not review_result.approved:
        print("      Plan could not be approved after replanning. Review manually.")
        for issue in review_result.feedback:
            print(f"        ! {issue}")
        return OrchestrationResult(
            goal=goal, intent=intent_result.intent.value,
            task_count=len(plan.tasks), results=[],
            duration_seconds=time.time() - start,
            status="blocked",
        )

    print("      Plan approved ✓")

    # ── Stage 4: Checkpoint Gates ─────────────────────────────────────────────
    print("\n[4/5] Evaluating checkpoints...")
    trace_event("checkpoint", metadata={"task_count": len(plan.tasks)},
               session_id=session_ref)
    approved_tasks = []
    for i, task in enumerate(plan.tasks):
        task_id = f"{session_ref}-plan-{i}"
        proceed, reason = evaluate(task, task_id=task_id)
        if proceed:
            print(f"      [{i}] {task.title} [{task.risk.value}] → {reason}")
            approved_tasks.append(task)
        else:
            print(f"      [{i}] {task.title} [{task.risk.value}] → BLOCKED: {reason}")

    if not approved_tasks:
        return OrchestrationResult(
            goal=goal, intent=intent_result.intent.value,
            task_count=len(plan.tasks), results=[],
            duration_seconds=time.time() - start,
            status="blocked",
        )

    # ── Stage 5: Delegate + Monitor ───────────────────────────────────────────
    print(f"\n[5/5] Delegating {len(approved_tasks)} task(s) to agents...")
    results = delegate_plan(approved_tasks, session_ref=session_ref)

    # ── Synthesize ────────────────────────────────────────────────────────────
    done = sum(1 for r in results if r.status == "done")
    failed = sum(1 for r in results if r.status == "failed")
    total = len(results)
    duration = time.time() - start
    overall_status = "complete" if failed == 0 else "partial"

    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║  Results                                             ║")
    print("╠══════════════════════════════════════════════════════╣")
    for r in results:
        icon = "✔" if r.status == "done" else "✖"
        print(f"║  {icon} [{r.task_id}] {r.title[:40]:<40}  ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  {done}/{total} tasks completed in {duration:.0f}s{'':<25}  ║")
    print("╚══════════════════════════════════════════════════════╝")

    # Store run result + session context
    summary = (
        f"goal={goal[:80]} | intent={intent_result.intent.value} | "
        f"tasks={total} | done={done} | failed={failed} | "
        f"duration={duration:.0f}s | session={session_ref}"
    )
    _store_memory(f"justai/runs/{session_ref}-{int(time.time())}", summary)
    _save_session_context(session_ref, summary)

    flush_traces()
    return OrchestrationResult(
        goal=goal,
        intent=intent_result.intent.value,
        task_count=total,
        results=results,
        duration_seconds=duration,
        status=overall_status,
    )


def _parse_args(argv: list[str]) -> tuple[str, bool]:
    """Parse CLI args. Returns (goal, auto_mode)."""
    auto = False
    remaining = []
    for arg in argv:
        if arg == "--auto":
            auto = True
        else:
            remaining.append(arg)
    goal = " ".join(remaining)
    return goal, auto


if __name__ == "__main__":
    goal, auto_flag = _parse_args(sys.argv[1:])
    if not goal:
        print("Usage: python3 -m justai.orchestrator [--auto] \"your goal here\"")
        sys.exit(1)
    result = run(goal, auto=auto_flag or AUTO_MODE)
    sys.exit(0 if result.status in ("complete", "ambiguous") else 1)
