# Track 2 Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Sprint 12 Track 2 experiments (trajectory learning + mini-first escalation) into the default orchestrator pipeline so every run learns from past executions and uses cheap models first.

**Architecture:** New `learning.py` module handles trajectory context enrichment and post-run storage. Escalation functions added to `mini_first.py` wrap existing delegators with try-cheap-then-escalate logic. Orchestrator gets three surgical insertions: trajectory context before planning, escalation dispatch for execution, trajectory storage after synthesis.

**Tech Stack:** Python 3.12, existing TrajectoryStore (MCP HTTP), existing delegators, LiteLLM model routing

**Spec:** `docs/superpowers/specs/2026-04-13-track2-integration-design.md`

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `justai/learning.py` | Trajectory context enrichment + post-run storage | **NEW** |
| `justai/mini_first.py` | Escalation strategy wrapping existing delegators | **MODIFY** (add functions, keep existing pipeline) |
| `justai/orchestrator.py` | Main pipeline — 3 insertion points | **MODIFY** |
| `tests/test_learning.py` | Learning layer unit tests | **NEW** |
| `tests/test_mini_first.py` | Escalation strategy tests | **MODIFY** (add tests, keep existing) |

---

### Task 1: Learning Layer — Tests

**Files:**
- Create: `tests/test_learning.py`

- [ ] **Step 1: Write test file with all learning layer tests**

```python
"""Tests for justai.learning — trajectory context enrichment + run recording."""
from __future__ import annotations
import json
import pytest
from unittest.mock import patch, MagicMock
from justai.delegator import DelegationResult


def _make_result(title: str, status: str = "done", result: str = "ok") -> DelegationResult:
    return DelegationResult(
        task_id=f"test-{title[:10]}",
        title=title,
        status=status,
        result=result,
        duration_seconds=1.5,
    )


class TestEnrichContext:
    def test_empty_store_returns_empty_string(self):
        """When trajectory store has no matches, enrich_context returns ''."""
        from justai.learning import enrich_context
        with patch("justai.learning._store") as mock_store:
            mock_store.search.return_value = []
            result = enrich_context("implement REST API")
        assert result == ""

    def test_low_similarity_filtered_out(self):
        """Matches below 0.6 similarity are excluded."""
        from justai.learning import enrich_context
        from justai.trajectory import TrajectoryMatch
        low_match = TrajectoryMatch(
            key="traj/old", goal="unrelated task", steps=["step1"],
            outcome="success", similarity=0.4,
        )
        with patch("justai.learning._store") as mock_store:
            mock_store.search.return_value = [low_match]
            result = enrich_context("implement REST API")
        assert result == ""

    def test_high_similarity_returns_context(self):
        """Matches above 0.6 similarity produce formatted context."""
        from justai.learning import enrich_context
        from justai.trajectory import TrajectoryMatch
        good_match = TrajectoryMatch(
            key="traj/rest-api", goal="build REST API with auth",
            steps=["scaffold", "add routes", "add tests"],
            outcome="success", similarity=0.82,
        )
        with patch("justai.learning._store") as mock_store:
            mock_store.search.return_value = [good_match]
            result = enrich_context("implement REST API")
        assert "Similar past trajectories" in result
        assert "build REST API with auth" in result
        assert "0.82" in result

    def test_mcp_failure_returns_empty(self):
        """If MCP is unreachable, enrich_context returns '' without raising."""
        from justai.learning import enrich_context
        with patch("justai.learning._store") as mock_store:
            mock_store.search.side_effect = Exception("MCP unreachable")
            result = enrich_context("any goal")
        assert result == ""


class TestRecordRun:
    def test_stores_successful_run(self):
        """record_run calls TrajectoryStore.store with correct outcome."""
        from justai.learning import record_run
        results = [_make_result("task A"), _make_result("task B")]
        with patch("justai.learning._store") as mock_store:
            mock_store.store.return_value = True
            ok = record_run("build feature X", results, duration=12.5)
        assert ok is True
        call_args = mock_store.store.call_args
        assert call_args.kwargs["goal"] == "build feature X"
        assert call_args.kwargs["outcome"] == "success"
        assert call_args.kwargs["duration"] == 12.5
        assert len(call_args.kwargs["steps"]) == 2

    def test_partial_run_outcome(self):
        """When some tasks fail, outcome is 'partial'."""
        from justai.learning import record_run
        results = [_make_result("ok task"), _make_result("bad task", status="failed")]
        with patch("justai.learning._store") as mock_store:
            mock_store.store.return_value = True
            record_run("mixed goal", results, duration=5.0)
        assert mock_store.store.call_args.kwargs["outcome"] == "partial"

    def test_all_failed_outcome(self):
        """When all tasks fail, outcome is 'failed'."""
        from justai.learning import record_run
        results = [_make_result("fail1", status="failed"), _make_result("fail2", status="error")]
        with patch("justai.learning._store") as mock_store:
            mock_store.store.return_value = True
            record_run("doomed goal", results, duration=3.0)
        assert mock_store.store.call_args.kwargs["outcome"] == "failed"

    def test_mcp_failure_returns_false(self):
        """If store raises, record_run returns False without raising."""
        from justai.learning import record_run
        results = [_make_result("task")]
        with patch("justai.learning._store") as mock_store:
            mock_store.store.side_effect = Exception("MCP down")
            ok = record_run("goal", results, duration=1.0)
        assert ok is False
```

- [ ] **Step 2: Run tests to verify they fail (module doesn't exist yet)**

Run: `python3 -m pytest tests/test_learning.py -v 2>&1 | tail -15`
Expected: ModuleNotFoundError — `justai.learning` does not exist

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_learning.py
git commit -m "test: add learning layer tests (red — module not yet created)"
```

---

### Task 2: Learning Layer — Implementation

**Files:**
- Create: `justai/learning.py`

- [ ] **Step 1: Create learning.py**

```python
"""
JustAi — Learning Layer
========================
Trajectory context enrichment for the planner and post-run trajectory storage.

Called by orchestrator at two points:
  - Before planning: enrich_context(goal) -> str of similar past trajectories
  - After synthesis: record_run(goal, results, duration) -> bool

Both functions are fire-and-forget — they never raise, never block the pipeline.
"""
from __future__ import annotations

import logging
from justai.trajectory import TrajectoryStore, TrajectoryMatch

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.6
SEARCH_LIMIT = 3

# Module-level store instance — reused across calls
_store = TrajectoryStore()


def enrich_context(goal: str) -> str:
    """Search trajectory store for similar past runs and format as planner context.

    Returns formatted context string, or "" on empty/failure.
    """
    try:
        matches = _store.search(goal, limit=SEARCH_LIMIT)
        # Filter by similarity threshold
        good_matches = [m for m in matches if m.similarity >= SIMILARITY_THRESHOLD]
        if not good_matches:
            return ""
        return TrajectoryStore.format_as_context(good_matches)
    except Exception as e:
        logger.debug(f"Trajectory search failed (non-fatal): {e}")
        return ""


def record_run(
    goal: str,
    results: list,
    duration: float,
) -> bool:
    """Store run results as a trajectory for future context enrichment.

    Returns True if stored, False on failure. Never raises.
    """
    try:
        steps = [r.title for r in results]
        done = sum(1 for r in results if r.status == "done")
        failed = sum(1 for r in results if r.status in ("failed", "error", "timeout"))

        if failed == 0:
            outcome = "success"
        elif done > 0:
            outcome = "partial"
        else:
            outcome = "failed"

        return _store.store(
            goal=goal,
            steps=steps,
            outcome=outcome,
            duration=duration,
        )
    except Exception as e:
        logger.debug(f"Trajectory store failed (non-fatal): {e}")
        return False
```

- [ ] **Step 2: Run learning layer tests**

Run: `python3 -m pytest tests/test_learning.py -v`
Expected: All 8 tests PASS

- [ ] **Step 3: Commit**

```bash
git add justai/learning.py
git commit -m "feat: add learning layer — trajectory context enrichment and run recording"
```

---

### Task 3: Escalation Strategy — Tests

**Files:**
- Modify: `tests/test_mini_first.py`

- [ ] **Step 1: Add escalation strategy tests to existing test file**

Append to the end of `tests/test_mini_first.py`:

```python


# ── Escalation Strategy Tests ────────────────────────────────────────────────

class TestEscalateTask:
    def test_succeeds_first_try_no_escalation(self):
        """When executor returns done, no escalation happens."""
        from justai.mini_first import escalate_task
        from justai.delegator import DelegationResult

        task = _make_task("add endpoint")
        executor = MagicMock(return_value=DelegationResult(
            task_id="t1", title="add endpoint", status="done",
            result="completed", duration_seconds=2.0,
        ))
        result = escalate_task(task, session_ref="test", executor=executor)
        assert result.status == "done"
        assert executor.call_count == 1  # no escalation call

    def test_fails_then_escalates_successfully(self):
        """When first attempt fails, escalation succeeds."""
        from justai.mini_first import escalate_task
        from justai.delegator import DelegationResult

        task = _make_task("fix bug")
        first_result = DelegationResult(
            task_id="t1", title="fix bug", status="failed",
            result="syntax error on line 42", duration_seconds=1.0,
        )
        escalation_result = DelegationResult(
            task_id="t1-esc", title="fix bug", status="done",
            result="fixed", duration_seconds=3.0,
        )
        executor = MagicMock(side_effect=[first_result, escalation_result])
        result = escalate_task(task, session_ref="test", executor=executor)
        assert result.status == "done"
        assert executor.call_count == 2

    def test_both_attempts_fail(self):
        """When both cheap and escalation fail, returns failed."""
        from justai.mini_first import escalate_task
        from justai.delegator import DelegationResult

        task = _make_task("impossible task")
        fail = DelegationResult(
            task_id="t1", title="impossible task", status="failed",
            result="cannot do", duration_seconds=1.0,
        )
        executor = MagicMock(return_value=fail)
        result = escalate_task(task, session_ref="test", executor=executor)
        assert result.status == "failed"
        assert executor.call_count == 2  # cheap + escalation

    def test_escalation_sets_model_env(self):
        """escalate_task sets JUSTAI_ACTIVE_MODEL env var for each attempt."""
        from justai.mini_first import escalate_task, MINI_MODEL, ESCALATION_MODEL
        from justai.delegator import DelegationResult
        import os

        captured_models = []
        def capture_executor(task, session_ref=""):
            captured_models.append(os.environ.get("JUSTAI_ACTIVE_MODEL", ""))
            return DelegationResult(
                task_id="t1", title=task.title, status="failed",
                result="fail", duration_seconds=1.0,
            )

        task = _make_task("test model routing")
        escalate_task(task, session_ref="test", executor=capture_executor)
        assert captured_models[0] == MINI_MODEL
        assert captured_models[1] == ESCALATION_MODEL


class TestEscalatePlan:
    def test_dependency_skip_after_escalation_failure(self):
        """If task 0 fails after escalation, task 1 (depends on 0) is skipped."""
        from justai.mini_first import escalate_plan
        from justai.delegator import DelegationResult

        task0 = _make_task("setup db")
        task1 = _make_task("add tables")
        task1.depends_on = [0]

        fail = DelegationResult(
            task_id="t0", title="setup db", status="failed",
            result="db unreachable", duration_seconds=1.0,
        )
        with patch("justai.mini_first.escalate_task", return_value=fail):
            results = escalate_plan([task0, task1], session_ref="test", mode="local")
        assert results[0].status == "failed"
        assert results[1].status == "skipped"

    def test_routes_to_correct_executor(self):
        """escalate_plan passes the right executor for each mode."""
        from justai.mini_first import escalate_plan
        from justai.delegator import DelegationResult

        task = _make_task("single task")
        done = DelegationResult(
            task_id="t0", title="single task", status="done",
            result="ok", duration_seconds=1.0,
        )
        with patch("justai.mini_first.escalate_task", return_value=done) as mock_esc:
            escalate_plan([task], session_ref="test", mode="delegated")
            executor_arg = mock_esc.call_args.kwargs.get("executor") or mock_esc.call_args[0][2]
            # The executor should be delegator.delegate for "delegated" mode
            from justai.delegator import delegate
            assert executor_arg == delegate

    def test_all_three_modes_accepted(self):
        """escalate_plan accepts 'local', 'delegated', and 'swarm' modes."""
        from justai.mini_first import escalate_plan
        from justai.delegator import DelegationResult

        task = _make_task("test")
        done = DelegationResult(
            task_id="t0", title="test", status="done",
            result="ok", duration_seconds=1.0,
        )
        with patch("justai.mini_first.escalate_task", return_value=done):
            for mode in ("local", "delegated", "swarm"):
                results = escalate_plan([task], session_ref="test", mode=mode)
                assert len(results) == 1
                assert results[0].status == "done"
```

- [ ] **Step 2: Run new tests to verify they fail (functions don't exist yet)**

Run: `python3 -m pytest tests/test_mini_first.py::TestEscalateTask -v 2>&1 | tail -10`
Expected: ImportError — `escalate_task` not found in `justai.mini_first`

- [ ] **Step 3: Commit**

```bash
git add tests/test_mini_first.py
git commit -m "test: add escalation strategy tests (red — functions not yet implemented)"
```

---

### Task 4: Escalation Strategy — Implementation

**Files:**
- Modify: `justai/mini_first.py` (append after existing code, line 269)

- [ ] **Step 1: Add escalation constants and imports to mini_first.py**

Add these imports at the top of `justai/mini_first.py` after the existing imports (after line 28 `from dataclasses import dataclass, field`):

```python
from typing import Callable
from justai.planner import Task
from justai.delegator import delegate, DelegationResult
from justai.executor import execute_plan as _execute_plan_all
from justai.swarm_delegator import SwarmDelegator
```

Add constants after the existing `LITELLM_URL` line (after line 32):

```python
MINI_MODEL = os.environ.get("JUSTAI_MINI_MODEL", "gpt-5.3-codex")
ESCALATION_MODEL = os.environ.get("JUSTAI_ESCALATION_MODEL", "claude-opus-4-6")
```

- [ ] **Step 2: Add escalate_task function**

Append to the end of `justai/mini_first.py` (after line 269):

```python


# ── Escalation Strategy ──────────────────────────────────────────────────────
# Wraps existing delegators with try-cheap-then-escalate logic.
# The MiniFirstPipeline above is preserved as a standalone LLM pipeline utility.


def escalate_task(
    task: Task,
    session_ref: str,
    executor: Callable[..., DelegationResult],
) -> DelegationResult:
    """Execute a task with cheap model first, escalate on failure.

    Args:
        task: The task to execute.
        session_ref: Session identifier for tracing.
        executor: A callable(task, session_ref) -> DelegationResult.
                  One of: delegator.delegate, executor single-task wrapper, swarm dispatch.

    Returns:
        DelegationResult — from first attempt if successful, from escalation otherwise.
    """
    original_model = os.environ.get("JUSTAI_ACTIVE_MODEL", "")

    # First attempt: cheap model
    try:
        os.environ["JUSTAI_ACTIVE_MODEL"] = MINI_MODEL
        result = executor(task, session_ref=session_ref)
    finally:
        os.environ["JUSTAI_ACTIVE_MODEL"] = original_model

    if result.status == "done":
        return result

    # Escalate: expensive model with failure context
    print(f"[escalation] task '{task.title}' failed on {MINI_MODEL}, escalating to {ESCALATION_MODEL}")
    escalated_task = Task(
        title=task.title,
        description=(
            f"{task.description}\n\n"
            f"NOTE: A previous attempt failed with: {result.result[:300]}\n"
            f"Take a different approach."
        ),
        agent=task.agent,
        risk=task.risk,
        success_criteria=task.success_criteria,
        depends_on=task.depends_on,
        session_ref=task.session_ref,
    )

    try:
        os.environ["JUSTAI_ACTIVE_MODEL"] = ESCALATION_MODEL
        escalation_result = executor(escalated_task, session_ref=session_ref)
    finally:
        os.environ["JUSTAI_ACTIVE_MODEL"] = original_model

    return escalation_result


def _execute_single_local(task: Task, session_ref: str = "") -> DelegationResult:
    """Adapter: run a single task through the local executor and return DelegationResult."""
    from justai.executor import ExecResult
    results = _execute_plan_all([task])
    if not results:
        return DelegationResult(
            task_id="local-err", title=task.title,
            status="error", result="Local executor returned no results",
            duration_seconds=0.0,
        )
    er = results[0]
    return DelegationResult(
        task_id=er.task_id, title=er.title,
        status=er.status, result=er.result,
        duration_seconds=er.duration_seconds,
    )


def _execute_single_swarm(task: Task, session_ref: str = "") -> DelegationResult:
    """Adapter: run a single task through swarm dispatch and return DelegationResult."""
    sd = SwarmDelegator(max_agents=1)
    sd.spawn_agents(1)
    swarm_results = sd.dispatch_parallel([task], session_ref=session_ref)
    sd.shutdown()
    if not swarm_results:
        return DelegationResult(
            task_id="swarm-err", title=task.title,
            status="error", result="Swarm returned no results",
            duration_seconds=0.0,
        )
    sr = swarm_results[0]
    return DelegationResult(
        task_id=sr.task_id, title=sr.title,
        status=sr.status, result=sr.result,
        duration_seconds=sr.duration_seconds,
    )


_EXECUTORS = {
    "delegated": delegate,
    "local": _execute_single_local,
    "swarm": _execute_single_swarm,
}


def escalate_plan(
    tasks: list[Task],
    session_ref: str = "",
    mode: str = "delegated",
) -> list[DelegationResult]:
    """Execute a task plan with per-task escalation.

    Each task tries cheap model first, escalates to expensive model on failure.
    Tasks run in dependency order; if a dependency fails (even after escalation),
    dependent tasks are skipped.

    Args:
        tasks: Ordered list of tasks from the planner.
        session_ref: Session identifier.
        mode: Execution mode — "delegated", "local", or "swarm".
    """
    executor = _EXECUTORS.get(mode, delegate)
    results: list[DelegationResult | None] = [None] * len(tasks)

    for i, task in enumerate(tasks):
        # Check dependencies
        skip = False
        for dep_idx in task.depends_on:
            if dep_idx < len(results) and results[dep_idx] and results[dep_idx].status != "done":
                print(f"[escalation] skipping task [{i}] '{task.title}' — dependency [{dep_idx}] failed")
                results[i] = DelegationResult(
                    task_id="skipped", title=task.title,
                    status="skipped",
                    result=f"Skipped — dependency [{dep_idx}] did not complete after escalation",
                    duration_seconds=0,
                )
                skip = True
                break

        if not skip:
            results[i] = escalate_task(task, session_ref=session_ref, executor=executor)
            status = results[i].status
            esc_note = ""
            print(f"[escalation] task [{i}] {status}{esc_note}: {results[i].result[:80]}")

    return [r for r in results if r is not None]
```

- [ ] **Step 3: Run escalation tests**

Run: `python3 -m pytest tests/test_mini_first.py -v`
Expected: All tests PASS (existing 7 + new 7 = 14 total)

- [ ] **Step 4: Commit**

```bash
git add justai/mini_first.py
git commit -m "feat: add escalation strategy — try cheap model first, escalate on failure"
```

---

### Task 5: Orchestrator Integration

**Files:**
- Modify: `justai/orchestrator.py`

- [ ] **Step 1: Add imports**

In `justai/orchestrator.py`, after line 41 (`from justai.discord import OrchestratorHook`), add:

```python
from justai.learning import enrich_context, record_run
from justai.mini_first import escalate_plan
```

- [ ] **Step 2: Add trajectory context enrichment before Stage 2**

In `justai/orchestrator.py`, after line 176 (`extra_context += f"Prior session context:\n{prior_context}\n\n"`), add:

```python
    # ── Trajectory enrichment: find similar past runs ────────────────────────
    trajectory_context = enrich_context(goal)
    if trajectory_context:
        extra_context += f"Trajectory context (from similar past runs):\n{trajectory_context}\n\n"
        print(f"  Trajectory context loaded ({len(trajectory_context)} chars)")
        print()
```

- [ ] **Step 3: Replace Stage 5 execution block**

In `justai/orchestrator.py`, replace lines 262-288 (the `if swarm` / `elif local` / `else` block) with:

```python
        mode = "swarm" if swarm else ("local" if local else "delegated")
        print(f"\n[5/5] Executing {len(approved_tasks)} task(s) via {mode} (with escalation)...")
        results = escalate_plan(approved_tasks, session_ref=session_ref, mode=mode)
```

- [ ] **Step 4: Add trajectory recording after synthesize**

In `justai/orchestrator.py`, after line 323 (`print(format_summary(summary))`), add:

```python
    # ── Record run as trajectory for future learning ─────────────────────────
    record_run(goal, results, duration)
```

- [ ] **Step 5: Add escalations field to OrchestrationResult**

In `justai/orchestrator.py`, modify the `OrchestrationResult` dataclass (line 50-57) to add:

```python
@dataclass
class OrchestrationResult:
    goal: str
    intent: str
    task_count: int
    results: list[DelegationResult]
    duration_seconds: float
    status: str   # "complete" | "partial" | "blocked" | "ambiguous"
    escalations: int = 0
```

And in the return statement at line 326, add the escalations count:

```python
    flush_traces()
    escalation_count = sum(1 for r in results if "previous attempt failed" in (r.result or "").lower())
    return OrchestrationResult(
        goal=goal,
        intent=intent_result.intent.value,
        task_count=summary.total_tasks,
        results=results,
        duration_seconds=duration,
        status=summary.status,
        escalations=escalation_count,
    )
```

- [ ] **Step 6: Remove unused imports**

The following imports in `orchestrator.py` are no longer directly used in Stage 5 (they're used internally by `escalate_plan`):

```python
# These can be removed from orchestrator.py imports:
from justai.executor import execute_plan, ExecResult
from justai.swarm_delegator import SwarmDelegator
```

Keep `from justai.delegator import delegate_plan, DelegationResult` — `DelegationResult` is still used in `OrchestrationResult` and other parts.

- [ ] **Step 7: Run full test suite**

Run: `python3 -m pytest tests/ -v 2>&1 | tail -20`
Expected: All tests PASS (451 existing + 15 new)

- [ ] **Step 8: Commit**

```bash
git add justai/orchestrator.py
git commit -m "feat: integrate trajectory learning + escalation into orchestrator pipeline"
```

---

### Task 6: Integration Smoke Test

**Files:**
- No new files — verification only

- [ ] **Step 1: Verify imports work**

Run: `python3 -c "from justai.learning import enrich_context, record_run; from justai.mini_first import escalate_plan, escalate_task; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 2: Verify orchestrator loads without errors**

Run: `python3 -c "from justai.orchestrator import run, OrchestrationResult; print(f'OrchestrationResult fields: {[f.name for f in __import__(\"dataclasses\").fields(OrchestrationResult)]}')"`
Expected: Field list includes `escalations`

- [ ] **Step 3: Verify trajectory store connectivity (if MCP running)**

Run: `python3 -c "from justai.learning import enrich_context; r = enrich_context('test goal'); print(f'enrich_context returned: {repr(r[:50] if r else \"(empty)\")}')"`
Expected: Either trajectory context string or `(empty)` — no exception

- [ ] **Step 4: Run full test suite one final time**

Run: `python3 -m pytest tests/ -v --tb=short 2>&1 | tail -25`
Expected: All tests PASS, 0 failures

- [ ] **Step 5: Final commit with all changes**

```bash
git add -A
git status
git commit -m "feat(sprint13): integrate Track 2 — trajectory learning + mini-first escalation

Trajectory learning is now always-on: similar past runs feed planner context.
Mini-first escalation wraps all execution paths: cheap model first, escalate on failure.
Each run stores results as trajectory data, creating a flywheel that improves over time.

New: justai/learning.py (enrich_context, record_run)
Modified: justai/mini_first.py (escalate_task, escalate_plan)
Modified: justai/orchestrator.py (3 integration points)
Tests: 15 new tests covering learning layer and escalation strategy"
```
