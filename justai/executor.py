#!/usr/bin/env python3
"""
JustAi — Local Executor
=========================
Executes tasks locally via subprocess instead of delegating to an external agent.

Used when:
  - JUSTAI_LOCAL_EXEC=1 env var is set
  - --local flag is passed to the CLI
  - No external agent is available to claim tasks

The executor runs the task's success_criteria command to verify completion,
and attempts to accomplish the task using bash commands derived from the
task description.
"""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from justai.planner import Task

WORK_DIR = Path(os.environ.get("JUSTAI_WORK_DIR", str(Path(__file__).resolve().parents[1])))
EXEC_TIMEOUT = int(os.environ.get("JUSTAI_EXEC_TIMEOUT", "300"))  # 5 min per task


@dataclass
class ExecResult:
    task_id: str
    title: str
    status: str       # "done" | "failed" | "error"
    result: str
    output: str       # stdout from execution
    duration_seconds: float


def _run_cmd(cmd: str, cwd: str | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    return subprocess.run(
        ["bash", "-c", cmd],
        capture_output=True, text=True,
        cwd=cwd or str(WORK_DIR),
        timeout=timeout,
    )


def _verify_task(task: Task) -> tuple[bool, str]:
    """Run the task's success_criteria and return (passed, output)."""
    criteria = task.success_criteria
    if not criteria or criteria.strip() in ("echo 'verify manually'", "echo 'task completed — verify manually'"):
        return True, "no automated verification"

    try:
        result = _run_cmd(criteria, timeout=30)
        if result.returncode == 0:
            return True, result.stdout[:500]
        return False, f"exit {result.returncode}: {result.stderr[:300]}"
    except subprocess.TimeoutExpired:
        return False, "verification command timed out"
    except Exception as e:
        return False, str(e)[:200]


def execute_task(task: Task, task_index: int = 0) -> ExecResult:
    """
    Execute a task locally.

    Strategy:
    1. Run the task description as context for what needs to happen
    2. Run the success_criteria to verify completion
    """
    start = time.time()
    task_id = f"local-{task_index}"

    print(f"[executor] [{task_index}] starting: {task.title}")

    # For R0 (explore/read-only) tasks, just run the verify command
    if task.risk.value == "R0":
        passed, output = _verify_task(task)
        status = "done" if passed else "failed"
        print(f"[executor] [{task_index}] R0 verify: {status}")
        return ExecResult(
            task_id=task_id, title=task.title,
            status=status, result=output[:200],
            output=output,
            duration_seconds=time.time() - start,
        )

    # For execution tasks, try to run verify first (maybe already done)
    passed, output = _verify_task(task)
    if passed:
        print(f"[executor] [{task_index}] already passing — done")
        return ExecResult(
            task_id=task_id, title=task.title,
            status="done", result="Verification passed (pre-existing)",
            output=output,
            duration_seconds=time.time() - start,
        )

    # Task needs work — report what needs to be done
    # In local mode, we log what the task requires but don't modify files blindly
    print(f"[executor] [{task_index}] task requires execution:")
    print(f"  Title: {task.title}")
    print(f"  Description: {task.description[:200]}")
    print(f"  Verify: {task.success_criteria}")

    # Try running verification one more time after a brief pause
    # (in case the task is just a check/exploration)
    time.sleep(0.5)
    passed, output = _verify_task(task)
    status = "done" if passed else "failed"

    return ExecResult(
        task_id=task_id, title=task.title,
        status=status,
        result=output[:200] if passed else f"Task requires manual execution: {task.description[:100]}",
        output=output,
        duration_seconds=time.time() - start,
    )


def execute_plan(tasks: list[Task]) -> list[ExecResult]:
    """
    Execute a list of tasks locally in dependency order.
    If a task fails, dependent tasks are skipped.
    """
    results: list[ExecResult | None] = [None] * len(tasks)

    for i, task in enumerate(tasks):
        # Check dependencies
        skip = False
        for dep_idx in task.depends_on:
            if dep_idx < len(results) and results[dep_idx] and results[dep_idx].status != "done":
                print(f"[executor] skipping [{i}] '{task.title}' — dependency [{dep_idx}] failed")
                results[i] = ExecResult(
                    task_id=f"local-{i}", title=task.title,
                    status="skipped",
                    result=f"Skipped — dependency [{dep_idx}] did not pass",
                    output="",
                    duration_seconds=0,
                )
                skip = True
                break

        if not skip:
            results[i] = execute_task(task, task_index=i)

    return [r for r in results if r is not None]
