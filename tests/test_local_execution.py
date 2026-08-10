"""Regression tests for real --local task execution (model-driven).

Proves local mode now EXECUTES the task action and only reports a task as
``done`` when it both executed and its success check passed -- while keeping
the honest-completion invariants from the honest-completion fix intact.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from justai import agent_dispatch
from justai.agent_dispatch import (
    JustAiSandboxRunner,
    _execute_single_local,
    _is_catastrophic,
    _perform_task_action,
    escalate_plan,
)
from justai.runner_protocol import (
    AgentRunner,
    Budget,
    Chunk,
    ExecutorPolicy,
    FailureClass,
)
from justai.scope_planner import AgentType, RiskLevel, Task
from justai.synthesizer import synthesize


# Atom C: execution goes through the bwrap boundary; only the task workdir is
# writable. Point the workdir at each test's tmp_path so host-visible artifact
# assertions still prove the real effect through the single rw bind.
needs_bwrap = pytest.mark.skipif(
    shutil.which("bwrap") is None, reason="bwrap not installed"
)


@pytest.fixture(autouse=True)
def _task_workdir_is_tmp_path(tmp_path, monkeypatch):
    monkeypatch.setenv("JUSTAI_TASK_WORKDIR", str(tmp_path))


@pytest.fixture(autouse=True)
def _remove_test_run_transcripts(monkeypatch):
    paths = []
    write_transcript = agent_dispatch._write_run_transcript

    def tracked_write(run):
        path = write_transcript(run)
        paths.append(path)
        return path

    monkeypatch.setattr(agent_dispatch, "_write_run_transcript", tracked_write)
    yield
    for path in paths:
        if path:
            Path(path).unlink(missing_ok=True)


def _task(description: str, criteria: str, title: str = "t") -> Task:
    return Task(
        title=title,
        description=description,
        agent=AgentType.MINI,
        risk=RiskLevel.R1,
        success_criteria=criteria,
        depends_on=[],
    )


def _stub_llm(monkeypatch, payload):
    def fake(model, prompt, system="", base_url=None):
        return payload(prompt) if callable(payload) else payload

    monkeypatch.setattr(agent_dispatch, "_llm_call", fake)


@needs_bwrap
def test_local_execution_creates_artifact_and_reports_done(tmp_path, monkeypatch):
    artifact = tmp_path / "art.txt"
    _stub_llm(monkeypatch, json.dumps({"command": f"printf %s HELLO_JUSTAI > {artifact}"}))
    task = _task(
        f"Create {artifact} containing HELLO_JUSTAI",
        f"test -f {artifact} && grep -qx HELLO_JUSTAI {artifact}",
    )
    assert not artifact.exists()
    res = _execute_single_local(task)
    assert artifact.read_text() == "HELLO_JUSTAI"
    assert res.status == "done"


def test_no_backend_is_failed_not_done(monkeypatch):
    def boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(agent_dispatch, "_llm_call", boom)
    # Verify would pass (true), but nothing executed -> must NOT be done.
    res = _execute_single_local(_task("do the thing", "true"))
    assert res.status == "failed"
    assert "not executed" in res.result and "no_backend" in res.result


def test_model_refusal_is_failed(monkeypatch):
    _stub_llm(monkeypatch, json.dumps({"skip_reason": "needs a human"}))
    res = _execute_single_local(_task("ambiguous task", "true"))
    assert res.status == "failed"
    assert "refused" in res.result


@needs_bwrap
def test_executed_but_verify_fails(monkeypatch):
    _stub_llm(monkeypatch, json.dumps({"command": "true"}))
    res = _execute_single_local(_task("x", "false"))  # verify exits 1
    assert res.status == "failed"
    assert "verify failed" in res.result


@needs_bwrap
def test_executed_without_criteria_is_unverified(monkeypatch):
    _stub_llm(monkeypatch, json.dumps({"command": "true"}))
    res = _execute_single_local(_task("x", ""))  # no criteria -> verify None
    assert res.status == "unverified"


def test_catastrophic_command_is_blocked_and_not_run(tmp_path, monkeypatch):
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("safe")
    _stub_llm(monkeypatch, json.dumps({"command": "rm -rf /"}))
    outcome, _ = _perform_task_action(_task("wipe", "true"))
    assert outcome == "blocked"
    assert sentinel.read_text() == "safe"  # nothing destructive ran
    # Guard precision: real catastrophes caught, ordinary rm -rf left alone.
    assert _is_catastrophic("rm -rf /")
    assert _is_catastrophic("sudo rm -rf /*")
    assert _is_catastrophic(":(){ :|:& };:")
    assert not _is_catastrophic("rm -rf ./build")
    assert not _is_catastrophic("rm -rf /tmp/justai-scratch")


@needs_bwrap
def test_parse_action_tolerates_fenced_json(monkeypatch):
    fenced = "```json\n{\"command\": \"echo hi\"}\n```"
    _stub_llm(monkeypatch, fenced)
    res = _execute_single_local(_task("say hi", "echo hi | grep -q hi"))
    assert res.status == "done"


@needs_bwrap
def test_end_to_end_local_run_flips_artifact_and_completes(tmp_path, monkeypatch):
    artifact = tmp_path / "e2e.txt"
    explore = _task("Explore the workspace", "echo ok", title="Explore")
    create = _task(
        f"Create {artifact} containing exactly HELLO_JUSTAI",
        f"test -f {artifact} && grep -qx HELLO_JUSTAI {artifact}",
        title="Create file",
    )
    create.depends_on = [0]

    def fake(model, prompt, system="", base_url=None):
        if "Explore" in prompt:
            return json.dumps({"command": "echo exploring"})
        return json.dumps({"command": f"printf %s HELLO_JUSTAI > {artifact}"})

    monkeypatch.setattr(agent_dispatch, "_llm_call", fake)

    assert not artifact.exists()  # ABSENT
    results = escalate_plan([explore, create], mode="local")
    summary = synthesize("goal", "intent", results)

    assert artifact.read_text() == "HELLO_JUSTAI"  # PRESENT
    assert summary.done == 2
    assert summary.status == "complete"


@needs_bwrap
def test_owned_runner_uses_chunk_as_its_only_task_authority(tmp_path, monkeypatch):
    artifact = tmp_path / "owned-runner.txt"
    observed_prompts = []

    def fake(model, prompt, system="", base_url=None):
        observed_prompts.append(prompt)
        return json.dumps({"command": f"printf %s CHUNK_ONLY > {artifact}"})

    monkeypatch.setattr(agent_dispatch, "_llm_call", fake)
    chunk = Chunk(
        goal="Chunk authority must reach the model unchanged",
        success_criteria=f"test -f {artifact} && grep -qx CHUNK_ONLY {artifact}",
        budget=Budget(move_budget=1, observation_budget=256),
    )

    runner = JustAiSandboxRunner()
    assert isinstance(runner, AgentRunner)
    result = runner.run(chunk)

    try:
        assert observed_prompts and chunk.goal in observed_prompts[0]
        assert artifact.read_text() == "CHUNK_ONLY"
        assert result.success is True
        assert [action.action_type for action in result.actions] == ["bash", "verify"]
        assert {record.action_id for record in result.results} == {
            action.action_id for action in result.actions
        }
        transcript = Path(result.transcript_path)
        assert transcript.is_file()
        evidence = json.loads(transcript.read_text())
        assert evidence["goal"] == chunk.goal
        assert evidence["success"] is True
    finally:
        if result.transcript_path:
            Path(result.transcript_path).unlink(missing_ok=True)


def test_owned_runner_rejects_non_safe_policy_before_any_side_effect(monkeypatch):
    def unexpected_model_call(*args, **kwargs):
        raise AssertionError("model must not run for a non-safe policy")

    monkeypatch.setattr(agent_dispatch, "_llm_call", unexpected_model_call)
    chunk = Chunk(
        goal="do not run",
        success_criteria="true",
        budget=Budget(move_budget=1, observation_budget=256),
    )

    result = JustAiSandboxRunner().run(chunk, executor_policy=ExecutorPolicy.OPEN)

    assert result.success is False
    assert result.failure_class is FailureClass.SAFETY_VIOLATION
    assert result.actions == []
    assert result.results == []
    assert result.transcript_path == ""


def test_owned_runner_does_not_record_verification_that_never_ran(monkeypatch):
    _stub_llm(monkeypatch, json.dumps({"command": "true"}))
    monkeypatch.setattr(
        agent_dispatch, "_run_local_command_result", lambda *args, **kwargs: ("ok", "ran")
    )
    monkeypatch.setattr(
        agent_dispatch,
        "_verify_chunk",
        lambda chunk: agent_dispatch._Verification(False, "sandbox unavailable", "fail"),
    )
    chunk = Chunk(
        goal="record only actions that actually ran",
        success_criteria="true",
        budget=Budget(move_budget=1, observation_budget=256),
    )

    result = JustAiSandboxRunner().run(chunk)

    try:
        assert result.success is False
        assert result.failure_class is FailureClass.EMBODIMENT_FAILURE
        assert [action.action_type for action in result.actions] == ["bash"]
        assert [record.status for record in result.results] == ["ok"]
    finally:
        if result.transcript_path:
            Path(result.transcript_path).unlink(missing_ok=True)


def test_owned_runner_enforces_observation_budget_on_returned_evidence(monkeypatch):
    _stub_llm(monkeypatch, json.dumps({"command": "true"}))
    monkeypatch.setattr(
        agent_dispatch,
        "_run_local_command_result",
        lambda *args, **kwargs: ("ok", "x" * 1000),
    )
    monkeypatch.setattr(
        agent_dispatch,
        "_verify_chunk",
        lambda chunk: agent_dispatch._Verification(True, "y" * 1000, "ok", True),
    )
    chunk = Chunk(
        goal="z" * 1000,
        success_criteria="true",
        budget=Budget(move_budget=1, observation_budget=64),
    )

    result = JustAiSandboxRunner().run(chunk)

    try:
        assert result.success is True
        assert len(result.execution_detail) <= 64
        assert len(result.verification_detail) <= 64
        evidence = json.loads(Path(result.transcript_path).read_text())
        assert len(evidence["goal"]) <= 64
        assert len(evidence["execution"]["detail"]) <= 64
        assert len(evidence["verification"]["detail"]) <= 64
    finally:
        if result.transcript_path:
            Path(result.transcript_path).unlink(missing_ok=True)


def test_owned_runner_preserves_marked_raw_tail_evidence(monkeypatch):
    _stub_llm(monkeypatch, json.dumps({"command": "true"}))
    tail = "TAIL_SENTINEL"
    monkeypatch.setattr(
        agent_dispatch,
        "_run_local_command_result",
        lambda *args, **kwargs: ("fail", "x" * 1500 + tail),
    )
    monkeypatch.setattr(
        agent_dispatch,
        "_verify_chunk",
        lambda chunk: agent_dispatch._Verification(False, "verify failed", "fail", True),
    )
    chunk = Chunk(
        goal="retain the raw process tail",
        success_criteria="true",
        budget=Budget(move_budget=1, observation_budget=1200),
    )

    result = JustAiSandboxRunner().run(chunk)

    try:
        assert result.execution_detail.startswith("…")
        assert result.execution_detail.endswith(tail)
        evidence = json.loads(Path(result.transcript_path).read_text())
        assert evidence["execution"]["detail"].startswith("…")
        assert evidence["execution"]["detail"].endswith(tail)
    finally:
        if result.transcript_path:
            Path(result.transcript_path).unlink(missing_ok=True)


def test_owned_runner_marks_one_character_observation_budget(monkeypatch):
    _stub_llm(monkeypatch, json.dumps({"command": "true"}))
    monkeypatch.setattr(
        agent_dispatch, "_run_local_command_result", lambda *args, **kwargs: ("ok", "ran")
    )
    monkeypatch.setattr(
        agent_dispatch,
        "_verify_chunk",
        lambda chunk: agent_dispatch._Verification(True, "verified", "ok", True),
    )
    chunk = Chunk(
        goal="longer than one character",
        success_criteria="true",
        budget=Budget(move_budget=1, observation_budget=1),
    )

    result = JustAiSandboxRunner().run(chunk)

    try:
        assert result.execution_detail == "…"
        assert result.verification_detail == "…"
        evidence = json.loads(Path(result.transcript_path).read_text())
        assert evidence["goal"] == "…"
        assert evidence["execution"]["detail"] == "…"
        assert evidence["verification"]["detail"] == "…"
    finally:
        if result.transcript_path:
            Path(result.transcript_path).unlink(missing_ok=True)


def test_owned_runner_preserves_marked_failed_verification_tail(monkeypatch):
    _stub_llm(monkeypatch, json.dumps({"command": "true"}))
    tail = "VERIFY_TAIL"
    monkeypatch.setattr(
        agent_dispatch, "_run_local_command_result", lambda *args, **kwargs: ("ok", "ran")
    )
    monkeypatch.setattr(
        agent_dispatch,
        "run_sandboxed",
        lambda *args, **kwargs: SimpleNamespace(
            timed_out=False, returncode=1, stdout="", stderr="x" * 1500 + tail
        ),
    )
    chunk = Chunk(
        goal="retain a failed verifier tail",
        success_criteria="false",
        budget=Budget(move_budget=1, observation_budget=1200),
    )

    result = JustAiSandboxRunner().run(chunk)

    try:
        assert result.success is False
        assert result.verification_detail.startswith("…")
        assert result.verification_detail.endswith(tail)
        evidence = json.loads(Path(result.transcript_path).read_text())
        assert evidence["verification"]["detail"].startswith("…")
        assert evidence["verification"]["detail"].endswith(tail)
    finally:
        if result.transcript_path:
            Path(result.transcript_path).unlink(missing_ok=True)


@needs_bwrap
def test_owned_runner_keeps_missing_criteria_unverified(monkeypatch):
    _stub_llm(monkeypatch, json.dumps({"command": "true"}))
    chunk = Chunk(
        goal="run one command without a completion criterion",
        success_criteria="",
        budget=Budget(move_budget=1, observation_budget=256),
    )

    result = JustAiSandboxRunner().run(chunk)

    try:
        assert result.success is False
        assert result.failure_class is None
        assert [action.action_type for action in result.actions] == ["bash"]
        assert [record.status for record in result.results] == ["ok"]
    finally:
        if result.transcript_path:
            Path(result.transcript_path).unlink(missing_ok=True)


@needs_bwrap
def test_transcript_write_failure_does_not_promote_or_demote_run(monkeypatch):
    _stub_llm(monkeypatch, json.dumps({"command": "true"}))
    monkeypatch.setattr(agent_dispatch, "_write_run_transcript", lambda run: "")
    chunk = Chunk(
        goal="run with an unavailable observation artifact",
        success_criteria="true",
        budget=Budget(move_budget=1, observation_budget=256),
    )

    result = JustAiSandboxRunner().run(chunk)

    assert result.success is True
    assert result.transcript_path == ""
