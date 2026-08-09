#!/usr/bin/env python3
"""
JustAi — Orchestrator
======================
Main pipeline: intake → intent → plan → review → checkpoint → delegate →
synthesize → intent-fidelity gate

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
  - Intent-fidelity gate judges whether the OUTCOME achieved the original
    intent ("A or better"); a task-complete-but-intent-missed run is honestly
    downgraded rather than reported as complete
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
from justai.health import preflight, print_preflight
from justai.intent_fidelity import score_fidelity
from justai.intent_gate import INTENT_MODEL, Intent, IntentResult, classify
from justai.learning import enrich_context, record_run
from justai.ledger import Ledger
from justai.memory import Memory
from justai.reviewer import REVIEWER_MODEL, ReviewResult, review
from justai.scope_planner import PLANNER_MODEL, Plan, decompose, format_plan
from justai.results import tally
from justai.synthesizer import format_summary, synthesize
from justai.tracing import flush_traces, trace_event, trace_generation

MAX_REPLAN_ATTEMPTS = 2
SESSION_REF = os.environ.get("JUSTAI_SESSION_REF", "sprint-2")
AUTO_MODE = os.environ.get("JUSTAI_AUTO_MODE", "").lower() in ("1", "true", "yes")
LOCAL_EXEC = os.environ.get("JUSTAI_LOCAL_EXEC", "").lower() in ("1", "true", "yes")
SWARM_MODE = os.environ.get("JUSTAI_SWARM_MODE", "").lower() in ("1", "true", "yes")
# Intent-fidelity gate: on by default; set JUSTAI_FIDELITY_GATE=0 to disable.
FIDELITY_GATE_ENABLED = os.environ.get("JUSTAI_FIDELITY_GATE", "1").lower() in ("1", "true", "yes")


@dataclass
class OrchestrationResult:
    goal: str
    intent: str
    task_count: int
    results: list
    duration_seconds: float
    status: str  # "complete" | "partial" | "blocked" | "failed" | "ambiguous"
    escalations: int = 0
    # Intent-fidelity gate (None when the gate did not run):
    intent_fidelity: float | None = None  # 0-100 percentile
    fidelity_verdict: str | None = None  # met | exceeded | missed
    fidelity_grade: str | None = None  # A+/A/B/C/D/F
    a_or_better: bool | None = None  # cleared the intent bar


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


def _print_header(goal: str, auto: bool = False) -> None:
    print()
    print("╔══════════════════════════════════════════════════════╗")
    mode = " [AUTO]" if auto else ""
    print(f"║  JustAi Orchestrator{mode:<36}║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  Goal: {goal[:70]}")
    print()


def _describe_unusable_results(results, validation_error: Exception) -> str:
    """Best-effort, operator-facing description of why a result set is unusable.

    Preserve the validator's exact field/type reason. For a real result
    sequence, also name the first offending task when one is available.
    """
    reason = str(validation_error)
    if not isinstance(results, (list, tuple)):
        return reason

    for result in results:
        try:
            tally([result], strict=True)
        except (ValueError, TypeError):
            task = getattr(result, "title", None) or getattr(result, "task_id", None)
            return f"{reason} on task {task!r}" if task is not None else reason
    return reason


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
        local: If True, execute tasks locally instead of delegating to agent.
    """
    start = time.time()
    run_id = f"{session_ref}-{int(start)}"
    _print_header(goal, auto=auto)

    # Discord notifications (no-op if webhook not configured)
    _hook = OrchestratorHook(run_id=run_id)

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
    print("[1/6] Classifying intent...")
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
    print("\n[2/6] Decomposing into tasks...")
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
    print("[3/6] Reviewing plan quality...")
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
    print("\n[4/6] Evaluating checkpoints...")
    trace_event("checkpoint", metadata={"task_count": len(plan.tasks)}, session_id=session_ref)
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
            goal=goal,
            intent=intent_result.intent.value,
            task_count=len(plan.tasks),
            results=[],
            duration_seconds=time.time() - start,
            status="blocked",
        )


    # ── Stage 5: Execute ─────────────────────────────────────────────────────
    stage5_name = "swarm" if swarm else ("local" if local else "external")
    with trace_generation(
        stage5_name,
        input_text=f"{len(approved_tasks)} tasks",
        session_id=session_ref,
        tags=[stage5_name],
        metadata={
            "stage": stage5_name,
            "task_count": len(approved_tasks),
            "mode": "swarm" if swarm else ("local" if local else "delegated"),
        },
    ) as _t5:
        mode = "swarm" if swarm else ("local" if local else "delegated")
        print(f"\n[5/6] Executing {len(approved_tasks)} task(s) via {mode} (with escalation)...")
        results = escalate_plan(approved_tasks, session_ref=session_ref, mode=mode)

        # Fail-closed boundary: a result set the run cannot report safely
        # (unknown status, malformed shape, non-numeric duration, or not even a
        # sequence) must END THE RUN AS FAILED with its traces flushed and a
        # record filed — never a traceback that loses the evidence, and never a
        # silent bucket that could read as success downstream.
        try:
            exec_counts = tally(results, strict=True)
        except (ValueError, TypeError) as exc:
            diag = _describe_unusable_results(results, exc)
            _t5.end(output_text="unusable results", metadata={"error": str(exc)[:160]})
            duration = time.time() - start
            print(f"\n[!] Run failed closed at execute: {diag}")
            _hook.on_error("unusable execution results", stage=stage5_name, root_cause=diag)
            _ledger.record(run_id=run_id, agent=session_ref, stage="execute-invalid")
            record_run(goal, [], duration, final_status="failed")
            flush_traces()
            return OrchestrationResult(
                goal=goal,
                intent=intent_result.intent.value,
                task_count=len(plan.tasks),
                results=[],
                duration_seconds=duration,
                status="failed",
            )

        done_count = exec_counts.done
        failed_count = exec_counts.failed
        _t5.end(
            output_text=f"{done_count}/{len(results)} done",
            metadata={"done": done_count, "failed": failed_count, "total": len(results)},
        )
    _hook.on_stage(stage5_name, f"{done_count}/{len(results)} done")
    _ledger.record(run_id=run_id, agent=session_ref, stage=stage5_name)

    # ── Stage 6: Intent-Fidelity Gate (A or better) ───────────────────────────
    # Judge whether the OUTCOME achieved the original intent — not just whether
    # tasks ran. A task-complete run that missed the intent is downgraded by the
    # synthesizer (below). The gate must never fail a run: any error → skip.
    fidelity = None
    if FIDELITY_GATE_ENABLED:
        print("\n[6/6] Intent-fidelity gate (A or better)...")
        try:
            fidelity = score_fidelity(goal, plan, results)
            print(
                f"      Fidelity: {fidelity.fidelity:.0f}/100 grade {fidelity.grade} "
                f"— {fidelity.verdict.value} (source: {fidelity.source})"
            )
            print(f"      {fidelity.rationale}")
        except Exception as e:  # noqa: BLE001 -- gate is best-effort, never fatal
            print(f"      (fidelity gate skipped: {e.__class__.__name__})")
            fidelity = None

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
            fidelity=fidelity,
        )
        _t6.end(
            output_text=f"{summary.status}: {summary.done}/{summary.total_tasks} done, {duration:.1f}s",
            metadata={
                "status": summary.status,
                "done": summary.done,
                "failed": summary.failed,
                "total": summary.total_tasks,
                "duration_s": round(duration, 2),
                "intent_fidelity": summary.intent_fidelity,
                "fidelity_verdict": summary.fidelity_verdict,
                "a_or_better": summary.a_or_better,
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
    record_run(goal, results, duration, final_status=summary.status)

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
        intent_fidelity=summary.intent_fidelity,
        fidelity_verdict=summary.fidelity_verdict,
        fidelity_grade=summary.fidelity_grade,
        a_or_better=summary.a_or_better,
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


def _run_cli(argv: list[str]) -> int:
    """Entry logic for `python -m justai.orchestrator`, returning an exit code.

    Routes the exit through the shared exit-code mapping so the direct module
    cannot report an ambiguous/unexecuted run as success (exit 0) — the same
    contract the `justai`/legacy CLIs use.
    """
    from justai.exit_codes import for_run_status

    goal, auto_flag, local_flag, swarm_flag = _parse_args(argv)
    if not goal:
        print('Usage: python3 -m justai.orchestrator [--auto] [--local] [--swarm] "your goal here"')
        return 1
    result = run(
        goal,
        auto=auto_flag or AUTO_MODE,
        local=local_flag or LOCAL_EXEC,
        swarm=swarm_flag or SWARM_MODE,
    )
    return for_run_status(result.status)


if __name__ == "__main__":
    sys.exit(_run_cli(sys.argv[1:]))
