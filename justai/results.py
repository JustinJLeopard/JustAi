"""Shared result types for JustAi task execution."""

from __future__ import annotations

from dataclasses import dataclass

#: The one run status that means verified completion. Exit 0 and a "success"
#: learning record are reserved for this value alone (see justai.exit_codes).
RUN_COMPLETE = "complete"


@dataclass
class DelegationResult:
    task_id: str
    title: str
    status: str
    result: str
    duration_seconds: float
