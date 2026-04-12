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
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator, Optional

# ── Conditional Import ───────────────────────────────────────────────────────

_langfuse = None
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
        usage: Optional[dict] = None,
        metadata: Optional[dict] = None,
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
        try:
            self._generation.end(**kwargs)
        except Exception:
            pass

    def error(self, message: str) -> None:
        self.end(output_text=message, level="ERROR")


@contextmanager
def trace_generation(
    name: str,
    model: str = "",
    input_text: str = "",
    metadata: Optional[dict] = None,
    session_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
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
    metadata: Optional[dict] = None,
    session_id: Optional[str] = None,
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
        try:
            _langfuse.flush()
        except Exception:
            pass


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
