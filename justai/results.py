"""Shared result types for JustAi task execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DelegationResult:
    task_id: str
    title: str
    status: str
    result: str
    duration_seconds: float
