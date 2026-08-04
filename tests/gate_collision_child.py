"""Child process for the two-process approval-gate reproduction.

The collision under test belongs to the orchestrator, not to the test: this
child enters through ``justai.cli.main`` exactly as ``justai run`` does, so
whatever gate identity the CLI and orchestrator derive is the identity being
reproduced. Everything around the checkpoint is stubbed by
:mod:`tests.gate_harness` — ``evaluate``, the gate directory, and the files it
reads and writes stay real.

    python -u -m tests.gate_collision_child [extra `justai run` args...]

Stdout carries the checkpoint's own operator instructions, including the gate
path it is waiting on. The parent reads the path from there and writes the
approval an operator would write, which is the whole point: if two runs
announce the same path, one approval releases both.
"""

from __future__ import annotations

import os
import sys

from tests.gate_harness import _silent_notify, delaying_notify, orchestrator_stubs, single_task_plan

GOAL = "gate identity reproduction"

#: Seconds to hold the R2 notification window open before the run records its
#: own pending gate. Set by a parent that needs to write an approval inside
#: that window; the shipped POST has a ten-second timeout, so the window is
#: real and this only makes it observable.
NOTIFY_DELAY_VAR = "JUSTAI_TEST_NOTIFY_DELAY"

#: Printed once the run is over, so the parent can tell "finished" from
#: "still waiting at the gate" without inferring it from a timeout alone.
DONE_MARKER = "CHILD-DONE exit="


def main(argv: list[str] | None = None) -> int:
    from justai.cli import main as cli_main

    extra = list(sys.argv[1:] if argv is None else argv)
    plan = single_task_plan("R2", goal=GOAL, title="Change a published interface")
    delay = os.environ.get(NOTIFY_DELAY_VAR, "").strip()
    notify = delaying_notify(float(delay)) if delay else _silent_notify
    with orchestrator_stubs(plan, notify=notify):
        code = cli_main(["run", GOAL, *extra])
    print(f"{DONE_MARKER}{code}", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
