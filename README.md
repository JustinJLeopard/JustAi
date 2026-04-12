# JustAi

> **"The best code agent in the world was missing one thing. We built it."**

JustAi is orchestration, memory, and control for [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) — the world's highest-performing open-source coding agent at 74% SWE-bench Verified. Built on research from Princeton & Stanford, powered by [rUv's agent infrastructure](https://github.com/ruvnet/ruflo).

---

## What It Does

Give JustAi a goal in plain English. It decomposes it into well-scoped tasks, executes them locally or delegates to mini-swe-agent via SpacetimeDB, persists all decisions in memory, and surfaces everything in real-time.

```
You                    JustAi                         mini-swe-agent
 |                       |                                  |
 |  "add /health         |                                  |
 |   endpoint"           |                                  |
 | -------------------->|  1. preflight (service health)    |
 |                       |  2. load session context          |
 |                       |  3. classify intent               |
 |                       |  4. decompose into tasks          |
 |                       |  5. review plan quality           |
 |                       |  6. evaluate risk gates           |
 |                       |  7a. execute locally       OR     |
 |                       |  7b. delegate to agent ---------->|
 |                       |                                   |  execute bash
 |                       |  8. synthesize results  <---------|
 | <--------------------|  9. store in memory                |
 |  "done - 1 task,      |                                  |
 |   10s, /health added" |                                  |
```

## Install

```bash
git clone https://github.com/user/JustAi.git
cd JustAi
bash install.sh          # full install
bash install.sh --check  # preflight only
pip install -e .         # install justai command
```

Requirements: Python 3.12+, Node 20+

## Quick Start

```bash
# 1. Start harness services
source ~/.ruv_env && ~/ruv_start.sh

# 2. Run a goal (local execution, auto mode)
justai run --auto --local "add a /health endpoint to server.py"

# 3. Open the dashboard
cd dashboard && npm run dev    # http://localhost:3001
```

## CLI

```bash
justai run "goal"                  # full pipeline with agent delegation
justai run --auto "goal"           # skip R1 checkpoint 60s wait
justai run --auto --local "goal"   # execute locally (no agent needed)
justai plan "goal"                 # decompose into tasks (no execution)
justai status                      # service health + memory stats
justai history                     # recent runs from memory
justai version                     # print version
```

All commands also work via `python3 -m justai <command>`.

## Dashboard

Five views, all real-time:

| View | What it shows |
|------|---------------|
| **Mission Control** | System health, agent status, active pipeline, task stats |
| **Task Board** | 5-column Kanban (pending -> done) from SpacetimeDB |
| **Runs** | Run history, trigger new runs, active run status |
| **Trajectory Viewer** | Step-by-step replay of any agent execution |
| **Memory Browser** | Browse, search, store claude-flow memory (HNSW vector) |

Start the API server for full dashboard features:
```bash
python3 -m justai.api   # API on :3002
cd dashboard && npm run dev   # Dashboard on :3001
```

## Pipeline Stages

| # | Stage | Module | Purpose |
|---|-------|--------|---------|
| 0 | Preflight | `health.py` | Check LiteLLM, SpacetimeDB, MCP health |
| 1 | Session | `orchestrator.py` | Load prior context from memory |
| 2 | Intent | `intent_gate.py` | Classify goal (execution/research/ambiguous) |
| 3 | Plan | `planner.py` | Decompose into mini-sized tasks with verify commands |
| 4 | Review | `reviewer.py` | LLM validates plan quality, replan if rejected |
| 5 | Checkpoint | `checkpoint.py` | R0-R3 risk gates (auto mode skips R1 wait) |
| 6 | Execute | `executor.py` / `delegator.py` | Local subprocess or agent via SpacetimeDB |
| 7 | Synthesize | `synthesizer.py` | Aggregate results, store to memory |

## Architecture

```
Orchestrator (Python)  -->  LiteLLM (:4000)  -->  Model APIs
       |
       v
SpacetimeDB (:3000)   <-->  mini-swe-agent (bash execution)
       |
       v
claude-flow MCP (:3100)     Dashboard (:3001) + API (:3002)
264 tools, HNSW memory      React + Vite, 5 views
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system diagram.

## Configuration

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `LITELLM_BASE_URL` | `http://localhost:4000` | Model routing proxy |
| `LITELLM_KEY` | *(from .env)* | LiteLLM auth token |
| `JUSTAI_AUTO_MODE` | `0` | Skip R1 checkpoint wait |
| `JUSTAI_LOCAL_EXEC` | `0` | Execute tasks locally |
| `JUSTAI_SESSION_REF` | `sprint-2` | Session identifier |
| `LANGFUSE_PUBLIC_KEY` | *(optional)* | LLM tracing |
| `LANGFUSE_SECRET_KEY` | *(optional)* | LLM tracing |

## Testing

```bash
python3 -m pytest tests/ -v
# 267+ tests across 11 sprints
```

## Built On

- **[mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent)** — Princeton & Stanford. 74% SWE-bench Verified. MIT License.
- **[Ruflo / claude-flow](https://github.com/ruvnet/ruflo)** — rUv. 6,000+ commit orchestration platform. MIT License.
- **[SpacetimeDB](https://spacetimedb.com)** — Clockwork Labs. Real-time distributed database. BSL License.
- **[LiteLLM](https://github.com/BerriAI/litellm)** — BerriAI. Model routing. MIT License.
- **[LangFuse](https://langfuse.com)** — LLM observability. MIT License.

See [docs/ATTRIBUTION.md](docs/ATTRIBUTION.md) for the complete credits.

---

**v1.0.0** — First release. Full pipeline, local execution, dashboard, CLI.
