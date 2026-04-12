#!/usr/bin/env python3
"""
JustAi — Planner
================
Decomposes a goal into an ordered list of mini-sized tasks ready for
delegation to mini-swe-agent via SpacetimeDB.

Evidence-based design (from 10 sprint traj analysis):
  - mini-swe-agent v2.2.8 completes tasks in ~35 messages
  - 100% first-try success when tasks are: single-concern, unambiguous,
    scoped to one file or directory, with testable success criteria
  - Task decomposition quality was the #1 driver of sprint success improvement
  - Each task must be completable in one mini run — no multi-session tasks

Task sizing rules (from evidence):
  - One primary target per task. If it touches multiple files, they must all
    serve a single atomic concern. If you can split it and verify each part
    independently, split it.
    Good: "add /health/agents endpoint to health_server.py"
    Good: "add retry_count to Task struct and increment in requeue_task reducer"
    Bad:  "add endpoint to health_server.py, write tests, and update README"
          (that's three tasks — endpoint, tests, docs — each independently verifiable)
  - The practical signal: if you can't write one bash command that verifies
    the whole task is done, it's probably two tasks.
  - Dependencies must be explicit — task N lists which prior task IDs it needs
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RiskLevel(str, Enum):
    R0 = "R0"   # no gate — read-only, low-risk file creation
    R1 = "R1"   # notify only — auto-proceed after 60s
    R2 = "R2"   # hard gate — wait for explicit approval
    R3 = "R3"   # blocked — operator must manually unlock


class AgentType(str, Enum):
    MINI = "mini"           # mini-swe-agent — any bash-possible task
    RESEARCHER = "researcher"  # Ruflo researcher agent


@dataclass
class Task:
    title: str
    description: str                  # full task text sent to mini
    agent: AgentType
    risk: RiskLevel
    success_criteria: str            # bash command or grep that verifies completion
    depends_on: list[int] = field(default_factory=list)  # indices into task list
    session_ref: str = ""            # e.g. "sprint-2"


@dataclass
class Plan:
    goal: str
    tasks: list[Task]
    session_ref: str = ""


_SYSTEM_PROMPT = """\
You are the Planner for JustAi, an AI orchestration system that delegates tasks
to mini-swe-agent — a bash-only execution agent that completes tasks in ~35 messages.

Your job: decompose a goal into an ordered list of mini-sized tasks.

CRITICAL SIZING RULES (from production evidence — these determine success rate):
1. One primary target per task. If it touches multiple files they must serve
   one atomic concern. Signal: if you can't verify it with one bash command, split it.
   Good: "add /health/agents endpoint to health_server.py"
   Bad:  "add endpoint, write tests, and update README" (three separate tasks)
2. Each task must be completable by mini in a single run (~35 bash steps)
3. Tasks must be UNAMBIGUOUS — zero decisions left to the executor
4. Success criteria must be a concrete bash command (exit 0 = success)
5. If a task would need more than ~10 bash commands to verify, split it
6. Always start with a read/explore task before any write tasks on unfamiliar code

RISK LEVELS:
  R0 — read-only, low-risk file creation, adding tests
  R1 — modifying existing code, adding new endpoints
  R2 — deleting files, changing interfaces, DB schema changes
  R3 — irreversible operations, production deploys

Respond with JSON only, no prose, no markdown fences:
{
  "tasks": [
    {
      "title": "<short imperative title>",
      "description": "<full task text that will be sent verbatim to mini-swe-agent>",
      "agent": "<mini|researcher>",
      "risk": "<R0|R1|R2|R3>",
      "success_criteria": "<bash command that exits 0 on success>",
      "depends_on": [<list of 0-based indices of tasks this depends on>]
    }
  ]
}

The description field is what mini-swe-agent will receive as its task — write it
as a complete, unambiguous instruction. Include file paths, expected behavior,
and how to verify. Do not leave any decisions to mini.
"""

LITELLM_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/").removesuffix("/v1")
PLANNER_MODEL = os.environ.get("JUSTAI_PLANNER_MODEL", "openai/claude-opus-4-6")


def _call_litellm(goal: str, context: str = "") -> dict:
    user_content = f"Goal: {goal}"
    if context:
        user_content += f"\n\nContext:\n{context}"

    payload = json.dumps({
        "model": PLANNER_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 2000,
        "temperature": 0.0,
    }).encode()

    req = urllib.request.Request(
        f"{LITELLM_URL}/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ.get('LITELLM_KEY', 'sk-justai')}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)

    content = data["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content)


def _parse_tasks(raw: dict, session_ref: str = "") -> list[Task]:
    tasks = []
    for t in raw.get("tasks", []):
        tasks.append(Task(
            title=t["title"],
            description=t["description"],
            agent=AgentType(t.get("agent", "mini")),
            risk=RiskLevel(t.get("risk", "R1")),
            success_criteria=t.get("success_criteria", "echo 'no criteria defined'"),
            depends_on=t.get("depends_on", []),
            session_ref=session_ref,
        ))
    return tasks


def _heuristic_plan(goal: str, session_ref: str = "") -> Plan:
    """Build a reasonable fallback plan without LLM.

    Generates an explore-then-execute plan instead of a blind single task.
    """
    # Infer the target from the goal
    words = goal.lower()
    is_add = any(w in words for w in ["add", "create", "implement", "write", "build"])
    is_fix = any(w in words for w in ["fix", "debug", "repair", "resolve"])
    is_test = any(w in words for w in ["test", "verify", "check", "validate"])

    tasks = []

    # Task 0: always explore first
    tasks.append(Task(
        title="Explore relevant files",
        description=(
            f"Read the codebase to understand what exists before making changes.\n"
            f"Goal context: {goal}\n"
            f"List files in the project, read the main module, and identify where changes are needed."
        ),
        agent=AgentType.MINI,
        risk=RiskLevel.R0,
        success_criteria="ls -la && echo 'exploration complete'",
        depends_on=[],
        session_ref=session_ref,
    ))

    # Task 1: the actual work
    risk = RiskLevel.R1
    if is_fix:
        risk = RiskLevel.R1
    elif is_add:
        risk = RiskLevel.R1

    tasks.append(Task(
        title=goal[:60],
        description=goal,
        agent=AgentType.MINI,
        risk=risk,
        success_criteria=_infer_verify_command(goal),
        depends_on=[0],
        session_ref=session_ref,
    ))

    # Task 2: verify if not already a test task
    if not is_test:
        tasks.append(Task(
            title=f"Verify: {goal[:50]}",
            description=f"Verify that the following goal was accomplished correctly:\n{goal}",
            agent=AgentType.MINI,
            risk=RiskLevel.R0,
            success_criteria=_infer_verify_command(goal),
            depends_on=[1],
            session_ref=session_ref,
        ))

    return Plan(goal=goal, tasks=tasks, session_ref=session_ref)


def _infer_verify_command(goal: str) -> str:
    """Infer a verification command from the goal text."""
    words = goal.lower()
    # If goal mentions an endpoint, try curling it
    if "/api/" in words or "endpoint" in words:
        return "curl -sf http://localhost:8080/health || echo 'verify endpoint manually'"
    # If goal mentions tests
    if "test" in words:
        return "python3 -m pytest -x --tb=short 2>&1 | tail -5"
    # If goal mentions a specific file
    if ".py" in words:
        return "python3 -c 'import ast; print(1)'"
    return "echo 'task completed — verify manually'"


LLM_RETRY_ATTEMPTS = 2


def decompose(
    goal: str,
    session_ref: str = "",
    context: str = "",
) -> Plan:
    """
    Decompose a goal into an ordered list of mini-sized Tasks.
    Uses LiteLLM with retry. Falls back to heuristic plan on repeated failure.
    """
    last_error = None
    for attempt in range(LLM_RETRY_ATTEMPTS):
        try:
            raw = _call_litellm(goal, context)
            tasks = _parse_tasks(raw, session_ref)
            if tasks:
                return Plan(goal=goal, tasks=tasks, session_ref=session_ref)
        except Exception as e:
            last_error = e
            if attempt < LLM_RETRY_ATTEMPTS - 1:
                import time
                wait = 2 ** attempt
                print(f"[planner] LLM call failed (attempt {attempt + 1}), retrying in {wait}s: {e}")
                time.sleep(wait)

    # Fallback: heuristic plan with explore-execute-verify structure
    print(f"[planner] LLM unavailable after {LLM_RETRY_ATTEMPTS} attempts — using heuristic plan")
    if last_error:
        print(f"[planner] Last error: {str(last_error)[:100]}")
    return _heuristic_plan(goal, session_ref)


def format_plan(plan: Plan) -> str:
    """Human-readable plan summary."""
    lines = [f"Plan for: {plan.goal}", f"Tasks: {len(plan.tasks)}", ""]
    for i, t in enumerate(plan.tasks):
        deps = f" (after {t.depends_on})" if t.depends_on else ""
        lines.append(f"  [{i}] {t.title} [{t.risk.value}]{deps}")
        lines.append(f"      Agent: {t.agent.value}")
        lines.append(f"      Verify: {t.success_criteria}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    goal = " ".join(sys.argv[1:]) or (
        "Add a /health/agents endpoint to scripts/health_server.py "
        "that returns a JSON list of registered agents with their status"
    )
    plan = decompose(goal, session_ref="sprint-2")
    print(format_plan(plan))
