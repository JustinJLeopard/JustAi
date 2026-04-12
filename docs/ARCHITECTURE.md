# JustAi Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Human (operator)                        │
│                  justai run "goal"                           │
└─────────┬───────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Orchestrator Pipeline                      │
│                                                             │
│  [1] Intent Gate ──► classify goal type + confidence        │
│  [2] Planner     ──► decompose into mini-sized tasks        │
│  [3] Reviewer    ──► validate plan quality                  │
│  [4] Checkpoint  ──► R0-R3 risk gates (approve/block)       │
│  [5] Delegator   ──► post to SpacetimeDB, monitor agents    │
│  [6] Synthesizer ──► aggregate results, store in memory     │
│                                                             │
│  Each LLM stage calls LiteLLM (:4000) for model routing.   │
│  Each stage is traced via LangFuse (when configured).       │
└─────────┬───────────────────────────────────────────────────┘
          │
          ▼
┌───────────────────────┐     ┌────────────────────────────────┐
│   SpacetimeDB (:3000) │◄───►│  mini-swe-agent (manuslocal)   │
│   Task backbone       │     │  Executes bash tasks           │
│   relay CLI interface  │     │  Writes .traj.json logs        │
└───────────────────────┘     └────────────────────────────────┘
          │
          ▼
┌───────────────────────┐     ┌────────────────────────────────┐
│  claude-flow MCP      │     │  Dashboard (:3001)             │
│  HTTP :3100           │◄───►│  React + Vite                  │
│  264 tools            │     │  Mission Control | Task Board   │
│  Memory: sql.js+HNSW  │     │  Trajectory Viewer | Memory    │
└───────────────────────┘     └────────────────────────────────┘
```

## Directory Structure

```
JustAi/
├── justai/                    # Python orchestrator package
│   ├── __init__.py            # Auto-loads .env
│   ├── orchestrator.py        # Main pipeline (6 stages)
│   ├── intent_gate.py         # Goal classification
│   ├── planner.py             # Task decomposition
│   ├── reviewer.py            # Plan quality gate
│   ├── checkpoint.py          # R0-R3 risk gates
│   ├── delegator.py           # SpacetimeDB task posting
│   ├── memory.py              # MCP HTTP memory client
│   └── tracing.py             # LangFuse observability
│
├── dashboard/                 # Web UI (React + TypeScript + Vite)
│   ├── src/
│   │   ├── App.tsx            # Root: 4-view nav
│   │   ├── views/
│   │   │   ├── MissionControl.tsx
│   │   │   ├── TaskBoard.tsx
│   │   │   ├── TrajectoryViewer.tsx
│   │   │   └── MemoryBrowser.tsx
│   │   └── lib/
│   │       ├── spacetime.ts   # SpacetimeDB polling client
│   │       ├── trajectories.ts # .traj.json file loader
│   │       └── memory-client.ts # MCP HTTP browser client
│   └── vite.config.ts         # Port 3001, proxy /api/memory → :3100
│
├── relay-room/                # SpacetimeDB backend (Rust)
│   └── spacetimedb/src/lib.rs # Task, Agent, Message, Event tables
│
├── LocalManus/                # mini-swe-agent runtime + logs
│   └── logs/                  # .traj.json trajectory files
│
├── tools/
│   ├── justai_cli.py          # CLI: justai run, status, health
│   └── justai_runtime.py      # Runtime utilities
│
├── scripts/
│   ├── start_justai.sh        # Start all JustAi services
│   └── check_justai.sh        # Health check (--status-only, --health-only)
│
├── tests/                     # pytest test suite
│   ├── test_orchestrator.py   # 24 tests: intent, planner, reviewer, checkpoint
│   ├── test_sprint4.py        # 25 tests: memory, tracing, integration
│   └── test_sprint5.py        # Installer + preflight tests
│
├── docs/
│   ├── JUSTAI_V1_SPEC.md      # Full product specification
│   ├── ARCHITECTURE.md        # This file
│   ├── ATTRIBUTION.md         # Credits and licenses
│   ├── EVIDENCE.md            # Performance data from 10 sprints
│   └── TESTING.md             # Test running guide
│
├── harness-notes/             # Operational notes per sprint
├── install.sh                 # Single-command installer
├── .env.example               # Environment template
└── README.md                  # Landing page
```

## Data Flow

### Task Lifecycle

1. `justai run "goal"` enters the orchestrator
2. Intent gate classifies: EXECUTION / RESEARCH / MULTI_STEP / AMBIGUOUS
3. Planner calls LiteLLM to decompose into tasks (one file, one concern each)
4. Reviewer validates the plan (LLM + heuristic checks)
5. Checkpoint evaluates risk: R0 (auto) → R3 (blocked, manual only)
6. Delegator posts approved tasks to SpacetimeDB via `relay post`
7. mini-swe-agent claims the task, executes bash commands, writes `.traj.json`
8. Delegator polls for completion, collects results
9. Synthesizer stores summary in claude-flow memory

### Memory Architecture

```
Python (justai/memory.py)  ──► HTTP POST /rpc ──► claude-flow MCP (:3100)
Dashboard (memory-client.ts) ──► /api/memory ──► Vite proxy ──► :3100
                                                       │
                                                       ▼
                                              sql.js + HNSW vectors
                                              ~/projects/ruv-research/.swarm/memory.db
```

- **Store:** key + value + 384-dim embedding (auto-generated)
- **Retrieve:** exact key lookup
- **Search:** HNSW approximate nearest neighbor on embeddings
- **Transport:** JSON-RPC 2.0 over HTTP. Requires `initialize` handshake.

### Model Routing

```
justai (Python) ──► LiteLLM (:4000) ──► Gameron API ──► Claude/GPT/etc
```

LiteLLM handles model selection, fallback chains, and rate limiting.
Each pipeline stage can use a different model via env vars.

## Key Design Decisions

1. **HTTP MCP over stdio** — One shared process for all agents. No DB lock collisions.
2. **relay CLI as delegation interface** — SpacetimeDB tasks via battle-tested relay scripts.
3. **Mocked tests** — All tests run offline. LLM and MCP calls are mocked.
4. **LangFuse opt-in** — Tracing is no-op without keys. Zero overhead when disabled.
5. **Vite proxy for dashboard** — Avoids CORS. Frontend doesn't know about MCP internals.
