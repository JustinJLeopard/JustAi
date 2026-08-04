"""Regression coverage for JustAi's completion-integrity boundary.

Every test here pins one rule: JustAi must never signal success for work it did
not verify. They are grouped by the surface that can leak a false success —
readiness reporting, process exit codes, dependency gating, run synthesis, and
the standalone dispatch experiment.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# tools/justai_cli.py imports its sibling as a top-level module, so `tools/`
# has to be importable before this file's legacy-CLI test can load it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from justai import agent_dispatch
from justai.agent_dispatch import escalate_plan
from justai.health import ServiceStatus
from justai.results import DelegationResult
from justai.scope_planner import AgentType, Plan, RiskLevel, Task


def _task(title: str, depends_on: list[int] | None = None) -> Task:
    return Task(
        title=title,
        description=f"Do {title}.",
        agent=AgentType.MINI,
        risk=RiskLevel.R0,
        success_criteria="echo ok",
        depends_on=list(depends_on or []),
    )


def _result(status: str = "done", title: str = "task") -> DelegationResult:
    return DelegationResult(
        task_id="t",
        title=title,
        status=status,
        result="ok",
        duration_seconds=1.0,
    )


def _statuses(*, litellm: bool = True, safe_mini: bool = False, memory: bool = True):
    return [
        ServiceStatus("LiteLLM", "http://localhost:4000", litellm, "probe"),
        ServiceStatus("safe-mini boundary", "justai.runner_protocol", safe_mini, "probe"),
        ServiceStatus("claude-flow MCP", "http://127.0.0.1:3100", memory, "probe"),
    ]


# ── Finding 1: readiness semantics disagree across CLI and API ───────────────


def test_status_exit_code_does_not_contradict_api_all_ok():
    """`justai status` must not exit 0 while the API reports all_ok false."""
    from justai.api import _get_health
    from justai.cli import cmd_status

    statuses = _statuses(safe_mini=False)
    with (
        patch("justai.health.preflight", return_value=statuses),
        patch("justai.api.preflight", return_value=statuses),
        patch("justai.memory.Memory", MagicMock()),
    ):
        health = _get_health()
        code = cmd_status(argparse.Namespace())

    assert health["all_ok"] is False
    assert code != 0, "status exited 0 while the API reported the control plane not ok"


def test_status_reports_planning_and_execution_readiness_separately():
    """Readiness must name which capability is available, not collapse to one bit."""
    from justai.health import readiness

    r = readiness(_statuses(litellm=True, safe_mini=False))

    assert r.planning_ready is True, "model-backed planning is available and must say so"
    assert r.execution_ready is False, "no concrete runner is integrated"
    assert r.all_ok is False


def test_api_health_exposes_the_same_readiness_fields_as_the_cli():
    from justai.api import _get_health

    with patch("justai.api.preflight", return_value=_statuses()):
        health = _get_health()

    assert health["planning_ready"] is True
    assert health["execution_ready"] is False
    assert health["all_ok"] is False


def test_readiness_of_an_empty_probe_set_is_not_ok():
    """No evidence is not evidence of health."""
    from justai.health import readiness

    assert readiness([]).all_ok is False


def test_status_exits_zero_only_when_every_probe_is_ok():
    from justai.cli import cmd_status
    from justai.exit_codes import OK

    statuses = _statuses(litellm=True, safe_mini=True, memory=True)
    with (
        patch("justai.health.preflight", return_value=statuses),
        patch("justai.memory.Memory", MagicMock()),
    ):
        assert cmd_status(argparse.Namespace()) == OK


# ── Finding 2: an ambiguous run with no tasks exits 0 ────────────────────────


def test_ambiguous_run_does_not_exit_zero():
    """Exit 0 is reserved for verified completion; a question is not completion."""
    from justai.cli import cmd_run
    from justai.exit_codes import CLARIFICATION_REQUIRED
    from justai.orchestrator import OrchestrationResult

    ambiguous = OrchestrationResult(
        goal="do something vague",
        intent="ambiguous",
        task_count=0,
        results=[],
        duration_seconds=0.1,
        status="ambiguous",
    )
    args = argparse.Namespace(goal=["do", "something"], session="", auto=True, local=True)
    with patch("justai.orchestrator.run", return_value=ambiguous):
        code = cmd_run(args)

    assert code == CLARIFICATION_REQUIRED
    assert code != 0


def test_legacy_tools_cli_also_refuses_to_exit_zero_when_ambiguous():
    from types import SimpleNamespace

    from justai.exit_codes import CLARIFICATION_REQUIRED
    from justai.orchestrator import OrchestrationResult
    from tools.justai_cli import run_cmd

    ambiguous = OrchestrationResult("goal", "ambiguous", 0, [], 1.0, "ambiguous")
    with patch("justai.orchestrator.run", return_value=ambiguous):
        code = run_cmd(SimpleNamespace(goal="goal", session_ref="test"))

    assert code == CLARIFICATION_REQUIRED


def test_exit_zero_requires_a_complete_run_with_at_least_one_task():
    from justai.exit_codes import FAILED, OK, for_run_status

    assert for_run_status("complete") == OK
    assert for_run_status("partial") == FAILED
    assert for_run_status("blocked") == FAILED
    assert for_run_status("failed") == FAILED


# ── Finding 3: checkpoint filtering breaks depends_on indices ────────────────


def test_blocked_dependency_does_not_let_its_dependent_run():
    """Compacting the task list used to shift indices so a dependent ran anyway."""
    from justai.orchestrator import run

    plan = Plan(goal="g", tasks=[_task("Task 0"), _task("Task 1", depends_on=[0])], session_ref="t")

    def gate(task, task_id="", auto=None):
        # Task 0 is blocked at the checkpoint; Task 1 would be approved on its own.
        return (task.title != "Task 0", "blocked for test" if task.title == "Task 0" else "auto")

    with patch.multiple(
        "justai.orchestrator",
        classify=MagicMock(return_value=_execution_intent()),
        decompose=MagicMock(return_value=plan),
        review=MagicMock(return_value=_approved_review()),
        evaluate=MagicMock(side_effect=gate),
        preflight=MagicMock(return_value=[]),
        print_preflight=MagicMock(return_value=True),
        flush_traces=MagicMock(),
        _memory=MagicMock(),
        _ledger=MagicMock(),
        OrchestratorHook=MagicMock(),
        trace_generation=MagicMock(return_value=_trace_ctx()),
        trace_event=MagicMock(),
        record_run=MagicMock(),
        enrich_context=MagicMock(return_value=""),
    ):
        result = run("goal", session_ref="t", auto=True, local=True)

    assert len(result.results) == 2, "every planned task must keep a result slot"
    assert result.results[0].status == "blocked"
    assert result.results[1].status == "skipped", (
        "Task 1 depends on a task the checkpoint blocked and must not be dispatched"
    )
    assert result.status != "complete"


@pytest.mark.parametrize(
    ("depends_on", "reason"),
    [
        ([-1], "negative"),
        ([5], "out-of-range"),
        ([1], "forward"),
        ([0], "self"),
        # depends_on is filled from model-authored JSON, so it is not typed.
        (["0"], "string"),
        ([True], "bool that would silently index task 1"),
        ([None], "null"),
    ],
)
def test_invalid_dependency_indices_fail_closed(depends_on, reason):
    """A dependency that cannot name an already-decided task is never satisfied."""
    tasks = [_task("only task", depends_on=depends_on)]

    [result] = escalate_plan(tasks, session_ref="dep", mode="local")

    assert result.status == "error", f"{reason} dependency should fail closed"
    assert "dependency" in result.result.lower()


def test_a_dependency_list_that_is_not_a_list_fails_closed():
    """The planner hands over whatever the model emitted; 2 is not [2]."""
    task = _task("only task")
    task.depends_on = 2  # type: ignore[assignment]

    [result] = escalate_plan([task], session_ref="dep", mode="local")

    assert result.status == "error"
    assert "dependency" in result.result.lower()


def test_blocked_indices_keep_original_task_positions():
    tasks = [_task("a"), _task("b"), _task("c", depends_on=[1])]

    results = escalate_plan(tasks, session_ref="dep", mode="local", blocked_indices={1})

    assert [r.title for r in results] == ["a", "b", "c"]
    assert results[1].status == "blocked"
    assert results[2].status == "skipped"


# ── Finding 4: empty and unknown-status results read as success ──────────────


def test_synthesize_refuses_to_call_an_empty_run_complete():
    from justai.synthesizer import synthesize

    summary = synthesize("goal", "execution", [], "test", 1.0)

    assert summary.total_tasks == 0
    assert summary.status != "complete"


def test_synthesize_rejects_an_unknown_result_status():
    from justai.synthesizer import synthesize

    with pytest.raises(ValueError, match="unknown result status"):
        synthesize("goal", "execution", [_result("mission-accomplished")], "test", 1.0)


def test_synthesize_counts_blocked_results_without_calling_them_complete():
    from justai.synthesizer import synthesize

    summary = synthesize("goal", "execution", [_result("blocked"), _result("done")], "test", 1.0)

    assert summary.blocked == 1
    assert summary.status == "partial"


def test_learning_does_not_record_an_empty_run_as_successful():
    from justai.learning import record_run

    with patch("justai.learning._store") as store:
        store.store.return_value = True
        recorded = record_run("goal", [], duration=1.0)

    assert recorded is False
    store.store.assert_not_called()


def test_learning_does_not_call_a_fully_skipped_run_successful():
    from justai.learning import record_run

    with patch("justai.learning._store") as store:
        store.store.return_value = True
        record_run("goal", [_result("skipped"), _result("blocked")], duration=1.0)

    assert store.store.call_args.kwargs["outcome"] != "success"


def test_learning_rejects_an_unknown_result_status_instead_of_storing_success():
    from justai.learning import record_run

    with patch("justai.learning._store") as store:
        store.store.return_value = True
        recorded = record_run("goal", [_result("mission-accomplished")], duration=1.0)

    assert recorded is False
    store.store.assert_not_called()


def test_synthesizer_and_learning_agree_on_what_counts_as_success():
    """The two surfaces must not disagree about the same result set."""
    from justai.learning import record_run
    from justai.synthesizer import synthesize

    cases = [
        [],
        [_result("done")],
        [_result("done"), _result("skipped")],
        [_result("failed")],
        [_result("blocked")],
    ]
    for results in cases:
        summary = synthesize("goal", "execution", results, "test", 1.0)
        with patch("justai.learning._store") as store:
            store.store.return_value = True
            record_run("goal", results, duration=1.0)
            outcome = (
                store.store.call_args.kwargs["outcome"] if store.store.call_args else "not-recorded"
            )
        assert (summary.status == "complete") == (outcome == "success"), (
            f"disagreement for {[r.status for r in results]}: "
            f"synthesizer={summary.status} learning={outcome}"
        )


# ── Finding 5: the dispatch experiment claims tests pass for unwritten code ──


def test_dispatch_pipeline_cannot_claim_tests_pass_for_code_it_never_wrote(tmp_path):
    """It holds generated code as strings, so any test run is about other code."""
    from justai.agent_dispatch import AgentDispatchConfig, AgentDispatchPipeline

    with (
        patch("justai.agent_dispatch._llm_call", return_value="def add(a, b): return a + b"),
        # Patched globally, not on the module: the module must no longer import
        # subprocess at all, and this still catches a shell-out from anywhere.
        patch(
            "subprocess.run",
            side_effect=AssertionError("pipeline shelled out against an unchanged worktree"),
        ),
        pytest.raises(NotImplementedError, match="materiali"),
    ):
        AgentDispatchPipeline(AgentDispatchConfig(max_mini_iterations=1)).run(
            "implement add", spec="add(a, b) returns a + b"
        )

    assert list(tmp_path.iterdir()) == [], "nothing was materialized anywhere"


def test_dispatch_pipeline_no_longer_ships_a_worktree_test_runner():
    """Wiring guard: the helper that produced the false pass must stay gone."""
    from justai.agent_dispatch import AgentDispatchConfig

    assert not hasattr(agent_dispatch, "_run_tests")
    cfg = AgentDispatchConfig()
    assert not hasattr(cfg, "test_command")
    assert not hasattr(cfg, "work_dir")


# ── Finding 6: a blocked index that names no task is silently dropped ────────


@pytest.mark.parametrize(
    ("blocked", "reason"),
    [
        ({-1: "vetoed"}, "negative"),
        ({2: "vetoed"}, "one past the end"),
        ({99: "vetoed"}, "far past the end"),
        ({-1}, "negative, as a bare collection"),
        ({2}, "past the end, as a bare collection"),
    ],
)
def test_a_blocked_index_outside_the_plan_is_rejected(blocked, reason):
    """An index naming no task means the caller and the plan disagree.

    Dropping it is the same false success ``escalate_plan`` takes the whole
    plan to prevent: the task a checkpoint refused gets dispatched anyway.
    """
    tasks = [_task("a"), _task("b")]

    with pytest.raises(ValueError, match="blocked index"):
        escalate_plan(tasks, session_ref="dep", mode="local", blocked_indices=blocked)


@pytest.mark.parametrize(
    ("blocked", "reason"),
    [
        ({True: "vetoed"}, "bool that would silently block task 1"),
        ({"0": "vetoed"}, "string"),
        ({None: "vetoed"}, "null"),
        ({1.0: "vetoed"}, "float"),
    ],
)
def test_a_blocked_index_that_is_not_a_task_position_is_rejected(blocked, reason):
    tasks = [_task("a"), _task("b")]

    with pytest.raises(ValueError, match="blocked index"):
        escalate_plan(tasks, session_ref="dep", mode="local", blocked_indices=blocked)


def test_a_blocked_index_against_an_empty_plan_is_rejected():
    with pytest.raises(ValueError, match="blocked index"):
        escalate_plan([], session_ref="dep", mode="local", blocked_indices={0})


def test_every_in_range_blocked_index_is_still_honoured():
    """Guarding the opposite error: rejecting strays must not drop real ones."""
    tasks = [_task("a"), _task("b"), _task("c")]

    results = escalate_plan(
        tasks, session_ref="dep", mode="local", blocked_indices={0: "vetoed", 2: "vetoed"}
    )

    assert [r.status for r in results] == ["blocked", "error", "blocked"]


# ── Finding 7: unusable results escape the orchestrator instead of failing it ─


def test_an_unknown_result_status_fails_the_run_closed_instead_of_raising(capsys):
    """The ValueError used to leave `run`, skipping the flush and the record.

    Refusing to count an unrecognised status is correct. Losing the run's
    traces and handing the operator a traceback instead of a verdict is not.
    """
    from justai.exit_codes import for_run_status
    from justai.orchestrator import run

    plan = Plan(goal="g", tasks=[_task("Task 0")], session_ref="t")
    unusable = [_result("mission-accomplished", title="Task 0")]

    with _orchestrated_run(plan, escalate_plan=MagicMock(return_value=unusable)) as stubs:
        result = run("goal", session_ref="t", auto=True, local=True)

    assert result.status == "failed"
    assert for_run_status(result.status) != 0, "an uncountable run must not exit 0"

    out = capsys.readouterr().out
    assert "mission-accomplished" in out, "the operator must be told which status was unusable"
    assert "Task 0" in out, "and which task carried it"

    stubs["flush_traces"].assert_called_once()
    stubs["record_run"].assert_called_once()
    stubs["OrchestratorHook"].return_value.on_error.assert_called_once()


def test_a_rejected_blocked_index_also_fails_the_run_closed():
    """The same boundary covers escalate_plan's contract, which raises too."""
    from justai.orchestrator import run

    plan = Plan(goal="g", tasks=[_task("Task 0")], session_ref="t")
    rejected = MagicMock(side_effect=ValueError("blocked index 7 does not name a task"))

    with _orchestrated_run(plan, escalate_plan=rejected) as stubs:
        result = run("goal", session_ref="t", auto=True, local=True)

    assert result.status == "failed"
    assert result.results == [], "nothing was dispatched, so nothing may be reported as a result"
    stubs["flush_traces"].assert_called_once()


@pytest.mark.parametrize(
    "malformed",
    [
        pytest.param(
            SimpleNamespace(title="Task 0", status="done", result="ok"),
            id="missing-task-id",
        ),
        pytest.param(
            SimpleNamespace(task_id="t", status="done", result="ok"),
            id="missing-title",
        ),
        pytest.param(
            SimpleNamespace(task_id="t", title="Task 0", result="ok"),
            id="missing-status",
        ),
        pytest.param(
            SimpleNamespace(task_id="t", title="Task 0", status="done"),
            id="missing-result",
        ),
        pytest.param(
            SimpleNamespace(task_id="t", title=7, status="done", result="ok"),
            id="non-string-title",
        ),
        pytest.param(
            SimpleNamespace(task_id="t", title="Task 0", status=["done"], result="ok"),
            id="non-string-status",
        ),
        pytest.param(
            SimpleNamespace(task_id="t", title="Task 0", status="done", result=7),
            id="non-string-result",
        ),
    ],
)
def test_a_malformed_result_still_preserves_the_failed_run(malformed):
    """A bad executor object must not skip the failure record or trace flush."""
    from justai.exit_codes import for_run_status
    from justai.orchestrator import run

    plan = Plan(goal="g", tasks=[_task("Task 0")], session_ref="t")

    with _orchestrated_run(plan, escalate_plan=MagicMock(return_value=[malformed])) as stubs:
        result = run("goal", session_ref="t", auto=True, local=True)

    assert result.status == "failed"
    assert for_run_status(result.status) != 0
    stubs["OrchestratorHook"].return_value.on_error.assert_called_once()
    stubs["_ledger"].record.assert_called()
    stubs["record_run"].assert_called_once()
    stubs["flush_traces"].assert_called_once()


# ── Finding 8: the execute stage counted statuses with its own vocabulary ────


def test_stage_five_trace_and_hook_counts_come_from_the_shared_tally():
    """Withheld work must appear in the trace, not vanish between two buckets."""
    from justai.orchestrator import run
    from justai.results import tally

    results = [_result("done"), _result("failed"), _result("skipped"), _result("blocked")]
    plan = Plan(goal="g", tasks=[_task(f"Task {i}") for i in range(4)], session_ref="t")
    traces = _TraceRecorder()

    with _orchestrated_run(
        plan,
        trace_generation=traces,
        escalate_plan=MagicMock(return_value=results),
    ) as stubs:
        run("goal", session_ref="t", auto=True, local=True)

    counts = tally(results)
    assert traces.end_kwargs("local")["metadata"] == {
        "done": counts.done,
        "failed": counts.failed,
        "skipped": counts.skipped,
        "blocked": counts.blocked,
        "total": counts.total,
    }
    stubs["OrchestratorHook"].return_value.on_stage.assert_any_call(
        "local", f"{counts.done}/{counts.total} done"
    )


# ── shared orchestrator harness ──────────────────────────────────────────────


class _TraceRecorder:
    """Stands in for ``trace_generation``, keeping one context per stage name."""

    def __init__(self) -> None:
        self.contexts: dict[str, MagicMock] = {}

    def __call__(self, name: str, *args, **kwargs) -> MagicMock:
        ctx = _trace_ctx()
        self.contexts[name] = ctx
        return ctx

    def end_kwargs(self, name: str) -> dict:
        return self.contexts[name].end.call_args.kwargs


@contextmanager
def _orchestrated_run(plan: Plan, **overrides):
    """Stub every stage but the one under test; keep memory writes local."""
    stubs: dict = {
        "classify": MagicMock(return_value=_execution_intent()),
        "decompose": MagicMock(return_value=plan),
        "review": MagicMock(return_value=_approved_review()),
        "evaluate": MagicMock(return_value=(True, "auto")),
        "preflight": MagicMock(return_value=[]),
        "print_preflight": MagicMock(return_value=True),
        "flush_traces": MagicMock(),
        "trace_generation": MagicMock(side_effect=lambda *a, **k: _trace_ctx()),
        "trace_event": MagicMock(),
        "record_run": MagicMock(),
        "enrich_context": MagicMock(return_value=""),
        "_memory": MagicMock(),
        "_ledger": MagicMock(),
        "OrchestratorHook": MagicMock(),
    }
    stubs.update(overrides)
    with (
        patch.multiple("justai.orchestrator", **stubs),
        patch("justai.synthesizer._memory", MagicMock()),
    ):
        yield stubs


def _trace_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.end = MagicMock()
    return ctx


def _execution_intent():
    from justai.intent_gate import Intent, IntentResult

    return IntentResult(
        intent=Intent("execution"), confidence=0.9, reasoning="test", clarifying_question=""
    )


def _approved_review():
    from justai.reviewer import ReviewResult

    return ReviewResult(approved=True, feedback=[])
