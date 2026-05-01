#!/usr/bin/env python3
"""
JustAi — Intent Gate
====================
First stage of the orchestrator pipeline. Classifies an incoming goal
into one of four intent types so downstream components know how to handle it.

Intent types (evidence-based from 10 sprint history):
  execution   — single well-scoped action, delegate directly to mini
  multi-step  — needs decomposition into ordered subtasks first
  research    — information gathering, delegate to Ruflo researcher
  ambiguous   — needs one clarifying question before proceeding

Design principle: fast, deterministic classification. Uses LiteLLM
at localhost:4000 (Gameron → local fallback chain). No external calls.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import StrEnum


class Intent(StrEnum):
    EXECUTION = "execution"
    MULTI_STEP = "multi-step"
    RESEARCH = "research"
    AMBIGUOUS = "ambiguous"


@dataclass
class IntentResult:
    intent: Intent
    confidence: float  # 0.0–1.0
    reasoning: str  # one sentence
    clarifying_question: str  # non-empty only when intent == AMBIGUOUS


_SYSTEM_PROMPT = """\
You are the Intent Gate for JustAi, an AI orchestration system.
Classify the user's goal into exactly one of these intent types:

  execution  — a single, well-scoped task that one agent can complete
               in one focused run (e.g. "add a /health endpoint to server.py",
               "write tests for the relay board command", "fix the import error")
  multi-step — a goal that requires multiple distinct subtasks in sequence
               (e.g. "build a FastAPI webhook that posts to Discord",
               "set up SpacetimeDB, write the schema, and add a CLI")
  research   — information gathering with no immediate code output
               (e.g. "what are the tradeoffs of X vs Y", "find examples of Z")
  ambiguous  — the goal is too vague to classify without one clarifying question

Respond with JSON only, no prose, no markdown fences:
{
  "intent": "<execution|multi-step|research|ambiguous>",
  "confidence": <0.0-1.0>,
  "reasoning": "<one sentence>",
  "clarifying_question": "<question if ambiguous, else empty string>"
}
"""

LITELLM_URL = (
    os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/").removesuffix("/v1")
)
INTENT_MODEL = os.environ.get("JUSTAI_INTENT_MODEL", "openai/claude-opus-4-6")


def _call_litellm(goal: str) -> dict:
    """Call LiteLLM proxy and return parsed JSON response."""
    payload = json.dumps(
        {
            "model": INTENT_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Goal: {goal}"},
            ],
            "max_tokens": 200,
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
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)

    content = data["choices"][0]["message"]["content"].strip()
    # Strip markdown fences if model ignored instructions
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content)


def _heuristic_classify(goal: str) -> IntentResult:
    """
    Fast rule-based fallback when LiteLLM is unavailable.
    Errs toward multi-step for safety — better to decompose than under-scope.
    """
    g = goal.lower().strip()

    research_keywords = [
        "what is",
        "what are",
        "explain",
        "compare",
        "research",
        "find examples",
        "tradeoffs",
        "how does",
        "why does",
    ]
    if any(g.startswith(k) or f" {k}" in g for k in research_keywords):
        return IntentResult(
            intent=Intent.RESEARCH,
            confidence=0.7,
            reasoning="Goal appears to be an information request.",
            clarifying_question="",
        )

    # Short, specific, single-file or single-concern goals → execution
    word_count = len(goal.split())
    has_single_target = any(
        k in g
        for k in [
            "add ",
            "fix ",
            "update ",
            "write test",
            "rename ",
            "delete ",
            "move ",
            "create file",
            "in ",
            ".py",
            ".sh",
            ".ts",
            ".rs",
        ]
    )
    if word_count <= 20 and has_single_target:
        return IntentResult(
            intent=Intent.EXECUTION,
            confidence=0.75,
            reasoning="Short, specific goal with a single identifiable target.",
            clarifying_question="",
        )

    if word_count < 5:
        return IntentResult(
            intent=Intent.AMBIGUOUS,
            confidence=0.8,
            reasoning="Goal is too brief to classify with confidence.",
            clarifying_question="Could you describe what you want to build or change in more detail?",
        )

    return IntentResult(
        intent=Intent.MULTI_STEP,
        confidence=0.65,
        reasoning="Goal appears to span multiple concerns or components.",
        clarifying_question="",
    )


def classify(goal: str) -> IntentResult:
    """
    Classify a goal string into an IntentResult.
    Uses LiteLLM if available, falls back to heuristic classifier.
    """
    if not goal or not goal.strip():
        return IntentResult(
            intent=Intent.AMBIGUOUS,
            confidence=1.0,
            reasoning="Empty goal provided.",
            clarifying_question="What would you like JustAi to do?",
        )

    try:
        raw = _call_litellm(goal)
        return IntentResult(
            intent=Intent(raw["intent"]),
            confidence=float(raw.get("confidence", 0.8)),
            reasoning=raw.get("reasoning", ""),
            clarifying_question=raw.get("clarifying_question", ""),
        )
    except Exception as e:
        # LiteLLM unavailable or response malformed — use heuristic
        result = _heuristic_classify(goal)
        result.reasoning = f"[heuristic: {e.__class__.__name__}] {result.reasoning}"
        return result


if __name__ == "__main__":
    import sys

    goal = (
        " ".join(sys.argv[1:])
        or "Build a FastAPI endpoint that accepts a GitHub webhook and posts to Discord"
    )
    result = classify(goal)
    print(f"Intent:    {result.intent.value}")
    print(f"Confidence:{result.confidence:.2f}")
    print(f"Reasoning: {result.reasoning}")
    if result.clarifying_question:
        print(f"Question:  {result.clarifying_question}")
