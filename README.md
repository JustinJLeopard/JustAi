# JustAi

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

JustAi is a thin project-orchestration control plane around safe-mini, the substrate that makes mini-swe-agent's bash-action loop trustworthy on private repos.

## Status

This repo is actively under restructure.

- The safe-mini repo is not stood up yet.
- The current code is the JustAi orchestrator half of the three-repo plan.
- The public docs are being aligned after the Phase 4 amputation pass.
- Some CLI paths still expose transitional behavior while stabilization continues.

If you are looking for the v1.0.0 product shape, this branch is no longer that. The old delegation backends were removed and the repo is being narrowed to the control-plane role.

## Architecture In Three Sentences

JustAi scopes a user goal into small, reviewable chunks, using `justai.scope_planner` and the existing checkpoint/reviewer flow to keep the work bounded. Execution is being reframed around safe-mini: a small, auditable substrate for mini-swe-agent-style bash actions with worktree isolation, env scrubbing, command/path guards, observation policies, and incident artifacts. The control plane should classify failures instead of pretending every failed run is the same, so budget exhaustion, context starvation, reward hacking, embodiment failures, safety violations, and action-protocol violations can drive different next steps.

## The Three-Repo Plan

The intended post-closure shape is:

| Repo | Role |
| --- | --- |
| `safe-mini` | Load-bearing foundation: runner loop, executor and observation policies, worktree provisioner, command/path guard, incident artifacts, failure classifier, trajectory recording, ledger, and canonical types. |
| `JustAi` | Thin orchestrator: goal decomposition, chunk sizing, checkpoints, review, coordination, dashboards, and synthesis. |
| `local-resident` | Local experiment driver: runs private benchmark slices over safe-mini, gathers calibration data, and validates whether JustAi adds value over raw mini. |

Ship plan:

- Phase A: JustAi and local-resident consume safe-mini through a git URL pin while the API stabilizes.
- Phase B: safe-mini publishes to PyPI and consumers move to normal version pins.
- Current reality: safe-mini does not exist as a repo yet. That is post-JustAi-closure work.

## CLI

Verified from the current venv:

```bash
.venv/bin/justai --help
.venv/bin/justai run --help
.venv/bin/justai plan "add a health endpoint"
.venv/bin/justai status
.venv/bin/justai history
.venv/bin/justai version
```

Current CLI surface:

```bash
justai run [--auto] [--local] [--session SESSION] "goal"
justai plan [--session SESSION] "goal"
justai status
justai history [--limit N]
justai version
justai --version
```

Important behavior:

- `justai plan` works and falls back to heuristic planning when the model call is unavailable.
- `justai status` reports the current control-plane dependencies: LiteLLM, the safe-mini boundary stub, and memory/MCP availability.
- `justai history` works against the memory client and prints no history when no run keys exist.
- `justai run --auto --local "goal"` runs the orchestrator and executes each approved task's verification command locally. It does not edit code for you.
- `justai run --auto "goal"` enters the default delegated mode, but that backend has been removed and currently returns an explicit error: use `--local` for the remaining local verification path.

All commands also work as:

```bash
python3 -m justai <command>
```

## Pipeline Stages

The current orchestrator still runs a compact five-stage control-plane flow:

| Stage | Module | Current role |
| --- | --- | --- |
| Intent | `intent_gate.py` | Classify the goal and ask for clarification when it is ambiguous. |
| Scope | `scope_planner.py` | Decompose the goal into bounded tasks with success criteria. |
| Review | `reviewer.py` | Check whether the plan is coherent enough to run. |
| Checkpoint | `checkpoint.py` | Apply R0-R3 gates; `--auto` skips the R1 wait. |
| Execute/Synthesize | `agent_dispatch.py`, `synthesizer.py` | Run local verification commands or return removed-backend errors, then summarize results. |

## Dashboard

The dashboard code is still present under `dashboard/`, and the build passed in Chunk D. Its visible product language may still reflect older flows until the UI cleanup catches up with the backend amputation.

Current docs stance:

- Treat the dashboard as a transitional operations surface.
- Do not assume removed backend views represent live execution paths.
- Dashboard cleanup is outside this README/architecture alignment chunk.

## Current Identity

JustAi is now a thin project-orchestration layer over safe-mini (load-bearing local-execution substrate). See ARCHITECTURE.md for the 3-repo decomposition.

The current repo should be read as the control plane: it scopes work, reviews chunks, applies checkpoints, records trajectories, and presents operational state. Runtime mechanics belong in safe-mini; experiment calibration belongs in local-resident.

## Install

For this branch, prefer the existing venv if it is already present:

```bash
source .venv/bin/activate
python -m pytest -q
justai --help
```

Fresh editable install should be:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m pytest -q
```

The historical installer is still in the repo, but it has not been aligned with the post-amputation shape in this chunk:

```bash
bash install.sh --check
```

Treat installer and script cleanup as fix-in-progress until the separate code-amputation pass lands.

## Quick Start

Use the current control-plane surface first:

```bash
source .venv/bin/activate
justai plan "describe the repo change you want"
justai run --auto --local "describe the repo change you want"
```

The `run --local` path runs checkpointed local verification commands for planned tasks. It is not a full autonomous code-editing backend in this branch.

## Testing

Canonical test run:

```bash
.venv/bin/python -m pytest -q
```

Current expected result for this branch is 370 passing tests, 0 failures, plus 14 passing subtests reported by pytest output.

## Current Repo Map

```text
justai/
  cli.py             # current `justai` CLI entrypoint
  orchestrator.py    # intent -> plan -> review -> checkpoint -> execute/synthesize
  scope_planner.py   # goal decomposition and task models
  agent_dispatch.py  # transitional dispatch ladder and removed-backend errors
  checkpoint.py      # R0-R3 risk gates
  reviewer.py        # plan quality gate
  memory.py          # claude-flow memory client
  trajectory.py      # run trajectory recording and lookup
  ledger.py          # run accounting
  health.py          # service probes
  results.py         # delegation/result dataclasses
  api.py             # dashboard/API support
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the fuller control-plane overview.

## Evidence Trail

Memory keys that explain the current direction:

- `justai-architecture-decision-mini-swe-agent-control-plane`
- `safe-mini-substrate-architecture`
- `justai-safe-mini-scaffold-pattern`
- `justai-two-repo-ship-pattern` (stale key name; content is the three-repo plan)

Relevant local files:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/TESTING.md](docs/TESTING.md)
- [VERIFY-REPORT-2026-04-30.md](VERIFY-REPORT-2026-04-30.md)
- [MINI-SWE-AGENT-RESEARCH-2026-04-30.md](MINI-SWE-AGENT-RESEARCH-2026-04-30.md)

## License

MIT. See [LICENSE](LICENSE).
