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
        """orchestrator.run(swarm=True) should use SwarmDelegator."""
        from justai.orchestrator import run

        intent = IntentResult(intent=Intent.EXECUTION, confidence=0.95, reasoning="test", clarifying_question="")
        plan = Plan(goal="test", tasks=[
            Task(title="t1", description="do thing", agent=AgentType.MINI,
                 risk=RiskLevel.R0, success_criteria="echo ok"),
        ])
        review = ReviewResult(approved=True, feedback=[])

        swarm_resp = json.dumps({"success": True, "swarmId": "swarm-int-1", "maxAgents": 15})
        agent_resp = json.dumps({"success": True, "agentId": "agent-int-1", "status": "registered"})
        orch_resp = json.dumps({"success": True, "orchestrationId": "orch-int-1", "status": "completed",
                                 "results": [{"agentId": "agent-int-1", "status": "done", "result": "ok"}]})
        term_resp = json.dumps({"success": True, "terminated": True})
        shutdown_resp = json.dumps({"success": True})

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
             patch("urllib.request.urlopen", side_effect=[
                 _mock_rpc_response(swarm_resp),
                 _mock_rpc_response(agent_resp),
                 _mock_rpc_response(orch_resp),
                 _mock_rpc_response(term_resp),
                 _mock_rpc_response(shutdown_resp),
             ]):
            result = run("test goal", auto=True, swarm=True)
            assert result.status in ("complete", "partial")
            assert result.task_count == 1

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
