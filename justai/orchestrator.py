#!/usr/bin/env python3
"""
JustAi — Orchestrator
======================
Main pipeline: intake → intent → plan → review → checkpoint → delegate → synthesize

Usage:
    python3 -m justai.orchestrator "your goal here"
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
import subprocess
import sys
import time
from dataclasses import dataclass

from justai.intent_gate import classify, Intent, IntentResult
from justai.planner import decompose, Plan, format_plan
from justai.reviewer import review, ReviewResult
from justai.checkpoint import evaluate
from justai.delegator import delegate_plan, DelegationResult

MAX_REPLAN_ATTEMPTS = 2
SESSION_REF = os.environ.get("JUSTAI_SESSION_REF", "sprint-2")
MEMORY_DB = os.path.expanduser("~/projects/ruv-research")


@dataclass
class OrchestrationResult:
    goal: str
    intent: str
    task_count: int
    results: list[DelegationResult]
    duration_seconds: float
    status: str   # "complete" | "partial" | "blocked" | "ambiguous"


def _store_memory(key: str, value: str) -> None:
    """Store outcome in claude-flow memory."""
    try:
        subprocess.run(
            ["claude-flow", "memory", "store", "-k", key, "-v", value],
            capture_output=True, cwd=MEMORY_DB, timeout=10
        )
    except Exception:
        pass


def _print_header(goal: str) -> None:
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║  JustAi Orchestrator                                 ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  Goal: {goal[:70]}")
    print()


def run(goal: str, session_ref: str = SESSION_REF) -> OrchestrationResult:
    """
    Full orchestration pipeline for a given goal.
    """
    start = time.time()
    _print_header(goal)

    # ── Stage 1: Intent Classification ───────────────────────────────────────
    print("[1/5] Classifying intent...")
    intent_result: IntentResult = classify(goal)
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
    plan: Plan = decompose(goal, session_ref=session_ref)
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

    # Store in claude-flow memory
    summary = (
        f"goal={goal[:80]} | intent={intent_result.intent.value} | "
        f"tasks={total} | done={done} | failed={failed} | "
        f"duration={duration:.0f}s | session={session_ref}"
    )
    _store_memory(f"justai/runs/{session_ref}-{int(time.time())}", summary)

    return OrchestrationResult(
        goal=goal,
        intent=intent_result.intent.value,
        task_count=total,
        results=results,
        duration_seconds=duration,
        status=overall_status,
    )


if __name__ == "__main__":
    goal = " ".join(sys.argv[1:])
    if not goal:
        print("Usage: python3 -m justai.orchestrator \"your goal here\"")
        sys.exit(1)
    result = run(goal)
    sys.exit(0 if result.status in ("complete", "ambiguous") else 1)
