# JustAi

> **"The best code agent in the world was missing one thing. We built it."**

JustAi is orchestration, memory, and control for [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) — the world's highest-performing open-source coding agent at 74% SWE-bench Verified. Built on research from Princeton & Stanford, powered by [rUv's agent infrastructure](https://github.com/ruvnet/ruflo).

---

## What It Does

Give JustAi a goal in plain English. It decomposes it into well-scoped tasks, delegates execution to mini-swe-agent via SpacetimeDB, persists all decisions in memory, and surfaces everything in real-time.

```
You                    JustAi                         mini-swe-agent
 │                       │                                  │
 │  "add /health         │                                  │
 │   endpoint"           │                                  │
 │ ─────────────────────►│  1. classify intent              │
 │                       │  2. decompose into tasks         │
 │                       │  3. review plan quality          │
 │                       │  4. evaluate risk gates          │
 │                       │  5. post to SpacetimeDB ────────►│
 │                       │                                  │  execute bash
 │                       │                                  │  write .traj.json
 │                       │  6. collect results ◄────────────│
 │  ◄────────────────────│  7. store in memory              │
 │  "done — 1 task,      │                                  │
 │   12s, /health added" │                                  │
```

## Install

```bash
git clone https://github.com/user/JustAi.git
cd JustAi
bash install.sh
```

The installer checks prerequisites (Python 3.12+, Node 20+), installs dependencies, creates `.env` from the template, and runs tests to verify.

Run `bash install.sh --check` for preflight only (no changes).

## Quick Start

```bash
# 1. Start the harness services
source ~/.ruv_env && ~/ruv_start.sh

# 2. Run a task
cd ~/projects/JustAi
python3 -m justai.orchestrator "add a /health endpoint to server.py"

# 3. Open the dashboard
cd dashboard && npm run dev
# → http://localhost:3001
```

## Dashboard

Four views, all real-time:

| View | What it shows |
|------|---------------|
| **Mission Control** | Agent status, system health, active pipeline |
| **Task Board** | 5-column Kanban (pending → done) |
| **Trajectory Viewer** | Step-by-step replay of any agent run |
| **Memory Browser** | Browse, search, store claude-flow memory |

## CLI

```bash
python3 tools/justai_cli.py status     # service health
python3 tools/justai_cli.py start      # start all services
python3 tools/justai_cli.py health     # detailed health check
python3 tools/justai_cli.py task "..."  # post a task
python3 tools/justai_cli.py mini "..."  # run mini-swe-agent directly
python3 tools/justai_cli.py relay status  # relay task system status
```

## Architecture

```
Orchestrator (Python)  ──►  LiteLLM (:4000)  ──►  Model APIs
       │
       ▼
SpacetimeDB (:3000)   ◄──►  mini-swe-agent (bash execution)
       │
       ▼
claude-flow MCP (:3100)     Dashboard (:3001)
264 tools, HNSW memory      React + Vite, 4 views
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system diagram.

## Configuration

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `LITELLM_BASE_URL` | `http://localhost:4000` | Model routing proxy |
| `LITELLM_KEY` | `sk-justai` | LiteLLM auth token |
| `JUSTAI_MCP_URL` | `http://127.0.0.1:3100` | Memory MCP server |
| `LANGFUSE_PUBLIC_KEY` | *(optional)* | LLM tracing |
| `LANGFUSE_SECRET_KEY` | *(optional)* | LLM tracing |

## Testing

```bash
python3 -m pytest tests/ -v
# 49+ tests, all run offline (mocked LLM + MCP calls)
```

## Built On

- **[mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent)** — Princeton & Stanford. 74% SWE-bench Verified. MIT License.
- **[Ruflo / claude-flow](https://github.com/ruvnet/ruflo)** — rUv. 6,000+ commit orchestration platform. MIT License.
- **[SpacetimeDB](https://spacetimedb.com)** — Clockwork Labs. Real-time distributed database. BSL License.
- **[LiteLLM](https://github.com/BerriAI/litellm)** — BerriAI. Model routing. MIT License.
- **[LangFuse](https://langfuse.com)** — LLM observability. MIT License.

See [docs/ATTRIBUTION.md](docs/ATTRIBUTION.md) for the complete credits.

---

**Status:** v1 in active development. See [docs/JUSTAI_V1_SPEC.md](docs/JUSTAI_V1_SPEC.md) for the full specification.
