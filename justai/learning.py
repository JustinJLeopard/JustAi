"""
JustAi — Learning Layer
========================
Trajectory context enrichment for the planner and post-run trajectory storage.

Called by orchestrator at two points:
  - Before planning: enrich_context(goal) -> str of similar past trajectories
  - After synthesis: record_run(goal, results, duration) -> bool

Both functions are fire-and-forget — they never raise, never block the pipeline.
"""

from __future__ import annotations

import logging

from justai.results import RUN_COMPLETE, tally
from justai.trajectory import TrajectoryStore

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.6
SEARCH_LIMIT = 3

#: Trajectory outcome for each run verdict. Only a verified-complete run may be
#: filed as "success" — this table is what keeps the stored trajectory from
#: disagreeing with the run summary the operator was shown.
_OUTCOME_FOR_RUN_STATUS = {RUN_COMPLETE: "success"}

# Module-level store instance — reused across calls
_store = TrajectoryStore()


def enrich_context(goal: str) -> str:
    """Search trajectory store for similar past runs and format as planner context.

    Returns formatted context string, or "" on empty/failure.
    """
    try:
        matches = _store.search(goal, limit=SEARCH_LIMIT)
        # Filter by similarity threshold
        good_matches = [m for m in matches if m.similarity >= SIMILARITY_THRESHOLD]
        if not good_matches:
            return ""
        return TrajectoryStore.format_as_context(good_matches)
    except Exception as e:
        logger.debug(f"Trajectory search failed (non-fatal): {e}")
        return ""


def record_run(
    goal: str,
    results: list,
    duration: float,
) -> bool:
    """Store run results as a trajectory for future context enrichment.

    A run with no results is not stored at all. There is no trajectory in it —
    no step was taken — and filing one would seed the planner's context with a
    goal that appears to have been handled.

    Returns True if stored, False on failure or on nothing worth storing.
    Never raises: an unrecognised result status is refused here rather than
    stored under a status this layer guessed at.
    """
    try:
        counts = tally(results)
        if counts.total == 0:
            logger.debug("Nothing to record: the run produced no results.")
            return False

        return _store.store(
            goal=goal,
            steps=[r.title for r in results],
            outcome=_OUTCOME_FOR_RUN_STATUS.get(counts.run_status, counts.run_status),
            duration=duration,
        )
    except Exception as e:
        logger.debug(f"Trajectory store failed (non-fatal): {e}")
        return False
