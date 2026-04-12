# Harness Notes — Sprint 12

## Sprint Focus
Swarm-scale parallel dispatch. Wire JustAi orchestrator to dispatch tasks
through claude-flow's swarm MCP for real parallel agent execution. Test at
15 → varying → 150 → 1500 concurrent agents.

## What We Built

### New Modules
- `justai/swarm_config.py` — Tier definitions (15/50/150/1500) with topology, strategy, timeouts
- `justai/swarm_delegator.py` — Parallel dispatch via claude-flow MCP JSON-RPC, dependency wave grouping

### Modified Modules
- `justai/orchestrator.py` — Added `--swarm` flag, `swarm=True` parameter to `run()`, routes to SwarmDelegator
- `justai/health.py` — Added `check_swarm()` for MCP swarm status in preflight

### Dashboard
- `dashboard/src/lib/spacetime.ts` — Added `fetchSwarmStatus()` MCP client, `SwarmStatus`/`SwarmAgent` types
- `dashboard/src/views/AgentRegistry.tsx` — Live swarm status bar, swarm agents rendered alongside SpacetimeDB agents
- `dashboard/src/App.tsx` — Fixed pre-existing TS error (`running` → `in_progress`)

### Tests
- `tests/test_swarm_delegator.py` — 13 tests: config tiers, init, spawn, dispatch, dependencies, skip-on-fail, shutdown, wave grouping
- `tests/test_swarm_scale.py` — 16 tests: parametric across 4 tiers (15/50/150/1500), each testing init/spawn/dispatch/shutdown
- `tests/test_sprint12.py` — 4 tests: orchestrator swarm integration, health check

## What We Ran

```bash
source ~/.ruv_env && ~/ruv_start.sh

cd ~/projects/JustAi

# Baseline
JUSTAI_LOCAL_EXEC=1 JUSTAI_AUTO_MODE=1 python3 -c "from justai.orchestrator import run; run('verify modules', auto=True, local=True)"

# Unit tests (TDD per module)
python3 -m pytest tests/test_swarm_delegator.py -v
python3 -m pytest tests/test_swarm_scale.py -v
python3 -m pytest tests/test_sprint12.py -v

# Live swarm tests (real MCP on :3100)
python3 -c "from justai.swarm_delegator import SwarmDelegator; ..."  # tier 1-4

# Dashboard type check
cd dashboard && npx tsc --noEmit

# Full test suite
python3 -m pytest tests/ -v
```

## Scale Test Results

| Tier | Agents | Tasks | Total (s) | Spawn (s) | Dispatch (s) | Shutdown (s) | Success |
|------|--------|-------|-----------|-----------|--------------|--------------|---------|
| 1    | 15     | 15    | 0.050     | 0.015     | 0.001        | 0.012        | 100%    |
| 2    | 5      | 5     | 0.032     | 0.005     | 0.001        | —            | 100%    |
| 2    | 25     | 25    | 0.045     | 0.024     | 0.001        | —            | 100%    |
| 2    | 50     | 50    | 0.099     | 0.054     | 0.001        | —            | 100%    |
| 3    | 150    | 150   | 0.412     | 0.191     | 0.001        | 0.198        | 100%    |
| 4    | 1500   | 1500  | 9.915     | 4.225     | 0.003        | 5.666        | 100%    |

### Key Findings
- **Dispatch is O(1)**: coordination_orchestrate handles 1500 tasks in 3ms regardless of count
- **Spawn is linear**: ~2.8ms per agent (1500 agents = 4.2s)
- **Shutdown is linear**: ~3.8ms per agent (1500 agents = 5.7s)
- **100% success rate** at all tiers
- **Bottleneck is spawn/shutdown**, not dispatch — batch spawn API would eliminate this

### Baseline Comparison
- Sequential local pipeline: 104s for 4 tasks (dominated by LLM planning)
- Swarm dispatch of 15 tasks: 50ms total (2000x faster at dispatch layer)
- The LLM planning stages (intent → plan → review) are the real wall-clock bottleneck, not execution

## Test Count

| Before Sprint | After Sprint | Delta |
|--------------|-------------|-------|
| 418          | 451         | +33   |

## Files Changed

```
justai/swarm_config.py          — NEW: tier definitions
justai/swarm_delegator.py       — NEW: parallel dispatch via MCP
justai/orchestrator.py          — MODIFIED: --swarm flag, SwarmDelegator path
justai/health.py                — MODIFIED: check_swarm()
tests/test_swarm_delegator.py   — NEW: 13 tests
tests/test_swarm_scale.py       — NEW: 16 tests
tests/test_sprint12.py          — NEW: 4 tests
tests/test_sprint7.py           — MODIFIED: _parse_args unpack (4-tuple)
tests/test_sprint10.py          — MODIFIED: _parse_args unpack (4-tuple)
tests/test_sprint11.py          — MODIFIED: module count 20→22
dashboard/src/lib/spacetime.ts  — MODIFIED: swarm MCP client
dashboard/src/views/AgentRegistry.tsx — MODIFIED: live swarm display
dashboard/src/App.tsx           — MODIFIED: TS fix (running→in_progress)
data/sprint12/*.json            — NEW: scale test data files
harness-notes/sprint12.md       — this file
```

## Commits

```
b97a0c9 feat(sprint12): SwarmConfig tiers + SwarmDelegator parallel dispatch
c0a7827 feat(sprint12): wire --swarm flag into orchestrator for parallel dispatch
9a5f2f9 feat(sprint12): add swarm health check to preflight
57bdfe1 test(sprint12): parametric scale tests for swarm at 15/50/150/1500 tiers
0abae41 feat(sprint12): live swarm status in AgentRegistry dashboard view
```
