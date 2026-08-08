"""Regression coverage for the R1 operator veto's independence from run order.

``run(auto=True)`` used to export ``JUSTAI_AUTO_MODE=1`` into the process
environment and never restore it. Auto mode is a per-run decision, so one
``--auto`` run silently converted every later checkpoint in that interpreter —
an API-triggered run, a second in-process call, a direct ``evaluate`` — into an
auto-approving one. What that disabled is the R1 operator veto: the gate an
operator writes to stop a task before it starts.

Every test here asks the same question from a different position in the order:
does a run that was never asked to skip the R1 wait still honour a veto that is
already on disk?

Each run is given its identity explicitly. A veto names one run — that is what
keeps it from reaching a run it was not about — so a test that plants one
before the run starts has to say which run it is planting it for. See
:mod:`justai.run_identity`.
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from justai.checkpoint import GateIdentity, evaluate, gate_path
from justai.orchestrator import OrchestrationResult, run
from justai.run_identity import new_run_id
from justai.scope_planner import AgentType, Plan, RiskLevel, Task

#: Long enough that the R1 veto poll runs at least once, short enough that a
#: regression which stops reading the gate fails the test instead of hanging.
VETO_POLL_TIMEOUT_SECONDS = 5

#: Bound on waiting for a worker thread. Long enough not to be flaky, short
#: enough to fail rather than hang the suite.
WORKER_TIMEOUT_SECONDS = 30.0


def _r1_task(title: str = "Modify an existing file") -> Task:
    """An R1 task: the only risk level whose gate auto mode is allowed to skip."""
    return Task(
        title=title,
        description="Edit a file that already exists.",
        agent=AgentType.MINI,
        risk=RiskLevel.R1,
        success_criteria="echo ok",
    )


def _one_task_plan() -> Plan:
    return Plan(goal="keep the veto honest", tasks=[_r1_task()], session_ref="veto")


def _veto(run_id: str, index: int = 0, reason: str = "operator said stop") -> None:
    """Write the veto an operator would write to stop one run's R1 task.

    Written through :func:`justai.checkpoint.gate_path` and nothing else, so
    this lands on the same file the checkpoint's own instructions tell the
    operator to write, and carries only the payload they are told to write.
    """
    gate_path(GateIdentity(run_id=run_id, index=index)).write_text(
        json.dumps({"status": "vetoed", "reason": reason, "ts": time.time()})
    )


@pytest.fixture
def vetoed_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checkpoint whose gate directory is local and whose R1 poll is short."""
    gate_dir = tmp_path / "gates"
    monkeypatch.setattr("justai.checkpoint.GATE_SIGNAL_DIR", gate_dir)
    monkeypatch.setattr("justai.checkpoint.R1_TIMEOUT_SECONDS", VETO_POLL_TIMEOUT_SECONDS)
    # How fast a decision is noticed, never what is decided.
    monkeypatch.setattr("justai.checkpoint.R1_POLL_SECONDS", 0.02)
    # Keep the decision local: a configured relay token would post to Discord.
    monkeypatch.setattr("justai.checkpoint._discord_notify", lambda message: False)
    return gate_dir


@contextmanager
def _orchestrator_stubs(plan: Plan):
    """Stub everything around the checkpoint. ``evaluate`` stays real — it is
    the surface under test, and so is the dispatch that follows it."""
    with (
        patch.multiple(
            "justai.orchestrator",
            classify=MagicMock(return_value=_execution_intent()),
            decompose=MagicMock(return_value=plan),
            review=MagicMock(return_value=_approved_review()),
            preflight=MagicMock(return_value=[]),
            print_preflight=MagicMock(return_value=True),
            flush_traces=MagicMock(),
            trace_generation=MagicMock(side_effect=lambda *a, **k: _trace_ctx()),
            trace_event=MagicMock(),
            record_run=MagicMock(),
            enrich_context=MagicMock(return_value=""),
            _memory=MagicMock(),
            _ledger=MagicMock(),
            OrchestratorHook=MagicMock(),
        ),
        patch("justai.synthesizer._memory", MagicMock()),
    ):
        yield


def _run_plan(*, auto: bool, session_ref: str, plan: Plan, run_id: str) -> OrchestrationResult:
    with _orchestrator_stubs(plan):
        return run(
            "keep the veto honest",
            session_ref=session_ref,
            auto=auto,
            local=True,
            run_id=run_id,
        )


def test_an_auto_run_does_not_disable_the_veto_for_a_later_run(vetoed_checkpoint: Path) -> None:
    plan = _one_task_plan()
    auto_run, manual_run = new_run_id(), new_run_id()
    _veto(auto_run)
    _veto(manual_run)

    auto_result = _run_plan(auto=True, session_ref="auto-run", plan=plan, run_id=auto_run)
    manual_result = _run_plan(auto=False, session_ref="manual-run", plan=plan, run_id=manual_run)

    # Documented contract: auto mode skips the R1 wait, so it never consults the
    # veto. That is precisely why it must not decide for anybody else.
    assert auto_result.results[0].status != "blocked"

    assert manual_result.results[0].status == "blocked", (
        "the second run was never asked to skip the R1 wait; the veto must still stop it"
    )
    assert "vetoed" in manual_result.results[0].result.lower()
    assert manual_result.status != "complete"


@pytest.mark.parametrize(
    "order",
    [(True, False), (False, True)],
    ids=["auto-then-manual", "manual-then-auto"],
)
def test_each_run_decides_its_own_gate_in_either_order(
    order: tuple[bool, bool], vetoed_checkpoint: Path
) -> None:
    """Reversing the order must not move the veto from one run to the other."""
    plan = _one_task_plan()

    for position, auto in enumerate(order):
        run_id = new_run_id()
        _veto(run_id)

        result = _run_plan(auto=auto, session_ref=f"order-{position}", plan=plan, run_id=run_id)

        blocked = result.results[0].status == "blocked"
        assert blocked is (not auto), (
            f"run {position} (auto={auto}) took its gate decision from another run"
        )


def test_an_auto_run_does_not_export_its_mode_into_the_process(
    vetoed_checkpoint: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)
    plan = _one_task_plan()
    run_id = new_run_id()
    _veto(run_id)

    _run_plan(auto=True, session_ref="env", plan=plan, run_id=run_id)

    assert "JUSTAI_AUTO_MODE" not in os.environ, (
        "auto is a per-run decision; leaving it in the environment hands it to every later caller"
    )


def test_a_later_direct_checkpoint_call_is_not_auto_approved_by_an_earlier_run(
    vetoed_checkpoint: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)
    plan = _one_task_plan()
    earlier = new_run_id()
    _veto(earlier)

    _run_plan(auto=True, session_ref="direct", plan=plan, run_id=earlier)

    later = GateIdentity(run_id=new_run_id(), index=0, session_ref="after-the-auto-run")
    _veto(later.run_id)
    proceed, reason = evaluate(_r1_task(), later)

    assert proceed is False, "a direct checkpoint call inherited an earlier run's auto decision"
    assert "vetoed" in reason.lower()


@contextmanager
def _paused_before_the_gate(plan: Plan):
    """Hold each run before its checkpoint so a veto can be planted for it.

    ``_start_run`` mints the run id and starts the worker in the same call, so
    a veto written after it returns races the gate it is meant to precede.
    Pausing the stage before the checkpoint removes the race: the veto is on
    disk, named for that exact run, before the run reaches its gate — which is
    the state every other test here sets up directly.

    Yields the event that releases the paused run.
    """
    reached = threading.Event()

    def _decompose(*_args, **_kwargs) -> Plan:
        reached.wait(timeout=WORKER_TIMEOUT_SECONDS)
        return plan

    with patch("justai.orchestrator.decompose", side_effect=_decompose):
        yield reached


def _await_api_run(timeout: float = WORKER_TIMEOUT_SECONDS) -> dict:
    """Block until the API's single active run leaves the running state."""
    from justai import api

    deadline = time.time() + timeout
    while time.time() < deadline:
        with api._run_lock:
            active = dict(api._active_run or {})
        if active and active.get("status") != "running":
            return active
        time.sleep(0.05)
    raise AssertionError("the API run did not finish within the timeout")


def test_two_api_requests_do_not_inherit_the_first_requests_auto_decision(
    vetoed_checkpoint: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two POSTs to /api/run in one server process: auto first, then not.

    The server is long-lived and shares one interpreter across requests, so it
    is where a process-global mode leaks furthest: an operator who ran one
    ``auto`` job from the dashboard lost the veto for every job after it.

    Each veto is written for the run id the request reports back, which is the
    reason that identity is minted in the caller and returned before the run
    reaches a gate: a dashboard operator has to be able to name the run that is
    asking while it is still asking.
    """
    from justai import api

    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)
    monkeypatch.setattr(api, "_active_run", None)

    plan = _one_task_plan()
    outcomes: list[dict] = []

    with _orchestrator_stubs(plan), _paused_before_the_gate(plan) as reach_gate:
        for auto, session_ref in ((True, "request-1"), (False, "request-2")):
            reach_gate.clear()
            started = api._start_run("goal", auto=auto, session=session_ref)
            assert started.get("started") is True
            _veto(started["run_id"])
            reach_gate.set()
            outcomes.append(_await_api_run())

    first, second = outcomes

    # The auto request skipped the R1 wait and reached the fail-closed backend.
    assert first["status"] == "failed"
    assert second["status"] == "blocked", (
        "the second request did not ask to skip the R1 wait; its task must still be vetoed"
    )


# ── shared harness ───────────────────────────────────────────────────────────


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
