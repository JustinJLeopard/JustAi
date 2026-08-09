"""Documented process exit codes for JustAi's command surfaces.

Exit 0 is reserved for a verified-complete outcome: work was planned, it ran,
and every task reported done. Everything else gets a distinct nonzero code.

That distinction matters for outcomes that are not errors. A goal the intent
gate could not understand is a legitimate result, but it is not completion --
nothing was planned and nothing ran. Returning 0 for it tells a script, a CI
job, or a shell `&&` chain that the requested work happened.

    0  OK                      verified complete
    1  FAILED                  the run did not complete (partial/blocked/failed)
    2  (reserved)              argparse's own usage-error code; never assigned here
    3  CLARIFICATION_REQUIRED  the goal was ambiguous; no plan was run
    4  NOT_READY               a readiness probe reported the control plane unready

2 is left alone deliberately. ``argparse`` exits 2 on a malformed command line
before any JustAi code runs, so reusing it would make "you typed the command
wrong" and "your goal needs clarification" indistinguishable to a caller.
"""

from __future__ import annotations

from justai.results import RUN_COMPLETE

OK = 0
FAILED = 1
#: 2 is argparse's usage-error code -- see the module docstring.
CLARIFICATION_REQUIRED = 3
NOT_READY = 4

#: Run statuses that map to something other than a plain failure.
_RUN_STATUS_CODES = {
    RUN_COMPLETE: OK,
    "ambiguous": CLARIFICATION_REQUIRED,
}


def for_run_status(status: str) -> int:
    """Map an :class:`~justai.orchestrator.OrchestrationResult` status to an exit code.

    Unrecognised statuses map to ``FAILED``. That is the safe direction: a
    status this table has not been taught about must never be read as success.
    """
    return _RUN_STATUS_CODES.get(status, FAILED)
