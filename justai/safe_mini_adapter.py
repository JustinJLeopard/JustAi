"""Opt-in JustAi adapter for the public SafeMini runner contract.

This module is intentionally not wired into the default local executor. A
caller must supply the repository that SafeMini will copy into a fresh
worktree; source integration alone does not activate productive execution.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from safe_mini import (
    Budget,
    Chunk,
    ExecutorPolicy,
    Observation,
    ObservationPolicy,
    RunResult,
    SafeMiniRunner,
)
from safe_mini.policies import SafeExecutor

from justai.agent_dispatch import (
    LOCAL_EXEC_TIMEOUT,
    MINI_MODEL,
    _ACTION_SYSTEM,
    _execution_endpoint,
    _is_catastrophic,
    _llm_call,
    _parse_action,
)
from justai.sandbox import SandboxUnavailable, run_sandboxed
from justai.scope_planner import Task

_MOVE_BUDGET = 1
_OBSERVATION_BUDGET = 1200
_GUEST_ENV_ALLOWLIST = ("LANG", "LC_ALL", "LC_CTYPE", "TZ", "PYTHONPATH")


class JustAiActionModel:
    """Translate JustAi's JSON action response into SafeMini's JSON protocol."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or MINI_MODEL

    def next(self, transcript: list[dict]) -> str:
        prompt = str(transcript[-1].get("content", ""))
        try:
            raw = _llm_call(
                self.model,
                prompt,
                system=_ACTION_SYSTEM,
                base_url=_execution_endpoint(),
            )
        except Exception as exc:
            return json.dumps({"action": "unavailable", "detail": str(exc)[:160]})

        action = _parse_action(raw)
        command = action.get("command")
        if action.get("skip_reason") or not isinstance(command, str) or not command.strip():
            return json.dumps({"action": "invalid", "detail": str(action)[:200]})
        return json.dumps({"action": "bash", "command": command.strip()})


class JustAiBwrapExecutor:
    """Run SafeMini actions with JustAi's Bubblewrap boundary and guard stack."""

    def __init__(self, cwd: Path, policy: ExecutorPolicy) -> None:
        self.cwd = Path(cwd).resolve()
        self.policy = policy
        self.blocked_commands = 0
        self._safe_guard = SafeExecutor(self.cwd)

    def run(self, command: str) -> Observation:
        if self.policy is not ExecutorPolicy.SAFE:
            return self._blocked("JustAi SafeMini adapter only accepts the safe executor policy", command)
        if _is_catastrophic(command):
            return self._blocked("refused catastrophic command", command)
        if reason := self._safe_guard.blocked_reason(command):
            return self._blocked(reason, command)

        try:
            result = run_sandboxed(
                ["bash", "-o", "pipefail", "-c", command],
                str(self.cwd),
                timeout=LOCAL_EXEC_TIMEOUT,
                env_allowlist=_GUEST_ENV_ALLOWLIST,
                host_env=_guest_environment(self.cwd),
            )
        except SandboxUnavailable as exc:
            detail = f"sandbox unavailable, command not executed: {str(exc)[:200]}"
            return Observation(
                command=command,
                output=detail,
                returncode=125,
                stderr=detail,
                raw_output=detail,
            )

        raw = result.stdout + result.stderr
        return Observation(
            command=command,
            output=raw,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            raw_output=raw,
            timed_out=result.timed_out,
        )

    def _blocked(self, detail: str, command: str) -> Observation:
        self.blocked_commands += 1
        return Observation(
            command=command,
            output=detail,
            returncode=126,
            blocked=True,
            raw_output=detail,
        )


def _guest_environment(cwd: Path) -> dict[str, str]:
    """Pass only locale settings and the fresh worktree import root to Bubblewrap."""

    environment = {
        key: os.environ[key]
        for key in _GUEST_ENV_ALLOWLIST
        if key != "PYTHONPATH" and key in os.environ
    }
    environment["PYTHONPATH"] = str(cwd)
    return environment


def executor_factory(cwd: Path, policy: ExecutorPolicy) -> JustAiBwrapExecutor:
    """Construct the injected SafeMini executor over the runner's fresh worktree."""

    return JustAiBwrapExecutor(cwd, policy)


def chunk_from_task(task: Task) -> Chunk:
    """Map one JustAi orchestration task to SafeMini's public work-unit type."""

    label = task.session_ref + ":" + task.title if task.session_ref else task.title
    return Chunk(
        id=label,
        description=task.description,
        success_criteria=task.success_criteria,
        budget=Budget(
            move_budget=_MOVE_BUDGET,
            observation_budget=_OBSERVATION_BUDGET,
        ),
    )


def run_task(
    task: Task,
    *,
    repo_path: str | Path,
    model: JustAiActionModel | None = None,
    final_check_command: str | None = None,
) -> RunResult:
    """Run one task through SafeMini only when a caller explicitly opts in."""

    chunk = chunk_from_task(task)
    runner = SafeMiniRunner(
        model or JustAiActionModel(),
        repo_path=repo_path,
        final_check_command=final_check_command or task.success_criteria,
        executor_factory=executor_factory,
    )
    return runner.run(
        chunk,
        chunk.budget,
        ObservationPolicy.STRUCTURED_RAW_TAIL,
        ExecutorPolicy.SAFE,
    )
