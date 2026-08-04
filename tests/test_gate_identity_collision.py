"""The approval gate must belong to one run, proven with two real processes.

The defect: the gate an R2 task waits on was named
``gates/gate_<session_ref>-plan-<index>.json``. ``session_ref`` is a human
label — ``justai run`` leaves it empty unless ``--session`` is passed, the
module default is the shared string ``sprint-2``, and a dashboard caller may
reuse one deliberately. Two ordinary concurrent runs therefore agreed on a plan
index and a label, agreed on a filename, and waited on the same file. One
operator approval released both — including the run the operator never looked
at.

These tests run two separate interpreters, because that is the shape of the
bug: one process cannot tell that another is about to consume its approval.
Both children enter through ``justai.cli.main``, so the identity under test is
the one the shipped CLI derives, not one the test invents.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: The checkpoint's own operator instruction, and the orchestrator's own verdict
#: line. Reading the shipped output is what makes this a reproduction rather
#: than a restatement of the implementation.
GATE_PATH_LINE = re.compile(r"Waiting for approval\. Write to: (\S+)")
APPROVED_LINE = "R2 approved by operator"
REJECTED_MARKER = "BLOCKED: R2 rejected"

#: Gate polling is an implementation detail of how fast a decision is noticed,
#: never of what is decided. Shortening it keeps the test bounded.
FAST_POLL_SECONDS = "0.05"

#: Long enough for many poll cycles, short enough to fail rather than hang.
ANNOUNCE_TIMEOUT = 60.0
RELEASE_TIMEOUT = 60.0

#: How long the unapproved run is watched before it is called "still waiting".
#: At 0.05s polling this is >100 cycles after the other run was released.
STILL_WAITING_WINDOW = 6.0


class Child:
    """One ``justai run`` in its own interpreter, blocked at an R2 gate."""

    def __init__(self, name: str, runtime_root: Path, extra_args: list[str]):
        self.name = name
        self.log = runtime_root / f"{name}.log"
        self._handle = self.log.open("w")
        env = os.environ.copy()
        env["JUSTAI_RUNTIME_ROOT"] = str(runtime_root)
        env["JUSTAI_GATE_POLL_SECONDS"] = FAST_POLL_SECONDS
        env["PYTHONPATH"] = str(REPO)
        for leaked in ("JUSTAI_AUTO_MODE", "JUSTAI_SESSION_REF", "JUSTAI_RUN_ID"):
            env.pop(leaked, None)
        self.proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "tests.gate_collision_child", *extra_args],
            cwd=str(REPO),
            stdout=self._handle,
            stderr=subprocess.STDOUT,
            env=env,
        )

    def output(self) -> str:
        return self.log.read_text(errors="replace") if self.log.exists() else ""

    def gate_path(self, timeout: float = ANNOUNCE_TIMEOUT) -> Path:
        """The gate path this run told the operator to write to."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            match = GATE_PATH_LINE.search(self.output())
            if match:
                return Path(match.group(1))
            if self.proc.poll() is not None:
                raise AssertionError(
                    f"{self.name} exited before announcing a gate:\n{self.output()}"
                )
            time.sleep(0.05)
        raise AssertionError(f"{self.name} never announced a gate:\n{self.output()}")

    @property
    def released(self) -> bool:
        return APPROVED_LINE in self.output()

    @property
    def decided(self) -> bool:
        """Released or refused — either way, no longer waiting."""
        out = self.output()
        return APPROVED_LINE in out or REJECTED_MARKER in out

    def await_parked(self, timeout: float = ANNOUNCE_TIMEOUT) -> None:
        """Block until this run has recorded the pending gate it is waiting on.

        Both runs are brought to the same point before either is approved, so
        what the assertions below observe is one decision reaching two runs
        rather than one run being further along than the other.

        An approval written earlier than this survives — the pending record is
        created, never written over (see ``test_gate_lifecycle.py``). Waiting
        here is for the symmetry, not to dodge a lost write.
        """
        gate = self.gate_path(timeout=timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if gate.exists():
                return
            if self.proc.poll() is not None:
                raise AssertionError(
                    f"{self.name} exited before parking at its gate:\n{self.output()}"
                )
            time.sleep(0.05)
        raise AssertionError(f"{self.name} never recorded a pending gate:\n{self.output()}")

    def await_release(self, timeout: float = RELEASE_TIMEOUT) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.released:
                return
            time.sleep(0.05)
        raise AssertionError(f"{self.name} was approved but never proceeded:\n{self.output()}")

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        self._handle.close()


def approve(gate: Path) -> None:
    """Write the approval an operator writes, the way the instructions say."""
    gate.parent.mkdir(parents=True, exist_ok=True)
    gate.write_text(json.dumps({"status": "approved"}))


@pytest.fixture
def runtime_root(tmp_path: Path) -> Path:
    root = tmp_path / "runtime"
    root.mkdir()
    return root


@pytest.mark.parametrize(
    "extra_args",
    [
        pytest.param([], id="ordinary-cli-defaults"),
        pytest.param(["--session", "shared-label"], id="reused-session-ref"),
    ],
)
def test_one_approval_releases_exactly_one_of_two_concurrent_runs(
    runtime_root: Path, extra_args: list[str]
) -> None:
    """Two processes, same label, same plan index, one approval.

    ``ordinary-cli-defaults`` is the case that shipped: no ``--session``, so
    both runs carry the same empty label. ``reused-session-ref`` is the case an
    operator creates by naming two runs the same thing. Neither may share a
    gate.

    The consequence is asserted before the mechanism. Against the collision
    this replaces, what fails is the second run reporting ``R2 approved by
    operator`` and going on to execute — a run cleared through a hard gate by a
    decision nobody made about it — rather than the milder observation that two
    paths happened to match.
    """
    first = Child("run-a", runtime_root, extra_args)
    second = Child("run-b", runtime_root, extra_args)
    try:
        first_gate = first.gate_path()
        second_gate = second.gate_path()
        # Bring both runs to the same point before either is approved.
        first.await_parked()
        second.await_parked()

        approve(first_gate)
        first.await_release()

        deadline = time.time() + STILL_WAITING_WINDOW
        while time.time() < deadline:
            assert not second.decided, (
                "the second run proceeded on an approval written for the first — "
                "one operator decision released a run nobody looked at:\n"
                f"{second.output()}"
            )
            time.sleep(0.05)

        # Positive control: the same harness releases the second run the moment
        # its own gate is written, so "still waiting" above is the gate holding
        # it and not the test failing to observe a release.
        approve(second_gate)
        second.await_release()

        # The mechanism under the assertions above: an approval is scoped by
        # the path it is written to, so two runs must never name one file.
        assert first_gate != second_gate, (
            "both runs told the operator to write to the same file, so a single "
            f"approval decides both: {first_gate}"
        )
    finally:
        first.close()
        second.close()


def test_each_run_gets_its_own_gate_directory(runtime_root: Path) -> None:
    """The identity is in the path, so two runs cannot name one file.

    Same label, same plan index, different runs: the announced paths must
    differ in a run-scoped component, not merely in the plan index.
    """
    first = Child("dir-a", runtime_root, [])
    second = Child("dir-b", runtime_root, [])
    try:
        first_gate = first.gate_path()
        second_gate = second.gate_path()

        assert first_gate.parent != second_gate.parent, (
            "gates for two different runs landed in one directory; a per-run "
            f"directory is what keeps cleanup and approval scoped: {first_gate.parent}"
        )
        assert first_gate.name == second_gate.name, (
            "both runs are at plan index 0; the index is not what should differ"
        )
    finally:
        first.close()
        second.close()
