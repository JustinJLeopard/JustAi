"""Synthesizer tests kept after Sprint 10 executor removal."""

from __future__ import annotations

from justai.results import DelegationResult


def _result(status: str = "done", title: str = "task") -> DelegationResult:
    return DelegationResult(
        task_id="t1",
        title=title,
        status=status,
        result="ok",
        duration_seconds=1.0,
    )


def test_synthesize_all_done():
    from justai.synthesizer import synthesize

    summary = synthesize("goal", "execution", [_result("done"), _result("done")], "test", 5.0)

    assert summary.status == "complete"
    assert summary.done == 2
    assert summary.failed == 0


def test_synthesize_partial_and_skipped():
    from justai.synthesizer import synthesize

    summary = synthesize("goal", "execution", [_result("done"), _result("skipped")], "test", 5.0)

    assert summary.status == "partial"
    assert summary.skipped == 1


def test_synthesize_all_failed():
    from justai.synthesizer import synthesize

    summary = synthesize("goal", "execution", [_result("failed")], "test", 5.0)

    assert summary.status == "failed"


def test_format_summary_includes_task_title():
    from justai.synthesizer import format_summary, synthesize

    summary = synthesize("goal", "execution", [_result("done", "Add endpoint")], "test", 5.0)
    text = format_summary(summary)

    assert "Run Summary" in text
    assert "Add endpoint" in text
