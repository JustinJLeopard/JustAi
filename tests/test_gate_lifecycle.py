"""What survives a gate's lifecycle: a decision, a lock, and a bounded directory.

Companion to ``test_gate_run_identity.py`` (what a gate belongs to) and
``test_gate_identity_collision.py`` (the two-process proof that it belongs to
one run). Scoping every gate to a run id fixed *which* file a decision lands
in. This file covers the three ways the lifecycle around that file did not
hold:

- **A decision that arrived early was overwritten.** The R2 branch announced
  its gate and then wrote ``pending`` to it unconditionally. An approval
  already on disk — a ``--run-id`` resume, or a dashboard operator using the
  run id the API returns before the run reaches a gate — was destroyed by that
  write, and the run then waited forever for a decision it had already been
  given.
- **Cleanup unlinked the lock while holding it.** A process queued on that
  file woke holding an inode no one else could reach by name, so the next
  process created a second lock file and held the same run at the same time.
- **Nothing removed a spent run directory.** A run that died before cleanup,
  and (once the lock stopped being unlinked) every run that finished, left a
  directory behind and nothing ever collected them.

The multi-process cases run real interpreters. Neither failure is visible
inside one: ``flock`` is held per open file description, and a write lost
across a resume needs a second process to lose it to.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path

import pytest

from justai.checkpoint import (
    LOCK_FILENAME,
    GateIdentity,
    _read_gate,
    _write_gate,
    cleanup_run,
    gate_dir,
    gate_path,
    run_gate_lock,
)
from justai.run_identity import InvalidRunId, new_run_id
from tests import gate_lifecycle_child as child_modes
from tests.gate_harness import ChildProcess

#: Imported inside the tests that need them rather than at module scope. These
#: are the names the fix adds, and a red run of this file against the
#: implementation it replaces has to fail on behaviour, not on an import.

#: Long enough for many gate poll cycles at the children's 0.05s, short enough
#: to fail rather than hang.
QUIET_WINDOW = 1.5
CHILD_TIMEOUT = 60.0

#: Wide enough that a parent writing an approval lands well inside it.
NOTIFY_WINDOW_SECONDS = "3.0"

APPROVED_LINE = "R2 approved by operator"
DONE_MARKER = "CHILD-DONE exit="


@pytest.fixture
def gate_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the gate directory for the in-process cases."""
    root = tmp_path / "gates"
    monkeypatch.setattr("justai.checkpoint.GATE_SIGNAL_DIR", root)
    monkeypatch.setattr("justai.checkpoint.R2_POLL_SECONDS", 0.02)
    monkeypatch.setattr("justai.checkpoint._discord_notify", lambda message: False)
    return root


@pytest.fixture
def runtime_root(tmp_path: Path) -> Path:
    """The runtime root the children are pointed at, holding ``gates/``."""
    root = tmp_path / "runtime"
    root.mkdir()
    return root


def child_gate_dir(runtime_root: Path, run_id: str) -> Path:
    """Where a child's gates live, derived the way the child derives it."""
    return runtime_root / "gates" / run_id


def hold_lock(name: str, runtime_root: Path, run_id: str, release: Path) -> ChildProcess:
    return ChildProcess(
        name, runtime_root, ["-m", "tests.gate_lifecycle_child", "hold", run_id, str(release)]
    )


def a_run(name: str, runtime_root: Path, extra: list[str], notify_delay: str = "") -> ChildProcess:
    """One ``justai run`` blocked at an R2 gate, in its own interpreter."""
    env = {"JUSTAI_TEST_NOTIFY_DELAY": notify_delay} if notify_delay else None
    return ChildProcess(
        name, runtime_root, ["-m", "tests.gate_collision_child", *extra], env_extra=env
    )


def approve(gate: Path) -> None:
    """Write the approval an operator writes, the way the instructions say."""
    gate.parent.mkdir(parents=True, exist_ok=True)
    gate.write_text(json.dumps({"status": "approved"}))


def stays_quiet(child: ChildProcess, marker: str, window: float = QUIET_WINDOW) -> bool:
    """Whether ``marker`` stays unprinted for the whole window."""
    deadline = time.time() + window
    while time.time() < deadline:
        if child.saw(marker):
            return False
        time.sleep(0.02)
    return True


def inode(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino)


# ── P1: a decision on disk is never overwritten ──────────────────────────────


def test_an_approval_written_before_the_run_starts_still_releases_it(
    runtime_root: Path,
) -> None:
    """The ``--run-id`` resume the README documents, in two real processes.

    An operator who was already asked about this run — before a crash, or
    through the dashboard, which is handed the run id before the run reaches a
    gate — writes the approval and restarts the run. Against the unconditional
    ``pending`` write, the restarted run destroyed that approval on its way to
    waiting for it, and then waited forever.
    """
    run_id = new_run_id()
    approve(child_gate_dir(runtime_root, run_id) / "plan-0.json")

    resumed = a_run("resume", runtime_root, ["--run-id", run_id])
    try:
        resumed.await_line(APPROVED_LINE, timeout=CHILD_TIMEOUT)
        resumed.await_line(DONE_MARKER, timeout=CHILD_TIMEOUT)
    finally:
        resumed.close()


def test_an_approval_written_while_the_gate_is_being_announced_is_not_lost(
    runtime_root: Path,
) -> None:
    """The window between announcing a gate and recording it belongs to nobody.

    The shipped R2 branch announces the gate over Discord — an HTTP POST with a
    ten-second timeout — and only then records its ``pending`` marker. An
    operator reading that notification and approving immediately wrote into a
    window the run then overwrote. The child holds the window open and says so,
    so this is the operator being fast rather than the test being lucky.
    """
    run_id = new_run_id()
    running = a_run(
        "notified", runtime_root, ["--run-id", run_id], notify_delay=NOTIFY_WINDOW_SECONDS
    )
    try:
        running.await_line("NOTIFY-WINDOW-OPEN", timeout=CHILD_TIMEOUT)
        approve(child_gate_dir(runtime_root, run_id) / "plan-0.json")

        running.await_line(APPROVED_LINE, timeout=CHILD_TIMEOUT)
        running.await_line(DONE_MARKER, timeout=CHILD_TIMEOUT)
    finally:
        running.close()


def test_recording_a_pending_gate_never_overwrites_a_decision(gate_root: Path) -> None:
    """The mechanism under the two process tests above."""
    from justai.checkpoint import _claim_gate

    gate = GateIdentity(run_id=new_run_id(), index=0, session_ref="early")
    gate_path(gate).write_text(json.dumps({"status": "approved"}))

    assert _claim_gate(gate, "pending", task_title="Change an interface") is False
    record = _read_gate(gate)
    assert record is not None and record["status"] == "approved"


def test_a_run_with_no_decision_yet_still_records_that_it_is_waiting(gate_root: Path) -> None:
    """Refusing to overwrite must not stop the pending marker being written."""
    from justai.checkpoint import _claim_gate

    gate = GateIdentity(run_id=new_run_id(), index=0)

    assert _claim_gate(gate, "pending", task_title="Change an interface") is True
    record = _read_gate(gate)
    assert record is not None and record["status"] == "pending"
    assert record["run_id"] == gate.run_id
    assert record["task"] == "Change an interface"


@pytest.mark.parametrize(
    "planted, why",
    [
        (lambda other: json.dumps({"run_id": other, "index": 0, "status": "approved"}), "foreign"),
        (lambda other: json.dumps({"index": 7, "status": "approved"}), "another-task"),
        (lambda other: "not json at all", "unreadable"),
    ],
    ids=["foreign-run", "another-task", "unreadable"],
)
def test_a_record_that_decides_nothing_leaves_the_gate_closed(
    gate_root: Path, planted, why: str
) -> None:
    """Preserving what is on disk must not turn a refused record into a release.

    A gate whose file cannot speak for this run is not a decision, and keeping
    it rather than overwriting it does not make it one: the R2 task keeps
    waiting, which is the fail-closed direction.
    """
    from justai.checkpoint import _claim_gate

    gate = GateIdentity(run_id=new_run_id(), index=0)
    gate_path(gate).write_text(planted(new_run_id()))

    assert _claim_gate(gate, "pending") is False
    assert _read_gate(gate) is None, f"a {why} record was read as a decision"


def test_an_operator_can_still_decide_a_gate_holding_a_refused_record(gate_root: Path) -> None:
    """Fail-closed must not mean stuck: ``echo > gate`` always resolves it."""
    gate = GateIdentity(run_id=new_run_id(), index=0)
    gate_path(gate).write_text(json.dumps({"run_id": new_run_id(), "status": "approved"}))
    assert _read_gate(gate) is None

    approve(gate_path(gate))

    record = _read_gate(gate)
    assert record is not None and record["status"] == "approved"


# ── P2: the lock file outlives every process that excludes on it ─────────────


def test_cleanup_leaves_the_lock_it_locked_in_place(gate_root: Path) -> None:
    """Two processes exclude on this file, so removing it excludes nobody.

    Cleanup used to unlink it while holding it. Every later reader of that
    inode was alone with it: the name was free, so the next process made a new
    file and held the same run at the same time.
    """
    run_id = new_run_id()
    _write_gate(GateIdentity(run_id=run_id, index=0), "pending")
    with run_gate_lock(run_id):
        pass
    lock = gate_dir(run_id) / LOCK_FILENAME
    before = inode(lock)

    assert cleanup_run(run_id) == 1

    assert lock.exists(), "cleanup removed the file two processes exclude on"
    assert inode(lock) == before, "cleanup replaced the lock with a different inode"
    assert not list(gate_dir(run_id).glob("plan-*.json")), "cleanup left a gate record behind"


def test_a_lock_taken_after_a_directory_moved_is_the_live_one(
    runtime_root: Path, tmp_path: Path
) -> None:
    """A process queued on a lock that is moved aside must not wake up alone.

    This is the interleaving that made unlinking the lock unsafe, and it is the
    one the sweep would reintroduce if a waiter kept whatever it was handed:
    the queued process wakes holding an inode nothing can reach by name, so the
    next process creates a fresh lock file and both are inside the critical
    section at once.

    The parent holds the lock the way :func:`run_gate_lock` holds it — an
    ``flock`` on the run's own ``.lock`` — so what the children contend with is
    the real thing.
    """
    run_id = new_run_id()
    directory = child_gate_dir(runtime_root, run_id)
    directory.mkdir(parents=True)
    lock = directory / LOCK_FILENAME
    release = runtime_root / "release"

    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    queued = hold_lock("queued", runtime_root, run_id, release)
    later = None
    try:
        queued.await_line(child_modes.QUEUEING)
        assert stays_quiet(queued, child_modes.HELD), (
            "a second process took a lock this one is holding"
        )

        # What the sweep does to a spent directory, and what an external
        # /tmp reaper does to this one whether or not anybody asked.
        os.rename(directory, runtime_root / "gates" / ".trash-moved")
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        fd = -1

        queued.await_line(child_modes.HELD)

        later = hold_lock("later", runtime_root, run_id, release)
        later.await_line(child_modes.QUEUEING)
        assert stays_quiet(later, child_modes.HELD), (
            "two processes held one run's lock at the same time: the queued "
            "process woke holding an inode that is no longer at the path, so "
            f"the next process made its own lock:\n{queued.output()}\n{later.output()}"
        )

        release.touch()
        queued.await_line(child_modes.RELEASED)
        later.await_line(child_modes.HELD)
    finally:
        if fd >= 0:
            os.close(fd)
        queued.close()
        if later is not None:
            later.close()


def test_cleanup_waits_for_a_live_holder_of_the_same_run(runtime_root: Path) -> None:
    """Cleanup takes the run's lock, so it cannot delete records mid-checkpoint."""
    run_id = new_run_id()
    directory = child_gate_dir(runtime_root, run_id)
    directory.mkdir(parents=True)
    (directory / "plan-0.json").write_text(json.dumps({"run_id": run_id, "status": "pending"}))
    release = runtime_root / "release"

    holder = hold_lock("holder", runtime_root, run_id, release)
    cleaner = None
    try:
        holder.await_line(child_modes.HELD)
        cleaner = ChildProcess(
            "cleaner", runtime_root, ["-m", "tests.gate_lifecycle_child", "clean", run_id]
        )
        cleaner.await_line(child_modes.CLEANING)
        assert stays_quiet(cleaner, child_modes.CLEANED), (
            "cleanup deleted a gate record while another process was deciding it"
        )
        assert (directory / "plan-0.json").exists()

        release.touch()
        holder.await_line(child_modes.RELEASED)
        cleaner.await_line(f"{child_modes.CLEANED}1")
        assert cleaner.await_exit() == 0
        assert not (directory / "plan-0.json").exists()
        assert (directory / LOCK_FILENAME).exists(), "cleanup removed the run's lock"
    finally:
        holder.close()
        if cleaner is not None:
            cleaner.close()


def test_exclusion_still_works_after_a_run_has_been_cleaned(runtime_root: Path) -> None:
    """A cleaned run is still one run, so two processes on it still serialise."""
    run_id = new_run_id()
    directory = child_gate_dir(runtime_root, run_id)
    directory.mkdir(parents=True)
    release = runtime_root / "release"

    cleaner = ChildProcess(
        "cleaner", runtime_root, ["-m", "tests.gate_lifecycle_child", "clean", run_id]
    )
    first = None
    second = None
    try:
        assert cleaner.await_exit() == 0
        first = hold_lock("first", runtime_root, run_id, release)
        first.await_line(child_modes.HELD)
        second = hold_lock("second", runtime_root, run_id, release)
        second.await_line(child_modes.QUEUEING)

        assert stays_quiet(second, child_modes.HELD), (
            f"a cleaned run stopped excluding a second process:\n{second.output()}"
        )

        release.touch()
        second.await_line(child_modes.HELD)
    finally:
        cleaner.close()
        for handle in (first, second):
            if handle is not None:
                handle.close()


# ── P3: the directory lifecycle, and what is kept on purpose ─────────────────


def test_a_cleaned_run_keeps_only_its_lock(gate_root: Path) -> None:
    """What cleanup honestly leaves: a lock, and no decisions.

    The directory is not removed, because the lock inside it is what two
    processes on this run exclude on and removing it is what broke that. The
    directory becomes a tombstone, and :func:`sweep_gate_dirs` is what bounds
    the number of them.
    """
    run_id = new_run_id()
    for index in range(3):
        _write_gate(GateIdentity(run_id=run_id, index=index), "pending")

    assert cleanup_run(run_id) == 3

    directory = gate_dir(run_id)
    assert directory.is_dir()
    assert sorted(entry.name for entry in directory.iterdir()) == [LOCK_FILENAME]


def test_the_sweep_removes_a_spent_tombstone(gate_root: Path) -> None:
    from justai.checkpoint import sweep_gate_dirs

    run_id = new_run_id()
    with run_gate_lock(run_id):
        pass
    assert gate_dir(run_id).is_dir()

    assert sweep_gate_dirs(older_than_seconds=0) == 1
    assert not gate_dir(run_id).exists()
    assert gate_root.is_dir(), "the sweep removed the gate root itself"


def test_the_sweep_keeps_a_run_that_is_still_waiting_to_be_decided(gate_root: Path) -> None:
    """A gate record is resume material, so age alone never removes it.

    A run interrupted at an R2 gate is exactly what ``--run-id`` resumes
    against. Sweeping it would delete a pending approval nobody answered — so
    the sweep collects directories that hold no decision at all, and nothing
    else. Interrupted runs are kept, deliberately and indefinitely.
    """
    from justai.checkpoint import sweep_gate_dirs

    undecided = new_run_id()
    _write_gate(GateIdentity(run_id=undecided, index=0), "pending")
    spent = new_run_id()
    with run_gate_lock(spent):
        pass

    assert sweep_gate_dirs(older_than_seconds=0) == 1

    assert gate_path(GateIdentity(run_id=undecided, index=0)).exists()
    assert not gate_dir(spent).exists()


def test_the_sweep_keeps_a_recent_tombstone(gate_root: Path) -> None:
    """The lifecycle is bounded by age, not by "the last run finished"."""
    from justai.checkpoint import sweep_gate_dirs

    run_id = new_run_id()
    with run_gate_lock(run_id):
        pass

    assert sweep_gate_dirs(older_than_seconds=3600) == 0
    assert gate_dir(run_id).is_dir()


def test_the_sweep_keeps_a_directory_holding_something_unrecognised(gate_root: Path) -> None:
    """Deleting something nobody asked about is not cleanup."""
    from justai.checkpoint import sweep_gate_dirs

    run_id = new_run_id()
    with run_gate_lock(run_id):
        pass
    (gate_dir(run_id) / "operator-notes.txt").write_text("why this was approved")

    assert sweep_gate_dirs(older_than_seconds=0) == 0
    assert (gate_dir(run_id) / "operator-notes.txt").exists()


def test_the_sweep_only_looks_at_run_directories(gate_root: Path) -> None:
    """A name that is not a run id was not written by this module."""
    from justai.checkpoint import sweep_gate_dirs

    gate_root.mkdir(parents=True, exist_ok=True)
    (gate_root / "gate_sprint-2-plan-0.json").write_text(json.dumps({"status": "approved"}))
    unrelated = gate_root / "sprint-2"
    unrelated.mkdir()
    (unrelated / "notes.txt").write_text("not a run")

    assert sweep_gate_dirs(older_than_seconds=0) == 0
    assert (gate_root / "gate_sprint-2-plan-0.json").exists()
    assert unrelated.is_dir()


def test_the_sweep_refuses_a_negative_age(gate_root: Path) -> None:
    from justai.checkpoint import sweep_gate_dirs

    with pytest.raises(ValueError):
        sweep_gate_dirs(older_than_seconds=-1)


def test_the_sweep_default_leaves_a_wide_margin(gate_root: Path) -> None:
    """The default delay is a margin around a microsecond-wide race."""
    from justai.checkpoint import GATE_TOMBSTONE_TTL_SECONDS, sweep_gate_dirs

    assert GATE_TOMBSTONE_TTL_SECONDS >= 3600, (
        "removal must stay far away from a directory anything could still be entering"
    )
    run_id = new_run_id()
    with run_gate_lock(run_id):
        pass

    assert sweep_gate_dirs() == 0
    assert gate_dir(run_id).is_dir()


def test_a_live_run_is_never_swept_out_from_under_itself(runtime_root: Path) -> None:
    """A run parked at its gate is holding its lock, so the sweep passes it by."""
    run_id = new_run_id()
    running = a_run("parked", runtime_root, ["--run-id", run_id])
    sweeper = None
    try:
        gate = child_gate_dir(runtime_root, run_id) / "plan-0.json"
        deadline = time.time() + CHILD_TIMEOUT
        while not gate.exists() and time.time() < deadline:
            time.sleep(0.02)
        assert gate.exists(), f"the run never parked at its gate:\n{running.output()}"

        sweeper = ChildProcess(
            "sweeper", runtime_root, ["-m", "tests.gate_lifecycle_child", "sweep", "0"]
        )
        sweeper.await_line(f"{child_modes.SWEPT}0")
        assert sweeper.await_exit() == 0
        assert gate.exists(), "the sweep deleted a gate a run was waiting on"

        approve(gate)
        running.await_line(APPROVED_LINE)
        running.await_line(DONE_MARKER)
    finally:
        running.close()
        if sweeper is not None:
            sweeper.close()


def test_an_ordinary_run_bounds_the_directories_it_leaves(runtime_root: Path) -> None:
    """A finished run leaves one tombstone, and the next run does not add a second.

    The orchestrator sweeps after cleaning up, so the number of directories
    under ``gates/`` is bounded by how many runs are live or recent rather than
    by how many have ever been started.
    """
    from justai.checkpoint import GATE_TOMBSTONE_TTL_SECONDS

    gates = runtime_root / "gates"
    stale = gates / new_run_id()
    stale.mkdir(parents=True)
    (stale / LOCK_FILENAME).touch()
    old = time.time() - (GATE_TOMBSTONE_TTL_SECONDS + 60)
    os.utime(stale, (old, old))

    finished = a_run("finished", runtime_root, [])
    try:
        gate_file = None
        deadline = time.time() + CHILD_TIMEOUT
        while gate_file is None and time.time() < deadline:
            found = sorted(gates.glob("*/plan-0.json"))
            gate_file = found[0] if found else None
            time.sleep(0.02)
        assert gate_file is not None, f"the run never parked at its gate:\n{finished.output()}"

        approve(gate_file)
        finished.await_line(DONE_MARKER)
    finally:
        finished.close()

    assert not stale.exists(), "a spent directory older than the retention window was kept"
    assert not list(gates.glob("*/plan-*.json")), "a finished run left a gate record behind"


# ── containment, unchanged ───────────────────────────────────────────────────


def test_cleanup_still_cannot_be_asked_to_remove_anything_else(gate_root: Path) -> None:
    survivor = GateIdentity(run_id=new_run_id(), index=0)
    _write_gate(survivor, "approved")

    for hostile in ["..", "../..", "", "sprint-2", "/", "a/b"]:
        with pytest.raises((InvalidRunId, ValueError)):
            cleanup_run(hostile)

    assert gate_path(survivor).exists()
