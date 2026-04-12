# Harness Notes — Sprint 4

## What is the rUv Harness?

Six services that give your agents memory, routing, orchestration, and observability.
They all run in WSL. You start them with one command, stop them with another.

```bash
# Start everything (WSL terminal)
source ~/.ruv_env && ~/ruv_start.sh

# Check what's running
~/ruv_status.sh

# Stop everything + save memory snapshot
~/ruv_stop.sh
```

## The 6 Services (what ruv-status checks)

| # | Service | Port | What it does |
|---|---------|------|-------------|
| 0 | LiteLLM | :4000 | Routes model calls. `openai/claude-opus-4-6` goes through here. Config: `~/projects/LocalManus/config/litellm_config.yaml` |
| 1 | SAFLA | :8765 | Memory + safety validation. Separate from claude-flow. |
| 2 | claude-flow MCP | :3100 | **264 tools** exposed via HTTP JSON-RPC. This is the big one. Memory, swarm, agents, hooks, HNSW search. |
| 3 | claude-flow swarm | — | V3 swarm coordinator (runs inline, not a daemon) |
| 4 | Federation hub | :8443 | agentic-flow v2 cross-agent federation |
| 5 | rUv helper | — | Background observer + suggestions |

## Commands You'll Use Most

### Memory (via claude-flow MCP at :3100)

```bash
# Quick health check
curl -s http://127.0.0.1:3100/health | python3 -m json.tool

# Store a value (raw JSON-RPC)
curl -s -X POST http://127.0.0.1:3100/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"dev","version":"1.0"}}}'

curl -s -X POST http://127.0.0.1:3100/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"memory_store","arguments":{"key":"test","value":"hello","namespace":"justai"}}}'

# From Python (much easier)
cd ~/projects/JustAi
python3 -c "
from justai.memory import Memory
m = Memory()
print('Connected:', m.connected)
m.store('my/key', 'my value')
print(m.retrieve('my/key'))
print(m.search('semantic query'))  # HNSW vector search
"
```

### Dashboard

```bash
cd ~/projects/JustAi/dashboard && npm run dev
# Opens at http://localhost:3001
# 4 views: Mission Control, Task Board, Trajectories, Memory
```

### Running the orchestrator

```bash
cd ~/projects/JustAi
python3 -m justai.orchestrator "add a /health endpoint to server.py"
# Runs: intent → plan → review → checkpoint → delegate → synthesize
```

### Tests

```bash
cd ~/projects/JustAi && python3 -m pytest tests/ -v
# 49 tests, all offline (mocked LLM + MCP calls)
```

## What Worked Well (Sprint 4)

1. **MCP HTTP memory — fast and reliable.** `Memory().store()` round-trips in ~5ms vs 200-300ms for the old `subprocess.run(["claude-flow", "memory", "store", ...])`. Zero failures during the sprint once the `initialize` handshake was understood.

2. **Shared MCP instance.** One HTTP server at :3100, all agents connect to it. No more DB lock collisions from multiple stdio processes. `ruv-start` owns the lifecycle.

3. **264 tools available via HTTP.** Every claude-flow capability is callable from any language that can POST JSON. The dashboard Memory Browser talks to the same endpoint as the Python orchestrator.

4. **Vite proxy pattern.** Dashboard proxies `/api/memory` → `:3100` to avoid CORS. Clean separation — frontend doesn't need to know about MCP internals.

5. **Trajectory files as data source.** .traj.json files from mini-swe-agent are a goldmine — full step-by-step replay with commands, output, reasoning. The Trajectory Viewer just reads these files.

6. **Tests run fast.** 49 tests in 2 seconds. All mocked, all offline. No flaky network dependencies.

## What Didn't Work Well / Gotchas

1. **MCP initialize handshake is mandatory.** Every new client must send `POST /rpc { method: "initialize" }` before any `tools/list` or `tools/call`. Without it you get `-32002 Server not initialized` with zero explanation. Cost me 30+ minutes the first time. **Fix: always call initialize on first use, re-initialize after any error.**

2. **Writing files to WSL from Windows is painful.** JavaScript template literals with backticks get mangled by bash heredocs. Python strings with `$()` get command-substituted. **Workaround: write to `C:\Zo\Workspace\temp\` on Windows, then `cp /mnt/c/Zo/Workspace/temp/file ~/target`.**

3. **`source ~/.ruv_env` is required for every bash -c command.** Non-interactive bash doesn't load `.bashrc`, so PATH doesn't include `~/.npm-global/bin` or `~/.local/bin`. Every `wsl.exe -d Ubuntu-24.04 -e bash -c "..."` needs `source ~/.ruv_env &&` prepended.

4. **4 tools had broken schemas.** `memory_store`, `config_set`, `hive-mind_consensus`, `hive-mind_memory` were missing `type` fields in their input schemas. `cf-mcp-http.mjs` patches these at startup. If you add new tools, check schemas.

5. **VS Code auto-activates .venv.** The Python extension found `relay-room/.venv` and slapped `(.venv)` in every terminal prompt. Fixed with `"python.terminal.activateEnvironment": false` in `.vscode/settings.json`.

6. **LangFuse is no-op without keys.** `justai/tracing.py` wraps orchestrator stages but does nothing unless `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set. This is by design — tracing is opt-in. Set the keys in `~/.ruv_env` when ready.

## Key Environment Variables

```bash
# In ~/.ruv_env (already set for you):
LITELLM_BASE_URL=http://localhost:4000     # model router
LITELLM_KEY=sk-justai                      # LiteLLM auth
JUSTAI_MCP_URL=http://127.0.0.1:3100       # memory MCP
JUSTAI_SESSION_REF=sprint-4                # orchestrator session tag

# Optional (add when ready):
LANGFUSE_PUBLIC_KEY=pk-...                 # tracing
LANGFUSE_SECRET_KEY=sk-...                 # tracing
LANGFUSE_HOST=https://cloud.langfuse.com   # or self-hosted
```

## File Map (Sprint 4 additions)

```
justai/
  memory.py          — MCP HTTP memory client (~40x faster than CLI)
  tracing.py         — LangFuse observability (no-op when unconfigured)
  orchestrator.py    — now uses Memory() + trace_generation()

dashboard/src/
  views/TrajectoryViewer.tsx  — step-by-step .traj.json replay
  views/MemoryBrowser.tsx     — browse/search/store claude-flow memory
  lib/trajectories.ts         — trajectory file loader
  lib/memory-client.ts        — browser MCP client (via Vite proxy)
  App.tsx                     — 4-view nav

dashboard/vite.config.ts     — trajectory middleware + /api/memory proxy

tests/test_sprint4.py        — 25 tests for memory, tracing, orchestrator integration
```
