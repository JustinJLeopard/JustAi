#!/usr/bin/env python3
"""
JustAi — Reviewer
=================
Pre-execution quality gate. Validates a Plan before any tasks are posted
to SpacetimeDB. Catches bad decomposition before mini wastes tokens on it.

Evidence basis (from sprint history):
  coworkclaude's value was at PLANNING TIME, not runtime. Its role as
  post-sprint reviewer correlated directly with the 80->90->100% improvement
  curve. This component formalizes that as a pre-execution gate.

What the reviewer checks:
  1. Task sizing — each task completable in ~35 mini steps?
  2. Ambiguity — zero open decisions left to executor?
  3. Sequence — dependencies ordered correctly?
  4. Criteria — success criteria is a real bash command?
  5. Scope creep — any single task trying to do too much?

Output: APPROVED (proceed) or REJECTED (with specific feedback for replanning)
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass

from justai.planner import Plan, Task


@dataclass
class ReviewResult:
    approved: bool
    feedback: list[str]      # specific issues found, empty if approved
    revised_tasks: list[Task] | None = None  # optional revised plan


_SYSTEM_PROMPT = """\
You are the Reviewer for JustAi, a pre-execution quality gate for AI agent task plans.

You will receive a plan consisting of an ordered list of tasks that will be sent
to mini-swe-agent — a bash-only execution agent that works in ~35 message steps.

Your job: validate the plan quality BEFORE execution. Be strict. A bad plan wastes
expensive Opus API calls and fails in production.

Check each task for:
1. SIZING — Can mini complete this in ~35 bash steps? If a task touches more than
   2-3 files or spans multiple concerns, it's too large. Flag it.
2. AMBIGUITY — Does the description leave any decisions to mini? File paths should
   be explicit. Expected behavior should be described. Flag any vagueness.
3. SEQUENCE — Are dependencies correct? A task that reads files another task creates
   must depend on that task. Flag ordering errors.
4. CRITERIA — Is the success_criteria a real bash command (not "echo verify manually"
   or similar placeholders)? Flag missing criteria.
5. SCOPE — Does any task try to do too many things? "Add endpoint AND write tests
   AND update README" in one task is too much. Flag it.

Respond with JSON only:
{
  "approved": <true|false>,
  "feedback": ["<specific issue 1>", "<specific issue 2>"],
  "suggestions": ["<concrete fix for issue 1>", "<concrete fix for issue 2>"]
}

If approved, feedback and suggestions should be empty arrays.
Be direct. One sentence per issue. Reference the task title.
"""

LITELLM_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/").removesuffix("/v1")
REVIEWER_MODEL = os.environ.get("JUSTAI_REVIEWER_MODEL", "openai/claude-opus-4-6")


def _format_plan_for_review(plan: Plan) -> str:
    tasks_json = []
    for i, t in enumerate(plan.tasks):
        tasks_json.append({
            "index": i,
            "title": t.title,
            "description": t.description,
            "agent": t.agent.value,
            "risk": t.risk.value,
            "success_criteria": t.success_criteria,
            "depends_on": t.depends_on,
        })
    return json.dumps({
        "goal": plan.goal,
        "task_count": len(plan.tasks),
        "tasks": tasks_json,
    }, indent=2)


def _call_litellm(plan_json: str) -> dict:
    payload = json.dumps({
        "model": REVIEWER_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Review this plan:\n\n{plan_json}"},
        ],
        "max_tokens": 1000,
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


def _heuristic_review(plan: Plan) -> ReviewResult:
    """Fast rule-based review when LiteLLM is unavailable."""
    issues = []
    for i, task in enumerate(plan.tasks):
        # Check for placeholder success criteria
        if "verify manually" in task.success_criteria or "no criteria" in task.success_criteria:
            issues.append(f"Task [{i}] '{task.title}': missing real success criteria")
        # Check for obviously oversized tasks (description > 500 chars usually means too much)
        if len(task.description) > 600:
            issues.append(f"Task [{i}] '{task.title}': description very long — may be oversized")
        # Check dependency ordering
        for dep in task.depends_on:
            if dep >= i:
                issues.append(f"Task [{i}] '{task.title}': depends_on [{dep}] which comes after it")

    return ReviewResult(approved=len(issues) == 0, feedback=issues)


def review(plan: Plan) -> ReviewResult:
    """
    Review a Plan before execution.
    Returns ReviewResult with approved=True if the plan is ready to execute.
    """
    if not plan.tasks:
        return ReviewResult(approved=False, feedback=["Plan has no tasks."])

    try:
        plan_json = _format_plan_for_review(plan)
        raw = _call_litellm(plan_json)
        return ReviewResult(
            approved=bool(raw.get("approved", False)),
            feedback=raw.get("feedback", []) + raw.get("suggestions", []),
        )
    except Exception as e:
        # LiteLLM unavailable — fall back to heuristic
        result = _heuristic_review(plan)
        if result.feedback:
            result.feedback.insert(0, f"[heuristic review: {e.__class__.__name__}]")
        return result


if __name__ == "__main__":
    from justai.planner import decompose, format_plan
    import sys

    goal = " ".join(sys.argv[1:]) or (
        "Add a /health/agents endpoint to scripts/health_server.py "
        "that returns a JSON list of registered agents with their status"
    )
    plan = decompose(goal, session_ref="sprint-2")
    print(format_plan(plan))
    print("--- Reviewing plan ---")
    result = review(plan)
    print(f"Approved: {result.approved}")
    for issue in result.feedback:
        print(f"  ! {issue}")
