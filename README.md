# JustAi

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

JustAi is a project-orchestration control-plane: it breaks engineering goals into small, reviewable tasks, reviews the resulting plan, and applies risk checkpoints. It does not currently execute those tasks — no execution backend is wired, so `run` fails closed rather than reporting work it did not perform.

[Live demo](https://justai-demo.vercel.app) · [Case study](https://www.delegateandorchestrate.com/work/justai) · [Portfolio](https://www.delegateandorchestrate.com) · [Safe execution substrate](https://github.com/JustinJLeopard/safe-mini)

## Status

JustAi is public as the control-plane layer of a broader agent-infrastructure system. The current split is intentional: keep orchestration, execution safety, evaluation, and experiments auditable as separate surfaces instead of hiding them in one opaque agent repo.

- Current code is the JustAi control-plane layer.
- The execution substrate exists separately as `safe-mini`, but this repository does not yet pin or invoke it.
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

JustAi scopes a user goal into bounded tasks, reviews the plan, and applies risk checkpoints. Its execution backends are currently unavailable: the removed delegated path and the unwired local safe-mini path both fail closed instead of claiming task completion.

The intended three-repo shape is:

| Repo | Role |
| --- | --- |
| `safe-mini` | Local execution substrate: runner loop, command/path guards, isolated worktrees, observation policy, incident artifacts, trajectory recording, and canonical execution types. |
| `JustAi` | Control-plane: goal decomposition, chunk sizing, checkpoints, review, coordination, dashboard/API support, and synthesis. |
| `local-resident` | Local experiment driver: private benchmark slices, calibration runs, and comparative evaluation. |

## CLI

Current CLI surface:

```bash
justai run [--auto] [--local] [--session SESSION] [--run-id ID] "goal"
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
- `justai status` reports control-plane dependency health, broken out into planning readiness and execution readiness. It exits 0 only when every probe is up — the same derivation the API's `/health` endpoint reports as `all_ok`.
- `justai history` reads prior run summaries when local memory is configured.
- `justai run --auto --local "goal"` currently returns an explicit unavailable-backend error. It does not execute planner-authored shell strings or report an unperformed edit as complete.
- `justai run --auto "goal"` enters a delegated mode that is intentionally disabled in this branch and returns an explicit error.

### Approval gates

Every run mints a run id — a UUID — and prints it before it reaches a gate. Its
R1 and R2 gates live under that id:

```text
$JUSTAI_RUNTIME_ROOT/gates/<run_id>/plan-<index>.json
```

The checkpoint prints the exact path to write to. An operator decides one task
in one run:

```bash
echo '{"status":"approved"}' > .../gates/<run_id>/plan-0.json   # release an R2 task
echo '{"status":"vetoed"}'   > .../gates/<run_id>/plan-0.json   # stop an R1 task
```

`--session` is a human label for tracing and memory. It is reused on purpose
and is usually empty, so it names nothing: two concurrent runs sharing a label
still have separate gates, and an approval written for one does not release the
other. `--run-id` is the deliberate exception — it resumes a run against the
gates already on disk. Omit it and a fresh identity is minted, which is what an
ordinary run wants.

An approval may be written before the run reaches the gate — a resume, or the
dashboard, which is handed the run id by `POST /api/run` while the run is still
starting. A run never writes over a decision already on disk; it only records
that it is waiting when nothing has decided yet.

What is left under `gates/` afterwards:

| Directory | Kept | Why |
| --- | --- | --- |
| A run that finished its gates | Until it is an hour old | It holds only `.lock`, and removing a lock other processes exclude on is how exclusion ends. There is nothing else in it. `JUSTAI_GATE_TOMBSTONE_TTL` sets the window. |
| A run interrupted at a gate | Indefinitely | Its records are a pending approval nobody answered, and are what `--run-id` resumes against. Remove the directory when you are done with the run. |

Old directories are collected at the end of each run. Nothing that still holds
a gate record, is still running, or holds a file JustAi did not write is ever
removed.

### Exit codes

Exit 0 means verified completion: work was planned, it ran, and every task reported done. Nothing else earns it — an ambiguous goal is a legitimate answer, but nothing was planned and nothing ran, so returning 0 would tell a `&&` chain the work happened.

| Code | Name | Meaning |
| --- | --- | --- |
| 0 | `OK` | Verified complete. |
| 1 | `FAILED` | The run did not complete (partial, blocked, or failed). |
| 2 | — | Reserved: `argparse`'s usage-error code, never assigned by JustAi. |
| 3 | `CLARIFICATION_REQUIRED` | The goal was ambiguous; no plan was run. |
| 4 | `NOT_READY` | A readiness probe reported the control plane unready. |

See [`justai/exit_codes.py`](justai/exit_codes.py) for the mapping.

## Pipeline

| Stage | Module | Role |
| --- | --- | --- |
| Intent | `intent_gate.py` | Classify the goal and ask for clarification when it is ambiguous. |
| Scope | `scope_planner.py` | Decompose the goal into bounded tasks with success criteria. |
| Review | `reviewer.py` | Check whether the plan is coherent enough to run. |
| Checkpoint | `checkpoint.py` | Apply R0-R3 risk gates, scoped to one run by `run_identity.py`; `--auto` skips the R1 wait. |
| Execute/Synthesize | `agent_dispatch.py`, `synthesizer.py` | Fail closed while execution backends are unavailable, then summarize the non-success result. |

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
```

The current branch is a planning and checkpointing control-plane skeleton, not a productive coding runner. Do not use `run` as a completion oracle until an exact-pinned safe-mini runner and goal-bound artifact acceptance are integrated and verified.

## Testing

Canonical test run:

```bash
.venv/bin/python -m pytest -q
```

Current expected result for this branch is 517 passing tests, 0 failures, plus 14 passing subtests reported by pytest output.

The suite is order-independent. Reversing collection order must produce the same result:

```bash
.venv/bin/python -m pytest -q $(ls -r tests/test_*.py)
```

## Repo Map

```text
justai/
  cli.py             # CLI entrypoint
  orchestrator.py    # intent -> plan -> review -> checkpoint -> execute/synthesize
  scope_planner.py   # goal decomposition and task models
  agent_dispatch.py  # transitional dispatch ladder and removed-backend errors
  checkpoint.py      # R0-R3 risk gates, scoped to one run
  run_identity.py    # the run id a gate belongs to
  reviewer.py        # plan quality gate
  memory.py          # local memory client
  trajectory.py      # run trajectory recording and lookup
  ledger.py          # run accounting
  health.py          # service probes and planning/execution readiness
  results.py         # result dataclasses, status vocabulary, run verdict
  exit_codes.py      # documented process exit codes
  api.py             # dashboard/API support
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the fuller control-plane overview.

## Security

See [SECURITY.md](SECURITY.md) for responsible disclosure and repository hygiene notes.

## License

MIT. See [LICENSE](LICENSE).
