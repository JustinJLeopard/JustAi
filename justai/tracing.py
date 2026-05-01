#!/usr/bin/env python3
"""
JustAi — LangFuse Tracing
==========================
Lightweight observability for the orchestrator pipeline.

Wraps each pipeline stage (intent, plan, review, delegate) in a LangFuse
trace+generation so you get per-call cost, latency, and token counts in
the LangFuse dashboard.

Setup:
    pip install langfuse
    export LANGFUSE_PUBLIC_KEY=pk-...
    export LANGFUSE_SECRET_KEY=sk-...
    export LANGFUSE_HOST=https://cloud.langfuse.com  # or self-hosted

If langfuse is not installed or keys are not set, all functions are no-ops
so the orchestrator runs identically without tracing overhead.

Usage:
    from justai.tracing import trace_generation, flush_traces

    with trace_generation("planner", model="openai/claude-opus-4-6",
                          input_text=prompt, metadata={"goal": goal}) as gen:
        result = _call_litellm(...)
        gen.end(output_text=result_text)

    # At end of pipeline
    flush_traces()
"""

from __future__ import annotations

import os
import time
from collections.abc import Generator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC
from typing import Any

# ── Conditional Import ───────────────────────────────────────────────────────

_langfuse: Any = None
_enabled = False

try:
    from langfuse import Langfuse

    _pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    _sk = os.environ.get("LANGFUSE_SECRET_KEY", "")
    if _pk and _sk:
        _langfuse = Langfuse(
            public_key=_pk,
            secret_key=_sk,
            host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
        _enabled = True
except ImportError:
    pass


# ── Public API ───────────────────────────────────────────────────────────────


def is_enabled() -> bool:
    """Whether LangFuse tracing is active."""
    return _enabled


@dataclass
class GenerationHandle:
    """Wraps a LangFuse generation span. Safe to use even when tracing is off."""

    _trace: Any = None
    _generation: Any = None
    _start: float = field(default_factory=time.time)

    def end(
        self,
        output_text: str = "",
        usage: dict | None = None,
        metadata: dict | None = None,
        level: str = "DEFAULT",
    ) -> None:
        if self._generation is None:
            return
        kwargs: dict[str, Any] = {
            "output": output_text[:2000],
            "level": level,
            "end_time": _now(),
        }
        if usage:
            kwargs["usage"] = usage
        if metadata:
            kwargs["metadata"] = metadata
        with suppress(Exception):
            self._generation.end(**kwargs)

    def error(self, message: str) -> None:
        self.end(output_text=message, level="ERROR")


@contextmanager
def trace_generation(
    name: str,
    model: str = "",
    input_text: str = "",
    metadata: dict | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
) -> Generator[GenerationHandle, None, None]:
    """
    Context manager that creates a LangFuse trace + generation span.

    Usage:
        with trace_generation("planner", model="openai/claude-opus-4-6",
                              input_text=prompt) as gen:
            result = call_llm(prompt)
            gen.end(output_text=result, usage={"total_tokens": 500})

    If LangFuse is not configured, yields a no-op handle.
    """
    handle = GenerationHandle()

    if not _enabled or _langfuse is None:
        yield handle
        return

    try:
        trace_kwargs: dict[str, Any] = {
            "name": f"justai-{name}",
            "metadata": metadata or {},
        }
        if session_id:
            trace_kwargs["session_id"] = session_id
        if tags:
            trace_kwargs["tags"] = tags

        trace = _langfuse.trace(**trace_kwargs)
        generation = trace.generation(
            name=name,
            model=model,
            input=input_text[:4000],
            start_time=_now(),
            metadata=metadata or {},
        )
        handle._trace = trace
        handle._generation = generation
    except Exception:
        pass

    yield handle


def trace_event(
    name: str,
    metadata: dict | None = None,
    session_id: str | None = None,
) -> None:
    """Log a non-LLM event (checkpoint gate, delegation, etc.)."""
    if not _enabled or _langfuse is None:
        return
    try:
        trace_kwargs: dict[str, Any] = {
            "name": f"justai-{name}",
            "metadata": metadata or {},
        }
        if session_id:
            trace_kwargs["session_id"] = session_id
        _langfuse.trace(**trace_kwargs)
    except Exception:
        pass


def flush_traces() -> None:
    """Flush pending traces to LangFuse. Call at end of pipeline."""
    if _langfuse is not None:
        with suppress(Exception):
            _langfuse.flush()


# ── Query Layer (read-side) ──────────────────────────────────────────────────

# Pipeline stage names used in trace_generation() calls
PIPELINE_STAGES = ["intent-gate", "planner", "reviewer", "local", "external", "synthesizer"]


def get_traces(
    limit: int = 50,
    session_id: str | None = None,
) -> list[dict]:
    """
    Fetch recent traces from LangFuse.

    Returns list of dicts with: id, name, session_id, timestamp,
    latency_ms, total_cost, input_tokens, output_tokens, status.
    """
    if not _enabled or _langfuse is None:
        return []
    try:
        kwargs: dict[str, Any] = {"limit": limit}
        if session_id:
            kwargs["session_id"] = session_id
        resp = _langfuse.fetch_traces(**kwargs)
        traces = []
        for t in resp.data:
            traces.append(
                {
                    "id": t.id,
                    "name": getattr(t, "name", ""),
                    "session_id": getattr(t, "session_id", ""),
                    "timestamp": getattr(t, "timestamp", ""),
                    "latency_ms": _calc_latency_ms(t),
                    "total_cost": _sum_cost(t),
                    "input_tokens": _sum_tokens(t, "input"),
                    "output_tokens": _sum_tokens(t, "output"),
                    "status": _trace_status(t),
                    "tags": getattr(t, "tags", []),
                    "metadata": getattr(t, "metadata", {}),
                }
            )
        return traces
    except Exception:
        return []


def get_trace_by_run(run_id: str) -> list[dict]:
    """Fetch all traces for a specific run (session_id)."""
    return get_traces(limit=100, session_id=run_id)


def get_aggregated_metrics(days: int = 7) -> dict:
    """
    Compute cost/latency/quality aggregates from recent traces.

    Returns:
        {
            "cost": {"daily": [...], "total": float, "by_model": {...}, "by_stage": {...}},
            "latency": {"daily": [...], "p50": int, "p90": int, "p99": int, "bottleneck": str, "by_stage": {...}},
            "quality": {"daily": [...], "overall_rate": float, "failure_categories": {...}},
            "summary": {"cost_24h": float, "cost_trend": [...], "avg_latency_ms": int, "latency_trend": [...], "p50": int, "p90": int}
        }
    """
    if not _enabled or _langfuse is None:
        return _empty_metrics()

    try:
        traces = get_traces(limit=500)
    except Exception:
        return _empty_metrics()

    if not traces:
        return _empty_metrics()

    from datetime import datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(days=days)
    cutoff_24h = datetime.now(UTC) - timedelta(days=1)

    # Filter to time window
    recent = []
    for t in traces:
        ts = t.get("timestamp")
        if ts and _parse_ts(ts) >= cutoff:
            recent.append(t)

    if not recent:
        return _empty_metrics()

    # ── Cost aggregation ─────────────────────────────────────────────────
    daily_cost: dict[str, float] = {}
    daily_cost_by_model: dict[str, dict[str, float]] = {}
    daily_cost_by_stage: dict[str, dict[str, float]] = {}
    daily_tokens: dict[str, dict[str, int]] = {}
    by_model: dict[str, float] = {}
    by_stage: dict[str, float] = {}
    cost_24h = 0.0
    running_total = 0.0
    input_tokens_total = 0
    output_tokens_total = 0

    for t in recent:
        cost = t.get("total_cost") or 0.0
        day = _day_key(t.get("timestamp"))
        daily_cost[day] = daily_cost.get(day, 0.0) + cost

        # Per-day model breakdown (for stacked bars)
        model = (t.get("metadata") or {}).get("model", "unknown")
        daily_cost_by_model.setdefault(day, {})
        daily_cost_by_model[day][model] = daily_cost_by_model[day].get(model, 0.0) + cost
        by_model[model] = by_model.get(model, 0.0) + cost

        # Per-day stage breakdown
        stage = _stage_from_name(t.get("name", ""))
        if stage:
            by_stage[stage] = by_stage.get(stage, 0.0) + cost
            daily_cost_by_stage.setdefault(day, {})
            daily_cost_by_stage[day][stage] = daily_cost_by_stage[day].get(stage, 0.0) + cost

        # Token counts per day
        tin = t.get("input_tokens") or 0
        tout = t.get("output_tokens") or 0
        daily_tokens.setdefault(day, {"input": 0, "output": 0})
        daily_tokens[day]["input"] += tin
        daily_tokens[day]["output"] += tout
        input_tokens_total += tin
        output_tokens_total += tout

        ts = t.get("timestamp")
        if ts and _parse_ts(ts) >= cutoff_24h:
            cost_24h += cost

    cost_daily = []
    for d in sorted(daily_cost):
        running_total += daily_cost[d]
        cost_daily.append(
            {
                "date": d,
                "total": round(daily_cost[d], 4),
                "running_total": round(running_total, 4),
                "by_model": {k: round(v, 4) for k, v in daily_cost_by_model.get(d, {}).items()},
                "by_stage": {k: round(v, 4) for k, v in daily_cost_by_stage.get(d, {}).items()},
                "input_tokens": daily_tokens.get(d, {}).get("input", 0),
                "output_tokens": daily_tokens.get(d, {}).get("output", 0),
            }
        )
    cost_total = round(running_total, 4)

    # ── Latency aggregation ──────────────────────────────────────────────
    latencies: list[int] = []
    daily_latency: dict[str, list[int]] = {}
    stage_latencies: dict[str, list[int]] = {}

    for t in recent:
        lat = t.get("latency_ms") or 0
        if lat > 0:
            latencies.append(lat)
            day = _day_key(t.get("timestamp"))
            daily_latency.setdefault(day, []).append(lat)

            stage = _stage_from_name(t.get("name", ""))
            if stage:
                stage_latencies.setdefault(stage, []).append(lat)

    p50, p90, p99 = _percentiles(latencies)
    avg_lat = int(sum(latencies) / len(latencies)) if latencies else 0

    bottleneck = ""
    if stage_latencies:
        bottleneck = max(
            stage_latencies, key=lambda s: sum(stage_latencies[s]) / len(stage_latencies[s])
        )

    latency_daily = []
    for d in sorted(daily_latency):
        vals = daily_latency[d]
        dp50, dp90, dp99 = _percentiles(vals)
        latency_daily.append(
            {
                "date": d,
                "avg_ms": int(sum(vals) / len(vals)),
                "p50": dp50,
                "p90": dp90,
                "p99": dp99,
                "by_stage": {
                    s: int(sum(v) / len(v))
                    for s, v in stage_latencies.items()
                    if any(
                        _day_key(t.get("timestamp")) == d
                        for t in recent
                        if _stage_from_name(t.get("name", "")) == s
                    )
                },
            }
        )

    # ── Quality aggregation ──────────────────────────────────────────────
    daily_quality: dict[str, dict[str, int]] = {}
    failure_cats: dict[str, int] = {}
    cost_quality_pairs: list[dict] = []  # For cost-vs-quality scatter

    for t in recent:
        day = _day_key(t.get("timestamp"))
        daily_quality.setdefault(
            day, {"total": 0, "success": 0, "failed": 0, "first_try": 0, "retry": 0}
        )
        daily_quality[day]["total"] += 1

        status = t.get("status", "")
        meta = t.get("metadata") or {}
        if status == "error":
            daily_quality[day]["failed"] += 1
            cat = meta.get("error_category", "unknown")
            failure_cats[cat] = failure_cats.get(cat, 0) + 1
        else:
            daily_quality[day]["success"] += 1

        # Track first-try vs retry (from reviewer metadata)
        first_try = meta.get("first_try")
        if first_try is True:
            daily_quality[day]["first_try"] += 1
        elif first_try is False:
            daily_quality[day]["retry"] += 1

        # Cost-vs-quality data point
        cost = t.get("total_cost") or 0.0
        if cost > 0:
            cost_quality_pairs.append(
                {
                    "cost": round(cost, 4),
                    "success": 1 if status != "error" else 0,
                    "session_id": t.get("session_id", ""),
                }
            )

    total_runs = sum(dq["total"] for dq in daily_quality.values())
    total_success = sum(dq["success"] for dq in daily_quality.values())
    total_first_try = sum(dq["first_try"] for dq in daily_quality.values())
    total_retry = sum(dq["retry"] for dq in daily_quality.values())
    overall_rate = round(total_success / total_runs, 3) if total_runs > 0 else 0.0

    quality_daily = []
    for d in sorted(daily_quality):
        dq = daily_quality[d]
        rate = round(dq["success"] / dq["total"], 3) if dq["total"] > 0 else 0.0
        quality_daily.append(
            {
                "date": d,
                "total": dq["total"],
                "success": dq["success"],
                "failed": dq["failed"],
                "rate": rate,
                "first_try": dq["first_try"],
                "retry": dq["retry"],
            }
        )

    # ── Build cost/latency trends (last 7 daily values) ──────────────────
    cost_trend = [e["total"] for e in cost_daily[-7:]]
    latency_trend = [e["avg_ms"] for e in latency_daily[-7:]]

    # ── AI insight (heuristic — real AI call deferred to API layer) ────────
    ai_insight = _generate_quality_insight(
        overall_rate,
        total_first_try,
        total_retry,
        total_runs,
        failure_cats,
        cost_quality_pairs,
    )

    return {
        "cost": {
            "daily": cost_daily,
            "total": cost_total,
            "by_model": {k: round(v, 4) for k, v in by_model.items()},
            "by_stage": {k: round(v, 4) for k, v in by_stage.items()},
            "models": sorted(by_model.keys()),
            "input_tokens": input_tokens_total,
            "output_tokens": output_tokens_total,
        },
        "latency": {
            "daily": latency_daily,
            "p50": p50,
            "p90": p90,
            "p99": p99,
            "avg_ms": avg_lat,
            "bottleneck": bottleneck,
            "by_stage": {s: int(sum(v) / len(v)) for s, v in stage_latencies.items()},
        },
        "quality": {
            "daily": quality_daily,
            "overall_rate": overall_rate,
            "failure_categories": failure_cats,
            "first_try_total": total_first_try,
            "retry_total": total_retry,
            "cost_quality": cost_quality_pairs[:100],
            "ai_insight": ai_insight,
        },
        "summary": {
            "cost_24h": round(cost_24h, 4),
            "cost_trend": cost_trend,
            "avg_latency_ms": avg_lat,
            "latency_trend": latency_trend,
            "p50": p50,
            "p90": p90,
            "input_tokens": input_tokens_total,
            "output_tokens": output_tokens_total,
        },
    }


def _empty_metrics() -> dict:
    """Return zero-valued metrics structure."""
    return {
        "cost": {
            "daily": [],
            "total": 0.0,
            "by_model": {},
            "by_stage": {},
            "models": [],
            "input_tokens": 0,
            "output_tokens": 0,
        },
        "latency": {
            "daily": [],
            "p50": 0,
            "p90": 0,
            "p99": 0,
            "avg_ms": 0,
            "bottleneck": "",
            "by_stage": {},
        },
        "quality": {
            "daily": [],
            "overall_rate": 0.0,
            "failure_categories": {},
            "first_try_total": 0,
            "retry_total": 0,
            "cost_quality": [],
            "ai_insight": "",
        },
        "summary": {
            "cost_24h": 0.0,
            "cost_trend": [],
            "avg_latency_ms": 0,
            "latency_trend": [],
            "p50": 0,
            "p90": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        },
    }


def _generate_quality_insight(
    overall_rate: float,
    first_try: int,
    retry: int,
    total: int,
    failure_cats: dict[str, int],
    cost_quality: list[dict],
) -> str:
    """Generate a heuristic AI insight about quality trends."""
    if total == 0:
        return ""

    parts = []

    # First-try rate insight
    if first_try + retry > 0:
        ft_rate = first_try / (first_try + retry)
        if ft_rate >= 0.8:
            parts.append(f"Strong first-try success rate ({ft_rate:.0%}) — plans are well-formed.")
        elif ft_rate >= 0.5:
            parts.append(
                f"First-try rate is {ft_rate:.0%}. Consider adding clearer success criteria to goals."
            )
        else:
            parts.append(f"Low first-try rate ({ft_rate:.0%}) — plans frequently need revision.")

    # Failure pattern insight
    if failure_cats:
        top_cat = max(failure_cats, key=lambda category: failure_cats[category])
        top_count = failure_cats[top_cat]
        if top_count >= 3:
            parts.append(f"Most common failure: '{top_cat}' ({top_count} occurrences).")

    # Cost-quality correlation
    if len(cost_quality) >= 5:
        successes = [p["cost"] for p in cost_quality if p["success"]]
        failures = [p["cost"] for p in cost_quality if not p["success"]]
        if successes and failures:
            avg_s = sum(successes) / len(successes)
            avg_f = sum(failures) / len(failures)
            if avg_f > avg_s * 1.5:
                parts.append(
                    "Failed runs cost significantly more than successful ones — early failure detection could save budget."
                )
            elif avg_s > avg_f * 1.5:
                parts.append(
                    "Higher-cost runs tend to succeed — the extra tokens may be paying for thoroughness."
                )

    return " ".join(parts) if parts else "Insufficient data for insights."


# ── Helpers ──────────────────────────────────────────────────────────────────


def _now():
    from datetime import datetime

    return datetime.now(UTC)


def _parse_ts(ts: Any) -> Any:
    """Parse a timestamp to datetime. Handles str and datetime."""
    from datetime import datetime

    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    if isinstance(ts, str):
        # ISO 8601 with or without Z
        ts_clean = ts.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(ts_clean)
        except ValueError:
            return datetime.min.replace(tzinfo=UTC)
    return datetime.min.replace(tzinfo=UTC)


def _day_key(ts: Any) -> str:
    """Extract YYYY-MM-DD from a timestamp."""
    dt = _parse_ts(ts)
    return dt.strftime("%Y-%m-%d")


def _stage_from_name(name: str) -> str:
    """Extract pipeline stage from trace name like 'justai-planner'."""
    if not name:
        return ""
    clean = name.replace("justai-", "")
    return clean if clean in PIPELINE_STAGES else ""


def _calc_latency_ms(trace: Any) -> int:
    """Calculate trace latency in milliseconds from start/end times."""
    try:
        # LangFuse traces have latency as a direct attribute in newer SDKs
        lat = getattr(trace, "latency", None)
        if lat is not None:
            return int(lat * 1000) if lat < 1000 else int(lat)
        # Fallback: look in observations
        obs = getattr(trace, "observations", []) or []
        for o in obs:
            s = getattr(o, "start_time", None)
            e = getattr(o, "end_time", None)
            if s and e:
                return int((e - s).total_seconds() * 1000)
    except Exception:
        pass
    return 0


def _sum_cost(trace: Any) -> float:
    """Sum total cost from trace observations."""
    try:
        # Direct attribute
        cost = getattr(trace, "total_cost", None)
        if cost is not None:
            return float(cost)
        # Sum from observations
        obs = getattr(trace, "observations", []) or []
        total = 0.0
        for o in obs:
            c = getattr(o, "total_cost", None) or 0.0
            total += float(c)
        return total
    except Exception:
        return 0.0


def _sum_tokens(trace: Any, direction: str) -> int:
    """Sum input or output tokens from trace observations."""
    try:
        obs = getattr(trace, "observations", []) or []
        total = 0
        for o in obs:
            usage = getattr(o, "usage", None)
            if usage:
                if direction == "input":
                    total += getattr(usage, "input", 0) or 0
                else:
                    total += getattr(usage, "output", 0) or 0
        return total
    except Exception:
        return 0


def _trace_status(trace: Any) -> str:
    """Determine trace status from observations."""
    try:
        obs = getattr(trace, "observations", []) or []
        for o in obs:
            level = getattr(o, "level", "")
            if level == "ERROR":
                return "error"
        return "ok"
    except Exception:
        return "unknown"


def _percentiles(values: list[int]) -> tuple[int, int, int]:
    """Compute p50, p90, p99 from a list of integers."""
    if not values:
        return (0, 0, 0)
    s = sorted(values)
    n = len(s)
    p50 = s[int(n * 0.5)] if n > 0 else 0
    p90 = s[min(int(n * 0.9), n - 1)]
    p99 = s[min(int(n * 0.99), n - 1)]
    return (p50, p90, p99)
