"""Child process for the gate-lifecycle reproductions.

Each mode is one shipped call, driven from its own interpreter so the parent
can observe what a single process cannot: who holds a run's lock, and when.

    python -u -m tests.gate_lifecycle_child hold  <run_id> <release_file>
    python -u -m tests.gate_lifecycle_child clean <run_id>
    python -u -m tests.gate_lifecycle_child sweep <older_than_seconds>

``hold`` announces that it is about to queue for the lock, announces again once
it holds it, and keeps holding until the parent creates the release file. The
two announcements are what make "queued" and "holding" distinguishable from
outside, which is the whole difficulty in proving that two processes were in a
critical section at the same time.

``JUSTAI_RUNTIME_ROOT`` selects the gate directory, exactly as it does for the
shipped CLI; :mod:`justai.checkpoint` reads it when it is imported.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

#: Printed just before the lock is asked for, and just after it is held. A
#: parent that sees QUEUEING and not HELD knows the child is blocked rather
#: than slow to start.
QUEUEING = "LOCK-QUEUEING"
HELD = "LOCK-HELD"
RELEASED = "LOCK-RELEASED"
CLEANING = "CLEAN-STARTED"
CLEANED = "CLEAN-REMOVED="
SWEPT = "SWEEP-REMOVED="

#: How often the release file is looked for. Only how fast the child notices.
POLL_SECONDS = 0.02

#: A held lock that is never released would hang the suite instead of failing it.
MAX_HOLD_SECONDS = 120.0


def _hold(run_id: str, release_file: str) -> int:
    from justai.checkpoint import run_gate_lock

    release = Path(release_file)
    print(QUEUEING, flush=True)
    with run_gate_lock(run_id):
        print(HELD, flush=True)
        deadline = time.time() + MAX_HOLD_SECONDS
        while not release.exists():
            if time.time() > deadline:
                print("HOLD-TIMEOUT", flush=True)
                return 1
            time.sleep(POLL_SECONDS)
    print(RELEASED, flush=True)
    return 0


def _clean(run_id: str) -> int:
    from justai.checkpoint import cleanup_run

    print(CLEANING, flush=True)
    print(f"{CLEANED}{cleanup_run(run_id)}", flush=True)
    return 0


def _sweep(older_than_seconds: str) -> int:
    from justai.checkpoint import sweep_gate_dirs

    print(f"{SWEPT}{sweep_gate_dirs(older_than_seconds=float(older_than_seconds))}", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    mode, rest = args[0], args[1:]
    if mode == "hold":
        return _hold(*rest)
    if mode == "clean":
        return _clean(*rest)
    if mode == "sweep":
        return _sweep(*rest)
    raise SystemExit(f"unknown mode {mode!r}")


if __name__ == "__main__":
    sys.exit(main())
