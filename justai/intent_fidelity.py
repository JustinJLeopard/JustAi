#!/usr/bin/env python3
"""
JustAi — Intent Fidelity Gate
=============================
Post-execution gate. After tasks run and before the run is reported, this stage
asks the question the task-count status cannot: did the OUTCOME actually achieve
the user's original intent — "A" — or something genuinely better?

Motivation (evidence): the synthesizer marks a run "complete" whenever every
task's status is "done". But a plan can decompose a goal into tasks that all
pass while drifting from the real intent, so "all tasks done" masquerades as
"achieved your goal". This gate scores intent fidelity as a 0-100 percentile
and, when the outcome falls short of the intent bar, honestly downgrades the
reported status (complete -> partial).

Acceptance model (framing: "the intent is A or better"):
  met       — fidelity >= bar: the intended outcome ("A") was achieved
  exceeded  — the outcome is genuinely better than the intent ("or better")
  missed    — fidelity < bar: do NOT report a drifted run as complete

Primary judge is LiteLLM (same localhost:4000 chain as the other stages). When
the proxy is unavailable it falls back to a deterministic, completion-based
heuristic that is honest about its own limits: without a real judge it does not
fabricate a confident "missed" verdict from fuzzy token matching.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from enum import StrEnum


class FidelityVerdict(StrEnum):
    MET = "met"           # intended outcome ("A") achieved
    EXCEEDED = "exceeded"  # genuinely better than the intent
    MISSED = "missed"     # fell short of the intent


@dataclass
class FidelityResult:
    fidelity: float            # 0-100 intent-achievement percentile
    verdict: FidelityVerdict
    a_or_better: bool          # verdict in {met, exceeded} — cleared the intent bar
    grade: str                 # A+/A/B/C/D/F, derived from fidelity
    rationale: str             # one sentence
    source: str                # "llm" | "heuristic"


# "A or better" — the intent bar. Default: A == 90th-percentile fidelity.
# a_or_better tracks THIS bar; the letter grade is a fixed scale, so at the
# default bar (90) a_or_better is exactly (grade in {A, A+}).
INTENT_BAR = float(os.environ.get("JUSTAI_INTENT_BAR", "90"))
FIDELITY_MODEL = os.environ.get("JUSTAI_FIDELITY_MODEL", "openai/claude-opus-4-6")
LITELLM_URL = (
    os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/").removesuffix("/v1")
)


def grade_for(fidelity: float) -> str:
    """Map a 0-100 fidelity percentile to a letter grade."""
    if fidelity >= 97:
        return "A+"
    if fidelity >= 90:
        return "A"
    if fidelity >= 80:
        return "B"
    if fidelity >= 70:
        return "C"
    if fidelity >= 60:
        return "D"
    return "F"


def _verdict_for(fidelity: float, better: bool, bar: float = INTENT_BAR) -> FidelityVerdict:
    if fidelity >= bar and better:
        return FidelityVerdict.EXCEEDED
    if fidelity >= bar:
        return FidelityVerdict.MET
    return FidelityVerdict.MISSED


def _make(fidelity, better, rationale, source, bar: float = INTENT_BAR) -> FidelityResult:
    """Clamp, grade, and package a fidelity score into a FidelityResult."""
    fidelity = max(0.0, min(100.0, float(fidelity)))
    verdict = _verdict_for(fidelity, bool(better), bar)
    return FidelityResult(
        fidelity=round(fidelity, 1),
        verdict=verdict,
        a_or_better=verdict in (FidelityVerdict.MET, FidelityVerdict.EXCEEDED),
        grade=grade_for(fidelity),
        rationale=(rationale or "").strip() or "(no rationale)",
        source=source,
    )


_SYSTEM_PROMPT = """\
You are the Intent-Fidelity Gate for JustAi. You judge whether an executed run
actually achieved the USER'S ORIGINAL INTENT — not merely whether its tasks ran.

You receive: the original goal, the plan's tasks, and the execution results.

Score intent fidelity as a percentile 0-100:
  100    = the intent was fully achieved, or the outcome is genuinely better
  90-99  = the intended outcome was achieved ("A")
  70-89  = mostly achieved, minor gaps
  40-69  = partial — tasks ran but drifted from the real intent
  0-39   = the intent was not achieved

Judge the OUTCOME against the INTENT. All tasks "done" does NOT imply the intent
was met if the plan solved a different or adjacent problem. Be strict and
honest: under-claiming a miss is safer than over-claiming success.

Set "better_than_intent" true ONLY if the outcome genuinely exceeds what was
asked (more complete, more robust) — never as a consolation for a partial run.

Respond with JSON only, no prose, no fences:
{
  "fidelity": <0-100>,
  "better_than_intent": <true|false>,
  "rationale": "<one sentence>"
}
"""


def _format_for_judge(goal: str, plan, results: list) -> str:
    tasks = []
    for t in getattr(plan, "tasks", []) or []:
        tasks.append(
            {
                "title": getattr(t, "title", ""),
                "description": getattr(t, "description", ""),
                "success_criteria": getattr(t, "success_criteria", ""),
            }
        )
    payload = {
        "goal": goal,
        "tasks": tasks,
        "results": [
            {
                "title": getattr(r, "title", ""),
                "status": getattr(r, "status", "?"),
                "result": (getattr(r, "result", "") or "")[:300],
            }
            for r in results
        ],
    }
    return json.dumps(payload, indent=2)


def _call_litellm(goal: str, plan, results: list) -> dict:
    payload = json.dumps(
        {
            "model": FIDELITY_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "Judge this run:\n\n" + _format_for_judge(goal, plan, results),
                },
            ],
            "max_tokens": 300,
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
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.load(resp)

    content = data["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content)


def _completion_ratio(results: list) -> float:
    if not results:
        return 0.0
    done = sum(1 for r in results if getattr(r, "status", "") == "done")
    return done / len(results)


def _heuristic_fidelity(goal: str, plan, results: list) -> FidelityResult:
    """
    Deterministic fallback when the LLM judge is unavailable.

    Honest about its own limits: without a real intent judge it does NOT
    fabricate a confident "missed" verdict from fuzzy token matching. It scores
    fidelity from task completion and reports source="heuristic" so callers know
    the intent was not semantically verified. A run it cannot judge as a miss is
    left at its completion-implied fidelity rather than being wrongly failed.
    """
    ratio = _completion_ratio(results)
    fidelity = 100.0 * ratio
    n = len(results)
    done = sum(1 for r in results if getattr(r, "status", "") == "done")
    rationale = (
        f"heuristic (no LLM judge): {done}/{n} tasks completed; fidelity scored "
        "from completion, intent not semantically verified."
    )
    return _make(fidelity, better=False, rationale=rationale, source="heuristic")


def score_fidelity(goal: str, plan, results: list) -> FidelityResult:
    """
    Score how well an executed run achieved the original intent ("A or better").

    Returns a FidelityResult with a 0-100 percentile, a met/exceeded/missed
    verdict against the intent bar, and an a_or_better flag. Never raises: any
    judge failure degrades to the deterministic completion-based heuristic.
    """
    try:
        raw = _call_litellm(goal, plan, results)
        return _make(
            fidelity=raw.get("fidelity", 0),
            better=bool(raw.get("better_than_intent", False)),
            rationale=str(raw.get("rationale", "")),
            source="llm",
        )
    except Exception as e:  # noqa: BLE001 -- degrade, never fail the run
        result = _heuristic_fidelity(goal, plan, results)
        result.rationale = f"[{e.__class__.__name__}] {result.rationale}"
        return result


if __name__ == "__main__":
    import sys
    from types import SimpleNamespace

    goal = " ".join(sys.argv[1:]) or "Add a /health endpoint to server.py"
    fake_plan = SimpleNamespace(
        tasks=[SimpleNamespace(title="Add endpoint", description="edit server.py",
                               success_criteria="curl localhost/health")]
    )
    fake_results = [SimpleNamespace(title="Add endpoint", status="done", result="200 OK")]
    fr = score_fidelity(goal, fake_plan, fake_results)
    print(f"Fidelity: {fr.fidelity:.0f}/100  grade {fr.grade}  {fr.verdict.value}")
    print(f"a_or_better: {fr.a_or_better}  (source: {fr.source})")
    print(f"Rationale: {fr.rationale}")
