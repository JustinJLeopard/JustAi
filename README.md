# JustAi

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

JustAi is a project-orchestration control-plane for breaking engineering goals into small, reviewable tasks and running them through checkpointed local workflows.

[Live demo](https://justai-demo.vercel.app) · [Case study](https://www.delegateandorchestrate.com/work/justai) · [Portfolio](https://www.delegateandorchestrate.com) · [Safe execution substrate](https://github.com/JustinJLeopard/safe-mini)

## Status

JustAi is public as the control-plane layer of a broader agent-infrastructure system. The current split is intentional: keep orchestration, execution safety, evaluation, and experiments auditable as separate surfaces instead of hiding them in one opaque agent repo.

- Current code is the JustAi control-plane layer.
- The execution substrate is being separated into `safe-mini`.
- The experiment/calibration driver is being separated into `local-resident`.
- Some CLI paths still expose transitional behavior while the split finishes.

## Public Proof Path

| Surface | What to inspect |
| --- | --- |
| [JustAi demo](https://justai-demo.vercel.app) | Mission-control UI for tasks, routing, trajectories, review quality, and run accounting. |
| [JustAi case study](https://www.delegateandorchestrate.com/work/justai) | Product framing, system boundaries, and why orchestration needs visible checkpoints. |
| [`safe-mini`](https://github.com/JustinJLeopard/safe-mini) | Safe local execution substrate for bash-action coding agents. |
| [`route-mini`](https://github.com/JustinJLeopard/route-mini) | Routing-policy reference implementation for provider/model selection. |
| [`memory-mini`](https://github.com/JustinJLeopard/memory-mini) | Typed durable memory substrate for agent runs. |
| [`lab-mini`](https://github.com/JustinJLeopard/lab-mini) | Experiment loop for small, repeatable agent capability checks. |

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

Current expected result for this branch is 380 passing tests, 0 failures, plus 14 passing subtests reported by pytest output.

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

See [SECURITY.md](SECURITY.md) for responsible disclosure and repository hygiene notes.

## License

MIT. See [LICENSE](LICENSE).
