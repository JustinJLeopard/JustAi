"""What the gate directory deletes, and what it refuses to delete.

Companion to ``test_gate_lifecycle.py``, which established that a finished run
leaves a directory behind and that something has to collect it. Two things
about *how* it collected them did not hold:

- **Deletion went by name prefix.** Anything under ``gates/`` called
  ``.trash-*`` was removed, and the name a sweep parked a directory under was
  derived from the run id alone. An operator directory called
  ``.trash-operator-owned`` was deleted for its name, and a directory sitting
  at the name the sweep wanted was deleted to make room. Neither was ever
  written by this module.
- **A run interrupted at a gate was kept forever.** That is right for a gate an
  operator may still answer and wrong as an end state: a child killed while
  parked at R2 leaves a record no one will ever decide, and nothing removed it
  at any age. ``gates/`` grew by one directory per killed run, permanently.

The fix keeps the resumability and bounds the accumulation: a run's directory
says what it is — active, resumable, abandoned, terminal, or holding something
this module did not write — and only the last two of those are ever collected,
by two operations that each name what they collect.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

from justai.checkpoint import (
    LOCK_FILENAME,
    GateIdentity,
    _write_gate,
    gate_dir,
    gate_path,
    run_gate_lock,
    sweep_gate_dirs,
)
from justai.run_identity import new_run_id
from tests.gate_harness import ChildProcess

CHILD_TIMEOUT = 60.0
DONE_MARKER = "CHILD-DONE exit="

#: Any tombstone this module parks a directory under starts with this. The
#: prefix alone is not a licence to delete — that was the defect.
TRASH_PREFIX = ".trash-"


@pytest.fixture
def gate_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "gates"
    monkeypatch.setattr("justai.checkpoint.GATE_SIGNAL_DIR", root)
    monkeypatch.setattr("justai.checkpoint.R2_POLL_SECONDS", 0.02)
    monkeypatch.setattr("justai.checkpoint._discord_notify", lambda message: False)
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def runtime_root(tmp_path: Path) -> Path:
    root = tmp_path / "runtime"
    root.mkdir()
    return root


def backdate(path: Path, seconds: float) -> None:
    """Age a directory and everything in it, as time would."""
    when = time.time() - seconds
    if path.is_dir():
        for entry in sorted(path.iterdir()):
            os.utime(entry, (when, when))
    os.utime(path, (when, when))


def a_gated_run(gate_root: Path, *, age_seconds: float = 0.0) -> str:
    """A run that parked at a gate and was never answered."""
    run_id = new_run_id()
    with run_gate_lock(run_id):
        _write_gate(GateIdentity(run_id=run_id, index=0), "pending")
    if age_seconds:
        backdate(gate_dir(run_id), age_seconds)
    return run_id


def a_spent_run(gate_root: Path) -> str:
    """A run whose decisions have been cleaned up, leaving only its lock."""
    run_id = new_run_id()
    with run_gate_lock(run_id):
        pass
    return run_id


def tombstones(gate_root: Path) -> list[Path]:
    return sorted(p for p in gate_root.iterdir() if p.name.startswith(TRASH_PREFIX))


@contextmanager
def a_sweep_that_dies_before_deleting(monkeypatch: pytest.MonkeyPatch):
    """Stop the sweep between parking a directory and deleting it.

    The real delete is put back by name on the way out rather than through
    ``monkeypatch.undo``, which would also undo the fixture that redirects the
    gate root — and the next sweep in the test would then run against the real
    one.
    """
    import justai.checkpoint as checkpoint

    real = checkpoint._delete_tombstone
    monkeypatch.setattr(checkpoint, "_delete_tombstone", lambda path: False)
    try:
        yield
    finally:
        monkeypatch.setattr(checkpoint, "_delete_tombstone", real)


def child_gate_dir(runtime_root: Path, run_id: str) -> Path:
    return runtime_root / "gates" / run_id


# ── P2: nothing is deleted for its name ──────────────────────────────────────


def test_the_sweep_leaves_a_trash_name_this_module_did_not_write(gate_root: Path) -> None:
    """``.trash-`` is where this module parks its own work, not a licence.

    The sweep deleted every entry whose name started with the prefix, without
    ever having written one of them. An operator keeping notes under
    ``gates/.trash-operator-owned`` lost them to a sweep triggered by an
    unrelated run.
    """
    foreign = gate_root / ".trash-operator-owned"
    foreign.mkdir()
    (foreign / "keep.txt").write_text("why the last three approvals were refused")

    assert sweep_gate_dirs(older_than_seconds=0) == 0

    assert (foreign / "keep.txt").read_text() == "why the last three approvals were refused"


def test_the_sweep_does_not_clear_the_name_it_wants(gate_root: Path) -> None:
    """A directory is parked under a name nobody else can be holding.

    The name was ``.trash-<run_id>`` — one name per run — and the sweep deleted
    whatever was already there before renaming onto it. Anything an operator
    had put at that name went with it, and a second sweep of the same run id
    destroyed the first sweep's own unfinished work.
    """
    run_id = a_spent_run(gate_root)
    occupied = gate_root / f"{TRASH_PREFIX}{run_id}"
    occupied.mkdir()
    (occupied / "keep.txt").write_text("an operator was here first")

    assert sweep_gate_dirs(older_than_seconds=0) == 1

    assert not gate_dir(run_id).exists(), "the spent run directory was not collected"
    assert (occupied / "keep.txt").read_text() == "an operator was here first"


def test_a_tombstone_without_this_module_s_marker_is_left_alone(gate_root: Path) -> None:
    """A validated name is necessary and not sufficient.

    Nothing about a name proves who wrote it. A tombstone is deleted on the
    strength of the marker this module puts inside it before parking anything.
    """
    unmarked = gate_root / f"{TRASH_PREFIX}{new_run_id()}-{new_run_id()}"
    unmarked.mkdir()
    (unmarked / LOCK_FILENAME).touch()

    assert sweep_gate_dirs(older_than_seconds=0) == 0
    assert unmarked.is_dir()


def test_a_symlink_wearing_a_tombstone_name_is_not_followed(gate_root: Path) -> None:
    """Deleting through a link deletes something that was never here."""
    elsewhere = gate_root.parent / "operator-data"
    elsewhere.mkdir()
    (elsewhere / "keep.txt").write_text("not under gates/ at all")
    (gate_root / f"{TRASH_PREFIX}{new_run_id()}-{new_run_id()}").symlink_to(elsewhere)

    assert sweep_gate_dirs(older_than_seconds=0) == 0
    assert (elsewhere / "keep.txt").exists()


def test_a_tombstone_this_module_wrote_is_finished_on_a_later_sweep(
    gate_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sweep that dies between parking a directory and deleting it.

    The rename is what takes a directory out of the namespace; the delete is
    what frees the space. A crash in between leaves a tombstone this module
    wrote, and the next sweep is what finishes it — which is the one case where
    deleting a ``.trash-`` entry is deleting our own work.
    """
    run_id = a_spent_run(gate_root)

    with a_sweep_that_dies_before_deleting(monkeypatch):
        assert sweep_gate_dirs(older_than_seconds=0) == 1
        assert not gate_dir(run_id).exists()
        parked = tombstones(gate_root)
        assert len(parked) == 1, "a swept directory was not parked under a tombstone"
        assert run_id in parked[0].name, "the tombstone does not name the run it came from"

    sweep_gate_dirs(older_than_seconds=0)
    assert tombstones(gate_root) == []


def test_two_tombstones_for_one_run_id_do_not_collide(
    gate_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One run id can be parked twice — a resume, or an interrupted sweep.

    Naming a tombstone after the run alone meant the second one landed on the
    first, and the sweep cleared the way by deleting it. Both survive their way
    to being deleted on purpose.
    """
    with a_sweep_that_dies_before_deleting(monkeypatch):
        run_id = a_spent_run(gate_root)
        assert sweep_gate_dirs(older_than_seconds=0) == 1
        with run_gate_lock(run_id):
            pass
        assert sweep_gate_dirs(older_than_seconds=0) == 1

        parked = tombstones(gate_root)
        assert len(parked) == 2, f"one tombstone overwrote the other: {[p.name for p in parked]}"
        assert all(run_id in p.name for p in parked)

    sweep_gate_dirs(older_than_seconds=0)
    assert tombstones(gate_root) == []


def test_a_tombstone_holding_anything_else_is_left_alone(
    gate_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even our own tombstone stops being ours once something else is in it."""
    with a_sweep_that_dies_before_deleting(monkeypatch):
        a_spent_run(gate_root)
        assert sweep_gate_dirs(older_than_seconds=0) == 1
        parked = tombstones(gate_root)[0]
        (parked / "operator-notes.txt").write_text("do not delete")

    sweep_gate_dirs(older_than_seconds=0)

    assert (parked / "operator-notes.txt").exists()
    assert parked.is_dir()


# ── P3: a gate nobody will ever answer ───────────────────────────────────────


def test_the_sweep_still_keeps_every_run_that_holds_a_decision(gate_root: Path) -> None:
    """Unchanged, and deliberately: the sweep collects terminal runs only.

    Age is not evidence that a gate was abandoned — an operator can take a
    weekend over an R2 approval. Collecting a directory that still holds a
    decision is a separate operation with a separate window.
    """
    resumable = a_gated_run(gate_root, age_seconds=90 * 24 * 3600)

    assert sweep_gate_dirs(older_than_seconds=0) == 0
    assert gate_path(GateIdentity(run_id=resumable, index=0)).exists()


def test_a_gate_still_worth_resuming_is_kept(gate_root: Path) -> None:
    """The recovery window is what makes ``--run-id`` a resume, not a re-ask."""
    from justai.checkpoint import prune_abandoned_runs

    recent = a_gated_run(gate_root, age_seconds=3600)

    assert prune_abandoned_runs() == 0
    assert gate_path(GateIdentity(run_id=recent, index=0)).exists()


def test_a_gate_nobody_answered_stops_being_kept_once_it_is_abandoned(gate_root: Path) -> None:
    """The bound. A pending decision is not kept for the life of the machine."""
    from justai.checkpoint import GATE_ABANDON_TTL_SECONDS, prune_abandoned_runs

    abandoned = a_gated_run(gate_root, age_seconds=GATE_ABANDON_TTL_SECONDS + 60)

    assert prune_abandoned_runs() == 1
    assert not gate_dir(abandoned).exists()
    assert gate_root.is_dir(), "pruning removed the gate root itself"


def test_a_child_killed_at_its_gate_is_recoverable_and_then_collected(
    runtime_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reported case, from the process that dies to the directory going away.

    A run parked at R2 is killed. Its record is a decision nobody gave and
    nobody will now ask for, but it is also exactly what a resume needs, so it
    survives the sweep and the recovery window — and then it is collected,
    rather than being kept for as long as the machine lives.
    """
    from justai.checkpoint import (
        GATE_ABANDON_TTL_SECONDS,
        RunState,
        prune_abandoned_runs,
        run_state,
    )

    monkeypatch.setattr("justai.checkpoint.GATE_SIGNAL_DIR", runtime_root / "gates")
    run_id = new_run_id()
    killed = ChildProcess(
        "killed", runtime_root, ["-m", "tests.gate_collision_child", "--run-id", run_id]
    )
    try:
        gate = child_gate_dir(runtime_root, run_id) / "plan-0.json"
        deadline = time.time() + CHILD_TIMEOUT
        while not gate.exists() and time.time() < deadline:
            time.sleep(0.02)
        assert gate.exists(), f"the run never parked at its gate:\n{killed.output()}"

        killed.proc.kill()
        killed.proc.wait(timeout=CHILD_TIMEOUT)
    finally:
        killed.close()

    assert run_state(run_id) is RunState.RESUMABLE
    assert sweep_gate_dirs(older_than_seconds=0) == 0
    assert prune_abandoned_runs() == 0
    assert gate.exists(), "a killed run's record was collected inside the recovery window"

    backdate(gate.parent, GATE_ABANDON_TTL_SECONDS + 60)
    assert run_state(run_id) is RunState.ABANDONED

    assert prune_abandoned_runs() == 1
    assert not gate.parent.exists()


def test_an_operator_answering_a_gate_restarts_its_recovery_window(gate_root: Path) -> None:
    """A decision written into a record is the newest thing about that run.

    An approval is written into an existing file, which leaves the directory's
    own timestamp untouched. Dating a run by the directory alone would let a
    gate an operator answered a minute ago be collected as abandoned.
    """
    from justai.checkpoint import GATE_ABANDON_TTL_SECONDS, prune_abandoned_runs

    run_id = a_gated_run(gate_root, age_seconds=GATE_ABANDON_TTL_SECONDS + 60)
    gate = gate_path(GateIdentity(run_id=run_id, index=0))
    gate.write_text(json.dumps({"status": "approved"}))

    assert prune_abandoned_runs() == 0
    assert gate.exists()


def test_pruning_leaves_a_run_that_is_still_going_alone(gate_root: Path) -> None:
    """A parked R2 gate holds its run's lock for as long as the operator takes."""
    from justai.checkpoint import prune_abandoned_runs

    run_id = a_gated_run(gate_root, age_seconds=90 * 24 * 3600)

    from justai.checkpoint import own_run

    with own_run(run_id):
        assert prune_abandoned_runs(older_than_seconds=0) == 0

    assert gate_path(GateIdentity(run_id=run_id, index=0)).exists()


def test_pruning_leaves_a_directory_holding_something_unrecognised(gate_root: Path) -> None:
    """Deleting something nobody asked about is not cleanup, here either."""
    from justai.checkpoint import prune_abandoned_runs

    run_id = a_gated_run(gate_root)
    (gate_dir(run_id) / "operator-notes.txt").write_text("why this was left open")
    backdate(gate_dir(run_id), 90 * 24 * 3600)

    assert prune_abandoned_runs(older_than_seconds=0) == 0
    assert (gate_dir(run_id) / "operator-notes.txt").exists()


def test_retained_runs_are_bounded_by_count_as_well_as_age(gate_root: Path) -> None:
    """A window alone is not a bound: enough runs inside it is still unbounded.

    The oldest go first, so what is kept is the work most likely to still be
    worth resuming.
    """
    from justai.checkpoint import prune_abandoned_runs

    runs = []
    for minutes in range(6, 0, -1):
        runs.append(a_gated_run(gate_root, age_seconds=minutes * 60))

    assert prune_abandoned_runs(keep_at_most=3) == 3

    for gone in runs[:3]:
        assert not gate_dir(gone).exists(), "the oldest retained runs were not the ones dropped"
    for kept in runs[3:]:
        assert gate_path(GateIdentity(run_id=kept, index=0)).exists()


def test_the_count_bound_still_leaves_a_live_run_alone(gate_root: Path) -> None:
    """Being over the cap is not a reason to collect a run that is executing."""
    from justai.checkpoint import own_run, prune_abandoned_runs

    live = a_gated_run(gate_root, age_seconds=7200)
    for _ in range(3):
        a_gated_run(gate_root, age_seconds=60)

    with own_run(live):
        assert prune_abandoned_runs(keep_at_most=1) == 2

    assert gate_path(GateIdentity(run_id=live, index=0)).exists()


def test_a_gate_planted_for_a_run_that_never_started_is_collected_too(gate_root: Path) -> None:
    """An approval written ahead of a run that never came still ages out.

    Writing one creates the directory, so it exists with a record in it and no
    lock — nothing has ever excluded on it. A collector that could only work
    through an existing lock would keep these forever, and a collector that
    creates one has to not then read its own file as fresh activity.
    """
    from justai.checkpoint import GATE_ABANDON_TTL_SECONDS, prune_abandoned_runs

    run_id = new_run_id()
    gate = gate_path(GateIdentity(run_id=run_id, index=0))
    gate.write_text(json.dumps({"status": "approved"}))
    assert not (gate_dir(run_id) / LOCK_FILENAME).exists()
    backdate(gate_dir(run_id), GATE_ABANDON_TTL_SECONDS + 60)

    assert prune_abandoned_runs() == 1
    assert not gate_dir(run_id).exists()


def test_pruning_refuses_a_window_or_a_bound_that_is_not_one(gate_root: Path) -> None:
    from justai.checkpoint import prune_abandoned_runs

    with pytest.raises(ValueError):
        prune_abandoned_runs(older_than_seconds=-1)
    with pytest.raises(ValueError):
        prune_abandoned_runs(keep_at_most=-1)


def test_the_recovery_window_is_generous(gate_root: Path) -> None:
    """The window exists for a human, so it is measured in days, not minutes."""
    from justai.checkpoint import GATE_ABANDON_TTL_SECONDS, GATE_MAX_RETAINED_RUNS

    assert GATE_ABANDON_TTL_SECONDS >= 24 * 3600, (
        "an operator must have at least a day to answer a gate before it is collected"
    )
    assert GATE_MAX_RETAINED_RUNS >= 16, "the count bound must not be tight enough to lose work"


# ── the evidence a directory carries about its own run ───────────────────────


def test_a_run_directory_says_what_it_is(gate_root: Path) -> None:
    """One reading of the directory, named, so both operations agree on it."""
    from justai.checkpoint import GATE_ABANDON_TTL_SECONDS, RunState, own_run, run_state

    assert run_state(new_run_id()) is RunState.MISSING

    active = a_gated_run(gate_root)
    with own_run(active):
        assert run_state(active) is RunState.ACTIVE
    assert run_state(active) is RunState.RESUMABLE

    abandoned = a_gated_run(gate_root, age_seconds=GATE_ABANDON_TTL_SECONDS + 60)
    assert run_state(abandoned) is RunState.ABANDONED

    assert run_state(a_spent_run(gate_root)) is RunState.TERMINAL

    foreign = a_spent_run(gate_root)
    (gate_dir(foreign) / "operator-notes.txt").write_text("mine")
    assert run_state(foreign) is RunState.FOREIGN


def test_run_state_reads_a_run_without_changing_it(gate_root: Path) -> None:
    """Asking what a directory is must not be what creates or alters it."""
    from justai.checkpoint import run_state

    absent = new_run_id()
    run_state(absent)
    assert not gate_dir(absent).exists(), "reading a run's state created its directory"

    run_id = a_gated_run(gate_root)
    before = sorted(entry.name for entry in gate_dir(run_id).iterdir())
    run_state(run_id)
    assert sorted(entry.name for entry in gate_dir(run_id).iterdir()) == before


def test_pruning_still_cannot_reach_outside_the_gate_directory(gate_root: Path) -> None:
    """The prune takes no argument that could name a path, and adds none.

    Including through a link: a run-id-shaped name pointing somewhere else is
    not a run directory, whatever it points at.
    """
    from justai.checkpoint import prune_abandoned_runs

    outsider = gate_root.parent / "not-gates"
    outsider.mkdir()
    (outsider / new_run_id()).mkdir()
    (gate_root / "sprint-2").mkdir()
    linked = gate_root / new_run_id()
    linked.symlink_to(outsider)

    assert prune_abandoned_runs(older_than_seconds=0) == 0
    assert sweep_gate_dirs(older_than_seconds=0) == 0

    assert (gate_root / "sprint-2").is_dir()
    assert linked.is_symlink()
    assert len(list(outsider.iterdir())) == 1


# ── what an ordinary run does about all of this ──────────────────────────────


def test_an_ordinary_run_collects_an_abandoned_one(runtime_root: Path) -> None:
    """The bound has to be reached by shipped behaviour, not only by a helper.

    A run that finishes collects what is finished: spent directories past the
    tombstone window, and gates past the recovery window. Nothing else.
    """
    from justai.checkpoint import GATE_ABANDON_TTL_SECONDS

    gates = runtime_root / "gates"
    abandoned = gates / new_run_id()
    abandoned.mkdir(parents=True)
    (abandoned / LOCK_FILENAME).touch()
    (abandoned / "plan-0.json").write_text(json.dumps({"status": "pending"}))
    backdate(abandoned, GATE_ABANDON_TTL_SECONDS + 60)

    recent = gates / new_run_id()
    recent.mkdir(parents=True)
    (recent / LOCK_FILENAME).touch()
    (recent / "plan-0.json").write_text(json.dumps({"status": "pending"}))

    finished = ChildProcess("finished", runtime_root, ["-m", "tests.gate_collision_child"])
    try:
        gate_file = None
        deadline = time.time() + CHILD_TIMEOUT
        while gate_file is None and time.time() < deadline:
            found = [p for p in gates.glob("*/plan-0.json") if p.parent not in (abandoned, recent)]
            gate_file = found[0] if found else None
            time.sleep(0.02)
        assert gate_file is not None, f"the run never parked at its gate:\n{finished.output()}"

        gate_file.write_text(json.dumps({"status": "approved"}))
        finished.await_line(DONE_MARKER, timeout=CHILD_TIMEOUT)
    finally:
        finished.close()

    assert not abandoned.exists(), "a gate past the recovery window was kept"
    assert (recent / "plan-0.json").exists(), "a gate still worth resuming was collected"
