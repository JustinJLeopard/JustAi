"""
JustAi — Mini-First Workflow
==============================
Maximizes mini-swe-agent utilization by front-loading cheap agents:

  1. PSEUDOCODE — Capable model (codex) generates pseudocode from spec
  2. WRITE_TESTS — Mini writes tests per function (with IDs)
  3. WRITE_CODE — Mini writes code to pass tests
  4. ITERATE — Mini runs tests → fixes failures → runs tests (up to N iterations)
  5. ESCALATE — If mini is stuck after N iterations, a capable model takes over

This tests whether front-loading cheap agents increases speed, quality,
and success rate compared to the standard single-agent pipeline.

Usage:
    from justai.mini_first import MiniFirstPipeline, MiniFirstConfig
    cfg = MiniFirstConfig(max_mini_iterations=3)
    pipeline = MiniFirstPipeline(cfg)
    result = pipeline.run("implement feature X", spec="detailed spec...")
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable
from justai.planner import Task
from justai.delegator import delegate, DelegationResult
from justai.executor import execute_plan as _execute_plan_all
from justai.swarm_delegator import SwarmDelegator

PHASES = ["pseudocode", "write_tests", "write_code", "iterate", "escalate"]

LITELLM_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000/v1")
MINI_MODEL = os.environ.get("JUSTAI_MINI_MODEL", "gpt-5.3-codex")
ESCALATION_MODEL = os.environ.get("JUSTAI_ESCALATION_MODEL", "claude-opus-4-6")


@dataclass
class MiniFirstConfig:
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


def _llm_call(model: str, prompt: str, system: str = "") -> str:
    """Call LLM via LiteLLM proxy. Returns response text."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 4096,
    }).encode()

    req = urllib.request.Request(
        f"{LITELLM_URL}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def _run_tests(test_cmd: str, work_dir: str = "") -> tuple[bool, str]:
    """Run test command and return (passed, output)."""
    try:
        result = subprocess.run(
            ["bash", "-c", test_cmd],
            capture_output=True, text=True,
            cwd=work_dir or None,
            timeout=60,
        )
        output = result.stdout[-500:] + result.stderr[-500:]
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "test command timed out"
    except Exception as e:
        return False, str(e)[:200]


class MiniFirstPipeline:
    """Run the mini-first escalation workflow."""

    def __init__(self, config: MiniFirstConfig | None = None):
        self.config = config or MiniFirstConfig()
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
        output = _llm_call(self.config.pseudocode_model, prompt,
                           system="You are a code architect. Output pseudocode only.")
        self._model_calls += 1
        self._mini_calls += 1
        return PhaseResult(
            phase="pseudocode", status="done", output=output,
            model=self.config.pseudocode_model, duration_seconds=time.time() - start,
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
        output = self._call_mini(prompt, system="You write Python pytest tests. Output test code only.")
        return PhaseResult(
            phase="write_tests", status="done", output=output,
            model=self.config.mini_model, duration_seconds=time.time() - start,
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
        output = self._call_mini(prompt, system="You write Python code. Output implementation only.")
        return PhaseResult(
            phase="write_code", status="done", output=output,
            model=self.config.mini_model, duration_seconds=time.time() - start,
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
        output = self._call_mini(prompt, system="You fix Python code to pass tests. Output fixed code only.")
        return PhaseResult(
            phase="iterate", status="done", output=output,
            model=self.config.mini_model, duration_seconds=time.time() - start,
        )

    def _phase_escalate(self, goal: str, spec: str, code: str, tests: str, test_output: str) -> PhaseResult:
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
            phase="escalate", status="done", output=output,
            model=self.config.escalation_model, duration_seconds=time.time() - start,
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
                phases.append(PhaseResult(
                    phase="iterate", status="done",
                    output=f"Tests pass on iteration {iteration}",
                    iterations=iteration,
                ))
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
# Wraps existing delegators with try-cheap-then-escalate logic.
# The MiniFirstPipeline above is preserved as a standalone LLM pipeline utility.


def escalate_task(
    task: Task,
    session_ref: str,
    executor: Callable[..., DelegationResult],
) -> DelegationResult:
    """Execute a task with cheap model first, escalate on failure.

    Args:
        task: The task to execute.
        session_ref: Session identifier for tracing.
        executor: A callable(task, session_ref) -> DelegationResult.
                  One of: delegator.delegate, executor single-task wrapper, swarm dispatch.

    Returns:
        DelegationResult — from first attempt if successful, from escalation otherwise.
    """
    original_model = os.environ.get("JUSTAI_ACTIVE_MODEL", "")

    # First attempt: cheap model
    try:
        os.environ["JUSTAI_ACTIVE_MODEL"] = MINI_MODEL
        result = executor(task, session_ref=session_ref)
    finally:
        os.environ["JUSTAI_ACTIVE_MODEL"] = original_model

    if result.status == "done":
        return result

    # Escalate: expensive model with failure context
    print(f"[escalation] task '{task.title}' failed on {MINI_MODEL}, escalating to {ESCALATION_MODEL}")
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
        escalation_result = executor(escalated_task, session_ref=session_ref)
    finally:
        os.environ["JUSTAI_ACTIVE_MODEL"] = original_model

    return escalation_result


def _execute_single_local(task: Task, session_ref: str = "") -> DelegationResult:
    """Adapter: run a single task through the local executor and return DelegationResult."""
    results = _execute_plan_all([task])
    if not results:
        return DelegationResult(
            task_id="local-err", title=task.title,
            status="error", result="Local executor returned no results",
            duration_seconds=0.0,
        )
    er = results[0]
    return DelegationResult(
        task_id=er.task_id, title=er.title,
        status=er.status, result=er.result,
        duration_seconds=er.duration_seconds,
    )


def _execute_single_swarm(task: Task, session_ref: str = "") -> DelegationResult:
    """Adapter: run a single task through swarm dispatch and return DelegationResult."""
    sd = SwarmDelegator(max_agents=1)
    sd.spawn_agents(1)
    swarm_results = sd.dispatch_parallel([task], session_ref=session_ref)
    sd.shutdown()
    if not swarm_results:
        return DelegationResult(
            task_id="swarm-err", title=task.title,
            status="error", result="Swarm returned no results",
            duration_seconds=0.0,
        )
    sr = swarm_results[0]
    return DelegationResult(
        task_id=sr.task_id, title=sr.title,
        status=sr.status, result=sr.result,
        duration_seconds=sr.duration_seconds,
    )


_EXECUTORS = {
    "delegated": delegate,
    "local": _execute_single_local,
    "swarm": _execute_single_swarm,
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
    executor = _EXECUTORS.get(mode, delegate)
    results: list[DelegationResult | None] = [None] * len(tasks)

    for i, task in enumerate(tasks):
        # Check dependencies
        skip = False
        for dep_idx in task.depends_on:
            if dep_idx < len(results) and results[dep_idx] and results[dep_idx].status != "done":
                print(f"[escalation] skipping task [{i}] '{task.title}' — dependency [{dep_idx}] failed")
                results[i] = DelegationResult(
                    task_id="skipped", title=task.title,
                    status="skipped",
                    result=f"Skipped — dependency [{dep_idx}] did not complete after escalation",
                    duration_seconds=0,
                )
                skip = True
                break

        if not skip:
            results[i] = escalate_task(task, session_ref=session_ref, executor=executor)
            status = results[i].status
            print(f"[escalation] task [{i}] {status}: {results[i].result[:80]}")

    return [r for r in results if r is not None]
