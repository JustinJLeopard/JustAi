"""Sprint 12 integration tests — swarm dispatch wired into orchestrator."""
from __future__ import annotations
import json
import pytest
from unittest.mock import patch, MagicMock
from justai.planner import Task, RiskLevel, AgentType, Plan
from justai.intent_gate import IntentResult, Intent
from justai.reviewer import ReviewResult


def _mock_rpc_response(result_text: str):
    resp = MagicMock()
    resp.status = 200
    resp.read.return_value = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "result": {"content": [{"type": "text", "text": result_text}]}
    }).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestOrchestratorSwarmFlag:
    def test_run_with_swarm_flag(self):
        """orchestrator.run(swarm=True) should use escalate_plan with mode=swarm."""
        from justai.orchestrator import run
        from justai.delegator import DelegationResult

        intent = IntentResult(intent=Intent.EXECUTION, confidence=0.95, reasoning="test", clarifying_question="")
        plan = Plan(goal="test", tasks=[
            Task(title="t1", description="do thing", agent=AgentType.MINI,
                 risk=RiskLevel.R0, success_criteria="echo ok"),
        ])
        review = ReviewResult(approved=True, feedback=[])
        done_result = [DelegationResult(task_id="1", title="t1", status="done", result="ok", duration_seconds=1.0)]

        mock_trace_ctx = MagicMock()
        mock_trace_ctx.__enter__ = MagicMock(return_value=mock_trace_ctx)
        mock_trace_ctx.__exit__ = MagicMock(return_value=False)
        mock_trace_ctx.end = MagicMock()

        with patch("justai.orchestrator.classify", return_value=intent), \
             patch("justai.orchestrator.decompose", return_value=plan), \
             patch("justai.orchestrator.review", return_value=review), \
             patch("justai.orchestrator.preflight", return_value=[]), \
             patch("justai.orchestrator.print_preflight", return_value=True), \
             patch("justai.orchestrator.flush_traces"), \
             patch("justai.orchestrator._memory"), \
             patch("justai.orchestrator._ledger"), \
             patch("justai.orchestrator.OrchestratorHook"), \
             patch("justai.orchestrator.trace_generation", return_value=mock_trace_ctx), \
             patch("justai.orchestrator.trace_event"), \
             patch("justai.orchestrator.escalate_plan", return_value=done_result) as mock_esc:
            result = run("test goal", auto=True, swarm=True)
            assert result.status in ("complete", "partial")
            assert result.task_count == 1
            # Verify escalate_plan was called with mode="swarm"
            mock_esc.assert_called_once()
            assert mock_esc.call_args[1]["mode"] == "swarm"

    def test_run_without_swarm_still_works(self):
        """Existing local path still works when swarm=False."""
        from justai.orchestrator import run

        intent = IntentResult(intent=Intent.EXECUTION, confidence=0.95, reasoning="test", clarifying_question="")
        plan = Plan(goal="test", tasks=[
            Task(title="t1", description="do thing", agent=AgentType.MINI,
                 risk=RiskLevel.R0, success_criteria="echo ok"),
        ])
        review = ReviewResult(approved=True, feedback=[])

        mock_trace_ctx = MagicMock()
        mock_trace_ctx.__enter__ = MagicMock(return_value=mock_trace_ctx)
        mock_trace_ctx.__exit__ = MagicMock(return_value=False)
        mock_trace_ctx.end = MagicMock()

        with patch("justai.orchestrator.classify", return_value=intent), \
             patch("justai.orchestrator.decompose", return_value=plan), \
             patch("justai.orchestrator.review", return_value=review), \
             patch("justai.orchestrator.preflight", return_value=[]), \
             patch("justai.orchestrator.print_preflight", return_value=True), \
             patch("justai.orchestrator.flush_traces"), \
             patch("justai.orchestrator._memory"), \
             patch("justai.orchestrator._ledger"), \
             patch("justai.orchestrator.OrchestratorHook"), \
             patch("justai.orchestrator.trace_generation", return_value=mock_trace_ctx), \
             patch("justai.orchestrator.trace_event"):
            result = run("test goal", auto=True, local=True)
            assert result.status in ("complete", "partial", "failed")
            assert result.task_count == 1


class TestSwarmHealth:
    def test_check_swarm_healthy(self):
        from justai.health import check_swarm
        swarm_resp = json.dumps({"success": True, "swarmId": "swarm-h1", "status": "running", "agentCount": 5})
        with patch("urllib.request.urlopen", return_value=_mock_rpc_response(swarm_resp)):
            status = check_swarm()
            assert status.ok is True
            assert "running" in status.detail

    def test_check_swarm_unreachable(self):
        from justai.health import check_swarm
        with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
            status = check_swarm()
            assert status.ok is False
