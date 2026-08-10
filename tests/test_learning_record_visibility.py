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
    out = capsys.readouterr().err.lower()
    assert "not recorded" in out, f"operator must see the lost record, got: {out[-300:]}"


def test_successful_learning_write_is_quiet(capsys):
    from justai.orchestrator import run

    with _patch_pipeline(results=[_result("done")]):
        with patch("justai.orchestrator.record_run", return_value=True):
            run("a goal", session_ref="t")

    assert "not recorded" not in capsys.readouterr().err.lower()


def test_failed_learning_write_on_the_fail_closed_path_is_reported(capsys):
    """The fail-closed branch records evidence too; losing it must also show."""
    from justai.orchestrator import run

    with _patch_pipeline(results="not-a-sequence"):
        with patch("justai.orchestrator.record_run", return_value=False):
            result = run("a goal", session_ref="t")

    assert result.status == "failed"
    assert "not recorded" in capsys.readouterr().err.lower()


def test_reporting_never_fails_a_finished_run(monkeypatch):
    """A broken stdout/hook/tracer must not turn a lost record into a lost run."""
    import justai.orchestrator as O

    def broken_print(*a, **k):
        raise BrokenPipeError("stdout closed")
    monkeypatch.setattr("builtins.print", broken_print)

    hook = MagicMock()
    hook.on_stage.side_effect = RuntimeError("notifier down")
    monkeypatch.setattr(O, "_hook", hook, raising=False)
    monkeypatch.setattr(O, "trace_event", MagicMock(side_effect=RuntimeError("tracer down")))

    O._report_learning_write(False, "run-1", "sess")   # must not raise


def test_lost_record_is_informational_not_an_error_page(monkeypatch):
    """A backend that was simply never configured must not page per run."""
    import justai.orchestrator as O

    hook = MagicMock()
    monkeypatch.setattr(O, "_hook", hook, raising=False)
    monkeypatch.setattr(O, "trace_event", MagicMock())
    O._report_learning_write(False, "run-1", "sess")

    hook.on_error.assert_not_called()
    hook.on_stage.assert_called_once()
