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

from justai.trajectory import TrajectoryStore

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.6
SEARCH_LIMIT = 3

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

    Returns True if stored, False on failure. Never raises.
    """
    try:
        steps = [r.title for r in results]
        done = sum(1 for r in results if r.status == "done")
        failed = sum(1 for r in results if r.status in ("failed", "error", "timeout"))

        if failed == 0:
            outcome = "success"
        elif done > 0:
            outcome = "partial"
        else:
            outcome = "failed"

        return _store.store(
            goal=goal,
            steps=steps,
            outcome=outcome,
            duration=duration,
        )
    except Exception as e:
        logger.debug(f"Trajectory store failed (non-fatal): {e}")
        return False
