# JustAi

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

JustAi is a project-orchestration control-plane for breaking engineering goals into small, reviewable tasks and running them through checkpointed local workflows.

## Status

This repository is in a public stabilization pass after a cleanup and architecture reset.

- Current code is the JustAi control-plane layer.
- The execution substrate is being separated into `safe-mini`.
- The experiment/calibration driver is being separated into `local-resident`.
- Some CLI paths still expose transitional behavior while the split finishes.

## Architecture

JustAi scopes a user goal into bounded tasks, reviews the plan, applies risk checkpoints, runs the currently available local verification path, records run history, and synthesizes the result.

The intended three-repo shape is:

| Repo | Role |
| --- | --- |
| `safe-mini` | Local execution substrate: runner loop, command/path guards, isolated worktrees, observation policy, incident artifacts, trajectory recording, and canonical execution types. |
| `JustAi` | Control-plane: goal decomposition, chunk sizing, checkpoints, review, coordination, dashboard/API support, and synthesis. |
| `local-resident` | Local experiment driver: private benchmark slices, calibration runs, and comparative evaluation. |

## CLI

Current CLI surface:

```bash
justai run [--auto] [--local] [--session SESSION] "goal"
justai plan [--session SESSION] "goal"
justai status
justai history [--limit N]
justai version
justai --version
```

All commands also work as:

```bash
python3 -m justai <command>
```

Current behavior:

- `justai plan` produces a task plan and falls back to heuristic planning when the model-routing service is unavailable.
- `justai status` reports control-plane dependency health.
- `justai history` reads prior run summaries when local memory is configured.
- `justai run --auto --local "goal"` runs the orchestrator and executes each approved task's verification command locally.
- `justai run --auto "goal"` enters a delegated mode that is intentionally disabled in this branch and returns an explicit error.

## Pipeline

| Stage | Module | Role |
| --- | --- | --- |
| Intent | `intent_gate.py` | Classify the goal and ask for clarification when it is ambiguous. |
| Scope | `scope_planner.py` | Decompose the goal into bounded tasks with success criteria. |
| Review | `reviewer.py` | Check whether the plan is coherent enough to run. |
| Checkpoint | `checkpoint.py` | Apply R0-R3 risk gates; `--auto` skips the R1 wait. |
| Execute/Synthesize | `agent_dispatch.py`, `synthesizer.py` | Run local verification commands or return removed-backend errors, then summarize results. |

## Dashboard

The `dashboard/` directory contains the React control-plane UI. `src/` is the
authenticated control-plane surface (mission control, task board, run history,
observability); `demo/` is the self-contained sprint-simulation build served at
the public production deployment (justai-demo.vercel.app).

## Install

For an existing checkout with a prepared virtualenv:

```bash
source .venv/bin/activate
python -m pytest -q
justai --help
```

Fresh editable install:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m pytest -q
```

## Quick Start

```bash
source .venv/bin/activate
justai plan "describe the repo change you want"
justai run --auto --local "describe the repo change you want"
```

The local run path executes checkpointed verification commands for planned tasks. It is not a full autonomous code-editing backend in this branch.

## Testing

Canonical test run:

```bash
.venv/bin/python -m pytest -q
```

Current expected result for this branch is 424 passing tests, 0 failures, plus 14 passing subtests reported by pytest output.

## Repo Map

```text
justai/
  cli.py             # CLI entrypoint
  orchestrator.py    # intent -> plan -> review -> checkpoint -> execute/synthesize
  scope_planner.py   # goal decomposition and task models
  agent_dispatch.py  # transitional dispatch ladder and removed-backend errors
  checkpoint.py      # R0-R3 risk gates
  reviewer.py        # plan quality gate
  memory.py          # local memory client
  trajectory.py      # run trajectory recording and lookup
  ledger.py          # run accounting
  health.py          # service probes
  results.py         # delegation/result dataclasses
  api.py             # dashboard/API support
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the fuller control-plane overview.

## Security

See [SECURITY.md](SECURITY.md) for responsible disclosure and the documented historical-secret allowlist.

## License

MIT. See [LICENSE](LICENSE).
