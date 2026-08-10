"""A failed learning write must not disappear.

record_run() returns False when the trajectory store cannot persist a run (for
example the memory backend is unreachable). Both orchestrator call sites
discarded that value, so every run silently lost its learning evidence while
reporting success -- and `justai history` showed "No run history found", which
is indistinguishable from "no runs yet". Observed live: eleven real runs
recorded nothing.

A failed write must stay non-fatal (losing the record must never fail a
completed run) but must be visible.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.test_orchestrator_pipeline import _patch_pipeline, _result


def test_failed_learning_write_is_reported(capsys):
    from justai.orchestrator import run

    with _patch_pipeline(results=[_result("done")]):
        with patch("justai.orchestrator.record_run", return_value=False) as rec:
            result = run("a goal", session_ref="t")

    rec.assert_called_once()
    assert result.status == "complete", "a lost learning record must not fail the run"
    out = capsys.readouterr().out.lower()
    assert "not recorded" in out, f"operator must see the lost record, got: {out[-300:]}"


def test_successful_learning_write_is_quiet(capsys):
    from justai.orchestrator import run

    with _patch_pipeline(results=[_result("done")]):
        with patch("justai.orchestrator.record_run", return_value=True):
            run("a goal", session_ref="t")

    assert "not recorded" not in capsys.readouterr().out.lower()


def test_failed_learning_write_on_the_fail_closed_path_is_reported(capsys):
    """The fail-closed branch records evidence too; losing it must also show."""
    from justai.orchestrator import run

    with _patch_pipeline(results="not-a-sequence"):
        with patch("justai.orchestrator.record_run", return_value=False):
            result = run("a goal", session_ref="t")

    assert result.status == "failed"
    assert "not recorded" in capsys.readouterr().out.lower()
