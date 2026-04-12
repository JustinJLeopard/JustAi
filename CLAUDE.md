# JustAi — Project Context for Claude Code

> **This file is read automatically by every Claude Code session (CLI and IDE)
> when the working directory is this project. It is the single orientation
> document for any agent working in this repo.**
>
> Last updated: 2026-04-11

## What This Project Is

JustAi is orchestration, memory, and control for mini-swe-agent -- the
highest-performing open-source agent (74% SWE-bench Verified).
It decomposes goals into tasks, delegates to mini-swe-agent via SpacetimeDB,
persists decisions across sessions, and surfaces progress via Discord and
a web dashboard.

## Repo Layout

```
~/projects/JustAi/                  <-- YOU ARE HERE (WSL Ubuntu-24.04)
|-- justai/                          # Core Python package
|   |-- __init__.py
|   |-- orchestrator.py              # Main pipeline: goal -> plan -> delegate -> review
|   |-- intent_gate.py               # Classifies user intent
|   |-- planner.py                   # Decomposes goals into task plans
|   |-- delegator.py                 # Routes tasks to mini-swe-agent
|   |-- reviewer.py                  # Reviews completed task output
|   |-- checkpoint.py                # Saves/restores orchestrator state
|-- tools/
|   |-- justai_cli.py                # CLI: justai run|start|status|health|task|mini|relay
|   |-- justai_runtime.py            # Runtime env: repo_root(), runtime_env(), path helpers
|-- scripts/
|   |-- start_justai.sh              # Start the JustAi stack (SpacetimeDB, LiteLLM, etc.)
|   |-- check_justai.sh              # Health check for JustAi services
|-- dashboard/                       # React + TypeScript + Tailwind + Vite (port 3001)
|   |-- src/
|       |-- App.tsx                  # Sidebar nav, 3s SpacetimeDB polling, task detail panel
|       |-- lib/spacetime.ts         # SpacetimeDB HTTP polling client
|       |-- views/MissionControl.tsx # System health bar, agent grid, active pipeline
|       |-- views/TaskBoard.tsx      # Kanban: pending/claimed/running/done/failed
|       |-- components/              # AgentCard.tsx, TaskCard.tsx
|-- tests/                           # pytest suite -- run: python3 -m pytest tests/
|-- docs/
|   |-- JUSTAI_V1_SPEC.md           # Full product specification (v1.2)
|   |-- TESTING.md                   # Testing standards
|-- LocalManus/                      # Copied reference repo (do NOT edit originals)
|-- relay-room/                      # Copied reference repo (do NOT edit originals)
|-- JUSTAI_PLAN.md                   # Integration plan and sprint roadmap
|-- JUSTAI_SOURCES.md                # Source provenance (copied baseline commits)
|-- README.md                        # Project README
```

## CLI Commands

```bash
python3 tools/justai_cli.py run "your goal"       # Full orchestrator pipeline
python3 tools/justai_cli.py start                  # Start the JustAi stack
python3 tools/justai_cli.py status                 # Check service status
python3 tools/justai_cli.py health                 # Health check
python3 tools/justai_cli.py task "description"     # Direct LocalManus task
python3 tools/justai_cli.py mini "description"     # Direct mini-swe-agent task
python3 tools/justai_cli.py relay status            # Relay-room passthrough
```

## Sprint History

| Sprint | Commit | What Was Built |
|--------|--------|----------------|
| 1 | `31e2787` | Clean foundation scaffold |
| 2 | `2f4cf6c` | Orchestrator core: intent_gate, planner, reviewer, delegator, checkpoint |
| 2 | `c7e28ad` | Orchestrator test suite |
| 2.5 | `7eef976` | Test coverage audit: 34 to 118 tests, 45% to 92% coverage |
| 3 | `934583e` | Dashboard: React + SpacetimeDB + Mission Control + Task Board (port 3001) |
| **4 (next)** | -- | Trajectory Viewer, Memory Browser, justai/memory.py, LangFuse |

## Testing Rules (Non-Negotiable)

From `docs/JUSTAI_V1_SPEC.md` -- these apply to every sprint:

- Every sprint ends with tests covering everything built, committed together
- New module -> test file. New function -> happy path + edge case
- All tests run offline -- mock external calls (LiteLLM, SpacetimeDB, Discord)
- `python3 -m pytest tests/` must pass before any sprint commit
- Target: no untested code paths in files touched during the sprint

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `JUSTAI_ROOT` | auto-detected | Repo root |
| `JUSTAI_LOCALMANUS_ROOT` | `$JUSTAI_ROOT/LocalManus` | LocalManus runtime |
| `JUSTAI_RELAY_ROOT` | `$JUSTAI_ROOT/relay-room` | Relay task system |
| `JUSTAI_SPACETIME_SESSION` | `spacetime` | SpacetimeDB tmux session |
| `JUSTAI_RELAY_SERVER` | `local-server` | SpacetimeDB server |

## Model Routing

- `gpt-5.4` -- default model via LiteLLM (localhost:4000)
- `gpt-5.3-codex` -- direct path for code-heavy prompts
- `claude-opus-4-6` -- deep reasoning tasks
- LiteLLM config: `~/projects/LocalManus/config/litellm_config.yaml`

---

## rUv Agentic Harness (Development Environment)

> JustAi is built inside the rUv agentic harness. The harness is our dev
> environment -- it must be running before any project work begins.

### Starting/Stopping the Harness

```bash
# From any terminal (aliases defined in ~/.ruv_env, sourced via .bashrc):
ruv-start                    # Start all 6 services
ruv-stop                     # Stop all services, save memory snapshot
ruv-status                   # Check all 6 services

# If aliases are not loaded (new terminal without .bashrc):
source ~/.ruv_env            # Load env first
bash ~/ruv_start.sh          # Then start (actual script paths)
bash ~/ruv_stop.sh
bash ~/ruv_status.sh
```

**IMPORTANT for Claude Code:** `ruv-start`, `ruv-stop`, `ruv-status` are
shell **aliases** defined in `~/.ruv_env`. They are NOT available via
non-interactive `bash -c`. Use the actual script paths instead:
- `bash ~/ruv_start.sh`
- `bash ~/ruv_stop.sh`
- `bash ~/ruv_status.sh`

### Harness Services (6 total -- all must show green on ruv-status)

| # | Service | Endpoint | What It Does |
|---|---------|----------|--------------|
| 0 | LiteLLM | http://localhost:4000 | Model router (GPT-5.4, Codex, Claude) |
| 1 | SAFLA | http://127.0.0.1:8765 | Persistent memory + safety validation |
| 2 | claude-flow MCP | HTTP :3100 | 264 tools for Claude Code + Codex (shared) |
| 3 | claude-flow swarm | V3 inline | Background analysis workers |
| 4 | federation hub | ws://localhost:8443 | Cross-generation agent memory |
| 5 | rUv helper agent | background | Session observer + smart suggestions |

### Memory

- Backend: sql.js + HNSW (vector search)
- DB: `~/projects/ruv-research/.swarm/memory.db`
- **CWD-sensitive** -- `claude-flow memory` commands must run from `~/projects/ruv-research`
- `ruv-stop` saves session snapshot via direct SQLite upsert
- `ruv-start` restores and displays last session context

### Config File Map

| File | What It Does | Editable? |
|------|-------------|-----------|
| `~/.ruv_env` | Shell env: API keys, PATH, tool config, aliases | Yes -- with caution |
| `~/.claude/settings.json` | Claude Code: plugins, env overrides, effort | Yes |
| `~/.claude.json` | Claude Code: MCP servers, project trust | Avoid -- auto-managed |
| `.vscode/settings.json` | VS Code workspace settings (this project) | Yes |

### Harness File Paths (WSL absolute)

| File | Purpose |
|------|---------|
| `~/cf-mcp-http.mjs` | HTTP wrapper for claude-flow MCP (this is what ruv-start launches) |
| `~/ruv_start.sh` | Start all 6 harness services |
| `~/ruv_stop.sh` | Stop all services, save memory snapshot |
| `~/ruv_status.sh` | Check all 6 services |
| `~/ruv_helper.py` | Background observer + smart suggestions |
| `~/.ruv_env` | Shell env: API keys, PATH, aliases (sourced by .bashrc) |
| `~/.claude.json` | MCP server configs (claude-flow type:http, agentic-flow, safla) |
| `~/.claude/settings.json` | Claude Code plugins, env overrides, effort level |
| `~/.claude/SETTINGS_NOTES.md` | Documentation companion for settings.json |
| `~/.safla/cf_mcp.pid` | MCP server PID (written by wrapper, read by stop/status) |
| `~/.safla/cf_mcp_http.log` | MCP server log |
| `~/.npm-global/lib/node_modules/claude-flow/` | claude-flow v3 install root |
| `~/projects/ruv-research/.swarm/memory.db` | Memory DB (CWD must be ruv-research) |

### MCP HTTP Handshake (required)

Clients must send `initialize` before `tools/list` or `tools/call`:
```
POST /rpc  { "method": "initialize", "params": { "protocolVersion": "2024-11-05", "clientInfo": {...} } }
POST /rpc  { "method": "tools/list" }          -> 264 tools
POST /rpc  { "method": "tools/call", "params": { "name": "...", "arguments": {...} } }
GET /health                                     -> { "status": "ok" } (no handshake needed)
```

### Key Override: ANTHROPIC_BASE_URL

`~/.ruv_env` routes Anthropic traffic through Gameron (`https://api.gameron.ai/v1`)
for multi-model routing. `~/.claude/settings.json` overrides this to
`https://api.anthropic.com` for Claude Code only -- the IDE extension needs
first-party API for auth.

### Chain of Command

```
Justin (user)
  +-- JustAi (orchestrate and/or delegate)
        |-- cowork-claude: architecture, coordination, desktop, computer-use
        |-- codex: code/config/runtime (WSL execution)
        +-- claude-cli (you): specialized reasoning, tool use
```

### Constraints

- Do NOT modify the original repos at `~/projects/LocalManus` or `~/projects/relay-room`
- All edits inside `~/projects/JustAi` only
- The copied `LocalManus/` and `relay-room/` dirs inside JustAi are reference material
- Do not route execution through the broken OpenFang orchestrator
- Preserve the stable assistant-first LocalManus behavior

---

## Changelog

### 2026-04-11: MCP stdio -> HTTP transport

**What changed:** claude-flow MCP switched from stdio (1:1 per session) to HTTP
on port 3100 (shared, one instance for all agents).

**Why:** stdio transport meant every Claude Code session and Codex each spawned
their own MCP process. They collided on the memory DB and couldn't share state.
HTTP lets `ruv-start` own a single MCP server process that Claude Code IDE,
Claude Code CLI, and Codex all connect to.

**What was touched:**
- `~/cf-mcp-http.mjs` (new) -- thin wrapper: imports createMCPServer + 29 tool modules, starts HTTP on :3100
- `~/.claude.json` -- claude-flow entry: `type:stdio` -> `type:http, url:http://127.0.0.1:3100`
- `~/ruv_start.sh` -- step [2/5]: `claude-flow mcp start &` -> `setsid node ~/cf-mcp-http.mjs`
- `~/ruv_status.sh` -- MCP check: `claude-flow mcp status` -> `curl :3100/health`
- `~/ruv_stop.sh` -- added `fuser -k 3100/tcp` alongside PID-based kill
- `cli.js` (patched) -- wantsHttp bypass so `-t http` isn't swallowed by stdio fast-path
- `node_modules/@claude-flow/mcp` (symlink) -- fixes missing package import in startHttpServer()

**Data shape note:** HTTP uses JSON-RPC 2.0 POSTs to `/rpc` -- same protocol as
stdio, different transport. Requires `initialize` handshake before tool calls.
If tool responses behave differently (streaming, chunking, timeouts), the
transport change is the first place to investigate.

**Tool count:** 264 total (260 from 29 CLI modules + 4 built-in). 4 schemas
patched at startup (missing `type` field on flexible-value properties).
