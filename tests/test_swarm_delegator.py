"""Tests for swarm-based parallel delegation."""
from __future__ import annotations
import json
import pytest
from unittest.mock import patch, MagicMock
from justai.planner import Task, RiskLevel, AgentType


def _make_task(title: str, desc: str = "", depends: list[int] | None = None) -> Task:
    return Task(
        title=title,
        description=desc or f"Do {title}",
        agent=AgentType.MINI,
        risk=RiskLevel.R0,
        success_criteria="echo ok",
        depends_on=depends or [],
    )


def _mock_rpc_response(result_text: str):
    """Create a mock urllib response for MCP JSON-RPC."""
    resp = MagicMock()
    resp.status = 200
    resp.read.return_value = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "result": {"content": [{"type": "text", "text": result_text}]}
    }).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestSwarmConfig:
    def test_tier_15_defaults(self):
        from justai.swarm_config import SwarmTier, get_tier
        tier = get_tier(15)
        assert tier.max_agents == 15
        assert tier.topology == "hierarchical-mesh"
        assert tier.strategy == "specialized"

    def test_tier_150(self):
        from justai.swarm_config import get_tier
        tier = get_tier(150)
        assert tier.max_agents == 150

    def test_tier_1500(self):
        from justai.swarm_config import get_tier
        tier = get_tier(1500)
        assert tier.max_agents == 1500

    def test_custom_tier(self):
        from justai.swarm_config import SwarmTier
        tier = SwarmTier(max_agents=42, topology="mesh", strategy="round-robin")
        assert tier.max_agents == 42

    def test_get_tier_rounds_up(self):
        from justai.swarm_config import get_tier
        tier = get_tier(20)
        assert tier.max_agents == 50  # rounds up to next defined tier


class TestSwarmDelegator:
    def test_init_swarm(self):
        from justai.swarm_delegator import SwarmDelegator
        swarm_resp = json.dumps({"success": True, "swarmId": "swarm-test-1", "maxAgents": 15})
        with patch("urllib.request.urlopen", return_value=_mock_rpc_response(swarm_resp)):
            sd = SwarmDelegator(max_agents=15)
            assert sd.swarm_id == "swarm-test-1"
            assert sd.max_agents == 15

    def test_spawn_agents(self):
        from justai.swarm_delegator import SwarmDelegator
        swarm_resp = json.dumps({"success": True, "swarmId": "swarm-test-2", "maxAgents": 15})
        agent_resp = json.dumps({"success": True, "agentId": "agent-001", "status": "registered"})
        responses = [_mock_rpc_response(swarm_resp)] + [_mock_rpc_response(agent_resp)] * 3
        with patch("urllib.request.urlopen", side_effect=responses):
            sd = SwarmDelegator(max_agents=15)
            agents = sd.spawn_agents(3)
            assert len(agents) == 3
            assert all(a == "agent-001" for a in agents)

    def test_dispatch_parallel(self):
        from justai.swarm_delegator import SwarmDelegator, SwarmResult
        tasks = [_make_task("task-A"), _make_task("task-B"), _make_task("task-C")]
        swarm_resp = json.dumps({"success": True, "swarmId": "swarm-test-3", "maxAgents": 15})
        agent_resp = json.dumps({"success": True, "agentId": "agent-002", "status": "registered"})
        orch_resp = json.dumps({"success": True, "orchestrationId": "orch-001", "status": "completed",
                                 "results": [
                                     {"agentId": "agent-002", "status": "done", "result": "ok"},
                                     {"agentId": "agent-002", "status": "done", "result": "ok"},
                                     {"agentId": "agent-002", "status": "done", "result": "ok"},
                                 ]})
        responses = (
            [_mock_rpc_response(swarm_resp)]
            + [_mock_rpc_response(agent_resp)] * 3
            + [_mock_rpc_response(orch_resp)]
        )
        with patch("urllib.request.urlopen", side_effect=responses):
            sd = SwarmDelegator(max_agents=15)
            sd.spawn_agents(3)
            results = sd.dispatch_parallel(tasks, session_ref="test")
            assert len(results) == 3
            assert all(r.status == "done" for r in results)

    def test_dispatch_respects_dependencies(self):
        from justai.swarm_delegator import SwarmDelegator
        tasks = [_make_task("task-A"), _make_task("task-B", depends=[0])]
        swarm_resp = json.dumps({"success": True, "swarmId": "swarm-test-4", "maxAgents": 15})
        agent_resp = json.dumps({"success": True, "agentId": "agent-003", "status": "registered"})
        orch_resp_1 = json.dumps({"success": True, "orchestrationId": "orch-002", "status": "completed",
                                   "results": [{"agentId": "agent-003", "status": "done", "result": "ok"}]})
        orch_resp_2 = json.dumps({"success": True, "orchestrationId": "orch-003", "status": "completed",
                                   "results": [{"agentId": "agent-003", "status": "done", "result": "ok"}]})
        responses = (
            [_mock_rpc_response(swarm_resp)]
            + [_mock_rpc_response(agent_resp)] * 2
            + [_mock_rpc_response(orch_resp_1)]
            + [_mock_rpc_response(orch_resp_2)]
        )
        with patch("urllib.request.urlopen", side_effect=responses):
            sd = SwarmDelegator(max_agents=15)
            sd.spawn_agents(2)
            results = sd.dispatch_parallel(tasks, session_ref="test")
            assert len(results) == 2
            assert results[0].status == "done"
            assert results[1].status == "done"

    def test_dispatch_skips_on_failed_dependency(self):
        from justai.swarm_delegator import SwarmDelegator
        tasks = [_make_task("task-A"), _make_task("task-B", depends=[0])]
        swarm_resp = json.dumps({"success": True, "swarmId": "swarm-test-5", "maxAgents": 15})
        agent_resp = json.dumps({"success": True, "agentId": "agent-004", "status": "registered"})
        orch_resp = json.dumps({"success": True, "orchestrationId": "orch-004", "status": "completed",
                                 "results": [{"agentId": "agent-004", "status": "failed", "result": "error"}]})
        responses = (
            [_mock_rpc_response(swarm_resp)]
            + [_mock_rpc_response(agent_resp)] * 2
            + [_mock_rpc_response(orch_resp)]
        )
        with patch("urllib.request.urlopen", side_effect=responses):
            sd = SwarmDelegator(max_agents=15)
            sd.spawn_agents(2)
            results = sd.dispatch_parallel(tasks, session_ref="test")
            assert len(results) == 2
            assert results[0].status == "failed"
            assert results[1].status == "skipped"

    def test_shutdown(self):
        from justai.swarm_delegator import SwarmDelegator
        swarm_resp = json.dumps({"success": True, "swarmId": "swarm-test-6", "maxAgents": 15})
        term_resp = json.dumps({"success": True, "terminated": True})
        shutdown_resp = json.dumps({"success": True, "status": "shutdown"})
        responses = (
            [_mock_rpc_response(swarm_resp)]
            + [_mock_rpc_response(term_resp)]
            + [_mock_rpc_response(shutdown_resp)]
        )
        with patch("urllib.request.urlopen", side_effect=responses):
            sd = SwarmDelegator(max_agents=15)
            sd._agents = ["agent-x"]
            sd.shutdown()
            assert sd._agents == []

    def test_dependency_waves_independent(self):
        from justai.swarm_delegator import _dependency_waves
        tasks = [_make_task("a"), _make_task("b"), _make_task("c")]
        waves = _dependency_waves(tasks)
        assert len(waves) == 1  # all independent -> single wave
        assert set(waves[0]) == {0, 1, 2}

    def test_dependency_waves_chain(self):
        from justai.swarm_delegator import _dependency_waves
        tasks = [_make_task("a"), _make_task("b", depends=[0]), _make_task("c", depends=[1])]
        waves = _dependency_waves(tasks)
        assert len(waves) == 3
        assert waves[0] == [0]
        assert waves[1] == [1]
        assert waves[2] == [2]
