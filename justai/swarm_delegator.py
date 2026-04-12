"""
JustAi — Swarm Delegator
==========================
Parallel task dispatch via claude-flow's swarm MCP (JSON-RPC 2.0 on :3100).

Instead of posting tasks sequentially to SpacetimeDB and blocking,
this module:
  1. Initializes a swarm with a target agent count
  2. Spawns worker agents into the pool
  3. Groups tasks into dependency waves (tasks with no unmet deps run together)
  4. Dispatches each wave in parallel via coordination_orchestrate
  5. Collects results and feeds them into the next wave

Usage:
    from justai.swarm_delegator import SwarmDelegator
    sd = SwarmDelegator(max_agents=15)
    sd.spawn_agents(15)
    results = sd.dispatch_parallel(tasks, session_ref="sprint-12")
    sd.shutdown()
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass

from justai.planner import Task
from justai.swarm_config import SwarmTier, get_tier

MCP_URL = os.environ.get("JUSTAI_MCP_URL", "http://127.0.0.1:3100")
MCP_RPC = f"{MCP_URL}/rpc"
_REQUEST_TIMEOUT = 15


@dataclass
class SwarmResult:
    task_index: int
    task_id: str
    title: str
    status: str        # "done" | "failed" | "timeout" | "skipped" | "error"
    result: str
    agent_id: str
    duration_seconds: float


def _rpc_call(method: str, params: dict) -> dict:
    """Make a JSON-RPC 2.0 call to the MCP server."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": "tools/call",
        "params": {"name": method, "arguments": params},
    }).encode()
    req = urllib.request.Request(MCP_RPC, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
        data = json.loads(resp.read())
    content = data.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            return json.loads(item["text"])
    return {}


def _dependency_waves(tasks: list[Task]) -> list[list[int]]:
    """Group task indices into waves respecting depends_on ordering.
    Tasks with no unmet dependencies go in the current wave."""
    n = len(tasks)
    done: set[int] = set()
    waves: list[list[int]] = []
    remaining = set(range(n))

    while remaining:
        wave = []
        for i in sorted(remaining):
            deps = set(tasks[i].depends_on)
            if deps.issubset(done):
                wave.append(i)
        if not wave:
            wave = sorted(remaining)
        waves.append(wave)
        done.update(wave)
        remaining -= set(wave)

    return waves


class SwarmDelegator:
    """Manages a claude-flow swarm for parallel task dispatch."""

    def __init__(self, max_agents: int = 15):
        tier = get_tier(max_agents)
        self.max_agents = tier.max_agents
        self.tier = tier
        self._agents: list[str] = []
        self.swarm_id: str = ""
        self._init_swarm(tier)

    def _init_swarm(self, tier: SwarmTier) -> None:
        result = _rpc_call("swarm_init", {
            "topology": tier.topology,
            "maxAgents": tier.max_agents,
            "strategy": tier.strategy,
        })
        self.swarm_id = result.get("swarmId", "")

    def spawn_agents(self, count: int) -> list[str]:
        """Spawn `count` worker agents and return their IDs."""
        agent_ids = []
        for i in range(count):
            result = _rpc_call("agent_spawn", {
                "type": "worker",
                "role": f"task-worker-{i}",
                "capabilities": ["code-execution", "bash"],
            })
            if result.get("success"):
                agent_ids.append(result["agentId"])
        self._agents = agent_ids
        return agent_ids

    def dispatch_parallel(
        self,
        tasks: list[Task],
        session_ref: str = "",
    ) -> list[SwarmResult]:
        """Dispatch tasks in dependency waves, each wave in parallel."""
        waves = _dependency_waves(tasks)
        all_results: dict[int, SwarmResult] = {}

        for wave_num, wave_indices in enumerate(waves):
            skip_indices = set()
            for idx in wave_indices:
                for dep in tasks[idx].depends_on:
                    if dep in all_results and all_results[dep].status != "done":
                        skip_indices.add(idx)
                        break

            dispatch_indices = [i for i in wave_indices if i not in skip_indices]

            for idx in skip_indices:
                all_results[idx] = SwarmResult(
                    task_index=idx, task_id="skipped", title=tasks[idx].title,
                    status="skipped", result="dependency failed",
                    agent_id="", duration_seconds=0,
                )

            if not dispatch_indices:
                continue

            start = time.time()
            agent_ids = self._agents[:len(dispatch_indices)] if self._agents else ["default"]
            task_descriptions = [
                f"[{i}] {tasks[i].title}: {tasks[i].description}" for i in dispatch_indices
            ]
            orch_result = _rpc_call("coordination_orchestrate", {
                "task": json.dumps(task_descriptions),
                "agents": agent_ids,
                "strategy": "parallel",
            })

            wave_duration = time.time() - start
            orch_id = orch_result.get("orchestrationId", "")
            orch_results = orch_result.get("results", [])

            for j, idx in enumerate(dispatch_indices):
                if j < len(orch_results):
                    r = orch_results[j]
                    status = r.get("status", "done")
                    result_text = r.get("result", "completed via swarm")
                    agent_id = r.get("agentId", agent_ids[j % len(agent_ids)])
                else:
                    status = "done"
                    result_text = "dispatched via swarm"
                    agent_id = agent_ids[j % len(agent_ids)] if agent_ids else ""

                all_results[idx] = SwarmResult(
                    task_index=idx, task_id=f"swarm-{orch_id}-{idx}",
                    title=tasks[idx].title, status=status,
                    result=result_text, agent_id=agent_id,
                    duration_seconds=wave_duration / max(len(dispatch_indices), 1),
                )

        return [all_results[i] for i in range(len(tasks)) if i in all_results]

    def shutdown(self) -> None:
        """Terminate all agents and shut down the swarm."""
        for agent_id in self._agents:
            try:
                _rpc_call("agent_terminate", {"agentId": agent_id})
            except Exception:
                pass
        self._agents = []
        try:
            _rpc_call("swarm_shutdown", {})
        except Exception:
            pass
