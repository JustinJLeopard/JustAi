"""run(auto=True) must scope JUSTAI_AUTO_MODE to the run, not leak it.

Before this fix, run(auto=True) set os.environ["JUSTAI_AUTO_MODE"]="1" and never
restored it, so a later run(auto=False) inherited auto approval and skipped its
R1 checkpoint waits — a sticky, cross-run (and cross-test) leak.
"""

from __future__ import annotations

import os

from unittest.mock import MagicMock, patch


def _trace_ctx():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.end = MagicMock()
    return ctx


def _pipeline_stubs():
    """Stub every stage so run() completes fast and hermetically.

    Deliberately does NOT patch os.environ — these tests assert on it. Fidelity
    is forced to skip so no live model endpoint is contacted.
    """
    from justai.intent_gate import Intent, IntentResult
    from justai.results import DelegationResult
    from justai.reviewer import ReviewResult
    from justai.scope_planner import AgentType, Plan, RiskLevel, Task

    plan = Plan(
        goal="g",
        tasks=[Task("Task 0", "do it", AgentType.MINI, RiskLevel.R0, "echo ok", [])],
        session_ref="t",
    )
    done = DelegationResult(task_id="t", title="Task 0", status="done", result="ok", duration_seconds=1.0)
    return {
        "classify": MagicMock(
            return_value=IntentResult(
                intent=Intent("execution"), confidence=0.9, reasoning="t", clarifying_question=""
            )
        ),
        "decompose": MagicMock(return_value=plan),
        "review": MagicMock(return_value=ReviewResult(approved=True, feedback=[])),
        "evaluate": MagicMock(return_value=(True, "auto")),
        "escalate_plan": MagicMock(return_value=[done]),
        "preflight": MagicMock(return_value=[]),
        "print_preflight": MagicMock(return_value=True),
        "flush_traces": MagicMock(),
        "trace_generation": MagicMock(side_effect=lambda *a, **k: _trace_ctx()),
        "trace_event": MagicMock(),
        "record_run": MagicMock(),
        "enrich_context": MagicMock(return_value=""),
        "score_fidelity": MagicMock(side_effect=RuntimeError("skip fidelity")),
        "_memory": MagicMock(),
        "_ledger": MagicMock(),
        "OrchestratorHook": MagicMock(),
    }


def test_auto_run_does_not_leave_auto_mode_set(monkeypatch):
    from justai.orchestrator import run

    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)
    with patch.multiple("justai.orchestrator", **_pipeline_stubs()), patch(
        "justai.synthesizer._memory", MagicMock()
    ):
        run("g", auto=True, local=True)

    assert "JUSTAI_AUTO_MODE" not in os.environ, (
        "auto=True leaked JUSTAI_AUTO_MODE process-wide; a later auto=False run "
        "would inherit auto approval"
    )


def test_auto_run_restores_a_prior_auto_mode_value(monkeypatch):
    from justai.orchestrator import run

    monkeypatch.setenv("JUSTAI_AUTO_MODE", "0")
    with patch.multiple("justai.orchestrator", **_pipeline_stubs()), patch(
        "justai.synthesizer._memory", MagicMock()
    ):
        run("g", auto=True, local=True)

    assert os.environ["JUSTAI_AUTO_MODE"] == "0", "prior JUSTAI_AUTO_MODE value not restored"


def test_non_auto_run_leaves_env_untouched(monkeypatch):
    from justai.orchestrator import run

    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)
    with patch.multiple("justai.orchestrator", **_pipeline_stubs()), patch(
        "justai.synthesizer._memory", MagicMock()
    ):
        run("g", auto=False, local=True)

    assert "JUSTAI_AUTO_MODE" not in os.environ

# ── PR #31 follow-up: auto authority + concurrency (Codex 2238 P1s) ───────────


def test_explicit_auto_false_overrides_inherited_auto_mode(monkeypatch):
    """auto=False must be authoritative for what the checkpoint actually reads,
    even when JUSTAI_AUTO_MODE is inherited as "1"."""
    from justai import checkpoint
    from justai.orchestrator import run

    monkeypatch.setenv("JUSTAI_AUTO_MODE", "1")
    seen = []

    def recording_evaluate(task, task_id=None):
        seen.append(checkpoint._is_auto_mode())
        return (True, "auto")

    stubs = _pipeline_stubs()
    stubs["evaluate"] = MagicMock(side_effect=recording_evaluate)
    with patch.multiple("justai.orchestrator", **stubs), patch(
        "justai.synthesizer._memory", MagicMock()
    ):
        run("g", auto=False, local=True)

    assert seen, "checkpoint should have been evaluated"
    assert all(s is False for s in seen), "checkpoint saw auto mode despite auto=False"
    assert os.environ["JUSTAI_AUTO_MODE"] == "1", "prior inherited value not restored"


def test_auto_true_is_seen_by_checkpoint_then_restored(monkeypatch):
    from justai import checkpoint
    from justai.orchestrator import run

    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)
    seen = []

    def recording_evaluate(task, task_id=None):
        seen.append(checkpoint._is_auto_mode())
        return (True, "auto")

    stubs = _pipeline_stubs()
    stubs["evaluate"] = MagicMock(side_effect=recording_evaluate)
    with patch.multiple("justai.orchestrator", **stubs), patch(
        "justai.synthesizer._memory", MagicMock()
    ):
        run("g", auto=True, local=True)

    assert seen and all(s is True for s in seen), "checkpoint did not see auto mode during auto run"
    assert "JUSTAI_AUTO_MODE" not in os.environ, "auto mode not restored to absent"


def test_run_holds_the_env_lock_during_execution(monkeypatch):
    """A concurrent run cannot enter the env-dependent section while another
    run holds it — that serialization is what prevents the save/restore race."""
    import threading

    from justai.orchestrator import _RUN_ENV_LOCK, run

    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)
    other_thread_got_lock = []

    def recording_evaluate(task, task_id=None):
        def try_acquire():
            got = _RUN_ENV_LOCK.acquire(blocking=False)
            other_thread_got_lock.append(got)
            if got:
                _RUN_ENV_LOCK.release()

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join()
        return (True, "auto")

    stubs = _pipeline_stubs()
    stubs["evaluate"] = MagicMock(side_effect=recording_evaluate)
    with patch.multiple("justai.orchestrator", **stubs), patch(
        "justai.synthesizer._memory", MagicMock()
    ):
        run("g", auto=True, local=True)

    assert other_thread_got_lock == [False], "run must hold the env lock during execution"


def test_auto_true_outer_with_nested_auto_false_inner(monkeypatch):
    """Codex 2238 case: an inner run(auto=False) inside an outer auto=True run.

    The inner run's checkpoint must read auto OFF (explicit false is
    authoritative even while the outer run's "1" is live), and when the inner
    run finishes the outer run must see its own "1" again, then full restore.
    """
    from justai import checkpoint
    from justai.orchestrator import run

    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)
    observed = {"outer": [], "inner": [], "outer_env_after_inner": []}
    state = {"depth": 0}

    def recording_evaluate(task, task_id=None):
        if state["depth"] == 0:
            state["depth"] = 1
            observed["outer"].append(checkpoint._is_auto_mode())
            run("inner", auto=False, local=True)  # nested, same thread
            observed["outer_env_after_inner"].append(
                os.environ.get("JUSTAI_AUTO_MODE")
            )
        else:
            observed["inner"].append(checkpoint._is_auto_mode())
        return (True, "auto")

    stubs = _pipeline_stubs()
    stubs["evaluate"] = MagicMock(side_effect=recording_evaluate)
    with patch.multiple("justai.orchestrator", **stubs), patch(
        "justai.synthesizer._memory", MagicMock()
    ):
        run("outer", auto=True, local=True)

    assert observed["outer"] == [True], "outer checkpoint must see auto ON"
    assert observed["inner"] == [False], (
        "nested auto=False checkpoint must see auto OFF while the outer "
        "run's '1' is live"
    )
    assert observed["outer_env_after_inner"] == ["1"], (
        "outer's auto state must be restored after the nested run returns"
    )
    assert "JUSTAI_AUTO_MODE" not in os.environ, "full restore to absent"


def test_overlapping_runs_serialize_and_restore_final_state(monkeypatch):
    """Codex 2238 case: two overlapping auto runs — in-flight + final state.

    Pre-fix exact failure: with initial env absent, overlapping runs interleave
    save/restore; one finisher pops the variable while the other is live, and
    the later finisher restores a stale prior "1" — auto ON out of thin air.
    The fix serializes the env-dependent run: while A is mid-run, B's pipeline
    must not have started (in-flight observation, so B can never capture A's
    "1" as its prior), and after both complete the variable is absent again.
    """
    import threading

    from justai.orchestrator import run

    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)

    a_mid_run = threading.Event()
    release_a = threading.Event()
    b_pipeline_ran = threading.Event()

    def recording_evaluate(task, task_id=None):
        name = threading.current_thread().name
        if name == "runA":
            a_mid_run.set()
            release_a.wait(timeout=10)
        elif name == "runB":
            b_pipeline_ran.set()
        return (True, "auto")

    stubs = _pipeline_stubs()
    stubs["evaluate"] = MagicMock(side_effect=recording_evaluate)
    with patch.multiple("justai.orchestrator", **stubs), patch(
        "justai.synthesizer._memory", MagicMock()
    ):
        ta = threading.Thread(
            target=lambda: run("a", auto=True, local=True), name="runA"
        )
        tb = threading.Thread(
            target=lambda: run("b", auto=True, local=True), name="runB"
        )
        ta.start()
        assert a_mid_run.wait(timeout=10), "run A never reached its checkpoint"
        tb.start()
        # In-flight observation: while A is mid-run, B must not have entered
        # its pipeline (serialization is what makes B's prior-capture safe).
        in_flight_b_ran = b_pipeline_ran.wait(timeout=1.0)
        release_a.set()
        ta.join(timeout=10)
        tb.join(timeout=10)
        assert not ta.is_alive() and not tb.is_alive(), "runs did not complete"

    assert in_flight_b_ran is False, (
        "run B entered the env-dependent pipeline while run A was mid-run; "
        "overlapping save/restore can corrupt JUSTAI_AUTO_MODE"
    )
    assert b_pipeline_ran.is_set(), "run B never ran after A released"
    assert "JUSTAI_AUTO_MODE" not in os.environ, (
        "overlapping runs left a stale JUSTAI_AUTO_MODE behind (final state)"
    )
