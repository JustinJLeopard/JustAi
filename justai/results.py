"""Shared result types and the canonical status vocabulary for JustAi.

Every surface that decides whether a run succeeded — the synthesizer, the
learning layer, the CLI exit code — reads that decision from here. Keeping one
vocabulary is the point: the completion-integrity defects this module exists to
prevent all came from two surfaces disagreeing about what a status meant, or
from a surface quietly treating an unrecognised status as "not a failure".
"""

from __future__ import annotations

from dataclasses import dataclass

#: A task the executor reported as genuinely finished.
DONE_STATUS = "done"

#: The task's action ran but no automated success check confirmed it. JustAi's
#: honest 3-state executor emits this (executed, unverified) — it is NOT done
#: and it is NOT a failure, so it keeps a run out of "complete".
UNVERIFIED_STATUS = "unverified"

#: The executor tried and did not finish.
FAILURE_STATUSES = frozenset({"failed", "error", "timeout"})

#: The executor never ran the task: a checkpoint blocked it, or a dependency
#: did not complete. Withheld work is not success and is not an execution
#: failure, so it is counted on its own.
WITHHELD_STATUSES = frozenset({"skipped", "blocked"})

KNOWN_STATUSES = frozenset({DONE_STATUS, UNVERIFIED_STATUS}) | FAILURE_STATUSES | WITHHELD_STATUSES

#: Run-level verdicts. Only ``complete`` may be read as success, and only a
#: nonempty result set where every task finished can earn it.
RUN_COMPLETE = "complete"
RUN_PARTIAL = "partial"
RUN_BLOCKED = "blocked"
RUN_FAILED = "failed"


@dataclass
class DelegationResult:
    task_id: str
    title: str
    status: str
    result: str
    duration_seconds: float


@dataclass(frozen=True)
class ResultTally:
    total: int
    done: int
    failed: int
    skipped: int
    blocked: int
    unverified: int

    @property
    def withheld(self) -> int:
        return self.skipped + self.blocked

    @property
    def is_verified_complete(self) -> bool:
        """True only when work was actually attempted and all of it finished.

        A run with no results is not complete. It is a run that did nothing,
        and callers that treat "zero failures" as success read it as a win.
        """
        return self.total > 0 and self.done == self.total

    @property
    def run_status(self) -> str:
        """The single run verdict every completion surface reads.

        ``failed`` absorbs the empty result set on purpose. Nothing ran, so
        nothing was verified, and each of the other buckets would let a caller
        read "no failures" as a finished run. An ``unverified`` task keeps a run
        out of ``complete`` but, like a done one, keeps it off ``failed``.
        """
        if self.is_verified_complete:
            return RUN_COMPLETE
        if self.done > 0 or self.unverified > 0:
            return RUN_PARTIAL
        if self.total > 0 and self.withheld == self.total:
            return RUN_BLOCKED
        return RUN_FAILED


def classify_status(status: object) -> str:
    """Map a raw result status to a canonical bucket.

    Raises:
        ValueError: the status is not in the canonical vocabulary. Unknown
            statuses are rejected rather than bucketed, because every
            reasonable default here is a lie: counting one as a failure invents
            a failure, and counting it as anything else lets an unrecognised
            string reach a success path.
    """
    if not isinstance(status, str):
        raise ValueError(f"result status must be a string, got {type(status).__name__}")
    if status == DONE_STATUS:
        return "done"
    if status == UNVERIFIED_STATUS:
        return "unverified"
    if status in FAILURE_STATUSES:
        return "failed"
    if status in WITHHELD_STATUSES:
        return "withheld"
    raise ValueError(f"unknown result status {status!r}; expected one of {sorted(KNOWN_STATUSES)}")


def tally(results: list) -> ResultTally:
    """Count well-formed results, rejecting shapes the run cannot report safely.

    The result set itself is checked before anything in it. An executor that
    returned no sequence at all would otherwise reach the iteration below and
    raise ``TypeError``, which is not the refusal a caller catches — so the run
    could end in a traceback with its traces unflushed and no record filed.

    ``duration_seconds`` is optional (the synthesizer records it only when
    present) but must be a number when present, because that surface rounds it.
    """
    if not isinstance(results, (list, tuple)):
        raise ValueError(f"results must be a sequence of results, got {type(results).__name__}")

    # tally counts by status. It validates only what it reads: the status must
    # be in the canonical vocabulary, and a duration_seconds (optional) must be
    # a number when present, because reporting surfaces round it. Strict
    # result-shape validation (task_id/title/result string fields for the
    # malformed-result-preserves-the-run contract) is the orchestrator
    # fail-closed slice, not this counting primitive.
    for index, r in enumerate(results):
        duration = getattr(r, "duration_seconds", 0.0)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise ValueError(
                f"result [{index}] field 'duration_seconds' must be a number, "
                f"got {type(duration).__name__}"
            )
        classify_status(getattr(r, "status", None))

    return ResultTally(
        total=len(results),
        done=sum(1 for r in results if r.status == DONE_STATUS),
        failed=sum(1 for r in results if r.status in FAILURE_STATUSES),
        skipped=sum(1 for r in results if r.status == "skipped"),
        blocked=sum(1 for r in results if r.status == "blocked"),
        unverified=sum(1 for r in results if r.status == UNVERIFIED_STATUS),
    )
