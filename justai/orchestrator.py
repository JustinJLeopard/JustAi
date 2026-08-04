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
  - Mini-first execution handles local/delegated task outcomes
  - Synthesizer aggregates results and stores in claude-flow memory
"""

from __future__ import annotations

import os
import sys
import time
from contextlib import suppress
from dataclasses import dataclass

from justai.agent_dispatch import escalate_plan
from justai.checkpoint import evaluate
from justai.discord import OrchestratorHook
from justai.exit_codes import for_run_status
from justai.health import preflight, print_preflight, readiness
from justai.intent_gate import INTENT_MODEL, Intent, IntentResult, classify
from justai.learning import enrich_context, record_run
from justai.ledger import Ledger
from justai.memory import Memory
from justai.results import RUN_FAILED, tally
from justai.reviewer import REVIEWER_MODEL, ReviewResult, review
from justai.scope_planner import PLANNER_MODEL, Plan, decompose, format_plan
from justai.synthesizer import format_summary, synthesize
from justai.tracing import flush_traces, trace_event, trace_generation

MAX_REPLAN_ATTEMPTS = 2
SESSION_REF = os.environ.get("JUSTAI_SESSION_REF", "sprint-2")
AUTO_MODE = os.environ.get("JUSTAI_AUTO_MODE", "").lower() in ("1", "true", "yes")
LOCAL_EXEC = os.environ.get("JUSTAI_LOCAL_EXEC", "").lower() in ("1", "true", "yes")
SWARM_MODE = os.environ.get("JUSTAI_SWARM_MODE", "").lower() in ("1", "true", "yes")


@dataclass
class OrchestrationResult:
    goal: str
    intent: str
    task_count: int
    results: list
    duration_seconds: float
    status: str  # "complete" | "partial" | "blocked" | "ambiguous"
    escalations: int = 0


# Shared memory client — talks to MCP HTTP at :3100 (~5ms vs ~300ms CLI)
_memory = Memory()
_ledger = Ledger()


def _store_memory(key: str, value: str) -> None:
    """Store outcome in claude-flow memory via MCP HTTP."""
    with suppress(Exception):
        _memory.store(key, value)


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


def _fail_uncountable_results(
    *,
    goal: str,
    intent: str,
    results: list,
    duration: float,
    run_id: str,
    session_ref: str,
    stage: str,
    hook: OrchestratorHook,
    error: ValueError,
) -> OrchestrationResult:
    """End a run whose results cannot be counted, without losing the evidence.

    Two contracts under this stage raise rather than guess: ``tally`` refuses a
    status outside the canonical vocabulary, and ``escalate_plan`` refuses a
    blocked index that names no task in the plan. Both refusals are right.
    Letting the exception leave ``run`` was not — it skipped the trace flush and
    the run record, so the operator got a traceback in place of a verdict and
    the run left no artefact behind.

    The verdict is ``failed``: no result set was countable, so nothing here was
    verified, and :func:`justai.exit_codes.for_run_status` maps that to nonzero.
    ``record_run`` is still called and refuses an unusable status on its own —
    the trajectory store must not file a run it cannot classify either.
    """
    print()
    print(f"  ✗ Run failed at [{stage}]: {error}")
    for index, r in enumerate(results):
        task_id = getattr(r, "task_id", None)
        title = getattr(r, "title", None)
        status = getattr(r, "status", None)
        safe_task_id = task_id if isinstance(task_id, str) else f"result-{index}"
        safe_title = title[:38] if isinstance(title, str) else "<invalid title>"
        safe_status = status if isinstance(status, str) else f"<invalid {type(status).__name__}>"
        print(f"      unusable [{safe_task_id}] {safe_title} → status {safe_status!r}")
    print(f"    {len(results)} result(s) produced; the set is not countable. Nothing was verified.")
    print("    Fix the executor that emitted this, or the caller that named the blocked tasks.")
    print()

    hook.on_error("Run results could not be counted", stage=stage, root_cause=str(error))
    _ledger.record(run_id=run_id, agent=session_ref, stage=stage, duration_s=round(duration, 2))
    record_run(goal, results, duration)
    flush_traces()

    return OrchestrationResult(
        goal=goal,
        intent=intent,
        task_count=len(results),
        results=results,
        duration_seconds=duration,
        status=RUN_FAILED,
    )


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
    local: bool = LOCAL_EXEC,
    swarm: bool = SWARM_MODE,
) -> OrchestrationResult:
    """
    Full orchestration pipeline for a given goal.

    Args:
        goal: The task to accomplish.
        session_ref: Session identifier for tracing and memory.
        auto: If True, R1 checkpoints auto-approve immediately (no 60s wait).
            The decision is passed to each checkpoint rather than exported to
            the environment: it belongs to this run, and a process-global copy
            of it disabled the R1 operator veto for every later run in the same
            interpreter — including every subsequent request to the API server.
        local: If True, execute tasks locally instead of delegating to agent.
    """
    start = time.time()
    run_id = f"{session_ref}-{int(start)}"
    _print_header(goal, auto=auto)

    # Discord notifications (no-op if webhook not configured)
    _hook = OrchestratorHook(run_id=run_id)

    # ── Preflight: service health ─────────────────────────────────────────────
    statuses = preflight()
    litellm_ok = print_preflight(statuses)

    if not litellm_ok:
        print("  ⚠ LiteLLM unreachable — pipeline will use heuristic fallbacks")
        print()

    # Say up front what `justai status` and the API's /health already report,
    # so the run does not look like it is heading for completion.
    if not readiness(statuses).execution_ready:
        print("  ⚠ No execution backend is integrated — dispatch will fail closed")
        print()

    # ── Session context: load prior run ───────────────────────────────────────
    prior_context = _load_session_context(session_ref)
    if prior_context:
        print(f"  Session context loaded ({len(prior_context)} chars)")
        print(f"    {prior_context[:120]}...")
        print()

    # ── Stage 1: Intent Classification ───────────────────────────────────────
    print("[1/5] Classifying intent...")
    with trace_generation(
        "intent-gate",
        model=INTENT_MODEL,
        input_text=goal,
        session_id=session_ref,
        tags=["intent"],
        metadata={"stage": "intent-gate", "model": INTENT_MODEL},
    ) as _t1:
        intent_result: IntentResult = classify(goal)
        _t1.end(
            output_text=f"{intent_result.intent.value} ({intent_result.confidence:.2f})",
            metadata={
                "classification": intent_result.intent.value,
                "confidence": intent_result.confidence,
            },
        )
    _hook.on_stage("intent-gate", f"{intent_result.intent.value} ({intent_result.confidence:.2f})")
    _ledger.record(run_id=run_id, agent=session_ref, model=INTENT_MODEL, stage="intent-gate")
    print(
        f"      Intent: {intent_result.intent.value} (confidence: {intent_result.confidence:.2f})"
    )
    print(f"      Reason: {intent_result.reasoning}")

    if intent_result.intent == Intent.AMBIGUOUS:
        print(f"\n  Question: {intent_result.clarifying_question}")
        return OrchestrationResult(
            goal=goal,
            intent=intent_result.intent.value,
            task_count=0,
            results=[],
            duration_seconds=time.time() - start,
            status="ambiguous",
        )

    # ── Stage 2: Plan Decomposition ───────────────────────────────────────────
    print("\n[2/5] Decomposing into tasks...")
    extra_context = ""
    if prior_context:
        extra_context += f"Prior session context:\n{prior_context}\n\n"

    # ── Trajectory enrichment: find similar past runs ────────────────────────
    trajectory_context = enrich_context(goal)
    if trajectory_context:
        extra_context += f"Trajectory context (from similar past runs):\n{trajectory_context}\n\n"
        print(f"  Trajectory context loaded ({len(trajectory_context)} chars)")
        print()

    with trace_generation(
        "planner",
        model=PLANNER_MODEL,
        input_text=goal,
        session_id=session_ref,
        tags=["planner"],
        metadata={"stage": "planner", "model": PLANNER_MODEL},
    ) as _t2:
        plan: Plan = decompose(goal, session_ref=session_ref, context=extra_context)
        _t2.end(
            output_text=f"{len(plan.tasks)} tasks: {', '.join(t.title for t in plan.tasks[:5])}",
            metadata={"task_count": len(plan.tasks)},
        )
    _hook.on_stage("planner", f"{len(plan.tasks)} tasks generated")
    _ledger.record(run_id=run_id, agent=session_ref, model=PLANNER_MODEL, stage="planner")
    print(f"      {len(plan.tasks)} task(s) generated")
    print()
    print(format_plan(plan))

    # ── Stage 3: Plan Review ──────────────────────────────────────────────────
    print("[3/5] Reviewing plan quality...")
    with trace_generation(
        "reviewer",
        model=REVIEWER_MODEL,
        input_text=format_plan(plan),
        session_id=session_ref,
        tags=["reviewer"],
        metadata={"stage": "reviewer", "model": REVIEWER_MODEL},
    ) as _t3:
        review_result: ReviewResult = review(plan)

        attempts = 0
        while not review_result.approved and attempts < MAX_REPLAN_ATTEMPTS:
            print(f"      Plan rejected (attempt {attempts + 1}/{MAX_REPLAN_ATTEMPTS}):")
            for issue in review_result.feedback:
                print(f"        ! {issue}")

            # Replan with feedback as context
            context = "Previous plan was rejected. Issues to fix:\n" + "\n".join(
                review_result.feedback
            )
            plan = decompose(goal, session_ref=session_ref, context=context)
            review_result = review(plan)
            attempts += 1

        if not review_result.approved:
            _t3.end(
                output_text=f"rejected after {attempts} attempts",
                level="WARNING",
                metadata={
                    "verdict": "rejected",
                    "attempts": attempts,
                    "issues": review_result.feedback[:5],
                },
            )
            _hook.on_error(
                "Plan rejected after replanning",
                stage="reviewer",
                root_cause="; ".join(review_result.feedback[:3]),
            )
            print("      Plan could not be approved after replanning. Review manually.")
            for issue in review_result.feedback:
                print(f"        ! {issue}")
            return OrchestrationResult(
                goal=goal,
                intent=intent_result.intent.value,
                task_count=len(plan.tasks),
                results=[],
                duration_seconds=time.time() - start,
                status="blocked",
            )

        _t3.end(
            output_text=f"approved (attempts: {attempts + 1})",
            metadata={"verdict": "approved", "attempts": attempts + 1, "first_try": attempts == 0},
        )
    _hook.on_stage("reviewer", f"approved (attempts: {attempts + 1})")
    _ledger.record(run_id=run_id, agent=session_ref, model=REVIEWER_MODEL, stage="reviewer")
    print("      Plan approved ✓")

    # ── Stage 4: Checkpoint Gates ─────────────────────────────────────────────
    print("\n[4/5] Evaluating checkpoints...")
    trace_event("checkpoint", metadata={"task_count": len(plan.tasks)}, session_id=session_ref)
    # Blocked tasks keep their position in the plan. Dropping them here used to
    # renumber the survivors, which silently redirected every `depends_on`.
    blocked_reasons: dict[int, str] = {}
    for i, task in enumerate(plan.tasks):
        task_id = f"{session_ref}-plan-{i}"
        proceed, reason = evaluate(task, task_id=task_id, auto=auto)
        if proceed:
            print(f"      [{i}] {task.title} [{task.risk.value}] → {reason}")
        else:
            print(f"      [{i}] {task.title} [{task.risk.value}] → BLOCKED: {reason}")
            blocked_reasons[i] = reason

    dispatchable = len(plan.tasks) - len(blocked_reasons)

    # ── Stage 5: Execute ─────────────────────────────────────────────────────
    stage5_name = "swarm" if swarm else ("local" if local else "external")
    with trace_generation(
        stage5_name,
        input_text=f"{dispatchable} tasks",
        session_id=session_ref,
        tags=[stage5_name],
        metadata={
            "stage": stage5_name,
            "task_count": dispatchable,
            "blocked": len(blocked_reasons),
            "mode": "swarm" if swarm else ("local" if local else "delegated"),
        },
    ) as _t5:
        mode = "swarm" if swarm else ("local" if local else "delegated")
        print(f"\n[5/5] Executing {dispatchable} task(s) via {mode} (with escalation)...")

        # One vocabulary decides these counts. Summing statuses inline here let
        # this stage disagree with the run verdict below it: withheld work fell
        # between "done" and "failed" and was reported by neither, and a status
        # nothing recognised was counted as an absence of failure.
        results: list = []
        try:
            results = escalate_plan(
                plan.tasks,
                session_ref=session_ref,
                mode=mode,
                blocked_indices=blocked_reasons,
            )
            counts = tally(results)
        except ValueError as exc:
            _t5.end(
                output_text=f"results cannot be counted: {exc}",
                level="ERROR",
                metadata={"stage": stage5_name, "error": "uncountable-results"},
            )
            return _fail_uncountable_results(
                goal=goal,
                intent=intent_result.intent.value,
                results=results,
                duration=time.time() - start,
                run_id=run_id,
                session_ref=session_ref,
                stage=stage5_name,
                hook=_hook,
                error=exc,
            )

        _t5.end(
            output_text=f"{counts.done}/{counts.total} done",
            metadata={
                "done": counts.done,
                "failed": counts.failed,
                "skipped": counts.skipped,
                "blocked": counts.blocked,
                "total": counts.total,
            },
        )
    _hook.on_stage(stage5_name, f"{counts.done}/{counts.total} done")
    _ledger.record(run_id=run_id, agent=session_ref, stage=stage5_name)

    # ── Synthesize ────────────────────────────────────────────────────────────
    duration = time.time() - start
    with trace_generation(
        "synthesizer",
        input_text=f"{len(results)} results",
        session_id=session_ref,
        tags=["synthesizer"],
        metadata={"stage": "synthesizer"},
    ) as _t6:
        summary = synthesize(
            goal=goal,
            intent=intent_result.intent.value,
            results=results,
            session_ref=session_ref,
            duration=duration,
        )
        _t6.end(
            output_text=f"{summary.status}: {summary.done}/{summary.total_tasks} done, {duration:.1f}s",
            metadata={
                "status": summary.status,
                "done": summary.done,
                "failed": summary.failed,
                "total": summary.total_tasks,
                "duration_s": round(duration, 2),
            },
        )
    _ledger.record(
        run_id=run_id, agent=session_ref, stage="synthesizer", duration_s=round(duration, 2)
    )
    _hook.on_complete(
        {
            "goal": goal,
            "status": summary.status,
            "done": summary.done,
            "total": summary.total_tasks,
            "failed": summary.failed,
            "duration": duration,
        }
    )
    print(format_summary(summary))

    # ── Record run as trajectory for future learning ─────────────────────────
    record_run(goal, results, duration)

    flush_traces()
    escalation_count = sum(
        1 for r in results if "previous attempt failed" in (r.result or "").lower()
    )
    return OrchestrationResult(
        goal=goal,
        intent=intent_result.intent.value,
        task_count=summary.total_tasks,
        results=results,
        duration_seconds=duration,
        status=summary.status,
        escalations=escalation_count,
    )


def _parse_args(argv: list[str]) -> tuple[str, bool, bool, bool]:
    """Parse CLI args. Returns (goal, auto_mode, local_mode, swarm_mode)."""
    auto = False
    local = False
    swarm = False
    remaining = []
    for arg in argv:
        if arg == "--auto":
            auto = True
        elif arg == "--local":
            local = True
        elif arg == "--swarm":
            swarm = True
        else:
            remaining.append(arg)
    goal = " ".join(remaining)
    return goal, auto, local, swarm


if __name__ == "__main__":
    goal, auto_flag, local_flag, swarm_flag = _parse_args(sys.argv[1:])
    if not goal:
        print('Usage: python3 -m justai.orchestrator [--auto] [--local] [--swarm] "your goal here"')
        sys.exit(1)
    result = run(
        goal,
        auto=auto_flag or AUTO_MODE,
        local=local_flag or LOCAL_EXEC,
        swarm=swarm_flag or SWARM_MODE,
    )
    sys.exit(for_run_status(result.status))
