# Changelog

## [Unreleased]

### Added
- Public-facing landing repo at github.com/JustinJLeopard/justai-demo with polished README, screenshots, architecture diagram, OG image, and .github/ scaffolding.

### Changed
- Dashboard identity rename: `SpacetimeClient` → `RealtimeClient`, `dashboard/src/lib/spacetime.ts` → `realtime.ts`, `dashboard/src/components/Pipeline.tsx` → `ControlPlaneStages.tsx` (PR #2).
- Page titles, meta descriptions, and Open Graph tags reframed around control-plane / safe-mini / 3-repo identity in `dashboard/index.html` and `dashboard/app.html` (PR #2).
- README test count corrected: 363 → 370 (post-Phase-4-H reality).

## [v0.4.0] - 2026-04-30

### Changed
- Repo identity reframed around the three-repo split (safe-mini substrate + JustAi orchestrator + local-resident experiment driver).
- Pipeline narrative reduced from "6-stage" framing to a transparent control-plane: scope_planner -> intent_gate -> reviewer -> checkpoint -> agent_dispatch.

### Added
- Stub AgentRunner Protocol + canonical substrate types (will migrate to safe-mini repo when stood up).
- ruff + mypy in dev tooling, clean across `justai/` and `tests/`.
- `tests/test_docs_contract.py` lock-in to prevent legacy-term regressions.
- PHASE_5_RATIFICATION.md (secrets scrub, dep audit, license, install verify, dashboard verify, 3-repo consistency).

### Removed
- SpacetimeDB live dependency (Python + dashboard `spacetimedb` npm package).
- ManusLocal / manuslocal runtime integration.
- relay-room and `delegator.py` dispatch backend.
- swarm dispatch surface.

### Fixed
- Various test references to amputated services (test_orchestrator, test_sprint5, test_sprint7, test_slice2, test_justai_cli).
- Demo deployment (2026-04-24): `dashboard/index.html` now loads the simulation entry (`/demo/demo-entry.tsx`); was loading the real prod app. The canonical demo URL `justai-demo.vercel.app/` was previously serving the LoginPage with no live backend.
- Demo deployment (2026-04-24): `useSimulation.initialState()` changed from `{phase:'idle', paused:true}` to `{phase:'planning', paused:false}` — the sprint auto-plays on page load.
- Demo deployment (2026-04-24): `+ New Run` button in `DemoMissionControl` wired to `controls.replay()` (was a placeholder with no `onClick`).

### Documentation
- README and `docs/ARCHITECTURE.md` rewritten around control-plane thesis and the three-repo plan.
- Historical evidence archived under `docs/archive/`.

### Renamed
- `dashboard/demo.html` → `dashboard/app.html` (the file at this URL serves the original production dashboard, not the demo).

### Build
- `dashboard/vercel.json` added with explicit framework/build/cleanUrls config.
- `vite.config.ts` rollup input keys renamed `main`→`demo` and `demo`→`app` so dist/assets bundle filenames match content.

### Internal
- Memory keys: `justai-architecture-decision-mini-swe-agent-control-plane`, `safe-mini-substrate-architecture`, `justai-two-repo-ship-pattern` (note: key name is provisional; content reflects the 3-repo decision).

## [1.0.0] - 2026-04-15

### Core Pipeline
- 9-stage orchestration: preflight, session load, intent classification, task decomposition, plan review with replan, checkpoint gates (R0-R3), execution, delegation, synthesis
- Local executor for offline/no-agent mode
- control-plane data dispatch with heartbeat monitoring, retry, and failure escalation
- Swarm dispatch for parallel dispatch via claude-flow MCP (tested 15-1500 agents)
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
- All external calls mocked (LiteLLM, control-plane data, Discord, MCP)
- Parametric scale tests at 15/50/150/1500 agent tiers

### Sprint History

| Sprint | What Was Built |
|--------|----------------|
| 1 | Clean foundation scaffold |
| 2 | Orchestrator core: intent gate, planner, reviewer, dispatch, checkpoint |
| 2.5 | Test coverage audit: 34 to 118 tests |
| 3 | Dashboard: React + control-plane data + Mission Control + Task Board |
| 4 | Trajectory Viewer, Memory Browser |
| 5 | Memory bridge (claude-flow MCP HTTP client) |
| 6 | LangFuse tracing, health preflight |
| 7 | Synthesizer, CLI, local executor |
| 8 | API server (:3002), Run History view |
| 9 | Dashboard API client, Vite proxy |
| 10 | Glass Aurora redesign, Observability, Trajectory Intelligence |
| 11 | v1.0.0 release: config centralization, install.sh, pyproject.toml |
| 12 | Swarm parallel dispatch, trajectory learning, mini-first workflow |
