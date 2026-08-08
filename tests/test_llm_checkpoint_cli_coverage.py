"""Non-backend coverage tests salvaged from obsolete coverage padding files."""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch


def _make_http_mock(response_dict: dict):
    buf = io.BytesIO(json.dumps(response_dict).encode())
    cm = MagicMock()
    cm.__enter__ = lambda s: buf
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def test_intent_call_litellm_strips_markdown_json_fence():
    from justai.intent_gate import _call_litellm

    raw = '```json\n{"intent": "execution", "confidence": 0.9, "reasoning": "r", "clarifying_question": ""}\n```'
    response = {"choices": [{"message": {"content": raw}}]}
    with patch("justai.intent_gate.urllib.request.urlopen", return_value=_make_http_mock(response)):
        result = _call_litellm("test goal")

    assert result["intent"] == "execution"


def test_planner_call_litellm_includes_context():
    from justai.scope_planner import _call_litellm

    response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "tasks": [
                                {
                                    "title": "T",
                                    "description": "D",
                                    "agent": "mini",
                                    "risk": "R0",
                                    "success_criteria": "echo done",
                                    "depends_on": [],
                                }
                            ]
                        }
                    )
                }
            }
        ]
    }
    with patch(
        "justai.scope_planner.urllib.request.urlopen", return_value=_make_http_mock(response)
    ) as mock_open:
        _call_litellm("add endpoint", context="Prior attempt failed")

    payload = json.loads(mock_open.call_args[0][0].data)
    assert "Prior attempt failed" in payload["messages"][-1]["content"]


def test_reviewer_merges_feedback_and_suggestions():
    from justai.reviewer import review
    from justai.scope_planner import AgentType, Plan, RiskLevel, Task

    plan = Plan(
        goal="add endpoint",
        tasks=[Task("Explore", "Read.", AgentType.MINI, RiskLevel.R0, "echo done", [])],
    )
    with patch(
        "justai.reviewer._call_litellm",
        return_value={
            "approved": False,
            "feedback": ["Task too large"],
            "suggestions": ["Split it"],
        },
    ):
        result = review(plan)

    assert result.approved is False
    assert "Task too large" in result.feedback
    assert "Split it" in result.feedback


def test_checkpoint_gate_file_write_and_read_roundtrip(tmp_path, monkeypatch):
    from justai.checkpoint import GateIdentity, _read_gate, _write_gate, cleanup_run, gate_dir
    from justai.run_identity import new_run_id

    monkeypatch.setattr("justai.checkpoint.GATE_SIGNAL_DIR", tmp_path / "gates")
    gate = GateIdentity(run_id=new_run_id(), index=0, session_ref="roundtrip")
    _write_gate(gate, "approved", "looks good")

    result = _read_gate(gate)
    assert result["status"] == "approved"
    assert result["reason"] == "looks good"
    assert result["run_id"] == gate.run_id, "a record must say which run it decided"

    assert cleanup_run(gate.run_id) == 1
    assert not list(gate_dir(gate.run_id).glob("plan-*.json"))


def test_runtime_env_sets_expected_root_aliases():
    from tools.justai_runtime import repo_root, runtime_env

    env = runtime_env()

    assert env["JUSTAI_ROOT"] == str(repo_root())
    assert env["JUSTAI_SAFE_MINI_MODE"] == "stub"
    assert "JUSTAI_RUN_LOG_FILE" in env


def test_check_swarm_unreachable_reports_not_ok():
    from justai.health import check_swarm

    with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
        status = check_swarm()

    assert status.ok is False
