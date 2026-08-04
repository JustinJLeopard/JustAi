"""Shared harness for the approval-gate identity tests.

Stubs every orchestration stage except the checkpoint and the dispatch that
follows it. ``evaluate``, the gate directory, and the files it reads and writes
stay real — they are what is under test.

Lives outside a ``test_*.py`` module so both the in-process tests and the
subprocess child in :mod:`tests.gate_collision_child` describe the same run.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[1]

#: Printed by :func:`delaying_notify` when the notification window opens, so a
#: parent can write inside it instead of racing it.
NOTIFY_WINDOW_MARKER = "NOTIFY-WINDOW-OPEN"

#: Gate polling is how fast a decision is noticed, never what is decided.
#: Shortening it in a child keeps a real-process test bounded.
FAST_POLL_SECONDS = "0.05"

#: Long enough for many poll cycles, short enough to fail rather than hang.
CHILD_TIMEOUT = 60.0


def single_task_plan(risk: str, goal: str = "gate identity", title: str = "Change an interface"):
    """A one-task plan at the given risk level.

    R2 is the hard gate that waits for an approval; R1 is the one an operator
    can veto. Both are decided per task per run, which is the point.
    """
    from justai.scope_planner import AgentType, Plan, RiskLevel, Task

    return Plan(
        goal=goal,
        tasks=[
            Task(
                title=title,
                description="A gated task.",
                agent=AgentType.MINI,
                risk=RiskLevel(risk),
                success_criteria="echo ok",
            )
        ],
    )


def _trace_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.end = MagicMock()
    return ctx


def _execution_intent():
    from justai.intent_gate import Intent, IntentResult

    return IntentResult(
        intent=Intent("execution"),
        confidence=0.9,
        reasoning="harness",
        clarifying_question="",
    )


def _approved_review():
    from justai.reviewer import ReviewResult

    return ReviewResult(approved=True, feedback=[])


def _silent_notify(message: str) -> bool:
    """Keep the gate decision local.

    A configured relay token would send the operator to Discord instead of
    printing the path these tests read.
    """
    return False


def delaying_notify(seconds: float):
    """A ``_discord_notify`` that holds the notification window open.

    The shipped call is an HTTP POST with a ten-second timeout, so the gap
    between a gate being announced and the run recording it is wide and real.
    An operator who approves inside that gap is the case this makes observable:
    the marker says the window is open, the sleep keeps it open long enough for
    a parent to write, and the return value is the ordinary "Discord is not
    configured" answer the rest of the harness gives.
    """

    def _notify(message: str) -> bool:
        print(NOTIFY_WINDOW_MARKER, flush=True)
        time.sleep(seconds)
        return False

    return _notify


@contextmanager
def orchestrator_stubs(plan, notify=_silent_notify):
    """Run the pipeline offline, with the checkpoint stage left real."""
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
        patch("justai.checkpoint._discord_notify", new=notify),
    ):
        yield


class ChildProcess:
    """One helper interpreter, with its stdout on disk so a parent can watch it.

    Two simultaneous holders of one lock, and a write lost across a resume, are
    both invisible inside a single interpreter: ``flock`` is held per open file
    description, and a lost write needs a second process to lose it to. These
    tests therefore drive real processes and read what they print.
    """

    def __init__(
        self,
        name: str,
        runtime_root: Path,
        argv: list[str],
        env_extra: dict[str, str] | None = None,
    ):
        self.name = name
        self.log = runtime_root / f"{name}.log"
        self._handle = self.log.open("w")
        env = os.environ.copy()
        env["JUSTAI_RUNTIME_ROOT"] = str(runtime_root)
        env["JUSTAI_GATE_POLL_SECONDS"] = FAST_POLL_SECONDS
        env["PYTHONPATH"] = str(REPO)
        for leaked in ("JUSTAI_AUTO_MODE", "JUSTAI_SESSION_REF", "JUSTAI_RUN_ID"):
            env.pop(leaked, None)
        env.update(env_extra or {})
        self.proc = subprocess.Popen(
            [sys.executable, "-u", *argv],
            cwd=str(REPO),
            stdout=self._handle,
            stderr=subprocess.STDOUT,
            env=env,
        )

    def output(self) -> str:
        return self.log.read_text(errors="replace") if self.log.exists() else ""

    def saw(self, marker: str) -> bool:
        return marker in self.output()

    def await_line(self, marker: str, timeout: float = CHILD_TIMEOUT) -> None:
        """Block until ``marker`` is printed, failing if the child dies first."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.saw(marker):
                return
            if self.proc.poll() is not None and not self.saw(marker):
                raise AssertionError(
                    f"{self.name} exited before printing {marker!r}:\n{self.output()}"
                )
            time.sleep(0.02)
        raise AssertionError(f"{self.name} never printed {marker!r}:\n{self.output()}")

    def await_exit(self, timeout: float = CHILD_TIMEOUT) -> int:
        try:
            return self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise AssertionError(f"{self.name} did not exit:\n{self.output()}") from exc

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        self._handle.close()
