"""Regression tests for real --local task execution (model-driven).

Proves local mode now EXECUTES the task action and only reports a task as
``done`` when it both executed and its success check passed -- while keeping
the honest-completion invariants from the honest-completion fix intact.
"""

from __future__ import annotations

import json

from justai import agent_dispatch
from justai.agent_dispatch import (
    _execute_single_local,
    _is_catastrophic,
    _perform_task_action,
    escalate_plan,
)
from justai.scope_planner import AgentType, RiskLevel, Task
from justai.synthesizer import synthesize


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
    def fake(model, prompt, system=""):
        return payload(prompt) if callable(payload) else payload

    monkeypatch.setattr(agent_dispatch, "_llm_call", fake)


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


def test_executed_but_verify_fails(monkeypatch):
    _stub_llm(monkeypatch, json.dumps({"command": "true"}))
    res = _execute_single_local(_task("x", "false"))  # verify exits 1
    assert res.status == "failed"
    assert "verify failed" in res.result


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


def test_parse_action_tolerates_fenced_json(monkeypatch):
    fenced = "```json\n{\"command\": \"echo hi\"}\n```"
    _stub_llm(monkeypatch, fenced)
    res = _execute_single_local(_task("say hi", "echo hi | grep -q hi"))
    assert res.status == "done"


def test_end_to_end_local_run_flips_artifact_and_completes(tmp_path, monkeypatch):
    artifact = tmp_path / "e2e.txt"
    explore = _task("Explore the workspace", "echo ok", title="Explore")
    create = _task(
        f"Create {artifact} containing exactly HELLO_JUSTAI",
        f"test -f {artifact} && grep -qx HELLO_JUSTAI {artifact}",
        title="Create file",
    )
    create.depends_on = [0]

    def fake(model, prompt, system=""):
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
