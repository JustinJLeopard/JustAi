# JustAi Architecture

JustAi is a thin project-orchestration control plane around safe-mini, the substrate that makes mini-swe-agent's bash-action loop trustworthy on private repos.

This document describes the post-amputation architecture. It does not describe the original v1.0.0 delegation stack.

## Current Shape

```text
Orchestrator
============

Human / agent operator
        |
        v
JustAi control plane
  - classify intent
  - decompose goal into chunks
  - review plan quality
  - apply R0-R3 checkpoints
  - dispatch remaining executable work
  - synthesize results and memory
        |
        v
safe-mini substrate (separate repo; not yet wired here)
  - mini-style bash-action loop
  - worktree isolation
  - env scrubbing
  - command/path guard
  - observation policy
  - incident artifacts
  - trajectory + ledger
  - failure classifier
        |
        v
private benchmark / repo worktrees
```

The control plane should stay small enough to reason about. The substrate should stay small enough to audit in one sitting. The experiment driver should live outside both, because calibration work is not orchestration and not runtime substrate.

## Three Pillars

### 1. Scope

Scope lives in JustAi.

`justai.scope_planner` turns a goal into bounded tasks with success criteria, dependencies, risk labels, and target agent hints. `justai.reviewer` checks whether the plan is coherent. `justai.checkpoint` applies R0-R3 gates before anything is allowed to run.

The long-term job of this layer is to predict both budgets:

- move budget: how many bash actions a chunk should get
- observation budget: how much command output the agent should see per action

### 2. Substrate

Substrate lives in the separate safe-mini repository. JustAi does not yet import or invoke it.

The substrate is the load-bearing runtime around a mini-swe-agent-style loop:

- prompt -> one bash action -> observation -> repeat
- executor policies: open, safe, allowlist
- observation policies: full, tail, headtail, structured, structured plus raw tail
- worktree provisioner: copied repo, scoped HOME, sanitized PATH
- command/path guard: denylisted commands and sensitive paths
- incident artifact: full transcript saved for audit

JustAi should consume this as an imported dependency, not own it forever.

### 3. Guardrails And Classifier

Guardrails and failure classification also belong in safe-mini.

JustAi needs structured failure information from the runner so it can decide whether to re-scope, retry, escalate, or stop. That means the runtime should report failure class, trajectory, budget usage, and relevant incident artifacts in its `RunResult`.

## Three Repos

| Repo | Responsibility |
| --- | --- |
| `safe-mini` | Runtime foundation and public substrate API. |
| `JustAi` | Project orchestration, chunk sizing, checkpoints, dashboard, synthesis. |
| `local-resident` | Local experiment driver for private benchmark slices and calibration data. |

Planned dependency graph:

```text
JustAi -----------+
                  +--> safe-mini
local-resident ---+
```

Planned ship sequence:

- Phase A: consumers pin `safe-mini @ git+https://github.com/JustinJLeopard/safe-mini.git@...`.
- Phase B: safe-mini publishes to PyPI and consumers use a version pin.
- Current state: the safe-mini repo exists and has its own validation evidence, but JustAi has no pinned dependency or concrete runner integration. The local and delegated execution modes therefore fail closed.

## Current Repo Layout

The relevant Python package shape after the Phase 4 renames:

```text
justai/
  __init__.py
  __main__.py
  cli.py
  orchestrator.py
  scope_planner.py
  agent_dispatch.py
  checkpoint.py
  reviewer.py
  intent_gate.py
  synthesizer.py
  results.py
  memory.py
  trajectory.py
  ledger.py
  learning.py
  health.py
  tracing.py
  api.py
  auth.py
  discord.py
```

Important boundaries:

- `scope_planner.py` owns task decomposition and task data shapes for the current repo.
- `agent_dispatch.py` is transitional. Local, delegated, and swarm modes return explicit unavailable-backend errors; planner-authored success criteria are not executed as task completion.
- `checkpoint.py`, `reviewer.py`, and `intent_gate.py` are control-plane gates.
- `results.py`, `trajectory.py`, and `ledger.py` are the local result/accounting surface until safe-mini owns the canonical types.
- `memory.py` is integration glue with the surrounding development memory system.

## Failure Taxonomy

safe-mini should report failure classes rather than a single generic failure state:

- `exhausted-ideas`
- `budget-exhausted`
- `context-starvation`
- `reward-hacking`
- `embodiment-failure`
- `safety-violation`
- `action-protocol-violation`

These classes come from the safe-mini substrate architecture memory. JustAi should use them to choose the next orchestration move. For example, budget exhaustion implies a different fix than a safety violation.

## Two Budgets

The architecture uses two budgets, not one:

| Budget | Meaning |
| --- | --- |
| Move budget | Maximum bash actions for a chunk. |
| Observation budget | Maximum command output kept visible per action. |

The lab evidence matters here: tiny observations can fail an otherwise solvable task even if the move budget is generous. Scope prediction must size both.

## Runtime Data Flow

Current transitional flow:

```text
justai run --auto --local "goal"
  -> intent_gate.classify
  -> scope_planner.decompose
  -> reviewer.review_plan
  -> checkpoint.evaluate
  -> agent_dispatch.escalate_plan(mode="local")
  -> explicit unavailable-backend results
  -> synthesizer.synthesize(status="failed")
  -> trajectory / ledger / memory best-effort writes
```

No execution mode is a live backend right now. Local mode stays exposed only as a transitional compatibility surface and fails closed until exact-pinned safe-mini execution plus goal-bound artifact acceptance are integrated.

## Current Boundary

The live architectural boundary is the control-plane / substrate split:

- JustAi owns project orchestration, chunk sizing, checkpoints, dashboards, and synthesis.
- safe-mini owns the bash-action runner, executor policy, observation policy, worktree isolation, guards, incident artifacts, trajectory recording, ledger, and failure classifier.
- local-resident owns the private benchmark and calibration loop that proves whether the orchestration layer adds value.

Historical sprint-era designs now live under `docs/archive/` when they are still useful as evidence. They are not current product contracts.

## Migration Plan

When JustAi integrates safe-mini, remove or replace the remaining local placeholders and bind these pieces to the substrate's public API:

- runner loop and action protocol
- executor policy types
- observation policy types
- worktree provisioner
- command/path guard
- incident artifact writer
- failure classifier
- trajectory recorder
- run ledger
- canonical `Chunk`, `Budget`, `RunResult`, `FailureClass`, `ObservationPolicy`, and `ExecutorPolicy` types
- `AgentRunner` Protocol/ABC

TBD post-JustAi-closure:

- whether JustAi keeps a temporary local Protocol stub in Chunk F
- exact split between JustAi's current `trajectory.py`/`ledger.py` and safe-mini's canonical versions
- whether safe-mini ships benchmark fixtures or leaves all benchmark data to local-resident

## Design Rules

- Keep JustAi honest about what exists today.
- Do not reintroduce removed backends as documentation promises.
- Keep safe-mini generic; it should not know JustAi-specific dashboards, Discord, auth, or learning aggregation.
- Keep local-resident focused on experiment generation and calibration, not orchestration.
