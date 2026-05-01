"""
JustAi - Runner Protocol (stub)
================================
Dispatch contract between JustAi's orchestrator and the substrate that actually
runs bash-action coding agents.

STATUS: STUB. The canonical home for this Protocol and the types below is the
safe-mini repo (https://github.com/JustinJLeopard/safe-mini - now live). This file is a placeholder so JustAi's orchestrator can
declare its dispatch boundary today; consumers will migrate to
`from safe_mini import AgentRunner, Chunk, Budget, RunResult, FailureClass,
    ExecutorPolicy, ObservationPolicy`
once safe-mini is on PyPI (currently git-URL-pinnable from
https://github.com/JustinJLeopard/safe-mini).

Architectural source of truth:
- justai-architecture-decision-mini-swe-agent-control-plane (memory key)
- safe-mini-substrate-architecture (memory key)
- justai-two-repo-ship-pattern (memory key)

DO NOT ADD JustAi-specific fields to these types. They are intentionally
generic - the substrate doesn't know about session_ref, dashboards, Discord,
learning aggregation, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


# -- Failure taxonomy (7-class) ---------------------------------------------
# From safe-mini-substrate-architecture. Two NEW classes added 2026-04-29:
# safety-violation and action-protocol-violation.
class FailureClass(StrEnum):
    SAFETY_VIOLATION = "safety-violation"  # blocked-op attempt
    ACTION_PROTOCOL_VIOLATION = "action-protocol-violation"  # malformed bash
    EXHAUSTED_IDEAS = "exhausted-ideas"
    BUDGET_EXHAUSTED = "budget-exhausted"
    CONTEXT_STARVATION = "context-starvation"
    REWARD_HACKING = "reward-hacking"
    EMBODIMENT_FAILURE = "embodiment-failure"


# -- Policies ----------------------------------------------------------------
class ObservationPolicy(StrEnum):
    FULL = "full"
    TAIL = "tail"
    HEAD_TAIL = "head-tail"
    STRUCTURED = "structured"
    STRUCTURED_RAW_TAIL = "structured+raw-tail"


class ExecutorPolicy(StrEnum):
    OPEN = "open"  # bare shell, no guard
    SAFE = "safe"  # path guard + env scrub
    ALLOWLIST = "allowlist"  # explicit command allowlist


# -- Two-budget model --------------------------------------------------------
@dataclass
class Budget:
    """Two-budget contract: move budget AND observation budget.

    Empirical: lab proved tiny obs killed tasks even with infinite moves.
    Both budgets need explicit predictions per chunk.
    """

    move_budget: int  # max bash actions per chunk
    observation_budget: int  # max observation chars/tokens kept visible per action


# -- Work unit ---------------------------------------------------------------
@dataclass
class Chunk:
    """A unit of work fitted to mini-swe-agent's bash-move budget.

    Distinct from JustAi's Task: Task is orchestration-level (carries
    session_ref, depends_on); Chunk is substrate-level (just goal + success
    criteria + budget).
    """

    goal: str
    success_criteria: str  # bash command/grep that verifies completion
    budget: Budget

    def __post_init__(self) -> None:
        if not isinstance(self.goal, str):
            raise TypeError("Chunk.goal must be a string")
        if not isinstance(self.success_criteria, str):
            raise TypeError("Chunk.success_criteria must be a string")
        if not isinstance(self.budget, Budget):
            raise TypeError("Chunk.budget must be a Budget")


# -- Run result --------------------------------------------------------------
@dataclass
class RunResult:
    """Outcome of running a Chunk through the substrate.

    Distinct from JustAi's DelegationResult: RunResult is substrate-level
    (transcript, steps, classification); DelegationResult is orchestration-
    level (task_id, session linkage).
    """

    chunk: Chunk
    success: bool
    steps_used: int
    final_diff: str  # unified diff of repo changes (may be empty)
    transcript_path: str  # path to incident artifact
    failure_class: FailureClass | None = None
    cost_usd: float = 0.0
    tokens_used: int = 0
    latency_seconds: float = 0.0


# -- The dispatch contract ---------------------------------------------------
@runtime_checkable
class AgentRunner(Protocol):
    """The dispatch contract.

    Concrete implementations (SafeMiniRunner) live in safe-mini. JustAi's
    orchestrator calls .run() on whatever AgentRunner is configured.

    A FakeRunner for tests should satisfy this Protocol via duck typing.
    """

    def run(
        self,
        chunk: Chunk,
        observation_policy: ObservationPolicy = ObservationPolicy.STRUCTURED_RAW_TAIL,
        executor_policy: ExecutorPolicy = ExecutorPolicy.SAFE,
    ) -> RunResult:
        """Execute a chunk under the given policies.

        Returns a RunResult regardless of success/failure; failure mode is
        encoded in result.success + result.failure_class.
        """
        ...

    def classify_failure(self, result: RunResult) -> FailureClass:
        """Post-hoc classification of a failed run.

        Concrete runners may cache this on result.failure_class during run().
        """
        ...


# -- Migration markers -------------------------------------------------------
# TODO: when safe-mini repo is stood up:
#   1. Move this file's contents to safe_mini/runner_protocol.py
#   2. Replace this file with: `from safe_mini.runner_protocol import *`
#   3. Update justai's pyproject.toml to add safe-mini as a dependency
#      (Phase A: git-URL pin, Phase B: PyPI version pin per
#      justai-two-repo-ship-pattern memory key)
#   4. Update tests/test_runner_protocol.py to import from safe_mini directly
