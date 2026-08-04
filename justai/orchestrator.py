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
from justai.checkpoint import (
    GateIdentity,
    cleanup_run,
    evaluate,
    own_run,
    prune_abandoned_runs,
    sweep_gate_dirs,
)
from justai.discord import OrchestratorHook
from justai.exit_codes import for_run_status
from justai.health import preflight, print_preflight, readiness
from justai.intent_gate import INTENT_MODEL, Intent, IntentResult, classify
from justai.learning import enrich_context, record_run
from justai.ledger import Ledger
from justai.memory import Memory
from justai.results import RUN_FAILED, tally
from justai.reviewer import REVIEWER_MODEL, ReviewResult, review
from justai.run_identity import new_run_id, parse_run_id
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
    #: This run's identity — what its gates were scoped to. Returned so a
    #: caller can name the exact run afterwards, in a log or a resume.
    run_id: str = ""


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

    Everything below treats ``results`` as untrusted, including its type. An
    executor that returned no sequence at all reaches here too, and iterating
    or measuring it would raise a second exception inside the very handler that
    exists to record the first one.

    The verdict is ``failed``: no result set was countable, so nothing here was
    verified, and :func:`justai.exit_codes.for_run_status` maps that to nonzero.
    ``record_run`` is still called and refuses an unusable status on its own —
    the trajectory store must not file a run it cannot classify either.
    """
    produced = list(results) if isinstance(results, (list, tuple)) else []
    print()
    print(f"  ✗ Run failed at [{stage}]: {error}")
    for index, r in enumerate(produced):
        task_id = getattr(r, "task_id", None)
        title = getattr(r, "title", None)
        status = getattr(r, "status", None)
        safe_task_id = task_id if isinstance(task_id, str) else f"result-{index}"
        safe_title = title[:38] if isinstance(title, str) else "<invalid title>"
        safe_status = status if isinstance(status, str) else f"<invalid {type(status).__name__}>"
        print(f"      unusable [{safe_task_id}] {safe_title} → status {safe_status!r}")
    print(
        f"    {len(produced)} result(s) produced; the set is not countable. Nothing was verified."
    )
    print("    Fix the executor that emitted this, or the caller that named the blocked tasks.")
    print()

    hook.on_error("Run results could not be counted", stage=stage, root_cause=str(error))
    _ledger.record(run_id=run_id, agent=session_ref, stage=stage, duration_s=round(duration, 2))
    record_run(goal, produced, duration)
    flush_traces()

    return OrchestrationResult(
        goal=goal,
        intent=intent,
        task_count=len(produced),
        results=produced,
        duration_seconds=duration,
        status=RUN_FAILED,
        run_id=run_id,
    )


def _print_header(goal: str, auto: bool = False, run_id: str = "", session_ref: str = "") -> None:
    print()
    print("╔══════════════════════════════════════════════════════╗")
    mode = " [AUTO]" if auto else ""
    print(f"║  JustAi Orchestrator{mode:<36}║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  Goal: {goal[:70]}")
    # Named up front because it is what an operator needs before the run
    # reaches a gate: which run is asking, and which one an approval releases.
    print(f"  Run:  {run_id}  (session: {session_ref or 'unlabelled'})")
    print()


def run(
    goal: str,
    session_ref: str = SESSION_REF,
    auto: bool = AUTO_MODE,
    local: bool = LOCAL_EXEC,
    swarm: bool = SWARM_MODE,
    run_id: str | None = None,
) -> OrchestrationResult:
    """
    Full orchestration pipeline for a given goal.

    Args:
        goal: The task to accomplish.
        session_ref: Human label for tracing and memory. Reused on purpose and
            often empty; it names nothing and scopes nothing.
        auto: If True, R1 checkpoints auto-approve immediately (no 60s wait).
            The decision is passed to each checkpoint rather than exported to
            the environment: it belongs to this run, and a process-global copy
            of it disabled the R1 operator veto for every later run in the same
            interpreter — including every subsequent request to the API server.
        local: If True, execute tasks locally instead of delegating to agent.
        run_id: This run's identity, minted fresh when omitted — which is what
            an ordinary CLI or API run does. Pass one only deliberately: to
            resume a run whose gates are already on disk, or to mint the
            identity in the caller so an operator can be told where the gates
            will be before the run reaches them (the API server does this). It
            must be a UUID; a label, a timestamp or a goal is refused, because
            two runs can produce the same one and then one approval releases
            both.

    Raises:
        InvalidRunId: ``run_id`` was supplied and is not a UUID. Nothing runs —
            a run whose gates cannot be scoped must not reach a gate.
        RunAlreadyActive: another process is already driving this run id.
            Nothing runs. A resume that waited would execute the same run
            against the same approval as soon as the first process finished.
    """
    run_id = new_run_id() if run_id is None else parse_run_id(run_id)

    # One process drives one run, for the whole of it. The claim covers reading
    # the approval, the dispatch that acts on it, and the cleanup that removes
    # it, because a second process between any two of those reads a decision
    # this run has already been given — and executes it again.
    with own_run(run_id) as owner:
        try:
            return _run_stages(
                goal,
                session_ref=session_ref,
                auto=auto,
                local=local,
                swarm=swarm,
                run_id=run_id,
            )
        finally:
            # Terminal, and inside the claim: this run's decisions have done
            # their work, and nothing else may be reading them. Scoped to this
            # run id and to nothing else — a parallel run's pending approval is
            # not this run's to delete. A run that *dies* before here leaves
            # its gates behind on purpose; that is what makes a resume
            # possible, and `prune_abandoned_runs` is what bounds how long.
            cleanup_run(run_id, owner=owner)

            # Cleanup keeps this run's lock, because removing a lock other
            # processes exclude on is how exclusion ends rather than how a run
            # ends. The empty directory left behind is collected here once it
            # is old enough, and a gate nobody answered once nobody could still
            # be coming back for it. A run that is live, still holds a decision
            # worth resuming, or holds a file JustAi did not write is left.
            sweep_gate_dirs()
            prune_abandoned_runs()


def _run_stages(
    goal: str,
    *,
    session_ref: str,
    auto: bool,
    local: bool,
    swarm: bool,
    run_id: str,
) -> OrchestrationResult:
    """The pipeline itself, with this run already claimed by this process.

    Split from :func:`run` so the claim, and the cleanup that has to happen
    inside it, wrap every way this returns — including the early ones.
    """
    start = time.time()
    _print_header(goal, auto=auto, run_id=run_id, session_ref=session_ref)

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
            run_id=run_id,
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
                run_id=run_id,
            )

        _t3.end(
            output_text=f"approved (attempts: {attempts + 1})",
            metadata={"verdict": "approved", "attempts": attempts + 1, "first_try": attempts == 0},
        )
    _hook.on_stage("reviewer", f"approved (attempts: {attempts + 1})")
    _ledger.record(run_id=run_id, agent=session_ref, model=REVIEWER_MODEL, stage="reviewer")
    print("      Plan approved ✓")

    # ── Stage 4: Checkpoint Gates ─────────────────────────────────────────────
    print(f"\n[4/5] Evaluating checkpoints... (gates for run {run_id})")
    trace_event(
        "checkpoint",
        metadata={"task_count": len(plan.tasks), "run_id": run_id},
        session_id=session_ref,
    )
    # Blocked tasks keep their position in the plan. Dropping them here used to
    # renumber the survivors, which silently redirected every `depends_on`.
    blocked_reasons: dict[int, str] = {}
    # Every gate below is scoped to this run's id, so a concurrent run that
    # happens to share the session label — the default, since `justai run`
    # leaves it empty — cannot be released by an approval written for this one.
    # The run's own lock is already held for the whole run by `own_run`, and it
    # stays held past this stage: an approval read here is acted on in stage 5,
    # and a second process reading it in between is the same decision executed
    # twice.
    for i, task in enumerate(plan.tasks):
        gate = GateIdentity(run_id=run_id, index=i, session_ref=session_ref)
        proceed, reason = evaluate(task, gate, auto=auto)
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
        run_id=run_id,
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
