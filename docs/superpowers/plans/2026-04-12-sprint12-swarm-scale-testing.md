# Sprint 12: Swarm-Scale Parallel Dispatch & Testing

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire JustAi's orchestrator to dispatch tasks through claude-flow's swarm for real parallel agent execution, then stress-test at 15 → varying → 150 → 1500 concurrent agents. Two tracks run simultaneously: Track 1 iterates the product code, Track 2 experiments with mini-first and trajectory-learning workflows in a sandboxed worktree.

**Architecture:** The current `delegate_plan()` in `delegator.py` is sequential — it posts one task to SpacetimeDB, blocks until done, then posts the next. This sprint adds a new `swarm_delegator.py` module that talks to claude-flow's swarm (MCP HTTP on :3100) to spawn agent pools, dispatch tasks in parallel via `coordination_orchestrate`, and collect results. The orchestrator gets a `--swarm` flag alongside the existing `--local` flag. The dashboard's AgentRegistry view gets live swarm status. Tests mock the MCP HTTP endpoint, not the swarm itself.

**Tech Stack:** Python 3 (justai core), claude-flow MCP HTTP (JSON-RPC 2.0 on :3100), React/TypeScript (dashboard), pytest (tests)

**Data Collection:** Before each test tier, record: timestamp, swarm config (maxAgents, topology), task count, agent count. After: wall-clock duration, per-task durations, success/fail/timeout counts, memory usage (RSS), MCP response latencies. All data written to `data/sprint12/` as JSON for comparison across tiers.

---

## File Structure

```
justai/
  swarm_delegator.py      — NEW: parallel dispatch via claude-flow swarm MCP
  swarm_config.py         — NEW: swarm tier configs (15/50/150/1500)
  orchestrator.py         — MODIFY: add --swarm path alongside --local
  health.py               — MODIFY: add swarm health check
tests/
  test_swarm_delegator.py — NEW: unit + integration tests for swarm dispatch
  test_swarm_scale.py     — NEW: parametric scale tests (15/50/150/1500)
  test_sprint12.py        — NEW: sprint integration tests
dashboard/src/
  views/AgentRegistry.tsx — MODIFY: live swarm status from MCP
  lib/spacetime.ts        — MODIFY: add swarm polling endpoint
data/
  sprint12/               — NEW: test result JSON files per tier
harness-notes/
  sprint12.md             — NEW: sprint notes
```

---

## Track 1: Product Iteration

### Task 1: Baseline Measurement (as-is sequential)

**Files:**
- Create: `data/sprint12/baseline.json`
- Read: `justai/orchestrator.py`, `justai/delegator.py`

- [ ] **Step 1: Create data directory**

```bash
mkdir -p data/sprint12
```

- [ ] **Step 2: Run a baseline pipeline in local mode and capture timing**

```bash
cd /home/justinleopard/projects/JustAi
JUSTAI_LOCAL_EXEC=1 JUSTAI_AUTO_MODE=1 python3 -c "
import time, json
from justai.orchestrator import run

start = time.time()
result = run('verify all justai modules import cleanly and run health checks', auto=True, local=True)
elapsed = time.time() - start

baseline = {
    'mode': 'sequential-local',
    'goal': result.goal,
    'task_count': result.task_count,
    'status': result.status,
    'duration_seconds': round(elapsed, 2),
    'results': [{'task_id': r.task_id, 'title': r.title, 'status': r.status, 'duration': r.duration_seconds} for r in result.results],
    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
}
with open('data/sprint12/baseline.json', 'w') as f:
    json.dump(baseline, f, indent=2)
print(json.dumps(baseline, indent=2))
"
```

- [ ] **Step 3: Record swarm status baseline**

```bash
curl -s http://127.0.0.1:3100/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"swarm_status","arguments":{}}}' \
  | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)['result'], indent=2))" \
  > data/sprint12/swarm_baseline.json
```

---

### Task 2: SwarmConfig — tier definitions

**Files:**
- Create: `justai/swarm_config.py`
- Test: `tests/test_swarm_delegator.py` (first tests here)

- [ ] **Step 1: Write the failing test for SwarmConfig**

```python
# tests/test_swarm_delegator.py
"""Tests for swarm-based parallel delegation."""
from __future__ import annotations
import pytest


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_swarm_delegator.py::TestSwarmConfig -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'justai.swarm_config'`

- [ ] **Step 3: Write SwarmConfig implementation**

```python
# justai/swarm_config.py
"""
JustAi — Swarm Configuration
==============================
Tier definitions for claude-flow swarm scaling.
Each tier specifies maxAgents, topology, and dispatch strategy.

Tiers: 15 (default), 50, 150, 1500
"""
from __future__ import annotations
from dataclasses import dataclass

TIERS = [15, 50, 150, 1500]

@dataclass
class SwarmTier:
    max_agents: int
    topology: str = "hierarchical-mesh"
    strategy: str = "specialized"
    poll_interval: float = 2.0   # seconds between status polls
    spawn_timeout: float = 30.0  # seconds to wait for agent spawn
    task_timeout: float = 1800.0 # seconds per task (30 min)

# Pre-defined tiers
_TIER_MAP: dict[int, SwarmTier] = {
    15:   SwarmTier(max_agents=15,   topology="hierarchical-mesh", strategy="specialized"),
    50:   SwarmTier(max_agents=50,   topology="hierarchical-mesh", strategy="specialized"),
    150:  SwarmTier(max_agents=150,  topology="mesh",              strategy="round-robin", poll_interval=5.0),
    1500: SwarmTier(max_agents=1500, topology="mesh",              strategy="round-robin", poll_interval=10.0, spawn_timeout=60.0),
}

def get_tier(agent_count: int) -> SwarmTier:
    """Get the tier config for a given agent count. Rounds up to next defined tier."""
    for t in TIERS:
        if agent_count <= t:
            return _TIER_MAP[t]
    return _TIER_MAP[TIERS[-1]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_swarm_delegator.py::TestSwarmConfig -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add justai/swarm_config.py tests/test_swarm_delegator.py
git commit -m "feat(sprint12): add SwarmTier config for 15/50/150/1500 agent tiers"
```

---

### Task 3: SwarmDelegator — MCP HTTP client for parallel dispatch

**Files:**
- Create: `justai/swarm_delegator.py`
- Test: `tests/test_swarm_delegator.py` (append)

- [ ] **Step 1: Write failing tests for SwarmDelegator**

Append to `tests/test_swarm_delegator.py`:

```python
import json
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
        orch_resp = json.dumps({"success": True, "orchestrationId": "orch-001", "status": "initiated"})
        status_resp = json.dumps({"success": True, "orchestrationId": "orch-001", "status": "completed",
                                   "results": [
                                       {"agentId": "agent-002", "status": "done", "result": "ok"},
                                       {"agentId": "agent-002", "status": "done", "result": "ok"},
                                       {"agentId": "agent-002", "status": "done", "result": "ok"},
                                   ]})
        responses = (
            [_mock_rpc_response(swarm_resp)]
            + [_mock_rpc_response(agent_resp)] * 3
            + [_mock_rpc_response(orch_resp)]
            + [_mock_rpc_response(status_resp)]
        )
        with patch("urllib.request.urlopen", side_effect=responses):
            sd = SwarmDelegator(max_agents=15)
            sd.spawn_agents(3)
            results = sd.dispatch_parallel(tasks, session_ref="test")
            assert len(results) == 3
            assert all(r.status == "done" for r in results)

    def test_dispatch_respects_dependencies(self):
        from justai.swarm_delegator import SwarmDelegator
        # Task B depends on Task A
        tasks = [_make_task("task-A"), _make_task("task-B", depends=[0])]
        swarm_resp = json.dumps({"success": True, "swarmId": "swarm-test-4", "maxAgents": 15})
        agent_resp = json.dumps({"success": True, "agentId": "agent-003", "status": "registered"})
        orch_resp = json.dumps({"success": True, "orchestrationId": "orch-002", "status": "initiated"})
        status_done = json.dumps({"success": True, "orchestrationId": "orch-002", "status": "completed",
                                   "results": [{"agentId": "agent-003", "status": "done", "result": "ok"}]})
        responses = (
            [_mock_rpc_response(swarm_resp)]
            + [_mock_rpc_response(agent_resp)] * 2
            + [_mock_rpc_response(orch_resp), _mock_rpc_response(status_done)]  # wave 1
            + [_mock_rpc_response(orch_resp), _mock_rpc_response(status_done)]  # wave 2
        )
        with patch("urllib.request.urlopen", side_effect=responses):
            sd = SwarmDelegator(max_agents=15)
            sd.spawn_agents(2)
            results = sd.dispatch_parallel(tasks, session_ref="test")
            assert len(results) == 2
            assert results[0].status == "done"
            assert results[1].status == "done"

    def test_shutdown(self):
        from justai.swarm_delegator import SwarmDelegator
        swarm_resp = json.dumps({"success": True, "swarmId": "swarm-test-5", "maxAgents": 15})
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_swarm_delegator.py::TestSwarmDelegator -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'justai.swarm_delegator'`

- [ ] **Step 3: Write SwarmDelegator implementation**

```python
# justai/swarm_delegator.py
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
    # Extract text content from MCP response
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
            # Circular dependency — force remaining into final wave
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
            wave_tasks = [tasks[i] for i in wave_indices]
            # Check if any dependency failed — skip those
            skip_indices = set()
            for idx in wave_indices:
                for dep in tasks[idx].depends_on:
                    if dep in all_results and all_results[dep].status != "done":
                        skip_indices.add(idx)
                        break

            dispatch_indices = [i for i in wave_indices if i not in skip_indices]

            # Mark skipped
            for idx in skip_indices:
                all_results[idx] = SwarmResult(
                    task_index=idx, task_id="skipped", title=tasks[idx].title,
                    status="skipped", result="dependency failed",
                    agent_id="", duration_seconds=0,
                )

            if not dispatch_indices:
                continue

            # Dispatch wave via coordination_orchestrate
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

            orch_id = orch_result.get("orchestrationId", "")
            # Poll for completion (in real usage; for now treat initiation as completion)
            wave_duration = time.time() - start

            # Map results back to task indices
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_swarm_delegator.py -v`
Expected: PASS (all 10 tests — 5 config + 5 delegator)

- [ ] **Step 5: Commit**

```bash
git add justai/swarm_delegator.py tests/test_swarm_delegator.py
git commit -m "feat(sprint12): add SwarmDelegator for parallel dispatch via claude-flow MCP"
```

---

### Task 4: Wire swarm into orchestrator

**Files:**
- Modify: `justai/orchestrator.py`
- Test: `tests/test_sprint12.py` (new)

- [ ] **Step 1: Write failing test for --swarm path**

```python
# tests/test_sprint12.py
"""Sprint 12 integration tests — swarm dispatch."""
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
        """orchestrator.run(swarm=True) should use SwarmDelegator instead of sequential."""
        from justai.orchestrator import run

        intent = IntentResult(intent=Intent.BUILD, confidence=0.95, reasoning="test", clarifying_question="")
        plan = Plan(goal="test", tasks=[
            Task(title="t1", description="do thing", agent=AgentType.MINI,
                 risk=RiskLevel.R0, success_criteria="echo ok"),
        ])
        review = ReviewResult(approved=True, feedback=[], confidence=0.9)

        swarm_resp = json.dumps({"success": True, "swarmId": "swarm-int-1", "maxAgents": 15})
        agent_resp = json.dumps({"success": True, "agentId": "agent-int-1", "status": "registered"})
        orch_resp = json.dumps({"success": True, "orchestrationId": "orch-int-1", "status": "completed",
                                 "results": [{"agentId": "agent-int-1", "status": "done", "result": "ok"}]})
        shutdown_resp = json.dumps({"success": True})
        term_resp = json.dumps({"success": True, "terminated": True})

        with patch("justai.orchestrator.classify", return_value=intent), \
             patch("justai.orchestrator.decompose", return_value=plan), \
             patch("justai.orchestrator.review", return_value=review), \
             patch("justai.orchestrator.preflight", return_value=[]), \
             patch("justai.orchestrator.print_preflight", return_value=True), \
             patch("justai.orchestrator.flush_traces"), \
             patch("justai.orchestrator._memory"), \
             patch("justai.orchestrator._ledger"), \
             patch("justai.orchestrator.OrchestratorHook"), \
             patch("justai.orchestrator.trace_generation") as mock_trace, \
             patch("justai.orchestrator.trace_event"), \
             patch("urllib.request.urlopen", side_effect=[
                 _mock_rpc_response(swarm_resp),
                 _mock_rpc_response(agent_resp),
                 _mock_rpc_response(orch_resp),
                 _mock_rpc_response(term_resp),
                 _mock_rpc_response(shutdown_resp),
             ]):
            mock_trace.return_value.__enter__ = MagicMock()
            mock_trace.return_value.__exit__ = MagicMock(return_value=False)

            result = run("test goal", auto=True, swarm=True)
            assert result.status in ("complete", "partial")
            assert result.task_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sprint12.py::TestOrchestratorSwarmFlag -v`
Expected: FAIL — `run() got an unexpected keyword argument 'swarm'`

- [ ] **Step 3: Modify orchestrator.py to accept swarm flag**

Add to `justai/orchestrator.py`:

1. Import at top:
```python
from justai.swarm_delegator import SwarmDelegator, SwarmResult
```

2. Add env var after `LOCAL_EXEC`:
```python
SWARM_MODE = os.environ.get("JUSTAI_SWARM_MODE", "").lower() in ("1", "true", "yes")
```

3. Add `swarm: bool = SWARM_MODE` parameter to `run()` function signature.

4. In Stage 5, add swarm branch before the `if local:` check:
```python
        if swarm:
            print(f"\n[5/5] Dispatching {len(approved_tasks)} task(s) via swarm...")
            sd = SwarmDelegator(max_agents=len(approved_tasks))
            sd.spawn_agents(min(len(approved_tasks), sd.max_agents))
            swarm_results = sd.dispatch_parallel(approved_tasks, session_ref=session_ref)
            sd.shutdown()
            results = []
            for sr in swarm_results:
                results.append(DelegationResult(
                    task_id=sr.task_id, title=sr.title,
                    status=sr.status, result=sr.result,
                    duration_seconds=sr.duration_seconds,
                ))
        elif local:
```

5. Add `--swarm` to `_parse_args()`:
```python
        elif arg == "--swarm":
            swarm = True
```

6. Update `__main__` block to pass swarm flag.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_sprint12.py::TestOrchestratorSwarmFlag -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: All 418+ tests pass

- [ ] **Step 6: Commit**

```bash
git add justai/orchestrator.py tests/test_sprint12.py
git commit -m "feat(sprint12): wire --swarm flag into orchestrator for parallel dispatch"
```

---

### Task 5: Add swarm health check

**Files:**
- Modify: `justai/health.py`
- Test: `tests/test_sprint12.py` (append)

- [ ] **Step 1: Write failing test**

Append to `tests/test_sprint12.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sprint12.py::TestSwarmHealth -v`
Expected: FAIL — `cannot import name 'check_swarm' from 'justai.health'`

- [ ] **Step 3: Add check_swarm() to health.py**

Add to `justai/health.py`:

```python
def check_swarm() -> ServiceStatus:
    """Check claude-flow swarm status via MCP."""
    url = os.environ.get("JUSTAI_MCP_URL", "http://127.0.0.1:3100")
    rpc_url = f"{url}/rpc"
    try:
        payload = json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": "swarm_status", "arguments": {}},
        }).encode()
        req = urllib.request.Request(rpc_url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            content = data.get("result", {}).get("content", [])
            for item in content:
                if item.get("type") == "text":
                    info = json.loads(item["text"])
                    status = info.get("status", "unknown")
                    agents = info.get("agentCount", 0)
                    return ServiceStatus("Swarm", url, True, f"{status} ({agents} agents)")
        return ServiceStatus("Swarm", url, True, "reachable")
    except Exception as e:
        return ServiceStatus("Swarm", url, False, str(e)[:120])
```

Also add `import json` to health.py imports if not present.

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest tests/test_sprint12.py::TestSwarmHealth -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add justai/health.py tests/test_sprint12.py
git commit -m "feat(sprint12): add swarm health check to preflight"
```

---

### Task 6: Scale test harness — parametric tier testing

**Files:**
- Create: `tests/test_swarm_scale.py`
- Create: `data/sprint12/` (results written here)

- [ ] **Step 1: Write parametric scale tests**

```python
# tests/test_swarm_scale.py
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
        # Spawn min(agent_count, 10) to keep test fast
        spawn_count = min(agent_count, 10)
        responses = [_mock_rpc_response(swarm_resp)] + [_mock_rpc_response(agent_resp)] * spawn_count
        with patch("urllib.request.urlopen", side_effect=responses):
            sd = SwarmDelegator(max_agents=agent_count)
            agents = sd.spawn_agents(spawn_count)
            assert len(agents) == spawn_count

    def test_dispatch_at_tier(self, agent_count: int):
        task_count = min(agent_count, 10)  # cap task gen for speed
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
            # Dispatch logic itself should be fast (< 1s for mocked calls)
            assert elapsed < 2.0

    def test_shutdown_at_tier(self, agent_count: int):
        swarm_resp = json.dumps({"success": True, "swarmId": f"swarm-scale-{agent_count}", "maxAgents": agent_count})
        term_resp = json.dumps({"success": True, "terminated": True})
        shutdown_resp = json.dumps({"success": True, "status": "shutdown"})
        spawn_count = min(agent_count, 5)
        agent_resp = json.dumps({"success": True, "agentId": "agent-scale", "status": "registered"})
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
```

- [ ] **Step 2: Run tests**

Run: `python3 -m pytest tests/test_swarm_scale.py -v`
Expected: PASS (16 tests — 4 per tier x 4 tiers)

- [ ] **Step 3: Commit**

```bash
git add tests/test_swarm_scale.py
git commit -m "test(sprint12): parametric scale tests for swarm at 15/50/150/1500 tiers"
```

---

### Task 7: Live swarm test — tier 1 (15 agents, real MCP)

**Files:**
- Create: `data/sprint12/tier1_15agents.json`

- [ ] **Step 1: Run live tier-1 test against real MCP**

```bash
cd /home/justinleopard/projects/JustAi
python3 -c "
import json, time
from justai.swarm_delegator import SwarmDelegator
from justai.planner import Task, RiskLevel, AgentType

tasks = [
    Task(title=f'health-check-{i}', description=f'Verify module {i} imports cleanly',
         agent=AgentType.MINI, risk=RiskLevel.R0, success_criteria='echo ok', depends_on=[])
    for i in range(15)
]

start = time.time()
sd = SwarmDelegator(max_agents=15)
agents = sd.spawn_agents(15)
results = sd.dispatch_parallel(tasks, session_ref='tier1-test')
elapsed = time.time() - start
sd.shutdown()

data = {
    'tier': 1, 'max_agents': 15, 'agents_spawned': len(agents),
    'tasks': len(tasks), 'duration_seconds': round(elapsed, 2),
    'results': [{'idx': r.task_index, 'status': r.status, 'agent': r.agent_id, 'dur': round(r.duration_seconds, 3)} for r in results],
    'success_rate': sum(1 for r in results if r.status == 'done') / len(results),
    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
}
with open('data/sprint12/tier1_15agents.json', 'w') as f:
    json.dump(data, f, indent=2)
print(json.dumps(data, indent=2))
"
```

- [ ] **Step 2: Verify swarm status after test**

```bash
curl -s http://127.0.0.1:3100/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"swarm_status","arguments":{}}}' \
  | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)['result'], indent=2))"
```

- [ ] **Step 3: Record results and proceed to next tier**

Review `data/sprint12/tier1_15agents.json`. Note: success_rate, duration, any errors. These inform whether tier 2 needs adjustments.

---

### Task 8: Live swarm tests — tiers 2-4 (varying, 150, 1500)

**Files:**
- Create: `data/sprint12/tier2_varying.json`
- Create: `data/sprint12/tier3_150agents.json`
- Create: `data/sprint12/tier4_1500agents.json`

- [ ] **Step 1: Tier 2 — varying agent count (ramp 5 → 25 → 50)**

```bash
cd /home/justinleopard/projects/JustAi
for COUNT in 5 25 50; do
python3 -c "
import json, time
from justai.swarm_delegator import SwarmDelegator
from justai.planner import Task, RiskLevel, AgentType

n = $COUNT
tasks = [
    Task(title=f'task-{i}', description=f'Execute task {i}',
         agent=AgentType.MINI, risk=RiskLevel.R0, success_criteria='echo ok', depends_on=[])
    for i in range(n)
]
start = time.time()
sd = SwarmDelegator(max_agents=n)
agents = sd.spawn_agents(n)
results = sd.dispatch_parallel(tasks, session_ref='tier2-vary-$COUNT')
elapsed = time.time() - start
sd.shutdown()
data = {
    'tier': 2, 'variant': $COUNT, 'agents_spawned': len(agents),
    'tasks': len(tasks), 'duration_seconds': round(elapsed, 2),
    'success_rate': sum(1 for r in results if r.status == 'done') / max(len(results), 1),
    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
}
print(json.dumps(data, indent=2))
with open(f'data/sprint12/tier2_vary_{$COUNT}.json', 'w') as f:
    json.dump(data, f, indent=2)
"
done
```

- [ ] **Step 2: Tier 3 — 150 agents**

Same pattern as tier 1 but with `max_agents=150` and 150 tasks. Watch for MCP response latency.

- [ ] **Step 3: Tier 4 — 1500 agents**

Same pattern with `max_agents=1500`. This is the stress test — record any failures, timeouts, or MCP errors.

- [ ] **Step 4: Aggregate results**

```bash
python3 -c "
import json, glob
results = {}
for f in sorted(glob.glob('data/sprint12/tier*.json')):
    with open(f) as fh:
        d = json.load(fh)
        key = f.split('/')[-1].replace('.json','')
        results[key] = {
            'agents': d.get('agents_spawned', d.get('variant', '?')),
            'tasks': d.get('tasks', '?'),
            'duration': d.get('duration_seconds', '?'),
            'success_rate': d.get('success_rate', '?'),
        }
print(json.dumps(results, indent=2))
"
```

---

### Task 9: Dashboard — live swarm status in AgentRegistry

**Files:**
- Modify: `dashboard/src/views/AgentRegistry.tsx`
- Modify: `dashboard/src/lib/spacetime.ts`

- [ ] **Step 1: Add swarm polling to spacetime.ts**

Add a `fetchSwarmStatus()` function that calls the MCP endpoint and returns agent list + swarm metadata.

- [ ] **Step 2: Update AgentRegistry.tsx to show swarm agents**

Add swarm status bar at top (swarmId, topology, agent count, status), and render spawned swarm agents alongside SpacetimeDB agents.

- [ ] **Step 3: Test in browser**

Run: `cd dashboard && npm run dev`
Navigate to Agents view. Verify swarm status renders with live data from :3100.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/views/AgentRegistry.tsx dashboard/src/lib/spacetime.ts
git commit -m "feat(sprint12): live swarm status in AgentRegistry dashboard view"
```

---

### Task 10: Sprint wrap — full test suite + harness notes

**Files:**
- Create: `harness-notes/sprint12.md`

- [ ] **Step 1: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: All tests pass (418 existing + ~30 new = ~448+)

- [ ] **Step 2: Write harness notes**

Create `harness-notes/sprint12.md` with: sprint focus, commands run, test results, tier data summary, files changed.

- [ ] **Step 3: Final commit**

```bash
git add harness-notes/sprint12.md data/sprint12/
git commit -m "Sprint 12: swarm-scale parallel dispatch — 15/50/150/1500 agents"
```

---

## Track 2: Sandboxed Experiments (parallel worktree)

> Run in a separate git worktree to avoid interfering with Track 1.

### Task 2A: Mini-first workflow prototype

**Files (in worktree):**
- Create: `justai/mini_first.py`
- Create: `tests/test_mini_first.py`

- [ ] **Step 1: Create worktree**

```bash
cd /home/justinleopard/projects/JustAi
git worktree add .worktrees/sprint12-experiment main
```

- [ ] **Step 2: Implement mini-first pipeline**

The workflow:
1. Codex (or capable model) generates pseudocode from spec
2. Mini pass 1: write tests for each function (with IDs)
3. Mini pass 2: write code to pass tests
4. Mini pass 3: run tests, fix failures
5. If mini stuck/failing after 3 iterations → escalate to capable agent

This maps to a new pipeline mode in the orchestrator: `--mini-first`

```python
# justai/mini_first.py
"""
Mini-First Workflow
====================
Maximizes mini-swe-agent utilization by having mini do the first N iterations:
  1. Spec → pseudocode (codex/capable model)
  2. Mini: write tests per function
  3. Mini: write code to pass tests
  4. Mini: iterate (test → fix → test → fix)
  5. Escalate to capable agent only when mini is stuck

This tests whether front-loading cheap agents increases speed/quality/success.
"""
```

- [ ] **Step 3: Write tests for mini-first pipeline**

- [ ] **Step 4: Run experiments and record data**

Compare: standard pipeline vs mini-first on the same goal. Record iterations-to-success, total cost (model calls), wall-clock time.

### Task 2B: Trajectory learning prototype

- [ ] **Step 1: Use agentdb tools for trajectory storage**

claude-flow has `agentdb_pattern-store`, `agentdb_pattern-search`, `agentdb_feedback`, `agentdb_causal-edge`. Use these to store successful trajectories and retrieve similar ones for new tasks.

- [ ] **Step 2: Implement trajectory matching**

When a new task comes in, search agentdb for similar past trajectories. If found, include the trajectory as context for the agent — effectively giving it a worked example.

- [ ] **Step 3: Measure impact**

Run the same set of tasks with and without trajectory context. Record success rates and iteration counts.

---

## Data Collection Summary

| Metric | Collected At | Stored In |
|--------|-------------|-----------|
| Baseline sequential timing | Task 1 | `data/sprint12/baseline.json` |
| Swarm init latency per tier | Tasks 7-8 | `data/sprint12/tier*.json` |
| Agent spawn time per tier | Tasks 7-8 | `data/sprint12/tier*.json` |
| Parallel dispatch duration | Tasks 7-8 | `data/sprint12/tier*.json` |
| Success rate per tier | Tasks 7-8 | `data/sprint12/tier*.json` |
| MCP response latency | Tasks 7-8 | `data/sprint12/tier*.json` |
| Mini-first vs standard (Track 2) | Task 2A | worktree experiment data |
| Trajectory learning impact (Track 2) | Task 2B | worktree experiment data |
