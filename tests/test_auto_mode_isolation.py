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
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from justai.checkpoint import evaluate
from justai.orchestrator import OrchestrationResult, run
from justai.scope_planner import AgentType, Plan, RiskLevel, Task

#: Long enough that the R1 veto poll runs at least once, short enough that a
#: regression which stops reading the gate fails the test instead of hanging.
VETO_POLL_TIMEOUT_SECONDS = 5


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


def _write_veto(gate_dir: Path, task_id: str, reason: str = "operator said stop") -> None:
    """Write the veto an operator would write to stop an R1 task."""
    gate_dir.mkdir(parents=True, exist_ok=True)
    (gate_dir / f"gate_{task_id}.json").write_text(
        json.dumps({"task_id": task_id, "status": "vetoed", "reason": reason, "ts": time.time()})
    )


@pytest.fixture
def vetoed_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checkpoint whose gate directory is local and whose R1 poll is short."""
    gate_dir = tmp_path / "gates"
    monkeypatch.setattr("justai.checkpoint.GATE_SIGNAL_DIR", gate_dir)
    monkeypatch.setattr("justai.checkpoint.R1_TIMEOUT_SECONDS", VETO_POLL_TIMEOUT_SECONDS)
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


def _run_plan(*, auto: bool, session_ref: str, plan: Plan) -> OrchestrationResult:
    with _orchestrator_stubs(plan):
        return run("keep the veto honest", session_ref=session_ref, auto=auto, local=True)


def test_an_auto_run_does_not_disable_the_veto_for_a_later_run(vetoed_checkpoint: Path) -> None:
    plan = _one_task_plan()
    for session_ref in ("auto-run", "manual-run"):
        _write_veto(vetoed_checkpoint, f"{session_ref}-plan-0")

    auto_result = _run_plan(auto=True, session_ref="auto-run", plan=plan)
    manual_result = _run_plan(auto=False, session_ref="manual-run", plan=plan)

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
        session_ref = f"order-{position}"
        _write_veto(vetoed_checkpoint, f"{session_ref}-plan-0")

        result = _run_plan(auto=auto, session_ref=session_ref, plan=plan)

        blocked = result.results[0].status == "blocked"
        assert blocked is (not auto), (
            f"run {position} (auto={auto}) took its gate decision from another run"
        )


def test_an_auto_run_does_not_export_its_mode_into_the_process(
    vetoed_checkpoint: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)
    plan = _one_task_plan()
    _write_veto(vetoed_checkpoint, "env-plan-0")

    _run_plan(auto=True, session_ref="env", plan=plan)

    assert "JUSTAI_AUTO_MODE" not in os.environ, (
        "auto is a per-run decision; leaving it in the environment hands it to every later caller"
    )


def test_a_later_direct_checkpoint_call_is_not_auto_approved_by_an_earlier_run(
    vetoed_checkpoint: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)
    plan = _one_task_plan()
    _write_veto(vetoed_checkpoint, "direct-plan-0")

    _run_plan(auto=True, session_ref="direct", plan=plan)

    _write_veto(vetoed_checkpoint, "after-the-auto-run")
    proceed, reason = evaluate(_r1_task(), task_id="after-the-auto-run")

    assert proceed is False, "a direct checkpoint call inherited an earlier run's auto decision"
    assert "vetoed" in reason.lower()


def _await_api_run(timeout: float = 30.0) -> dict:
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
    """
    from justai import api

    monkeypatch.delenv("JUSTAI_AUTO_MODE", raising=False)
    monkeypatch.setattr(api, "_active_run", None)

    plan = _one_task_plan()
    for session_ref in ("request-1", "request-2"):
        _write_veto(vetoed_checkpoint, f"{session_ref}-plan-0")

    with _orchestrator_stubs(plan):
        assert api._start_run("goal", auto=True, session="request-1").get("started") is True
        first = _await_api_run()
        assert api._start_run("goal", auto=False, session="request-2").get("started") is True
        second = _await_api_run()

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
