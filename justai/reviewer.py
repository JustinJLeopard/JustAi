#!/usr/bin/env python3
"""
JustAi — Reviewer
=================
Pre-execution quality gate. Validates a Plan before any chunk is sent toward
the execution substrate. Catches bad decomposition before mini wastes tokens.

Evidence basis (from sprint history):
  coworkclaude's value was at PLANNING TIME, not runtime. Its role as
  post-sprint reviewer correlated directly with the 80->90->100% improvement
  curve. This component formalizes that as a pre-execution gate.

What the reviewer checks:
  1. Task sizing — each task completable in ~35 mini steps?
  2. Ambiguity — zero open decisions left to the runner?
  3. Sequence — dependencies ordered correctly?
  4. Criteria — success criteria is a real bash command?
  5. Scope creep — any single task trying to do too much?

Output: APPROVED (proceed) or REJECTED (with specific feedback for replanning)
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass

from justai.scope_planner import Plan, Task


@dataclass
class ReviewResult:
    approved: bool
    feedback: list[str]  # specific issues found, empty if approved
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
6. PRECONDITION FABRICATION -- Does any task CREATE or generate an input the
   goal treats as already existing (e.g., goal "summarize report.csv" but a
   task runs "touch report.csv")? Inputs the goal names as existing must not
   be manufactured by the plan; that yields false success. Flag it.

Respond with JSON only:
{
  "approved": <true|false>,
  "feedback": ["<specific issue 1>", "<specific issue 2>"],
  "suggestions": ["<concrete fix for issue 1>", "<concrete fix for issue 2>"]
}

If approved, feedback and suggestions should be empty arrays.
Be direct. One sentence per issue. Reference the task title.
"""

LITELLM_URL = (
    os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/").removesuffix("/v1")
)
REVIEWER_MODEL = os.environ.get("JUSTAI_REVIEWER_MODEL", "openai/claude-opus-4-6")


def _format_plan_for_review(plan: Plan) -> str:
    tasks_json = []
    for i, t in enumerate(plan.tasks):
        tasks_json.append(
            {
                "index": i,
                "title": t.title,
                "description": t.description,
                "agent": t.agent.value,
                "risk": t.risk.value,
                "success_criteria": t.success_criteria,
                "depends_on": t.depends_on,
            }
        )
    return json.dumps(
        {
            "goal": plan.goal,
            "task_count": len(plan.tasks),
            "tasks": tasks_json,
        },
        indent=2,
    )


def _call_litellm(plan_json: str) -> dict:
    payload = json.dumps(
        {
            "model": REVIEWER_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Review this plan:\n\n{plan_json}"},
            ],
            "max_tokens": 1000,
            "temperature": 0.0,
        }
    ).encode()

    req = urllib.request.Request(
        f"{LITELLM_URL}/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ.get('LITELLM_KEY', '')}",
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


# Verbs that CONSUME a pre-existing input, matched at a word boundary (prefix)
# so "summariz" covers summarize/summarizing.
_CONSUMER_VERBS = (
    "copy", "copies", "move", "moves", "rename", "summariz", "analyz",
    "parse", "convert", "backup", "compress", "translat", "extract",
    "deduplicat", "ingest",
)
# Destination cues: when the goal introduces a path as an output/destination,
# a task creating it is correct, not a fabricated precondition. Kept liberal on
# purpose -- misclassifying an input as an output only costs a missed flag,
# never a blocked good plan (false positives are the worse failure here).
_DEST_CUE_RE = (
    r"(?:\bto|\binto|\bonto|\bas|\boutput|\bsave|\bexport|\bdump|\brender|"
    r"\bwrit\w*|\bgenerat\w*|\bcreat\w*|\bproduc\w*|-o)\s+"
)


def _has_consumer_verb(goal_lower: str) -> bool:
    return any(re.search(r"\b" + re.escape(v), goal_lower) for v in _CONSUMER_VERBS)


def _is_goal_output_path(goal_lower: str, path_lower: str) -> bool:
    """True if the goal introduces this path as an output/destination."""
    return bool(re.search(_DEST_CUE_RE + re.escape(path_lower), goal_lower))


def _task_creates_path(blob_lower: str, path_lower: str) -> bool:
    # Trailing boundary so a goal path that is a prefix of a longer path
    # (report.csv vs report.csv.lock) does not match.
    ep = re.escape(path_lower) + r"(?![\w./~-])"
    # Shell users commonly quote paths or terminate options before a path.
    # Normalize only those two unambiguous forms; this remains a conservative
    # heuristic rather than attempting to parse arbitrary shell syntax.
    path_argument = r"(?:--\s+)?(?:['\"])?" + ep + r"(?:['\"])?"
    redirection_path = r"(?:['\"])?" + ep + r"(?:['\"])?"
    return bool(
        re.search(r"(?:\btouch\b|\bmkdir\b(?:\s+-p)?|\binstall\s+-d\b|\btee\b)\s+" + path_argument, blob_lower)
        or re.search(r">>?\s*" + redirection_path, blob_lower)
    )


def _task_makes_exist(blob_lower: str, path_lower: str) -> bool:
    """True if a task makes the given path EXIST -- via a shell op, or a prose
    creation whose DIRECT OBJECT is the path/basename ("create X", "write a
    placeholder X"). Reads of the path ("summary FROM x", "backup OF x") and
    read-only checks ("confirm x exists") carry no creating-object match, so
    they are not flagged. Path is boundary-anchored so report.csv does not match
    report.csv.lock.
    """
    if _task_creates_path(blob_lower, path_lower):
        return True
    verb = (r"\b(?:create|creates|creating|touch|mkdir|generate|generates|"
            r"make|makes|initializ\w*|write|writes|writing)\s+")
    det = r"(?:(?:a|an|the|empty|new|blank|dummy|stub|initial|placeholder|requested)\s+){0,4}"
    basename = path_lower.rsplit("/", 1)[-1]
    for target in {re.escape(path_lower), re.escape(basename)}:
        if re.search(verb + det + r"(?<![\w./~-])" + target + r"(?![\w./~-])", blob_lower):
            return True
    return False


def _fabricated_preconditions(plan: Plan) -> list[str]:
    """Flag tasks that manufacture an input the goal assumes already exists.

    A goal that CONSUMES an input (copy/summarize/convert X) must not be
    satisfied against an X the plan itself created -- that is a false completion.
    Only fires for a concrete file-like input the goal does NOT introduce as an
    output/destination or ask to create, when a task makes that exact path exist
    (shell op or natural-language creation). Errs toward NOT flagging.
    """
    goal_lower = (plan.goal or "").lower()
    if not _has_consumer_verb(goal_lower):
        return []
    goal_paths = set(re.findall(r"[\w./~-]*\.[A-Za-z0-9]{1,6}\b", plan.goal or ""))
    issues: list[str] = []
    seen: set[tuple[int, str]] = set()
    for path in sorted(goal_paths):
        pl = path.lower()
        if _is_goal_output_path(goal_lower, pl):
            continue
        for i, t in enumerate(plan.tasks):
            blob = ((t.title or "") + " " + (t.description or "") + " " + (t.success_criteria or "")).lower()
            if pl in blob and _task_makes_exist(blob, pl) and (i, pl) not in seen:
                seen.add((i, pl))
                issues.append(
                    f"Task [{i}] '{t.title}': plan makes '{path}' exist, but the goal "
                    f"treats it as an existing input (fabricated precondition -- the goal "
                    f"could be satisfied against a file the plan created, not the real one)"
                )
    return issues


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

    issues.extend(_fabricated_preconditions(plan))

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
    import sys

    from justai.scope_planner import decompose, format_plan

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
