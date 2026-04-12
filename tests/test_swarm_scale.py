"""
Parametric scale tests for swarm dispatch.
Tests swarm init, agent spawn, and parallel dispatch at each tier.
All MCP calls are mocked — these test the dispatch logic, not the MCP server.
"""
from __future__ import annotations
import json
import time
import pytest
from unittest.mock import patch, MagicMock
from justai.planner import Task, RiskLevel, AgentType
from justai.swarm_delegator import SwarmDelegator


def _make_tasks(n: int) -> list[Task]:
    """Generate n independent tasks."""
    return [
        Task(
            title=f"task-{i}",
            description=f"Execute task {i} of {n}",
            agent=AgentType.MINI,
            risk=RiskLevel.R0,
            success_criteria="echo ok",
            depends_on=[],
        )
        for i in range(n)
    ]


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


TIERS = [15, 50, 150, 1500]


@pytest.mark.parametrize("agent_count", TIERS)
class TestSwarmScale:
    def test_swarm_init_at_tier(self, agent_count: int):
        swarm_resp = json.dumps({"success": True, "swarmId": f"swarm-scale-{agent_count}", "maxAgents": agent_count})
        with patch("urllib.request.urlopen", return_value=_mock_rpc_response(swarm_resp)):
            sd = SwarmDelegator(max_agents=agent_count)
            assert sd.max_agents >= agent_count

    def test_spawn_agents_at_tier(self, agent_count: int):
        swarm_resp = json.dumps({"success": True, "swarmId": f"swarm-scale-{agent_count}", "maxAgents": agent_count})
        agent_resp = json.dumps({"success": True, "agentId": "agent-scale", "status": "registered"})
        spawn_count = min(agent_count, 10)
        responses = [_mock_rpc_response(swarm_resp)] + [_mock_rpc_response(agent_resp)] * spawn_count
        with patch("urllib.request.urlopen", side_effect=responses):
            sd = SwarmDelegator(max_agents=agent_count)
            agents = sd.spawn_agents(spawn_count)
            assert len(agents) == spawn_count

    def test_dispatch_at_tier(self, agent_count: int):
        task_count = min(agent_count, 10)
        tasks = _make_tasks(task_count)
        swarm_resp = json.dumps({"success": True, "swarmId": f"swarm-scale-{agent_count}", "maxAgents": agent_count})
        agent_resp = json.dumps({"success": True, "agentId": "agent-scale", "status": "registered"})
        orch_resp = json.dumps({
            "success": True, "orchestrationId": f"orch-scale-{agent_count}", "status": "completed",
            "results": [{"agentId": "agent-scale", "status": "done", "result": "ok"} for _ in range(task_count)],
        })
        responses = (
            [_mock_rpc_response(swarm_resp)]
            + [_mock_rpc_response(agent_resp)] * task_count
            + [_mock_rpc_response(orch_resp)]
        )
        with patch("urllib.request.urlopen", side_effect=responses):
            sd = SwarmDelegator(max_agents=agent_count)
            sd.spawn_agents(task_count)
            start = time.time()
            results = sd.dispatch_parallel(tasks, session_ref="scale-test")
            elapsed = time.time() - start
            assert len(results) == task_count
            assert all(r.status == "done" for r in results)
            assert elapsed < 2.0

    def test_shutdown_at_tier(self, agent_count: int):
        swarm_resp = json.dumps({"success": True, "swarmId": f"swarm-scale-{agent_count}", "maxAgents": agent_count})
        spawn_count = min(agent_count, 5)
        agent_resp = json.dumps({"success": True, "agentId": "agent-scale", "status": "registered"})
        term_resp = json.dumps({"success": True, "terminated": True})
        shutdown_resp = json.dumps({"success": True, "status": "shutdown"})
        responses = (
            [_mock_rpc_response(swarm_resp)]
            + [_mock_rpc_response(agent_resp)] * spawn_count
            + [_mock_rpc_response(term_resp)] * spawn_count
            + [_mock_rpc_response(shutdown_resp)]
        )
        with patch("urllib.request.urlopen", side_effect=responses):
            sd = SwarmDelegator(max_agents=agent_count)
            sd.spawn_agents(spawn_count)
            sd.shutdown()
            assert sd._agents == []
