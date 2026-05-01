# JustAi Agent Orientation

This file is the working orientation card for agents in this repo.

JustAi is a thin project-orchestration control plane around safe-mini, the substrate that makes mini-swe-agent's bash-action loop trustworthy on private repos.

## What This Project Is

JustAi is the orchestration repo in a planned three-repo architecture:

- `safe-mini`: load-bearing runtime substrate for safe mini-style bash-action execution.
- `JustAi`: control plane for scoping, checkpointing, reviewing, coordinating, and synthesizing work.
- `local-resident`: experiment driver that generates private calibration data over safe-mini.

The safe-mini repo is not stood up yet. This repo currently contains the orchestrator half and some transitional runtime/result glue.

## Current State

Phase 4 cleanup is in progress.

- Chunks B, C, and D have landed.
- Chunk E rewrites README, architecture docs, and this orientation file around the post-amputation shape.
- Remaining planned chunks: F for Protocol stub work, G for ruff/mypy, H for test cleanup.
- safe-mini repo stand-up is post-JustAi-closure work.

Do not assume old v1.0.0 behavior exists. The branch is intentionally narrowing the repo.

## Repo Layout

```text
justai/
  cli.py             # current `justai` CLI entrypoint
  orchestrator.py    # intent -> plan -> review -> checkpoint -> execute/synthesize
  scope_planner.py   # goal decomposition and task models
  agent_dispatch.py  # transitional dispatch ladder and removed-backend errors
  checkpoint.py      # R0-R3 risk gates
  reviewer.py        # plan quality gate
  intent_gate.py     # goal classification
  synthesizer.py     # result summary formatting and memory write
  results.py         # delegation/result dataclasses
  memory.py          # claude-flow memory client
  trajectory.py      # run trajectory recording and lookup
  ledger.py          # run accounting
  learning.py        # learning aggregation
  health.py          # service probes
  tracing.py         # optional LangFuse tracing
  api.py             # dashboard/API support
  auth.py            # dashboard/API auth helpers
  discord.py         # optional notification hooks

dashboard/           # React/Vite dashboard; not part of this docs chunk
docs/                # public docs and legacy evidence/spec files
tests/               # pytest suite
scripts/             # legacy operational scripts; cleanup is a separate chunk
tools/               # legacy helper tools; cleanup is a separate chunk
```

Do not touch these during the current docs-alignment chunk:

- `docs/JUSTAI_V1_SPEC.md`
- `docs/EVIDENCE.md`
- `docs/superpowers/*`
- `docs/TESTING.md`
- `install.sh`
- `scripts/*`
- `tools/*`

## Test Discipline

Canonical run:

```bash
.venv/bin/python -m pytest -q
```

Expected current result: 363 passing tests, 0 failures, plus 14 passing subtests reported by pytest output.

Use the existing `.venv` for verification. Do not install new dependencies unless the task explicitly requires it.

## Working CLI Surface

Verified current help:

```bash
justai run [--auto] [--local] [--session SESSION] "goal"
justai plan [--session SESSION] "goal"
justai status
justai history [--limit N]
justai version
justai --version
```

Behavior to know:

- `justai plan` works and can fall back to heuristic planning when model routing fails.
- `justai status` runs health probes, but some probes are transitional and may report removed/unavailable services.
- `justai history` reads run keys from memory and prints "No run history found" when empty.
- `justai run --auto --local "goal"` runs the pipeline and executes verification commands for approved tasks.
- `justai run --auto "goal"` uses delegated mode, which currently returns an explicit removed-backend error.

## What's Amputated

Do not try to use or revive these while doing normal repo work:

- control-plane data delegation.
- swarm mode, including `--swarm`, `JUSTAI_SWARM`, `swarm_dispatch`, `swarm_config`, and `swarm_scale`.
- `dispatch.py`.
- `executor.py`.
- legacy local runtime integration.
- control-plane and relay CLI flows.

If you find these in legacy docs, scripts, install helpers, or evidence files, treat them as historical unless the current task explicitly asks for that cleanup.

## Sacred Rule Scope

This repo is not the Agentic-Harness.

Agents may work freely inside this repo when the task is scoped here. The harness Sacred Rule applies to harness files such as `~/ruv_*.sh`, `~/.ruv_env`, `~/bin/memory-global`, `~/bin/ruv-daemon`, and protected docs under `~/projects/justai-harness/`.

If a change crosses into harness files, stop and follow the harness approval gate.

## Agent Working Notes

- Prefer small, task-scoped edits.
- Keep code and docs honest about current behavior.
- Do not document aspirational features as live.
- For Cowork-style posture, dispatched edits via `cdx`, `af-do`, or the cowork shell bridge are preferred when coordinating between agents.
- Direct edits are fine for Codex on Resident-style task-scoped work in this repo.
- Do not revert unrelated dirty files. This repo often has generated logs and local artifacts.

## Context To Read

Memory keys:

- `justai-architecture-decision-mini-swe-agent-control-plane`
- `safe-mini-substrate-architecture`
- `justai-safe-mini-scaffold-pattern`
- `justai-two-repo-ship-pattern` (stale key name; content is the three-repo plan)

Local docs:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/TESTING.md`
- `VERIFY-REPORT-2026-04-30.md`

## Current Direction

The target is not "one repo owns everything." The target is:

- safe-mini owns the safe execution substrate.
- JustAi owns project orchestration around that substrate.
- local-resident owns experiment generation and calibration.

Keep that boundary clear in new work.
