"""
Intent-fidelity gate tests (#30 — "the intent is A or better", with percentile).

Covers the percentile/grade mapping, the LLM judge path (mocked), the honest
completion-based heuristic fallback, and the synthesizer's honest downgrade of a
task-complete-but-intent-missed run.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from justai.intent_fidelity import (
    FidelityResult,
    FidelityVerdict,
    _heuristic_fidelity,
    grade_for,
    score_fidelity,
)
from justai.results import DelegationResult
from justai.synthesizer import synthesize


def _res(status: str = "done", title: str = "t") -> DelegationResult:
    return DelegationResult(
        task_id="1", title=title, status=status, result="ok", duration_seconds=1.0
    )


def _plan():
    from justai.scope_planner import AgentType, Plan, RiskLevel, Task

    return Plan(
        goal="g",
        tasks=[Task("T", "do", AgentType.MINI, RiskLevel.R0, "echo ok")],
        session_ref="t",
    )


def _fr(fidelity: float, verdict: str, a_or_better: bool, grade: str) -> FidelityResult:
    return FidelityResult(
        fidelity=fidelity,
        verdict=FidelityVerdict(verdict),
        a_or_better=a_or_better,
        grade=grade,
        rationale="test",
        source="test",
    )


def _llm_resp(fidelity, better=False, rationale="r"):
    """Fake LiteLLM chat-completions response object."""
    content = json.dumps(
        {"fidelity": fidelity, "better_than_intent": better, "rationale": rationale}
    )
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
    return resp


# ── percentile → grade mapping ─────────────────────────────────────────────
def test_grade_boundaries():
    assert grade_for(100) == "A+"
    assert grade_for(97) == "A+"
    assert grade_for(96.9) == "A"
    assert grade_for(90) == "A"
    assert grade_for(89.9) == "B"
    assert grade_for(70) == "C"
    assert grade_for(60) == "D"
    assert grade_for(59.9) == "F"


# ── heuristic fallback (deterministic, completion-based) ───────────────────
def test_heuristic_all_done_is_met():
    fr = _heuristic_fidelity("g", _plan(), [_res("done"), _res("done")])
    assert fr.fidelity == 100.0
    assert fr.verdict == FidelityVerdict.MET
    assert fr.a_or_better is True
    assert fr.source == "heuristic"


def test_heuristic_partial_is_missed():
    fr = _heuristic_fidelity("g", _plan(), [_res("done"), _res("failed")])
    assert fr.fidelity == 50.0
    assert fr.verdict == FidelityVerdict.MISSED
    assert fr.a_or_better is False


def test_heuristic_never_fabricates_exceeded():
    # Without a real judge the heuristic must not claim the outcome beat the intent.
    fr = _heuristic_fidelity("g", _plan(), [_res("done")])
    assert fr.verdict != FidelityVerdict.EXCEEDED


# ── LLM judge path (mocked) ────────────────────────────────────────────────
def test_llm_low_fidelity_is_missed():
    with patch("urllib.request.urlopen", return_value=_llm_resp(30)):
        fr = score_fidelity("g", _plan(), [_res("done")])
    assert fr.source == "llm"
    assert fr.fidelity == 30.0
    assert fr.verdict == FidelityVerdict.MISSED
    assert fr.a_or_better is False


def test_llm_high_fidelity_is_met():
    with patch("urllib.request.urlopen", return_value=_llm_resp(95)):
        fr = score_fidelity("g", _plan(), [_res("done")])
    assert fr.verdict == FidelityVerdict.MET
    assert fr.grade == "A"


def test_llm_better_than_intent_is_exceeded():
    with patch("urllib.request.urlopen", return_value=_llm_resp(99, better=True)):
        fr = score_fidelity("g", _plan(), [_res("done")])
    assert fr.verdict == FidelityVerdict.EXCEEDED
    assert fr.a_or_better is True


def test_score_fidelity_falls_back_on_llm_error():
    with patch("urllib.request.urlopen", side_effect=URLError("down")):
        fr = score_fidelity("g", _plan(), [_res("done")])
    assert fr.source == "heuristic"
    assert fr.fidelity == 100.0


# ── integration: honest downgrade in synthesize ────────────────────────────
def test_synthesize_downgrades_complete_but_intent_missed():
    missed = _fr(20.0, "missed", False, "F")
    summary = synthesize("g", "execution", [_res("done"), _res("done")], "t", 1.0, fidelity=missed)
    assert summary.done == 2  # every task ran...
    assert summary.status == "partial"  # ...but the intent was not met → honest downgrade
    assert summary.fidelity_verdict == "missed"
    assert summary.a_or_better is False
    assert summary.intent_fidelity == 20.0


def test_synthesize_keeps_complete_when_intent_met():
    met = _fr(95.0, "met", True, "A")
    summary = synthesize("g", "execution", [_res("done")], "t", 1.0, fidelity=met)
    assert summary.status == "complete"
    assert summary.a_or_better is True
    assert summary.fidelity_grade == "A"


def test_synthesize_does_not_upgrade_partial_run():
    # Gate only downgrades false-completes; it never hides a real task failure.
    exceeded = _fr(100.0, "exceeded", True, "A+")
    summary = synthesize("g", "execution", [_res("done"), _res("failed")], "t", 1.0, fidelity=exceeded)
    assert summary.status == "partial"
    assert summary.a_or_better is True  # verdict still surfaced honestly


def test_synthesize_without_fidelity_is_unchanged():
    summary = synthesize("g", "execution", [_res("done")], "t", 1.0)
    assert summary.status == "complete"
    assert summary.intent_fidelity is None
    assert summary.a_or_better is None
