"""What a gate belongs to, and what it refuses to be released by.

Companion to ``test_gate_identity_collision.py``, which proves the two-process
failure. This file pins the pieces that make the proof hold: the identity
itself, the metadata binding a record to its run, the gates from the old layout
that must now be ignored, cleanup that can only name one run, resume, the
per-run lock, and the fail-closed behaviour none of it is allowed to weaken.
"""

from __future__ import annotations

import fcntl
import json
import os
import threading
import time
import uuid
from pathlib import Path

import pytest

from justai.checkpoint import (
    GateIdentity,
    _read_gate,
    _write_gate,
    cleanup_run,
    evaluate,
    gate_dir,
    gate_path,
    run_gate_lock,
)
from justai.run_identity import InvalidRunId, is_run_id, new_run_id, parse_run_id
from justai.scope_planner import AgentType, RiskLevel, Task
from tests.gate_harness import orchestrator_stubs, single_task_plan

#: Long enough for many gate poll cycles, short enough to fail rather than hang.
BLOCKED_WINDOW = 1.5
RELEASE_TIMEOUT = 30.0


#: Long enough that the R1 veto poll runs, short enough that a regression which
#: stops reading the gate fails the test instead of holding the suite for a
#: minute. Only how long R1 waits — never whether R2 or R3 wait at all.
R1_WAIT_SECONDS = 0.5


@pytest.fixture
def gate_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the gate directory, and make polling quick."""
    root = tmp_path / "gates"
    monkeypatch.setattr("justai.checkpoint.GATE_SIGNAL_DIR", root)
    monkeypatch.setattr("justai.checkpoint.R1_TIMEOUT_SECONDS", R1_WAIT_SECONDS)
    monkeypatch.setattr("justai.checkpoint.R1_POLL_SECONDS", 0.02)
    monkeypatch.setattr("justai.checkpoint.R2_POLL_SECONDS", 0.02)
    monkeypatch.setattr("justai.checkpoint._discord_notify", lambda message: False)
    return root


def a_task(risk: str, title: str = "Change an interface") -> Task:
    return Task(
        title=title,
        description="A gated task.",
        agent=AgentType.MINI,
        risk=RiskLevel(risk),
        success_criteria="echo ok",
    )


# ── the identity ─────────────────────────────────────────────────────────────


def test_every_run_gets_a_different_id() -> None:
    minted = {new_run_id() for _ in range(500)}
    assert len(minted) == 500, "two runs were handed the same identity"


def test_a_run_id_is_a_uuid_and_a_label_is_not() -> None:
    """The values that collided are exactly the ones refused here."""
    assert parse_run_id(new_run_id())
    dashed = str(uuid.uuid4())
    assert parse_run_id(dashed) == uuid.UUID(dashed).hex, "an operator copies what was printed"

    for not_an_identity in [
        "",  # `justai run` with no --session: the shipped default
        "sprint-2",  # the module default, shared by every direct caller
        "dashboard-1785864997",  # a label plus a second — two runs collide inside one
        "shared-label",
        "-plan-0",
        None,
        17,
    ]:
        with pytest.raises(InvalidRunId):
            parse_run_id(not_an_identity)
        assert is_run_id(not_an_identity) is False


@pytest.mark.parametrize(
    "hostile",
    ["../other-run", "..", "../../etc/passwd", "a/b", "/absolute", ".", "run id"],
)
def test_a_run_id_cannot_escape_the_gate_directory(hostile: str) -> None:
    """A run id becomes a path component, so it is a UUID or it is nothing."""
    with pytest.raises(InvalidRunId):
        parse_run_id(hostile)
    with pytest.raises(InvalidRunId):
        gate_dir(hostile)
    with pytest.raises(InvalidRunId):
        GateIdentity(run_id=hostile, index=0)


def test_a_gate_cannot_be_built_without_a_real_run(gate_root: Path) -> None:
    with pytest.raises(InvalidRunId):
        GateIdentity(run_id="sprint-2", index=0)
    for bad_index in [-1, "0", 1.5, True]:
        with pytest.raises((ValueError, TypeError)):
            GateIdentity(run_id=new_run_id(), index=bad_index)


def test_two_runs_sharing_a_label_and_an_index_do_not_share_a_path(gate_root: Path) -> None:
    first = GateIdentity(run_id=new_run_id(), index=0, session_ref="shared-label")
    second = GateIdentity(run_id=new_run_id(), index=0, session_ref="shared-label")

    assert gate_path(first) != gate_path(second)
    assert gate_path(first).parent != gate_path(second).parent
    assert gate_path(first).name == gate_path(second).name == "plan-0.json"


# ── metadata binding: stale and forged records ───────────────────────────────


def test_a_record_naming_another_run_is_not_a_decision(gate_root: Path) -> None:
    """A gate copied out of another run's directory must not release this one."""
    mine = GateIdentity(run_id=new_run_id(), index=0, session_ref="mine")
    theirs = GateIdentity(run_id=new_run_id(), index=0, session_ref="theirs")

    _write_gate(theirs, "approved", reason="approved for the other run")
    gate_path(mine).write_text(gate_path(theirs).read_text())

    assert _read_gate(mine) is None, "a record carrying another run's id was read as a decision"
    assert _read_gate(theirs) is not None, "the run it was actually written for still reads it"


def test_a_record_naming_another_task_is_not_a_decision(gate_root: Path) -> None:
    """Approving plan task 0 must not release plan task 1."""
    run_id = new_run_id()
    first = GateIdentity(run_id=run_id, index=0)
    second = GateIdentity(run_id=run_id, index=1)

    _write_gate(first, "approved")
    gate_path(second).write_text(gate_path(first).read_text())

    assert _read_gate(second) is None
    assert _read_gate(first) is not None


def test_a_stale_pending_record_does_not_release_a_resumed_run(gate_root: Path) -> None:
    """Left-behind state is only ever "no decision", never "go"."""
    gate = GateIdentity(run_id=new_run_id(), index=0)
    _write_gate(gate, "pending")

    record = _read_gate(gate)
    assert record is not None and record["status"] == "pending"

    proceed, reason = evaluate(a_task("R1"), gate, auto=False)
    assert proceed is True and "auto-approved" in reason, (
        "a pending record is not a veto either — R1 still times out into proceeding"
    )


def test_the_hand_written_approval_the_instructions_ask_for_still_works(gate_root: Path) -> None:
    """The operator is told to write ``{"status": "approved"}``, so that must count.

    The path already scopes the record to one run. Demanding metadata an
    operator was never told to write would break the documented workflow
    without making anything safer.
    """
    gate = GateIdentity(run_id=new_run_id(), index=0, session_ref="hand-written")
    gate_path(gate).write_text(json.dumps({"status": "approved"}))

    record = _read_gate(gate)
    assert record is not None and record["status"] == "approved"


@pytest.mark.parametrize(
    "garbage",
    ['{"status": "approved"', "not json at all", "[]", '"approved"', "null", ""],
    ids=["truncated", "prose", "list", "bare-string", "null", "empty"],
)
def test_an_unreadable_gate_is_never_an_approval(gate_root: Path, garbage: str) -> None:
    gate = GateIdentity(run_id=new_run_id(), index=0)
    gate_path(gate).write_text(garbage)

    assert _read_gate(gate) is None


def test_a_gate_record_records_who_it_belongs_to(gate_root: Path) -> None:
    run_id = new_run_id()
    gate = GateIdentity(run_id=run_id, index=3, session_ref="nightly")
    _write_gate(gate, "pending", task_title="Change an interface")

    record = json.loads(gate_path(gate).read_text())
    assert record["run_id"] == run_id
    assert record["session_ref"] == "nightly"
    assert record["index"] == 3
    assert record["task"] == "Change an interface"


def test_a_relabelled_resume_still_reads_its_own_gates(gate_root: Path) -> None:
    """``session_ref`` is a label, so changing it must not orphan a run's gates."""
    run_id = new_run_id()
    _write_gate(GateIdentity(run_id=run_id, index=0, session_ref="old-label"), "approved")

    relabelled = GateIdentity(run_id=run_id, index=0, session_ref="new-label")
    record = _read_gate(relabelled)

    assert record is not None and record["status"] == "approved"


# ── the old layout ───────────────────────────────────────────────────────────


def test_a_legacy_unscoped_gate_releases_nothing(gate_root: Path) -> None:
    """``gates/gate_<session>-plan-<i>.json`` names no run, so it decides nothing."""
    gate_root.mkdir(parents=True, exist_ok=True)
    for legacy_name in [
        "gate_-plan-0.json",
        "gate_sprint-2-plan-0.json",
        "gate_shared-plan-0.json",
    ]:
        (gate_root / legacy_name).write_text(json.dumps({"status": "approved"}))

    gate = GateIdentity(run_id=new_run_id(), index=0, session_ref="sprint-2")
    assert _read_gate(gate) is None


def test_a_legacy_veto_does_not_stop_a_run_either(gate_root: Path) -> None:
    """Ignoring the old layout is symmetric — it is not consulted at all."""
    gate_root.mkdir(parents=True, exist_ok=True)
    (gate_root / "gate_sprint-2-plan-0.json").write_text(json.dumps({"status": "vetoed"}))

    gate = GateIdentity(run_id=new_run_id(), index=0, session_ref="sprint-2")
    proceed, _ = evaluate(a_task("R1"), gate, auto=False)

    assert proceed is True


# ── cleanup ──────────────────────────────────────────────────────────────────


def test_cleanup_removes_one_run_and_leaves_the_other_alone(gate_root: Path) -> None:
    """The case that made parallel tests unlink each other's gates."""
    mine = GateIdentity(run_id=new_run_id(), index=0, session_ref="shared-label")
    theirs = GateIdentity(run_id=new_run_id(), index=0, session_ref="shared-label")
    _write_gate(mine, "pending")
    _write_gate(theirs, "approved")

    removed = cleanup_run(mine.run_id)

    assert removed == 1
    assert not gate_dir(mine.run_id).exists()
    assert gate_path(theirs).exists(), "cleaning one run deleted another run's approval"
    assert _read_gate(theirs) is not None


def test_cleanup_removes_every_gate_of_its_own_run(gate_root: Path) -> None:
    run_id = new_run_id()
    for index in range(4):
        _write_gate(GateIdentity(run_id=run_id, index=index), "pending")

    assert cleanup_run(run_id) == 4
    assert not gate_dir(run_id).exists()


def test_cleanup_cannot_be_asked_to_remove_anything_else(gate_root: Path) -> None:
    """There is no way to spell a target other than one run."""
    survivor = GateIdentity(run_id=new_run_id(), index=0)
    _write_gate(survivor, "approved")

    for hostile in ["..", "../..", "", "sprint-2", "/", "a/b"]:
        with pytest.raises((InvalidRunId, ValueError)):
            cleanup_run(hostile)

    assert gate_path(survivor).exists()
    assert gate_root.exists()


def test_cleanup_of_an_unknown_run_is_a_no_op(gate_root: Path) -> None:
    assert cleanup_run(new_run_id()) == 0


def test_cleanup_leaves_files_it_does_not_recognise(gate_root: Path) -> None:
    """Deleting something unrecognised is not cleanup."""
    run_id = new_run_id()
    _write_gate(GateIdentity(run_id=run_id, index=0), "pending")
    stray = gate_dir(run_id) / "operator-notes.txt"
    stray.write_text("why this was approved")

    assert cleanup_run(run_id) == 1
    assert stray.exists(), "cleanup deleted a file it was never asked about"
    assert gate_dir(run_id).exists()


# ── the per-run advisory lock ────────────────────────────────────────────────


def _held_elsewhere(run_id: str) -> bool:
    """Whether some other open file description holds this run's lock.

    ``flock`` is per open file description, so a second ``os.open`` of the same
    path contends with the first even inside one process — which is what makes
    this checkable without a second interpreter.
    """
    lock_file = gate_dir(run_id) / ".lock"
    if not lock_file.exists():
        return False
    fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def test_a_runs_lock_excludes_a_second_holder(gate_root: Path) -> None:
    run_id = new_run_id()
    with run_gate_lock(run_id):
        assert _held_elsewhere(run_id) is True
    assert _held_elsewhere(run_id) is False


def test_two_runs_never_wait_on_each_other(gate_root: Path) -> None:
    """Ordinary concurrent runs must not serialise — they share nothing."""
    mine, theirs = new_run_id(), new_run_id()
    with run_gate_lock(mine):
        assert _held_elsewhere(theirs) is False
        with run_gate_lock(theirs):
            assert _held_elsewhere(theirs) is True


def test_the_operator_is_never_blocked_by_the_lock(gate_root: Path) -> None:
    """The lock is advisory and internal; ``echo > gate`` must always work."""
    gate = GateIdentity(run_id=new_run_id(), index=0)
    with run_gate_lock(gate.run_id):
        gate_path(gate).write_text(json.dumps({"status": "approved"}))
        record = _read_gate(gate)

    assert record is not None and record["status"] == "approved"


# ── fail-closed behaviour, unchanged ─────────────────────────────────────────


def test_r3_is_still_blocked(gate_root: Path) -> None:
    proceed, reason = evaluate(a_task("R3"), GateIdentity(run_id=new_run_id(), index=0), auto=True)
    assert proceed is False
    assert "blocked" in reason.lower()


def test_r2_still_waits_even_in_auto_mode(gate_root: Path) -> None:
    """Auto mode skips the R1 wait and nothing else."""
    gate = GateIdentity(run_id=new_run_id(), index=0, session_ref="auto")
    outcome: list[tuple[bool, str]] = []

    worker = threading.Thread(
        target=lambda: outcome.append(evaluate(a_task("R2"), gate, auto=True)), daemon=True
    )
    worker.start()
    worker.join(timeout=BLOCKED_WINDOW)

    assert worker.is_alive(), "an R2 task proceeded without an approval"
    assert outcome == []

    gate_path(gate).write_text(json.dumps({"status": "approved"}))
    worker.join(timeout=RELEASE_TIMEOUT)

    assert outcome == [(True, "R2 approved by operator")]


def test_r2_is_refused_by_a_rejection(gate_root: Path) -> None:
    gate = GateIdentity(run_id=new_run_id(), index=0)
    outcome: list[tuple[bool, str]] = []

    worker = threading.Thread(
        target=lambda: outcome.append(evaluate(a_task("R2"), gate, auto=False)), daemon=True
    )
    worker.start()
    deadline = time.time() + RELEASE_TIMEOUT
    while not gate_path(gate).exists() and time.time() < deadline:
        time.sleep(0.02)

    gate_path(gate).write_text(json.dumps({"status": "rejected", "reason": "not this one"}))
    worker.join(timeout=RELEASE_TIMEOUT)

    assert outcome and outcome[0][0] is False
    assert "not this one" in outcome[0][1]


def test_an_r1_veto_stops_the_run_it_names(gate_root: Path) -> None:
    gate = GateIdentity(run_id=new_run_id(), index=0, session_ref="vetoed")
    _write_gate(gate, "vetoed", reason="operator said stop")

    proceed, reason = evaluate(a_task("R1"), gate, auto=False)

    assert proceed is False
    assert "operator said stop" in reason


def test_an_r1_veto_written_for_another_run_stops_nothing(gate_root: Path) -> None:
    """The R1 counterpart of the collision: a veto is about one run too."""
    theirs = GateIdentity(run_id=new_run_id(), index=0, session_ref="shared-label")
    _write_gate(theirs, "vetoed", reason="stop the other one")

    mine = GateIdentity(run_id=new_run_id(), index=0, session_ref="shared-label")
    proceed, _ = evaluate(a_task("R1"), mine, auto=False)

    assert proceed is True


# ── ordinary defaults, and deliberate resume ─────────────────────────────────


def _run(goal: str = "gate identity", risk: str = "R1", **kwargs):
    from justai.orchestrator import run

    with orchestrator_stubs(single_task_plan(risk, goal=goal)):
        return run(goal, local=True, **kwargs)


def test_ordinary_runs_mint_their_own_identity(gate_root: Path) -> None:
    """No ``--session``, no ``--run-id``: still two different runs."""
    first = _run()
    second = _run()

    assert is_run_id(first.run_id) and is_run_id(second.run_id)
    assert first.run_id != second.run_id
    assert first.run_id not in (first.goal, "")


def test_the_default_session_label_does_not_reach_the_identity(gate_root: Path) -> None:
    shared = _run(session_ref="sprint-2")
    also_shared = _run(session_ref="sprint-2")

    assert shared.run_id != also_shared.run_id, (
        "two runs under the shared default label were given one identity"
    )


def test_a_run_cleans_up_only_its_own_gates(gate_root: Path) -> None:
    """A finished run leaves a concurrent run's pending approval untouched."""
    concurrent = GateIdentity(run_id=new_run_id(), index=0, session_ref="sprint-2")
    _write_gate(concurrent, "pending")

    finished = _run(session_ref="sprint-2")

    assert not gate_dir(finished.run_id).exists(), "a finished run left its gates behind"
    assert gate_path(concurrent).exists(), "a finished run deleted another run's gate"


def test_a_resume_reuses_the_gates_of_the_run_it_names(gate_root: Path) -> None:
    """The one case where passing a run id is right."""
    run_id = new_run_id()
    _write_gate(
        GateIdentity(run_id=run_id, index=0, session_ref="resume"),
        "vetoed",
        reason="decided before the crash",
    )

    resumed = _run(session_ref="resume", run_id=run_id)

    assert resumed.run_id == run_id
    assert resumed.results[0].status == "blocked"
    assert "decided before the crash" in resumed.results[0].result


def test_a_fresh_run_does_not_inherit_a_resumable_runs_decisions(gate_root: Path) -> None:
    """Same label, no ``run_id``: the earlier decision is not this run's."""
    run_id = new_run_id()
    _write_gate(
        GateIdentity(run_id=run_id, index=0, session_ref="resume"),
        "vetoed",
        reason="decided before the crash",
    )

    fresh = _run(session_ref="resume")

    assert fresh.run_id != run_id
    assert fresh.results[0].status != "blocked"


def test_a_resume_must_name_a_real_run(gate_root: Path) -> None:
    """A label passed as a run id is refused before anything is gated."""
    for not_an_identity in ["sprint-2", "../other-run", ""]:
        with pytest.raises(InvalidRunId):
            _run(session_ref="resume", run_id=not_an_identity)


# ── the shipped entry points ─────────────────────────────────────────────────


def test_the_cli_gives_two_ordinary_runs_two_identities(
    gate_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``justai run "goal"`` twice, exactly as an operator types it."""
    from justai.cli import main as cli_main

    with orchestrator_stubs(single_task_plan("R1")):
        cli_main(["run", "gate identity"])
        cli_main(["run", "gate identity"])

    announced = [
        line.split("Run:")[1].split("(")[0].strip()
        for line in capsys.readouterr().out.splitlines()
        if line.strip().startswith("Run:")
    ]

    assert len(announced) == 2, "the run identity was not reported to the operator"
    assert all(is_run_id(value) for value in announced)
    assert announced[0] != announced[1]


def test_the_cli_refuses_a_run_id_that_is_not_one(
    gate_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from justai.cli import main as cli_main

    with orchestrator_stubs(single_task_plan("R1")):
        code = cli_main(["run", "gate identity", "--run-id", "sprint-2"])

    assert code != 0
    assert "run id" in capsys.readouterr().out.lower()


def test_the_api_reports_the_identity_its_gates_use(gate_root: Path) -> None:
    """The dashboard operator needs the run id while the run is still blocked."""
    from justai import api

    api._active_run = None
    started: list[dict] = []
    try:
        with orchestrator_stubs(single_task_plan("R1")):
            started.append(api._start_run("gate identity", auto=False, session=""))
            _await_api_run()
            started.append(api._start_run("gate identity", auto=False, session="shared-label"))
            _await_api_run()
    finally:
        api._active_run = None

    assert all(is_run_id(entry["run_id"]) for entry in started)
    assert started[0]["run_id"] != started[1]["run_id"]
    # The label is still reported, and is still just a label.
    assert started[1]["session_ref"] == "shared-label"


def _await_api_run(timeout: float = RELEASE_TIMEOUT) -> dict:
    from justai import api

    deadline = time.time() + timeout
    while time.time() < deadline:
        with api._run_lock:
            active = dict(api._active_run or {})
        if active and active.get("status") != "running":
            return active
        time.sleep(0.02)
    raise AssertionError("the API run did not finish within the timeout")
