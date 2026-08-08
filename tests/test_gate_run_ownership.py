"""One run, one driver: who owns a run while it is being executed.

Companion to ``test_gate_run_identity.py`` (which run a gate belongs to),
``test_gate_identity_collision.py`` (the two-process proof that it belongs to
one run), and ``test_gate_lifecycle.py`` (what survives a gate).

Scoping every gate to a run id stopped one approval releasing two *different*
runs. It said nothing about two processes driving the *same* run, and the
checkpoint stage left that open: the run's lock was taken for the gate loop and
released at the end of it, so reading the approval was serialised and
everything after it was not. Two resumes of one run id — the ``--run-id`` path
the README documents — each read the operator's single approval, each cleaned
up, and each dispatched. One decision, one run id, two executions.

What the tests below hold to:

- a second process asking for a run someone is already driving is refused, and
  refused immediately, rather than queued behind it and run afterwards;
- ownership covers reading the approval, the dispatch that acts on it, and the
  terminal cleanup — not just the gate loop;
- the lock file two processes exclude on is never unlinked, so the inode a
  waiter holds stays the inode the next process finds.

The multi-process cases run real interpreters. Two simultaneous holders of one
lock are invisible inside a single one: ``flock`` is held per open file
description, and the second execution needs a second process to perform it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from justai.checkpoint import LOCK_FILENAME, GateIdentity, _write_gate, gate_dir, gate_path
from justai.run_identity import new_run_id
from tests import gate_lifecycle_child as child_modes
from tests.gate_harness import ChildProcess, orchestrator_stubs, single_task_plan

CHILD_TIMEOUT = 60.0

#: What a run prints when it reaches the stage that acts on the approval. Two
#: processes printing this for one run id is the defect itself.
DISPATCH_LINE = "[5/5] Executing"

#: What a process must say when it is refused a run someone else is driving.
REFUSAL = "run already active"

APPROVED_LINE = "R2 approved by operator"
DONE_MARKER = "CHILD-DONE exit="
NOTIFY_WINDOW = "NOTIFY-WINDOW-OPEN"

#: Long enough that a second process starting under it is unambiguously inside
#: the first one's gate stage, short enough to keep the suite bounded.
NOTIFY_WINDOW_SECONDS = "6.0"


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
    return runtime_root / "gates" / run_id


def approve(gate: Path) -> None:
    """Write the approval an operator writes, the way the instructions say."""
    gate.parent.mkdir(parents=True, exist_ok=True)
    gate.write_text(json.dumps({"status": "approved"}))


def a_run(name: str, runtime_root: Path, extra: list[str], notify_delay: str = "") -> ChildProcess:
    """One ``justai run``, in its own interpreter."""
    env = {"JUSTAI_TEST_NOTIFY_DELAY": notify_delay} if notify_delay else None
    return ChildProcess(
        name, runtime_root, ["-m", "tests.gate_collision_child", *extra], env_extra=env
    )


def inode(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino)


def await_gate(runtime_root: Path, run_id: str, child: ChildProcess) -> Path:
    """Block until the run has parked at its first gate."""
    gate = child_gate_dir(runtime_root, run_id) / "plan-0.json"
    deadline = time.time() + CHILD_TIMEOUT
    while not gate.exists() and time.time() < deadline:
        time.sleep(0.02)
    assert gate.exists(), f"the run never parked at its gate:\n{child.output()}"
    return gate


# ── one approval, one execution ──────────────────────────────────────────────


def test_two_simultaneous_resumes_of_one_run_execute_it_once(runtime_root: Path) -> None:
    """The defect, in the two processes it takes to see it.

    One operator approval is planted for one run id, and two ``justai run
    --run-id`` processes are pointed at it — a resume racing the run it is
    resuming, or simply a second one started by hand. The first holds the run
    while it announces its gate; the second arrives inside that window.

    Against a lock released at the end of the gate stage, the second process
    queued for it, woke as soon as the first stage ended, read the same
    approval — cleanup had not yet re-taken the lock to remove it — and went on
    to dispatch. Both ran. An approval is a decision to execute a task once.
    """
    run_id = new_run_id()
    approve(child_gate_dir(runtime_root, run_id) / "plan-0.json")

    first = a_run("first", runtime_root, ["--run-id", run_id], notify_delay=NOTIFY_WINDOW_SECONDS)
    second = None
    try:
        first.await_line(NOTIFY_WINDOW, timeout=CHILD_TIMEOUT)
        second = a_run("second", runtime_root, ["--run-id", run_id])

        first.await_exit(timeout=CHILD_TIMEOUT)
        second.await_exit(timeout=CHILD_TIMEOUT)

        dispatched = [c for c in (first, second) if DISPATCH_LINE in c.output()]
        refused = [c for c in (first, second) if REFUSAL in c.output()]

        assert len(dispatched) == 1, (
            "one approval released two executions of one run:\n"
            f"--- first ---\n{first.output()}\n--- second ---\n{second.output()}"
        )
        assert len(refused) == 1, (
            "the process that did not get the run never said the run was already active:\n"
            f"--- first ---\n{first.output()}\n--- second ---\n{second.output()}"
        )
        assert refused[0] is not dispatched[0]
        assert refused[0].proc.returncode != 0, "a refused run must not exit 0"
    finally:
        first.close()
        if second is not None:
            second.close()


def test_a_second_resume_is_refused_while_the_first_is_parked_at_its_gate(
    runtime_root: Path,
) -> None:
    """A run parked at R2 is a run in progress, however long the operator takes.

    The second process must be told so and stop, not queue behind an approval
    that has not been given yet and then execute the run a second time when it
    is. Refusal is the fail-closed direction: nothing was run twice, and the
    operator still has exactly one run to answer.
    """
    run_id = new_run_id()
    parked = a_run("parked", runtime_root, ["--run-id", run_id])
    second = None
    try:
        gate = await_gate(runtime_root, run_id, parked)
        record = json.loads(gate.read_text())

        second = a_run("second", runtime_root, ["--run-id", run_id])
        assert second.await_exit(timeout=CHILD_TIMEOUT) != 0, (
            "a second resume of a parked run exited 0 instead of being refused"
        )
        assert REFUSAL in second.output(), (
            f"a second resume was not refused as an active run:\n{second.output()}"
        )
        assert DISPATCH_LINE not in second.output()

        # The refused process must leave the live run exactly as it found it.
        assert gate.exists(), "a refused resume removed the live run's gate record"
        assert json.loads(gate.read_text()) == record

        approve(gate)
        parked.await_line(APPROVED_LINE, timeout=CHILD_TIMEOUT)
        parked.await_line(DONE_MARKER, timeout=CHILD_TIMEOUT)
    finally:
        parked.close()
        if second is not None:
            second.close()


def test_claiming_a_run_someone_holds_is_refused_rather_than_queued(
    runtime_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ownership is not a queue.

    Waiting would be the same defect wearing a delay: the queued process runs
    the same run, with the same decision, as soon as the first one lets go.
    """
    from justai.checkpoint import RunAlreadyActive, own_run

    monkeypatch.setattr("justai.checkpoint.GATE_SIGNAL_DIR", runtime_root / "gates")
    run_id = new_run_id()
    release = runtime_root / "release"
    holder = ChildProcess(
        "holder", runtime_root, ["-m", "tests.gate_lifecycle_child", "hold", run_id, str(release)]
    )
    try:
        holder.await_line(child_modes.HELD, timeout=CHILD_TIMEOUT)
        lock = child_gate_dir(runtime_root, run_id) / LOCK_FILENAME
        before = inode(lock)

        started = time.time()
        with pytest.raises(RunAlreadyActive):
            with own_run(run_id):
                pass
        assert time.time() - started < 10, "the claim queued for the lock instead of failing"

        # A refused claim touches nothing. Replacing the lock here would be
        # the worst version of the bug: the holder would still be excluding on
        # an inode nobody else can reach.
        assert inode(lock) == before, "a refused claim replaced the lock the holder is using"

        release.touch()
        holder.await_line(child_modes.RELEASED, timeout=CHILD_TIMEOUT)
        assert holder.await_exit(timeout=CHILD_TIMEOUT) == 0

        # Released is released: the next process gets the run.
        with own_run(run_id):
            pass
        assert inode(lock) == before
    finally:
        holder.close()


def test_a_run_is_owned_through_dispatch_and_terminal_cleanup(gate_root: Path) -> None:
    """The window the fix has to cover, observed from inside the dispatch.

    Reading the approval, acting on it, and removing it are one indivisible
    step from any other process's point of view. Releasing between them is what
    let a second process read a decision this run had already consumed.
    """
    from justai.checkpoint import RunAlreadyActive, own_run
    from justai.orchestrator import run

    run_id = new_run_id()
    gate = GateIdentity(run_id=run_id, index=0)
    approve(gate_path(gate))
    observed: dict[str, object] = {}

    def probe(tasks, **kwargs):
        observed["record_present"] = gate_path(gate).exists()
        try:
            with own_run(run_id):
                observed["claimable"] = True
        except RunAlreadyActive:
            observed["claimable"] = False
        return []

    with (
        orchestrator_stubs(single_task_plan("R2")),
        patch("justai.orchestrator.escalate_plan", side_effect=probe),
    ):
        result = run("owned through dispatch", run_id=run_id)

    assert result.run_id == run_id
    assert observed["claimable"] is False, (
        "another process could have claimed this run while it was dispatching"
    )
    assert observed["record_present"] is True, (
        "the decision was removed before the work it authorised had been done"
    )
    assert not list(gate_dir(run_id).glob("plan-*.json")), (
        "a finished run left its decision on disk"
    )


def test_a_finished_run_can_be_claimed_again(gate_root: Path) -> None:
    """Ownership ends with the run. A resume afterwards is an ordinary claim."""
    from justai.checkpoint import own_run

    run_id = new_run_id()
    with own_run(run_id):
        pass
    with own_run(run_id):
        pass


# ── the lock inode is permanent ──────────────────────────────────────────────


def test_ownership_never_unlinks_the_lock_it_holds(gate_root: Path) -> None:
    """The file two processes exclude on outlives every one of them.

    ``flock`` excludes the holders of one inode, so replacing the file — or
    removing it and letting the next process create its own — ends exclusion
    rather than the run. Claiming, cleaning up under the claim, releasing, and
    claiming again must all leave the same inode at the same path.
    """
    from justai.checkpoint import cleanup_run, own_run

    run_id = new_run_id()
    lock = gate_dir(run_id) / LOCK_FILENAME

    with own_run(run_id) as owner:
        assert lock.exists(), "claiming a run did not leave a lock at the path"
        before = inode(lock)
        _write_gate(GateIdentity(run_id=run_id, index=0), "pending")
        assert cleanup_run(run_id, owner=owner) == 1
        assert lock.exists(), "cleanup removed the file two processes exclude on"
        assert inode(lock) == before

    assert lock.exists(), "releasing a run removed its lock"
    assert inode(lock) == before

    with own_run(run_id):
        assert inode(lock) == before, "a resume replaced the lock with a different inode"


def test_an_ordinary_run_leaves_its_lock_in_place(gate_root: Path) -> None:
    """The same promise, through the shipped pipeline rather than the helpers."""
    run_id = new_run_id()
    gate = GateIdentity(run_id=run_id, index=0)
    approve(gate_path(gate))
    lock = gate_dir(run_id) / LOCK_FILENAME

    with orchestrator_stubs(single_task_plan("R2")):
        from justai.orchestrator import run

        run("lock survives a run", run_id=run_id)

    assert lock.exists(), "a finished run removed the lock its resume would exclude on"
    assert sorted(entry.name for entry in gate_dir(run_id).iterdir()) == [LOCK_FILENAME]


# ── cleanup under an owner ───────────────────────────────────────────────────


def test_cleanup_under_an_owner_does_not_wait_for_the_lock_it_already_holds(
    gate_root: Path,
) -> None:
    """The owner holds the run's lock, and ``flock`` is not reentrant.

    Cleanup takes the lock for itself when nobody hands it one. Told who owns
    the run, it must use that claim rather than queue behind it — a second
    descriptor on the same file blocks even inside one process, which would
    deadlock the run at its own cleanup.
    """
    from justai.checkpoint import cleanup_run, own_run

    run_id = new_run_id()
    for index in range(2):
        _write_gate(GateIdentity(run_id=run_id, index=index), "pending")

    with own_run(run_id) as owner:
        assert cleanup_run(run_id, owner=owner) == 2

    assert not list(gate_dir(run_id).glob("plan-*.json"))


def test_cleanup_refuses_an_ownership_token_for_another_run(gate_root: Path) -> None:
    """A claim on one run proves nothing about another, and must not be used."""
    from justai.checkpoint import cleanup_run, own_run

    mine = new_run_id()
    theirs = new_run_id()
    _write_gate(GateIdentity(run_id=theirs, index=0), "pending")

    with own_run(mine) as owner:
        with pytest.raises(ValueError):
            cleanup_run(theirs, owner=owner)

    assert gate_path(GateIdentity(run_id=theirs, index=0)).exists()
