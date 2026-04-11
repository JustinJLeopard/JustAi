# JustAi

> **"The best code agent in the world was missing one thing. We built it."**

JustAi is orchestration, memory, and control for the world-class, benchmark-leading
mini-swe-agent. Built on research from Princeton & Stanford, powered by rUv's
agent infrastructure.

---

## What It Does

JustAi gives mini-swe-agent — the world's highest-performing open-source agent at
74% SWE-bench Verified — the planning, memory, human-in-the-loop control, and
real-time visibility it was missing.

- Takes a goal in plain English
- Decomposes it into well-scoped tasks
- Delegates execution to mini-swe-agent via SpacetimeDB
- Persists all decisions and outcomes across sessions
- Surfaces progress in real-time via Discord and a web dashboard

---

## Quick Start

```bash
cd ~/projects/JustAi
bash scripts/start_justai.sh
```

## CLI Commands

```bash
python3 tools/justai_cli.py status
python3 tools/justai_cli.py start
python3 tools/justai_cli.py health
python3 tools/justai_cli.py task "your task description"
python3 tools/justai_cli.py mini "summarize the workspace"
python3 tools/justai_cli.py relay status
```

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `JUSTAI_ROOT` | auto-detected | Repo root |
| `JUSTAI_LOCALMANUS_ROOT` | `$JUSTAI_ROOT/LocalManus` | LocalManus runtime |
| `JUSTAI_RELAY_ROOT` | `$JUSTAI_ROOT/relay-room` | Relay task system |
| `JUSTAI_SPACETIME_SESSION` | `spacetime` | SpacetimeDB tmux session |
| `JUSTAI_RELAY_SERVER` | `local-server` | SpacetimeDB server |

---

## Built On

JustAi stands on the shoulders of giants:

- **mini-swe-agent** by the SWE-agent team at Princeton & Stanford University
  (https://github.com/SWE-agent/mini-swe-agent) — MIT License
  74% SWE-bench Verified. The world's best open-source agent.

- **Ruflo / claude-flow / SAFLA / agentic-flow** by rUv (Reuven Cohen)
  (https://github.com/ruvnet) — MIT License
  6,000+ commit agent orchestration infrastructure. Used by Meta, NVIDIA, IBM.

- **SpacetimeDB** by Clockwork Labs (https://spacetimedb.com) — BSL License
  Real-time distributed database powering our task backbone.

- **LiteLLM** by BerriAI (https://github.com/BerriAI/litellm) — MIT License
  Model routing and fallback chain.

- **LangFuse** (https://langfuse.com) — MIT License
  LLM observability and cost tracking.

---

## Status

v1 in active development. See [docs/JUSTAI_V1_SPEC.md](docs/JUSTAI_V1_SPEC.md)
for the full product specification.
