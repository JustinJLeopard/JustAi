# Brief — JustAi Bubble-Up: Retire-Confirmed-N/A, Substrate-Targeted Action IDs, Learning.py Meta-Cognition

**Date:** 2026-05-06
**Status:** REFINED 2026-05-06 (post-rite-of-passage; targets corrected via `git ls-tree origin/<branch>` verification)
**Source:** home-bubbleup-followups Cowork session
**Upstream:** `~/projects/lem/handins/2026-05-06-research-home-environment-applications.md` Section C; Lem L5 audit; `loop-stuck-fix-2026-05-06`; `lesson-working-tree-fallacy-2026-05-06`

## Refinement notes (what changed since v1 of this brief)

The original 2026-05-06 brief had three items. After applying rite-of-passage discipline (`git status` + `git ls-tree origin/<branch>` per path):

- **Item 1 (quarantine `swarm_delegator.py`): CONFIRMED N/A.** Justin caught: file is not on `origin/demo-build`. Local working tree had a pre-reset orphan. Lesson canonized at `lesson-working-tree-fallacy-2026-05-06`. Item dropped from this revised brief.
- **Item 2 (explicit action_id/result_id): RETARGETED.** `JustAi/justai/runner_protocol.py` is a STUB on `origin/demo-build` that explicitly declares **safe-mini** as canonical home: *"The canonical home for this Protocol and the types below is the safe-mini repo... DO NOT ADD JustAi-specific fields to these types."* Action-evidence IDs are substrate-generic (no JustAi-specific fields), so they belong in **safe-mini**, not JustAi or the verify sandbox. Item 2 below is rewritten as a safe-mini RFC pointer; the implementation belongs in safe-mini.
- **Item 3 (learning.py meta-cognition): VIABLE on origin/demo-build.** `justai/learning.py` exists on the public branch and matches my earlier quote-grounded read. Items 3 below.

Confidence: 0.94 on retargeting (grounded in verbatim stub-doc quote); 0.92 on Item 3 (verbatim code grounded).

## Item 2 (REVISED) — safe-mini explicit action_id / result_id RFC pointer

This is no longer a JustAi brief item. It belongs at `~/projects/safe-mini/<RFC-path>`.

The Lem L4 lesson — every emitted action gets a `tool_call_id`, every result gets a `result_id`, durable `(action_id, result_id, evidence_ref)` triples on the bus — is exactly the substrate-generic shape that fits `runner_protocol.Protocol` upstream of JustAi.

Recommended structure for the safe-mini RFC:

- Add `ActionRecord(action_id: UUID, action_type: str, args: dict, issued_at: datetime)` and `ResultRecord(result_id: UUID, action_id: UUID, status: Literal["ok","fail","timeout"], evidence_ref: str | None, finished_at: datetime)` to safe-mini types.
- Extend `RunResult` with `actions: list[ActionRecord]` and `results: list[ResultRecord]`, preserving existing `transcript_path / final_diff / failure_class` for back-compat.
- Tests in `safe-mini/tests/test_protocol.py` proving every action emitted lands a result with matching `action_id` (or explicit timeout result).
- Once safe-mini ships the new types, JustAi's `runner_protocol.py` stub gets minor revision (or stays a stub; consumers migrate when they're ready).

This brief proposes that the next JustAi-side action is to **wait** for safe-mini to ship action-evidence types, then JustAi consumes them. Cross-repo coordination — safe-mini RFC is a separate dispatch, not part of this brief.

If Justin wants me to draft the safe-mini RFC, that's a fresh brief targeting the safe-mini repo — would land at `~/projects/safe-mini/handins/` (verifying first that handins/ is the convention used there, since Justin's three public repos may have different layouts).

## Item 3 — `learning.py` meta-cognition upgrade

### Current code on origin/demo-build (verbatim quote-before-assert)

`JustAi/justai/learning.py` head from `git show origin/demo-build`:

```python
SIMILARITY_THRESHOLD = 0.6
SEARCH_LIMIT = 3

def enrich_context(goal: str) -> str:
    """Search trajectory store for similar past runs and format as planner context."""
    try:
        matches = _store.search(goal, limit=SEARCH_LIMIT)
        good_matches = [m for m in matches if m.similarity >= SIMILARITY_THRESHOLD]
        if not good_matches: return ""
        return TrajectoryStore.format_as_context(good_matches)
    except Exception as e:
        logger.debug(f"Trajectory search failed (non-fatal): {e}")
        return ""

def record_run(goal: str, results: list, duration: float) -> bool:
    # ... stores: goal, steps, outcome, duration. Outcome inferred from r.status counts.
```

Same shape as my prior local read. Trajectory model is minimal: `goal/steps/outcome/duration`.

### What's missing (Lem L4b lesson + 8eb8c1c auto-review pipeline pattern)

1. **Failure class** — categorical (timeout / tool_error / wrong_action / inferred_action / verification_fail) rather than just outcome.
2. **Execution evidence** — for each step, the `(action_id, result_id, evidence_ref)` triple (depends on safe-mini Item 2 above).
3. **Strategy used** — which strategy from the catalog was chosen, with explicit `accepted/ignored` outcome on the next plan.
4. **Did-next-plan-change** — boolean: did the prior trajectory's outcome actually shift the next plan's chosen_focus? Per `workflow-sop` v8 loop-awareness pattern, this distinguishes learning from looping.

### NEW reference pattern from lem commit 8eb8c1c (auto-review pipeline)

Lem's loop-stuck fix at `8eb8c1c` solved a parallel problem: `review_proposal/verdict` pipeline was wired ONLY to one tool path (`propose_new_tool`) but Lem's prompt directed proposals to a different path (raw `bus_insert` to `lem/proposal`). Result: proposals landed but never received verdicts; loop awareness silently degraded.

Same shape applies to JustAi's `record_run`: if the verdict-or-failure-class assignment pipeline is wired to ONE source of evidence (e.g. `r.status` text), it'll silently fail when actions arrive via a path that doesn't populate `r.status` cleanly. The fix pattern from 8eb8c1c:

- When a write hits a "review-eligible" channel/event, mirror the verdict pipeline rather than gating on a single tool name.
- Auto-attach correlation_id; emit verdict on the same id so downstream context picks it up.
- Non-fatal: review exception is captured as `evidence.verdict_error`, not swallowed.

For JustAi: when `record_run` lands, mirror the meta-correction pipeline regardless of which subsystem emitted the action evidence. Don't gate on `r.status` text inference.

### Recommended `record_run` upgrade

```python
def record_run(
    goal: str,
    results: list,
    duration: float,
    *,
    actions: list[ActionRecord] | None = None,    # from safe-mini (Item 2 dependency)
    failure_class: str | None = None,             # categorical
    strategy: str | None = None,                  # which strategy was applied
    next_plan_changed: bool | None = None,        # filled in on the NEXT run
    correlation_id: str | None = None,            # for auto-verdict mirroring
) -> bool:
```

`enrich_context` returns: similar trajectories + their `failure_class` distribution + which strategies worked + which were tried-and-discarded. Next planner pass has `prior_plans + execution_evidence + loop_detected` per workflow-sop v8.

### Did-next-plan-change closure (delayed update)

Cleanest implementation: `record_run` stores trajectory open-ended; the *next* `enrich_context` call (which knows the new plan's chosen_focus) writes back `next_plan_changed = (new_chosen_focus != prior_chosen_focus)` on the prior trajectory row. Mirrors Lem's L3 pattern: real `experiment_executed` event_ids post-facto, NOT keyword inference.

## Sequencing

1. **Item 3 (learning.py)** can land WITHOUT Item 2 (safe-mini types). The new `record_run` kwargs are optional; the trajectory rows can carry `failure_class / strategy / next_plan_changed` independently of `actions`. When safe-mini ships, wire actions through.
2. **Item 2 (safe-mini RFC)** is a separate dispatch to a separate repo. Surface for separate verdict.

Action this session: dispatch Item 3 only.

## Acceptance criteria for THIS brief

- [ ] Justin verdict.
- [ ] If PROCEED on Item 3: cdx dispatch lands updated `learning.py` + tests + a follow-up handin documenting the 4-field schema (failure_class, strategy, next_plan_changed, correlation_id).
- [ ] No code changes to JustAi main without per-item verdict.
- [ ] Safe-mini RFC for Item 2 = separate brief if Justin says go.

Confidence: 0.92 on Item 3 (grounded in origin/demo-build code + memory keys); 0.85 on the safe-mini retarget being correct (depends on safe-mini's RFC layout convention which I haven't verified yet).
