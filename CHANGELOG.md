# Changelog

## [1.0.0] - 2026-04-15

### Core Pipeline
- 9-stage orchestration: preflight, session load, intent classification, task decomposition, plan review with replan, checkpoint gates (R0-R3), execution, delegation, synthesis
- Local executor for offline/no-agent mode
- SpacetimeDB delegator with heartbeat monitoring, retry, and failure escalation
- Swarm delegator for parallel dispatch via claude-flow MCP (tested 15-1500 agents)
- Memory bridge to claude-flow (HNSW vector search, ~5ms store, ~7ms search)
- LangFuse tracing integration
- Agent payment ledger (SQLite cost tracking per agent)
- Discord integration (webhooks, bot commands, orchestrator hooks)
- JWT authentication with PBKDF2 password hashing and role-based access

### CLI
- `justai run` — full pipeline (`--auto`, `--local`, `--swarm`, `--session`)
- `justai plan` — decompose only
- `justai status` — service health
- `justai history` — run history from memory
- `justai version` — print version

### Dashboard (React + TypeScript + Tailwind + Vite)
- 7 views: Mission Control, Task Board, Run History, Trajectory Viewer, Memory Browser, Observability, Agent Registry
- Glass Aurora design system (Midnight Rose theme)
- WebSocket real-time subscriptions with HTTP polling fallback
- Live swarm status display

### Experimental (Sprint 12)
- Mini-first workflow: 5-phase escalation pipeline (pseudocode, write tests, write code, iterate, escalate)
- Trajectory learning: HNSW vector store for past run outcomes, semantic search for similar trajectories

### Testing
- 464 tests across 12 sprints
- All external calls mocked (LiteLLM, SpacetimeDB, Discord, MCP)
- Parametric scale tests at 15/50/150/1500 agent tiers

### Sprint History

| Sprint | What Was Built |
|--------|----------------|
| 1 | Clean foundation scaffold |
| 2 | Orchestrator core: intent gate, planner, reviewer, delegator, checkpoint |
| 2.5 | Test coverage audit: 34 to 118 tests |
| 3 | Dashboard: React + SpacetimeDB + Mission Control + Task Board |
| 4 | Trajectory Viewer, Memory Browser |
| 5 | Memory bridge (claude-flow MCP HTTP client) |
| 6 | LangFuse tracing, health preflight |
| 7 | Synthesizer, CLI, local executor |
| 8 | API server (:3002), Run History view |
| 9 | Dashboard API client, Vite proxy |
| 10 | Glass Aurora redesign, Observability, Trajectory Intelligence |
| 11 | v1.0.0 release: config centralization, install.sh, pyproject.toml |
| 12 | Swarm parallel dispatch, trajectory learning, mini-first workflow |
