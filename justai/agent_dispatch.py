"""
JustAi - Agent Dispatch (transitional control plane)
=====================================================
The CLI dispatch surface currently fails closed because neither the removed
delegated backend nor a safe local editing runner is wired. ``escalate_plan``
still preserves dependency ordering and result synthesis, but it must not
promote planner-authored verification commands into task completion.

POST-SAFE-MINI MIGRATION: this module's role narrows to "JustAi's
specific configuration + adaptation layer" between JustAi's Plan/Task
types and safe-mini's Chunk/Budget. The actual run loop will move to
safe-mini's SafeMiniRunner. See justai/runner_protocol.py for the
forward-looking dispatch contract.

The standalone ``AgentDispatchPipeline`` experiment below is QUARANTINED. It
models a small-model-first generation ladder — a capable model drafts
pseudocode, then a mini model writes tests and code from it:

  1. PSEUDOCODE — Capable model (codex) generates pseudocode from spec
  2. WRITE_TESTS — Mini writes tests per function (with IDs)
  3. WRITE_CODE — Mini writes code to pass tests

Every phase returns a *string*. The pipeline has no step that writes those
strings to a file, so no generated line of code has ever existed anywhere a
runtime could load it. It previously closed the ladder by shelling out to
``pytest`` in the current working directory and treating a green run as proof
that the generated code worked — but that run exercised the checkout it was
launched from, which the pipeline had not touched. A pass was guaranteed and
meaningless, and a repo with passing tests made any generated code look
correct.

That test-running loop is gone, and :meth:`AgentDispatchPipeline.run` now
refuses. Restoring it means adding the materialization step it never had:
write the generated files to an isolated worktree and run the tests there.
Until then this class is an inert record of the experiment's shape.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import NoReturn

from justai.results import DONE_STATUS, DelegationResult
from justai.runner_protocol import (
    AgentRunner,  # noqa: F401  # stub; full integration post-safe-mini
)
from justai.scope_planner import Task

PHASES = ["pseudocode", "write_tests", "write_code"]

LITELLM_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000/v1")
MINI_MODEL = os.environ.get("JUSTAI_MINI_MODEL", "gpt-5.3-codex")
ESCALATION_MODEL = os.environ.get("JUSTAI_ESCALATION_MODEL", "claude-opus-4-6")


@dataclass
class AgentDispatchConfig:
    max_mini_iterations: int = 3
    mini_model: str = "gpt-5.3-codex"
    escalation_model: str = "claude-opus-4-6"
    pseudocode_model: str = "gpt-5.3-codex"


@dataclass
class PhaseResult:
    phase: str
    status: str  # "done" | "failed" | "skipped"
    output: str
    iterations: int = 1
    model: str = ""
    duration_seconds: float = 0.0


def _llm_call(model: str, prompt: str, system: str = "") -> str:
    """Call LLM via LiteLLM proxy. Returns response text."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4096,
        }
    ).encode()

    req = urllib.request.Request(
        f"{LITELLM_URL}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


class AgentDispatchPipeline:
    """Quarantined small-model-first generation ladder — see the module docstring.

    The generation phases are preserved verbatim for whoever wires the missing
    materialization step. :meth:`run` refuses, because the ladder as a whole
    reported an outcome about code it never wrote.
    """

    def __init__(self, config: AgentDispatchConfig | None = None):
        self.config = config or AgentDispatchConfig()
        self._model_calls = 0
        self._mini_calls = 0
        self._escalation_calls = 0

    def _call_mini(self, prompt: str, system: str = "") -> str:
        self._model_calls += 1
        self._mini_calls += 1
        return _llm_call(self.config.mini_model, prompt, system)

    def _call_escalation(self, prompt: str, system: str = "") -> str:
        self._model_calls += 1
        self._escalation_calls += 1
        return _llm_call(self.config.escalation_model, prompt, system)

    def _phase_pseudocode(self, goal: str, spec: str) -> PhaseResult:
        """Phase 1: Generate pseudocode from spec using capable model."""
        start = time.time()
        prompt = (
            f"Generate pseudocode for the following goal and specification.\n\n"
            f"Goal: {goal}\n\nSpec:\n{spec}\n\n"
            f"Output clean pseudocode with function signatures, data structures, "
            f"and control flow. No implementation yet — just the skeleton."
        )
        output = _llm_call(
            self.config.pseudocode_model,
            prompt,
            system="You are a code architect. Output pseudocode only.",
        )
        self._model_calls += 1
        self._mini_calls += 1
        return PhaseResult(
            phase="pseudocode",
            status="done",
            output=output,
            model=self.config.pseudocode_model,
            duration_seconds=time.time() - start,
        )

    def _phase_write_tests(self, pseudocode: str, spec: str) -> PhaseResult:
        """Phase 2: Mini writes tests per function."""
        start = time.time()
        prompt = (
            f"Given this pseudocode and spec, write pytest tests for each function.\n\n"
            f"Pseudocode:\n{pseudocode}\n\nSpec:\n{spec}\n\n"
            f"Each test function should have a unique ID in its name. "
            f"Cover happy path and edge cases."
        )
        output = self._call_mini(
            prompt, system="You write Python pytest tests. Output test code only."
        )
        return PhaseResult(
            phase="write_tests",
            status="done",
            output=output,
            model=self.config.mini_model,
            duration_seconds=time.time() - start,
        )

    def _phase_write_code(self, pseudocode: str, tests: str) -> PhaseResult:
        """Phase 3: Mini writes code to pass tests."""
        start = time.time()
        prompt = (
            f"Given this pseudocode and these tests, write the implementation "
            f"code that passes all tests.\n\n"
            f"Pseudocode:\n{pseudocode}\n\nTests:\n{tests}\n\n"
            f"Output implementation code only."
        )
        output = self._call_mini(
            prompt, system="You write Python code. Output implementation only."
        )
        return PhaseResult(
            phase="write_code",
            status="done",
            output=output,
            model=self.config.mini_model,
            duration_seconds=time.time() - start,
        )

    def run(self, goal: str, spec: str) -> NoReturn:
        """Refuse to run: the ladder has no step that materializes its output.

        Raising here rather than at the end is deliberate. Generating three
        phases of code and *then* admitting none of it was written would spend
        real model calls to produce a result the caller cannot act on.

        Raises:
            NotImplementedError: always.
        """
        raise NotImplementedError(
            "AgentDispatchPipeline is quarantined: it holds generated code as "
            "strings and never materializes it to disk, so no test run can say "
            "anything about that code. Wire a materialization step — write the "
            "generated files into an isolated worktree and run the tests there "
            "— before restoring this ladder."
        )


# ── Escalation Strategy ──────────────────────────────────────────────────────
# Wraps task runners with try-cheap-then-escalate logic. This is the path the
# orchestrator actually uses; the quarantined pipeline above is not wired to it.


def escalate_task(
    task: Task,
    session_ref: str,
    runner: Callable[..., DelegationResult],
) -> DelegationResult:
    """Execute a task with cheap model first, escalate on failure.

    Args:
        task: The task to execute.
        session_ref: Session identifier for tracing.
        runner: A callable(task, session_ref) -> DelegationResult.

    Returns:
        DelegationResult — from first attempt if successful, from escalation otherwise.
    """
    if not _dispatches_to_model(runner):
        # No backend is wired. This runner reports unavailability without
        # invoking a model or touching the workspace, so there is no first
        # attempt that could have failed and nothing to escalate to. Answer
        # from a single call: a retry would repeat the same error while the
        # escalation notice would narrate model work that never happened.
        return runner(task, session_ref=session_ref)

    original_model = os.environ.get("JUSTAI_ACTIVE_MODEL", "")

    # First attempt: cheap model
    try:
        os.environ["JUSTAI_ACTIVE_MODEL"] = MINI_MODEL
        result = runner(task, session_ref=session_ref)
    finally:
        os.environ["JUSTAI_ACTIVE_MODEL"] = original_model

    if result.status == "done":
        return result

    # Escalate: expensive model with failure context
    print(
        f"[escalation] task '{task.title}' failed on {MINI_MODEL}, escalating to {ESCALATION_MODEL}"
    )
    escalated_task = Task(
        title=task.title,
        description=(
            f"{task.description}\n\n"
            f"NOTE: A previous attempt failed with: {result.result[:300]}\n"
            f"Take a different approach."
        ),
        agent=task.agent,
        risk=task.risk,
        success_criteria=task.success_criteria,
        depends_on=task.depends_on,
        session_ref=task.session_ref,
    )

    try:
        os.environ["JUSTAI_ACTIVE_MODEL"] = ESCALATION_MODEL
        escalation_result = runner(escalated_task, session_ref=session_ref)
    finally:
        os.environ["JUSTAI_ACTIVE_MODEL"] = original_model

    return escalation_result


def _execute_removed_backend(task: Task, session_ref: str = "") -> DelegationResult:
    """Return an explicit error for backend modes removed in Phase 4 cleanup."""
    return DelegationResult(
        task_id=f"removed-{session_ref or 'task'}",
        title=task.title,
        status="error",
        result="External delegation backend was removed; use `justai plan`.",
        duration_seconds=0.0,
    )


def _execute_local_unavailable(task: Task, session_ref: str = "") -> DelegationResult:
    """Fail closed until a real, acceptance-bound local executor is wired."""
    return DelegationResult(
        task_id=f"local-unavailable-{session_ref or 'task'}",
        title=task.title,
        status="error",
        result=(
            "Local execution backend is unavailable; use `justai plan` until "
            "safe-mini integration is installed and verified."
        ),
        duration_seconds=0.0,
    )


#: Runners that return an unavailable-backend result without invoking a model
#: or touching the workspace. ``escalate_task`` must not run its retry ladder
#: over these: the second call cannot behave differently, and the escalation
#: notice would claim model work that never happened. A concrete runner is
#: deliberately absent from this set so the ladder still applies to real work.
_NON_DISPATCHING_RUNNERS: frozenset[Callable[..., DelegationResult]] = frozenset(
    {_execute_removed_backend, _execute_local_unavailable}
)


def _dispatches_to_model(runner: Callable[..., DelegationResult]) -> bool:
    """Whether a runner invokes a model, and can therefore be meaningfully retried."""
    return runner not in _NON_DISPATCHING_RUNNERS


_EXECUTORS = {
    "delegated": _execute_removed_backend,
    "local": _execute_local_unavailable,
    "swarm": _execute_removed_backend,
}


def _invalid_dependency(position: int, task: Task) -> str | None:
    """Describe the first dependency that cannot name an already-decided task.

    ``depends_on`` holds positions in the plan, so a dependency is only
    meaningful if it points strictly backwards: ``0 <= dep < position``. Every
    other value — negative, past the end, its own position, or a later task —
    names something that has no outcome by the time this task would run.

    The planner fills ``depends_on`` from model-authored JSON, so the contents
    are not guaranteed to be integers, or even to be a list. Anything this
    function cannot resolve to a backward position is reported rather than
    coerced.

    Returns:
        A reason string, or None when every dependency resolves.
    """
    deps = task.depends_on
    if not isinstance(deps, list):
        return f"dependency list is {type(deps).__name__}, not a list of task positions"

    for dep in deps:
        # `type(dep) is int` on purpose: JSON `true` is a bool, and a bool
        # silently indexing task 0 or 1 is exactly the kind of accidental
        # resolution this check exists to refuse.
        if type(dep) is not int:
            return f"dependency {dep!r} is not a task position"
        if not 0 <= dep < position:
            return (
                f"dependency [{dep}] must name an earlier task "
                f"(0..{position - 1}) to have an outcome by now"
            )
    return None


def _normalize_blocked(
    blocked_indices: Mapping[int, str] | Iterable[int] | None,
    task_count: int,
) -> dict[int, str]:
    """Accept either ``{index: reason}`` or a bare collection of indices.

    Every index must name a task in ``tasks``. One that does not means the
    caller and this function disagree about which plan is being executed, and
    the disagreement is not safe to absorb: quietly dropping the stray index
    dispatches a task some checkpoint refused, which is the same false success
    :func:`escalate_plan` takes the whole plan to prevent. There is no reading
    of an out-of-plan index that is better than refusing it.

    Args:
        blocked_indices: Positions a checkpoint refused, optionally with reasons.
        task_count: How many tasks the plan holds.

    Raises:
        ValueError: an index is not an ``int``, or names no task in the plan.
    """
    if blocked_indices is None:
        return {}

    pairs = (
        blocked_indices.items()
        if isinstance(blocked_indices, Mapping)
        else ((index, "") for index in blocked_indices)
    )

    blocked: dict[int, str] = {}
    for index, reason in pairs:
        # `type(index) is int` on purpose, as in _invalid_dependency: True is a
        # bool, and letting it block task 1 is an accidental resolution, not a
        # decision anybody made.
        if type(index) is not int:
            raise ValueError(f"blocked index {index!r} is not a task position")
        if not 0 <= index < task_count:
            plan = f"0..{task_count - 1}" if task_count else "the plan has no tasks"
            raise ValueError(f"blocked index {index} names no task in this plan ({plan})")
        blocked[index] = reason
    return blocked


def escalate_plan(
    tasks: list[Task],
    session_ref: str = "",
    mode: str = "delegated",
    blocked_indices: Mapping[int, str] | Iterable[int] | None = None,
) -> list[DelegationResult]:
    """Execute a task plan with per-task escalation, one result per planned task.

    A model-dispatching task tries the cheap model first and escalates to the
    expensive model on failure. Unavailable-backend modes report once and are
    not escalated, since no model is invoked.

    Every task in ``tasks`` gets exactly one result at its own position, and
    positions never move. That is what makes ``depends_on`` mean anything: the
    caller must pass the whole plan and name the tasks a checkpoint blocked,
    rather than filtering them out. Handing over a compacted list used to
    renumber the survivors, so a task could inherit the outcome of whichever
    task landed on its dependency's old index and run on a dependency that
    never completed.

    Args:
        tasks: The full ordered plan. Do not pre-filter it.
        session_ref: Session identifier.
        mode: Execution mode — "delegated", "local", or "swarm".
        blocked_indices: Positions a checkpoint refused, optionally mapped to
            the reason. Blocked tasks are not dispatched and do not satisfy a
            dependency. Every index must name a task in ``tasks``.

    Raises:
        ValueError: a blocked index names no task in ``tasks``. Nothing is
            dispatched — the caller is describing a different plan.
    """
    runner = _EXECUTORS.get(mode, _execute_removed_backend)
    blocked = _normalize_blocked(blocked_indices, len(tasks))
    results: list[DelegationResult] = []

    for i, task in enumerate(tasks):
        results.append(_result_for(i, task, results, blocked, runner, session_ref))

    return results


def _result_for(
    position: int,
    task: Task,
    decided: list[DelegationResult],
    blocked: dict[int, str],
    runner: Callable[..., DelegationResult],
    session_ref: str,
) -> DelegationResult:
    """Decide one task's outcome. ``decided`` holds results for positions 0..position-1."""
    bad_dep = _invalid_dependency(position, task)
    if bad_dep is not None:
        # Fail closed. An unresolvable dependency is a defect in the plan, and
        # dispatching anyway would run a task whose precondition is unknown.
        print(f"[escalation] task [{position}] '{task.title}' — invalid dependency: {bad_dep}")
        return DelegationResult(
            task_id=f"invalid-dependency-{position}",
            title=task.title,
            status="error",
            result=(
                f"Invalid dependency: {bad_dep}. This task's precondition cannot "
                f"be checked, so it was not dispatched."
            ),
            duration_seconds=0.0,
        )

    if position in blocked:
        reason = blocked[position] or "blocked at the risk checkpoint"
        print(f"[escalation] task [{position}] blocked: {reason}")
        return DelegationResult(
            task_id=f"blocked-{position}",
            title=task.title,
            status="blocked",
            result=f"Not dispatched — {reason}",
            duration_seconds=0.0,
        )

    for dep in task.depends_on:
        if decided[dep].status != DONE_STATUS:
            print(
                f"[escalation] skipping task [{position}] '{task.title}' — "
                f"dependency [{dep}] did not complete"
            )
            return DelegationResult(
                task_id=f"skipped-{position}",
                title=task.title,
                status="skipped",
                result=f"Skipped — dependency [{dep}] did not complete",
                duration_seconds=0.0,
            )

    result = escalate_task(task, session_ref=session_ref, runner=runner)
    print(f"[escalation] task [{position}] {result.status}: {result.result[:80]}")
    return result
