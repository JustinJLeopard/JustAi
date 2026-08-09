"""
JustAi - Agent Dispatch (current concrete impl)
===============================================
Today this module IS the dispatch implementation: it calls escalate_plan/
escalate_task with the existing mini-swe-agent flow.

POST-SAFE-MINI MIGRATION: this module's role narrows to "JustAi's
specific configuration + adaptation layer" between JustAi's Plan/Task
types and safe-mini's Chunk/Budget. The actual run loop will move to
safe-mini's SafeMiniRunner. See justai/runner_protocol.py for the
forward-looking dispatch contract.

Current workflow routes task execution through a small-model-first dispatch
ladder:

  1. PSEUDOCODE — Capable model (codex) generates pseudocode from spec
  2. WRITE_TESTS — Mini writes tests per function (with IDs)
  3. WRITE_CODE — Mini writes code to pass tests
  4. ITERATE — Mini runs tests → fixes failures → runs tests (up to N iterations)
  5. ESCALATE — If mini is stuck after N iterations, a capable model takes over

This tests whether front-loading lower-cost agents increases speed, quality,
and success rate compared to the standard single-agent pipeline.

Usage:
    from justai.agent_dispatch import AgentDispatchPipeline, AgentDispatchConfig
    cfg = AgentDispatchConfig(max_mini_iterations=3)
    pipeline = AgentDispatchPipeline(cfg)
    result = pipeline.run("implement feature X", spec="detailed spec...")
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from justai.results import DelegationResult
from justai.runner_protocol import (
    AgentRunner,  # noqa: F401  # stub; full integration post-safe-mini
)
from justai.scope_planner import Task

PHASES = ["pseudocode", "write_tests", "write_code", "iterate", "escalate"]

LITELLM_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000/v1")
MINI_MODEL = os.environ.get("JUSTAI_MINI_MODEL", "gpt-5.3-codex")
ESCALATION_MODEL = os.environ.get("JUSTAI_ESCALATION_MODEL", "claude-opus-4-6")


@dataclass
class AgentDispatchConfig:
    max_mini_iterations: int = 3
    mini_model: str = "gpt-5.3-codex"
    escalation_model: str = "claude-opus-4-6"
    pseudocode_model: str = "gpt-5.3-codex"
    test_command: str = "python3 -m pytest tests/ -v --tb=short"
    work_dir: str = ""


@dataclass
class PhaseResult:
    phase: str
    status: str  # "done" | "failed" | "skipped"
    output: str
    iterations: int = 1
    model: str = ""
    duration_seconds: float = 0.0


@dataclass
class PipelineResult:
    goal: str
    spec: str
    phases: list[PhaseResult]
    escalated: bool
    total_iterations: int
    model_calls: int
    mini_calls: int
    escalation_calls: int
    duration_seconds: float
    final_output: str = ""


def _executor_base_url() -> str | None:
    """Executor endpoint override — default-OFF.

    When JUSTAI_EXECUTOR_BASE_URL is set, mini/executor calls route here so a
    dedicated coder (e.g. a local Qwen3-Coder-Next server) can run the executor
    while planner/reviewer/pseudocode/escalation stay on LITELLM_BASE_URL.
    Unset/empty -> None -> primary endpoint (byte-for-byte equivalent).
    Endpoint is selected by call site, never inferred from model text.
    """
    url = os.environ.get("JUSTAI_EXECUTOR_BASE_URL", "").strip().rstrip("/").removesuffix("/v1")
    return url or None


def _llm_call(model: str, prompt: str, system: str = "", base_url: str | None = None) -> str:
    """Call LLM via the OpenAI-compatible endpoint. Returns response text.

    base_url overrides the endpoint for this call only (executor routing);
    None uses the primary LITELLM_URL.
    """
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

    headers = {"Content-Type": "application/json"}
    _key = os.environ.get("JUSTAI_LLM_KEY") or os.environ.get("LITELLM_KEY", "")
    if _key:
        headers["Authorization"] = f"Bearer {_key}"
    req = urllib.request.Request(
        f"{base_url or LITELLM_URL}/chat/completions",
        data=payload,
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def _run_tests(test_cmd: str, work_dir: str = "") -> tuple[bool, str]:
    """Run test command and return (passed, output)."""
    try:
        result = subprocess.run(
            ["bash", "-c", test_cmd],
            capture_output=True,
            text=True,
            cwd=work_dir or None,
            timeout=60,
        )
        output = result.stdout[-500:] + result.stderr[-500:]
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "test command timed out"
    except Exception as e:
        return False, str(e)[:200]


class AgentDispatchPipeline:
    """Run the small-model-first agent dispatch workflow."""

    def __init__(self, config: AgentDispatchConfig | None = None):
        self.config = config or AgentDispatchConfig()
        self._model_calls = 0
        self._mini_calls = 0
        self._escalation_calls = 0

    def _call_mini(self, prompt: str, system: str = "") -> str:
        self._model_calls += 1
        self._mini_calls += 1
        return _llm_call(self.config.mini_model, prompt, system, base_url=_executor_base_url())

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

    def _phase_iterate(self, code: str, tests: str, test_output: str) -> PhaseResult:
        """Phase 4: Mini fixes failures."""
        start = time.time()
        prompt = (
            f"The following tests are failing. Fix the code.\n\n"
            f"Code:\n{code}\n\nTests:\n{tests}\n\n"
            f"Test output:\n{test_output}\n\n"
            f"Output the fixed code only."
        )
        output = self._call_mini(
            prompt, system="You fix Python code to pass tests. Output fixed code only."
        )
        return PhaseResult(
            phase="iterate",
            status="done",
            output=output,
            model=self.config.mini_model,
            duration_seconds=time.time() - start,
        )

    def _phase_escalate(
        self, goal: str, spec: str, code: str, tests: str, test_output: str
    ) -> PhaseResult:
        """Phase 5: Capable model takes over."""
        start = time.time()
        prompt = (
            f"A junior agent attempted this task but couldn't get tests passing.\n\n"
            f"Goal: {goal}\nSpec:\n{spec}\n\n"
            f"Their code:\n{code}\n\nTests:\n{tests}\n\n"
            f"Last test output:\n{test_output}\n\n"
            f"Fix the code completely. Output the corrected implementation."
        )
        output = self._call_escalation(
            prompt, system="You are a senior engineer fixing code that a junior couldn't get right."
        )
        return PhaseResult(
            phase="escalate",
            status="done",
            output=output,
            model=self.config.escalation_model,
            duration_seconds=time.time() - start,
        )

    def run(self, goal: str, spec: str) -> PipelineResult:
        """Execute the full mini-first pipeline."""
        start = time.time()
        phases: list[PhaseResult] = []

        # Phase 1: Pseudocode
        pseudo_result = self._phase_pseudocode(goal, spec)
        phases.append(pseudo_result)
        pseudocode = pseudo_result.output

        # Phase 2: Write tests
        test_result = self._phase_write_tests(pseudocode, spec)
        phases.append(test_result)
        tests = test_result.output

        # Phase 3: Write code
        code_result = self._phase_write_code(pseudocode, tests)
        phases.append(code_result)
        code = code_result.output

        # Phase 4: Iterate — run tests, fix, repeat
        iteration = 0
        escalated = False
        test_output = ""

        for iteration in range(1, self.config.max_mini_iterations + 1):
            passed, test_output = _run_tests(self.config.test_command, self.config.work_dir)

            if passed:
                phases.append(
                    PhaseResult(
                        phase="iterate",
                        status="done",
                        output=f"Tests pass on iteration {iteration}",
                        iterations=iteration,
                    )
                )
                break

            # Mini attempts fix
            fix_result = self._phase_iterate(code, tests, test_output)
            phases.append(fix_result)
            code = fix_result.output
        else:
            # Mini exhausted iterations — escalate
            escalated = True
            esc_result = self._phase_escalate(goal, spec, code, tests, test_output)
            phases.append(esc_result)
            code = esc_result.output

        return PipelineResult(
            goal=goal,
            spec=spec,
            phases=phases,
            escalated=escalated,
            total_iterations=iteration,
            model_calls=self._model_calls,
            mini_calls=self._mini_calls,
            escalation_calls=self._escalation_calls,
            duration_seconds=time.time() - start,
            final_output=code,
        )


# ── Escalation Strategy ──────────────────────────────────────────────────────
# Wraps task runners with try-cheap-then-escalate logic.
# The AgentDispatchPipeline above is preserved as a standalone LLM pipeline utility.


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


def _verify_task(task: Task) -> tuple[bool, str]:
    """Run the task's success criteria and return (passed, output)."""
    criteria = task.success_criteria
    if not criteria or criteria.strip() in (
        "echo 'verify manually'",
        "echo 'task completed -- verify manually'",
    ):
        return None, "no automated verification (task not confirmed done)"

    try:
        result = subprocess.run(
            ["bash", "-o", "pipefail", "-c", criteria],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, result.stdout[:500]
        return False, f"exit {result.returncode}: {result.stderr[:300]}"
    except subprocess.TimeoutExpired:
        return False, "verification command timed out"
    except Exception as exc:
        return False, str(exc)[:200]


LOCAL_EXEC_TIMEOUT = int(os.environ.get("JUSTAI_LOCAL_EXEC_TIMEOUT", "60"))

_ACTION_SYSTEM = (
    "You execute ONE JustAi task on a Linux bash shell. Respond with JSON only, "
    "no prose and no markdown fences. Use one of these shapes (real JSON uses "
    "double quotes): {'command': '<one bash command; && and pipes allowed>'} "
    "or {'skip_reason': '<why no shell command should run>'} when the task needs "
    "no shell action or would be unsafe. The command runs under bash -o pipefail."
)

# A floor, not a sandbox: refuse a few unambiguously catastrophic commands so a
# bad model action cannot wipe the machine. Real isolation belongs in safe-mini.
_CATASTROPHIC_TARGETS = {
    "/", "/*", "~", "$home", "/etc", "/bin", "/sbin", "/usr", "/var", "/boot",
    "/lib", "/lib64", "/home", "/root", "/sys", "/proc", "/dev",
}


def _is_catastrophic(command: str) -> bool:
    low = " ".join(command.lower().split())
    if ":(){:|:&};:" in low.replace(" ", ""):
        return True
    hard = ("mkfs", " of=/dev/sd", "> /dev/sd", "reboot", "poweroff", "halt")
    if any(h in low for h in hard):
        return True
    toks = low.split()
    if toks and toks[0] == "sudo":
        toks = toks[1:]
    if toks and toks[0] in ("shutdown",):
        return True
    if toks and toks[0] == "rm":
        flags = "".join(t.replace("-", "") for t in toks[1:] if t.startswith("-"))
        args = [t for t in toks[1:] if not t.startswith("-")]
        if "r" in flags and "f" in flags:
            for arg in args:
                if arg in _CATASTROPHIC_TARGETS or arg.rstrip("/") in _CATASTROPHIC_TARGETS:
                    return True
    if "chmod" in toks and "000" in toks and any(t in ("-r", "-rf", "-fr") for t in toks):
        if any(arg in _CATASTROPHIC_TARGETS for arg in toks):
            return True
    return False


def _parse_action(raw: str) -> dict:
    """Extract the action dict from a model response, tolerating fences/prose."""
    text = (raw or "").strip()
    if "```" in text:
        parts = text.split("```")
        for block in parts[1:len(parts):2]:
            stripped = block.lstrip()
            low = stripped.lower()
            if low.startswith("json"):
                stripped = stripped[4:]
            elif low.startswith(("bash", "sh", "shell")):
                newline = stripped.find(chr(10))
                return {"command": stripped[newline + 1:].strip() if newline != -1 else ""}
            try:
                obj = json.loads(stripped.strip())
                if isinstance(obj, dict):
                    return obj
            except Exception:
                continue
    try:
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    if text and chr(10) not in text and len(text) < 400:
        return {"command": text}
    return {"skip_reason": "unparseable model action"}


def _run_local_command(command: str, timeout: int = LOCAL_EXEC_TIMEOUT) -> tuple[bool, str]:
    """Run one bash command with a timeout; return (ok, receipts)."""
    try:
        result = subprocess.run(
            ["bash", "-o", "pipefail", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (result.stdout[-800:] + result.stderr[-400:]).strip()
        return result.returncode == 0, out or f"(exit {result.returncode})"
    except subprocess.TimeoutExpired:
        return False, "execution timed out"
    except Exception as exc:
        return False, str(exc)[:200]


def _perform_task_action(task: Task) -> tuple[str, str]:
    """Execute the task via the active model's shell action.

    Returns (outcome, detail); outcome is one of
    executed | no_backend | refused | blocked | error.
    """
    model = os.environ.get("JUSTAI_ACTIVE_MODEL") or MINI_MODEL
    prompt = (
        "Task: " + task.title + chr(10) + chr(10) + task.description
        + chr(10) + chr(10) + "Produce the shell command."
    )
    try:
        raw = _llm_call(model, prompt, system=_ACTION_SYSTEM, base_url=_executor_base_url())
    except Exception as exc:
        return "no_backend", f"execution model unavailable: {str(exc)[:160]}"
    action = _parse_action(raw)
    if action.get("skip_reason"):
        return "refused", str(action["skip_reason"])[:200]
    command = str(action.get("command", "")).strip()
    if not command:
        return "error", "model returned no command"
    if _is_catastrophic(command):
        return "blocked", f"refused catastrophic command: {command[:120]}"
    ok, out = _run_local_command(command)
    return ("executed" if ok else "error"), "$ " + command[:160] + chr(10) + out[:400]


def _execute_single_local(task: Task, session_ref: str = "") -> DelegationResult:
    """Execute a task's action locally (model-driven), then verify it.

    Honest 3-state: a task is ``done`` only when it BOTH executed and its
    success check passed. Execution without an automated check is
    ``unverified``; anything else (no backend, refusal, blocked command,
    non-zero exit, or a failed check) is ``failed`` -- never a silent success.
    """
    start = time.time()
    outcome, exec_detail = _perform_task_action(task)
    executed = outcome == "executed"
    passed, verify_output = _verify_task(task)

    if executed and passed is True:
        status = "done"
        detail = verify_output[:200]
    elif executed and passed is None:
        status = "unverified"
        detail = f"executed but no automated success check ran: {exec_detail[:150]}"
    elif executed and passed is False:
        status = "failed"
        detail = f"executed, but verify failed: {verify_output[:150]}"
    else:
        status = "failed"
        detail = f"not executed ({outcome}): {exec_detail[:170]}"

    return DelegationResult(
        task_id=f"local-{session_ref or 'task'}",
        title=task.title,
        status=status,
        result=detail,
        duration_seconds=time.time() - start,
    )


def _execute_removed_backend(task: Task, session_ref: str = "") -> DelegationResult:
    """Return an explicit error for backend modes removed in Phase 4 cleanup."""
    return DelegationResult(
        task_id=f"removed-{session_ref or 'task'}",
        title=task.title,
        status="error",
        result="External delegation backend was removed; use local mode.",
        duration_seconds=0.0,
    )


_EXECUTORS = {
    "delegated": _execute_removed_backend,
    "local": _execute_single_local,
    "swarm": _execute_removed_backend,
}


def escalate_plan(
    tasks: list[Task],
    session_ref: str = "",
    mode: str = "delegated",
) -> list[DelegationResult]:
    """Execute a task plan with per-task escalation.

    Each task tries cheap model first, escalates to expensive model on failure.
    Tasks run in dependency order; if a dependency fails (even after escalation),
    dependent tasks are skipped.

    Args:
        tasks: Ordered list of tasks from the planner.
        session_ref: Session identifier.
        mode: Execution mode — "delegated", "local", or "swarm".
    """
    runner = _EXECUTORS.get(mode, _execute_removed_backend)
    results: list[DelegationResult | None] = [None] * len(tasks)

    for i, task in enumerate(tasks):
        # Check dependencies
        skip = False
        for dep_idx in task.depends_on:
            dep_result = results[dep_idx] if dep_idx < len(results) else None
            if dep_result is not None and dep_result.status != "done":
                print(
                    f"[escalation] skipping task [{i}] '{task.title}' — dependency [{dep_idx}] failed"
                )
                results[i] = DelegationResult(
                    task_id="skipped",
                    title=task.title,
                    status="skipped",
                    result=f"Skipped — dependency [{dep_idx}] did not complete after escalation",
                    duration_seconds=0,
                )
                skip = True
                break

        if not skip:
            result = escalate_task(task, session_ref=session_ref, runner=runner)
            results[i] = result
            print(f"[escalation] task [{i}] {result.status}: {result.result[:80]}")

    return [r for r in results if r is not None]
