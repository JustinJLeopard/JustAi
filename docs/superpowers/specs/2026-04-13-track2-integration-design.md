# Track 2 Integration: Trajectory Learning + Mini-First Escalation

**Date:** 2026-04-13
**Status:** Approved
**Sprint:** 13 (post-Sprint 12 experiments)
**Approach:** B — Learning Layer Module

## Summary

Integrate the Sprint 12 Track 2 experiment findings into the default
orchestrator pipeline. Trajectory learning becomes always-on context
enrichment for the planner. Mini-first escalation becomes the default
execution strategy (try cheap model first, escalate on failure). Together
they create a flywheel: each run produces trajectory data that improves
future runs.

The compounding pipeline:
1. Goal arrives
2. Trajectory search finds similar past runs (~22ms HNSW lookup)
3. Those trajectories become planner context -> better task decomposition
4. Mini-first executes each task: cheap model handles routine work
5. Only escalates to expensive model when the cheap model fails
6. Results stored as new trajectory -> next similar run is better

## Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Trajectory learning | Always-on (default) | ~22ms cost, no downside when store empty, zero-impact graceful degradation |
| Mini-first | Always-on (default) | Same execution paths, just adds retry-with-escalation wrapper |
| Mini-first scope | Per-task (not whole-plan) | Preserves planner decomposition benefits, each task independently escalates |
| Mini-first mechanism | Delegator wrapper (not LLM pipeline) | Uses proven mini-swe-agent runtime, produces .traj.json data for the flywheel |
| Architecture | Learning Layer module (Approach B) | Clean separation, orchestrator stays lean, independently testable |

## New Module: `justai/learning.py`

Two functions the orchestrator calls at fixed points in the pipeline.

### `enrich_context(goal: str) -> str`

- Calls `TrajectoryStore.search(goal, limit=3)`
- Filters matches with similarity > 0.6
- Formats via `TrajectoryStore.format_as_context()`
- Returns context string (prepended to planner's `context` parameter)
- Returns `""` on empty store, MCP failure, or no matches — zero impact on flow

### `record_run(goal: str, results: list[DelegationResult], duration: float) -> bool`

- Extracts step summaries from DelegationResult list
- Determines outcome from result statuses ("success" / "partial" / "failed")
- Calls `TrajectoryStore.store(goal, steps, outcome, duration)`
- Returns True/False, never raises — fire-and-forget

Both functions reuse the existing `TrajectoryStore` from `trajectory.py` unchanged.

## Refactored Module: `justai/mini_first.py`

The existing `MiniFirstPipeline` (pseudocode->tests->code LLM pipeline) stays
as an importable utility but is not part of the default orchestrator flow.

New functions added for the escalation strategy:

### `escalate_task(task: Task, session_ref: str, executor: Callable) -> DelegationResult`

- Takes a Task, session ref, and an executor function (existing delegate/execute/swarm)
- **First attempt:** Runs task via `executor` with cheap model configured
- **Check:** If `status == "done"`, return immediately
- **Escalate:** If failed, re-run same task with escalation model, prepending
  failure context: "A previous attempt failed with: {error}. Take a different approach."
- Returns DelegationResult with metadata indicating whether escalation occurred
- Max 1 escalation attempt per task (no infinite retries)

### `escalate_plan(tasks: list[Task], session_ref: str, mode: str) -> list[DelegationResult]`

- Iterates tasks in dependency order (same logic as current `delegate_plan`)
- For each task, calls `escalate_task()` with appropriate executor based on mode:
  - `mode="delegated"` -> `delegator.delegate`
  - `mode="local"` -> `executor.execute_plan` (single task)
  - `mode="swarm"` -> `SwarmDelegator` dispatch
- Dependency skipping: if a task's dependency failed even after escalation, skip it

### Model routing

- Cheap model: `gpt-5.3-codex` (env: `JUSTAI_MINI_MODEL`)
- Escalation model: `claude-opus-4-6` (env: `JUSTAI_ESCALATION_MODEL`)
- Model selection: `escalate_task` sets `JUSTAI_ACTIVE_MODEL` env var before
  calling the executor. First attempt sets it to `JUSTAI_MINI_MODEL`, escalation
  sets it to `JUSTAI_ESCALATION_MODEL`. The delegator/executor reads this to
  determine which model to request from LiteLLM. Env var is restored after each call.

## Orchestrator Changes (`justai/orchestrator.py`)

Three surgical insertion points. No restructuring.

### 1. Before Stage 2 — Trajectory context enrichment (~line 147)

After session context loading, before plan decomposition:

```python
trajectory_context = enrich_context(goal)
if trajectory_context:
    extra_context += trajectory_context
    print(f"  Trajectory context loaded ({len(trajectory_context)} chars)")
```

Flows into existing `decompose(goal, context=extra_context)`. No changes to
`planner.py` — it already accepts arbitrary context.

### 2. Stage 5 — Replace execution branching

Replace the `if swarm / elif local / else` block with:

```python
mode = "swarm" if swarm else ("local" if local else "delegated")
results = escalate_plan(approved_tasks, session_ref=session_ref, mode=mode)
```

The three execution paths (swarm, local, delegated) move inside `escalate_plan`.
Each task tries cheap model first, escalates on failure.

### 3. After synthesize — Record trajectory (~line 323)

```python
record_run(goal, results, duration)
```

Fire-and-forget. Stores the run for future trajectory lookups.

### New imports

```python
from justai.learning import enrich_context, record_run
from justai.mini_first import escalate_plan
```

### OrchestrationResult change

Add one field:

```python
escalations: int  # count of tasks that required escalation
```

## What Doesn't Change

- Stages 1-4 (intent, plan, review, checkpoint) — untouched
- `planner.py` — untouched (already accepts context parameter)
- `delegator.py` — untouched (used internally by escalate_plan)
- `swarm_delegator.py` — untouched (used internally by escalate_plan)
- `synthesizer.py` — untouched
- `trajectory.py` — untouched (TrajectoryStore reused as-is)
- `memory.py` — untouched
- CLI flags (`--swarm`, `--local`, `--auto`) — same behavior
- Existing 451 tests — must still pass

## Testing

### `tests/test_learning.py`

- Empty store returns `""`, planner works unchanged
- Store with matches returns formatted context string
- `record_run` stores trajectory (mock MCP call, verify payload shape)
- MCP unreachable — both functions return gracefully (no exceptions)

### `tests/test_mini_first.py` (updated)

- Task succeeds on first try (cheap model) — no escalation, returns "done"
- Task fails on cheap, succeeds on escalation — returns "done" with metadata
- Task fails on both — returns "failed"
- Dependency skipping works with escalation
- Each execution mode (local/delegated/swarm) routes correctly

### Integration verification

- Full `python3 -m pytest tests/` must pass (451+ tests)
- No untested code paths in touched files

## Error Handling

| Failure | Behavior |
|---------|----------|
| Trajectory search: MCP down/timeout | `enrich_context` returns `""`. Planner proceeds without trajectory context. Logged. |
| Trajectory store: MCP down/timeout | `record_run` returns `False`. Run completes normally. Logged. |
| Escalation: both models fail | Task result is "failed" (same as today). Max 1 escalation attempt. |
| Malformed trajectory data | Filtered out during search result parsing. Logged. |

## Dependencies

No new external packages. All integration uses:
- `TrajectoryStore` from `justai/trajectory.py` (existing, MCP HTTP)
- Existing delegators (`delegator.py`, `executor.py`, `swarm_delegator.py`)
- Existing LiteLLM routing (model selection via env vars)

## Files Touched

| File | Change |
|------|--------|
| `justai/learning.py` | **NEW** — enrich_context, record_run |
| `justai/mini_first.py` | **MODIFY** — add escalate_task, escalate_plan alongside existing MiniFirstPipeline |
| `justai/orchestrator.py` | **MODIFY** — 3 insertion points (trajectory context, escalation dispatch, trajectory store) |
| `tests/test_learning.py` | **NEW** — learning layer tests |
| `tests/test_mini_first.py` | **MODIFY** — add escalation strategy tests |
