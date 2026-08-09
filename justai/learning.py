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
from collections.abc import Iterable
from typing import Any

from justai.trajectory import TrajectoryStore

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.6
SEARCH_LIMIT = 3

# Module-level store instance — reused across calls
_store = TrajectoryStore()

FAILURE_CLASSES = {
    "timeout",
    "tool_error",
    "wrong_action",
    "inferred_action",
    "verification_fail",
}


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
    *,
    actions: list | None = None,
    failure_class: str | None = None,
    strategy_used: str | dict | None = None,
    strategy_outcome: str | None = None,
    strategy_accepted: bool | None = None,
    did_next_plan_change: bool | None = None,
    next_plan_changed: bool | None = None,
    prior_chosen_focus: str | None = None,
    chosen_focus: str | None = None,
    prior_next_experiment: str | None = None,
    next_experiment: str | None = None,
    correlation_id: str | None = None,
) -> bool:
    """Store run results as a trajectory for future context enrichment.

    Returns True if stored, False on failure. Never raises.
    """
    try:
        steps = [r.title for r in results]
        # Shared vocabulary with the synthesizer (justai.results.tally): the two
        # surfaces must agree on what counts as success. "success" is reserved
        # for a verified-complete run; an empty run records nothing; an unknown
        # or malformed result status is refused (tally raises -> caught below ->
        # return False) rather than counted as "no failures = success".
        from justai.results import RUN_COMPLETE, RUN_PARTIAL, tally

        counts = tally(results)
        if counts.total == 0:
            return False
        run_status = counts.run_status
        if run_status == RUN_COMPLETE:
            outcome = "success"
        elif run_status == RUN_PARTIAL:
            outcome = "partial"
        else:
            outcome = "failed"

        execution_evidence = _extract_execution_evidence(results, actions)
        did_change = _resolve_next_plan_change(
            did_next_plan_change=did_next_plan_change,
            next_plan_changed=next_plan_changed,
            prior_chosen_focus=prior_chosen_focus,
            chosen_focus=chosen_focus,
            prior_next_experiment=prior_next_experiment,
            next_experiment=next_experiment,
        )
        derived_failure_class = _derive_failure_class(
            explicit=failure_class,
            outcome=outcome,
            results=results,
            execution_evidence=execution_evidence,
        )
        strategy = _normalize_strategy_used(
            strategy_used=strategy_used,
            strategy_outcome=strategy_outcome,
            strategy_accepted=strategy_accepted,
            outcome=outcome,
        )

        return _store.store(
            goal=goal,
            steps=steps,
            outcome=outcome,
            duration=duration,
            failure_class=derived_failure_class,
            execution_evidence=execution_evidence,
            strategy_used=strategy,
            did_next_plan_change=did_change,
            correlation_id=correlation_id,
        )
    except Exception as e:
        logger.debug(f"Trajectory store failed (non-fatal): {e}")
        return False


def _extract_execution_evidence(results: list, actions: list | None = None) -> list[dict[str, Any]]:
    """Extract action/result evidence from safe-mini-shaped RunResult objects."""
    evidence: list[dict[str, Any]] = []
    for run_result in _iter_run_results(results):
        run_actions = list(actions or _as_list(getattr(run_result, "actions", [])))
        run_result_records = list(_as_list(getattr(run_result, "results", [])))
        if not run_actions and not run_result_records:
            continue

        result_by_action_id = {
            str(getattr(result, "action_id", "")): result
            for result in run_result_records
            if getattr(result, "action_id", None) is not None
        }
        step_title = getattr(run_result, "title", None) or getattr(
            getattr(run_result, "chunk", None), "goal", None
        )

        for action in run_actions:
            action_id = _stringify(getattr(action, "action_id", None))
            paired_result = result_by_action_id.get(action_id) if action_id is not None else None
            evidence.append(
                {
                    "step": step_title,
                    "action_id": action_id,
                    "result_id": _stringify(getattr(paired_result, "result_id", None)),
                    "evidence_ref": getattr(paired_result, "evidence_ref", None),
                    "status": getattr(paired_result, "status", None),
                }
            )

        action_ids = {item["action_id"] for item in evidence if item.get("action_id")}
        for result in run_result_records:
            action_id = _stringify(getattr(result, "action_id", None))
            if action_id in action_ids:
                continue
            evidence.append(
                {
                    "step": step_title,
                    "action_id": action_id,
                    "result_id": _stringify(getattr(result, "result_id", None)),
                    "evidence_ref": getattr(result, "evidence_ref", None),
                    "status": getattr(result, "status", None),
                }
            )

    return evidence


def _derive_failure_class(
    *,
    explicit: str | None,
    outcome: str,
    results: list,
    execution_evidence: list[dict[str, Any]],
) -> str | None:
    normalized = _normalize_failure_class(explicit)
    if normalized:
        return normalized
    if outcome == "success":
        return None

    values: list[str] = []
    for result in _iter_run_results(results):
        values.append(str(getattr(result, "status", "")))
        values.append(str(getattr(result, "failure_class", "")))
        for child in _as_list(getattr(result, "results", [])):
            values.append(str(getattr(child, "status", "")))
            values.append(str(getattr(child, "failure_class", "")))
    values.extend(str(item.get("status", "")) for item in execution_evidence)

    normalized_values = [_normalize_failure_class(value) for value in values]
    for candidate in ("timeout", "wrong_action", "tool_error", "verification_fail", "inferred_action"):
        if candidate in normalized_values:
            return candidate

    if execution_evidence and any(item.get("result_id") is None for item in execution_evidence):
        return "inferred_action"
    return "verification_fail"


def _normalize_failure_class(value: str | None) -> str | None:
    if not value:
        return None
    normalized = str(value).strip().lower().replace("-", "_")
    aliases = {
        "budget_exhausted": "timeout",
        "timed_out": "timeout",
        "error": "tool_error",
        "embodiment_failure": "tool_error",
        "context_starvation": "tool_error",
        "action_protocol_violation": "wrong_action",
        "safety_violation": "wrong_action",
        "reward_hacking": "wrong_action",
        "exhausted_ideas": "inferred_action",
        "fail": "verification_fail",
        "failed": "verification_fail",
        "failure": "verification_fail",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in FAILURE_CLASSES else None


def _normalize_strategy_used(
    *,
    strategy_used: str | dict | None,
    strategy_outcome: str | None,
    strategy_accepted: bool | None,
    outcome: str,
) -> dict[str, Any] | None:
    if strategy_used is None:
        return None

    if isinstance(strategy_used, dict):
        strategy = dict(strategy_used)
        name = strategy.get("name") or strategy.get("strategy") or strategy.get("id")
    else:
        strategy = {"name": str(strategy_used)}
        name = strategy["name"]

    if not name:
        return None

    explicit_outcome = strategy_outcome or strategy.get("outcome")
    if explicit_outcome in {"accepted", "ignored"}:
        accepted_outcome = explicit_outcome
    elif strategy_accepted is not None:
        accepted_outcome = "accepted" if strategy_accepted else "ignored"
    else:
        accepted_outcome = "accepted" if outcome == "success" else "ignored"

    strategy["name"] = str(name)
    strategy["outcome"] = accepted_outcome
    return strategy


def _resolve_next_plan_change(
    *,
    did_next_plan_change: bool | None,
    next_plan_changed: bool | None,
    prior_chosen_focus: str | None,
    chosen_focus: str | None,
    prior_next_experiment: str | None,
    next_experiment: str | None,
) -> bool | None:
    if did_next_plan_change is not None:
        return bool(did_next_plan_change)
    if next_plan_changed is not None:
        return bool(next_plan_changed)

    comparable_pairs = [
        (prior_chosen_focus, chosen_focus),
        (prior_next_experiment, next_experiment),
    ]
    known_pairs = [(before, after) for before, after in comparable_pairs if before or after]
    if not known_pairs:
        return None
    return any(before != after for before, after in known_pairs)


def _iter_run_results(results: list) -> Iterable[Any]:
    if hasattr(results, "actions") or hasattr(results, "results"):
        return [results]
    return results or []


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return list(value) if isinstance(value, tuple) else [value]


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
