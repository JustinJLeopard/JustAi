"""Regression: honest completion.

Guards the false-completion defect proven first-hand 2026-08-07: a run reported
"2/2 done | Status: complete" for a "create a file" goal while the file was never
created, because (a) `--local` verifies but never executes, (b) no-verification
counted as done, (c) a piped verify (`pytest | tail`) masked the failure, and
(d) synthesize() called it "complete" whenever failed==0. A task must not be
"done"/"complete" unless it genuinely is.
"""
from justai.scope_planner import Task
from justai.results import DelegationResult
from justai.agent_dispatch import _verify_task, _execute_single_local
from justai.synthesizer import synthesize


def _task(criteria, title="t", desc="d"):
    return Task(title=title, description=desc, agent="mini", risk="R0",
                success_criteria=criteria, depends_on=[], session_ref="test")


def test_pipefail_masking_is_fixed():
    passed, _ = _verify_task(_task("false | cat"))
    assert passed is False  # was True before pipefail


def test_no_verification_is_unverified_not_done():
    assert _verify_task(_task(""))[0] is None
    assert _verify_task(_task("echo 'verify manually'"))[0] is None


def test_passing_verify_is_done():
    assert _verify_task(_task("true"))[0] is True


def test_local_executor_three_states(monkeypatch):
    # Local mode now EXECUTES (model-driven) then verifies. Stub execution to a
    # harmless successful command so the 3-state mapping is driven by the check.
    import json

    from justai import agent_dispatch

    monkeypatch.setattr(agent_dispatch, "_llm_call", lambda *a, **k: json.dumps({"command": "true"}))
    assert _execute_single_local(_task("true")).status == "done"
    assert _execute_single_local(_task("")).status == "unverified"
    assert _execute_single_local(_task("false")).status == "failed"


def test_goal_artifact_absent_is_not_done(monkeypatch):
    # The exact defect: a file-creation goal whose artifact does not exist must
    # not be "done" -- even when a command ran, if the check can't confirm it.
    import json

    from justai import agent_dispatch

    monkeypatch.setattr(agent_dispatch, "_llm_call", lambda *a, **k: json.dumps({"command": "true"}))
    r = _execute_single_local(_task("test -f /tmp/__justai_nonexistent_artifact__"))
    assert r.status == "failed"


def _res(status):
    return DelegationResult(task_id="x", title="t", status=status, result="", duration_seconds=0.0)


def test_synthesize_complete_requires_all_done():
    assert synthesize("g", "i", [_res("done"), _res("done")]).status == "complete"
    assert synthesize("g", "i", [_res("done"), _res("unverified")]).status != "complete"
    assert synthesize("g", "i", [_res("done"), _res("failed")]).status != "complete"
    assert synthesize("g", "i", [_res("unverified"), _res("unverified")]).status != "complete"
