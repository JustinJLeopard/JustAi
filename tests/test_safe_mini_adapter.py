import json
import shutil
from pathlib import Path

import pytest
from safe_mini import ExecutorPolicy

import justai.safe_mini_adapter as adapter
from justai.safe_mini_adapter import (
    JustAiBwrapExecutor,
    _guest_environment,
    chunk_from_task,
    run_task,
)
from justai.scope_planner import AgentType, RiskLevel, Task

needs_bwrap = pytest.mark.skipif(shutil.which("bwrap") is None, reason="bwrap not installed")


class FixedActionModel:
    def __init__(self, command: str) -> None:
        self.command = command

    def next(self, transcript: list[dict]) -> str:
        return json.dumps({"action": "bash", "command": self.command})


def task(criteria: str = "") -> Task:
    return Task(
        title="create greeting",
        description="Create greeting.py with a deterministic greeting function.",
        agent=AgentType.MINI,
        risk=RiskLevel.R0,
        success_criteria=criteria,
        session_ref="adapter-smoke",
    )


@needs_bwrap
def test_opt_in_adapter_runs_safe_mini_in_a_fresh_bwrap_worktree(tmp_path: Path):
    source = tmp_path / "source"
    tests = source / "tests"
    tests.mkdir(parents=True)
    (tests / "run_tests.py").write_text(
        "from greeting import greet\n\nassert greet('Justin') == 'Hello, Justin!'\n"
    )
    criteria = "python3 tests/run_tests.py"
    result = run_task(
        task(criteria),
        repo_path=source,
        model=FixedActionModel(
            "printf '%b' \"def greet(name):\\n    return 'Hello, ' + name + '!'\\n\" > greeting.py"
        ),
    )

    assert result.success is True
    assert result.final_tests_pass is True
    assert result.steps == 1
    assert result.worktree_path is None
    assert not (source / "greeting.py").exists()


def test_adapter_blocks_catastrophic_commands_before_bwrap(tmp_path: Path):
    executor = JustAiBwrapExecutor(tmp_path, policy=ExecutorPolicy.SAFE)
    observation = executor.run("rm -rf /")

    assert observation.blocked is True
    assert observation.returncode == 126
    assert executor.blocked_commands == 1
    assert "catastrophic" in observation.output


def test_action_model_translates_justai_json_to_safe_mini_json(monkeypatch):
    monkeypatch.setattr(adapter, "_execution_endpoint", lambda: "http://127.0.0.1:8085/v1")
    monkeypatch.setattr(adapter, "_llm_call", lambda *args, **kwargs: '{"command": "pwd"}')

    response = adapter.JustAiActionModel("test-model").next([{"content": "task"}])

    assert json.loads(response) == {"action": "bash", "command": "pwd"}


def test_action_model_keeps_justai_refusal_non_executable(monkeypatch):
    monkeypatch.setattr(adapter, "_execution_endpoint", lambda: "http://127.0.0.1:8085/v1")
    monkeypatch.setattr(adapter, "_llm_call", lambda *args, **kwargs: '{"skip_reason": "declined"}')

    response = adapter.JustAiActionModel("test-model").next([{"content": "task"}])

    assert json.loads(response)["action"] == "invalid"


def test_adapter_replaces_host_pythonpath_with_its_fresh_worktree(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("PYTHONPATH", "/host/pythonpath-that-must-not-leak")

    environment = _guest_environment(tmp_path)

    assert environment["PYTHONPATH"] == str(tmp_path)
    assert "/host/" not in environment["PYTHONPATH"]
