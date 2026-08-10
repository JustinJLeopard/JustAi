# JustAi

**A thin project-orchestration layer with an explicit, bounded local-execution adapter for mini-swe-agent–style coding agents.**

JustAi sits between an engineering goal and the bash actions that fulfill it. It decomposes goals into bounded chunks, applies checkpoints, and records control-plane results. Its explicit SafeMini adapter runs actions through JustAi's Bubblewrap boundary in a copied worktree. SafeMini itself contributes worktree copying, environment scrubbing, command-policy guards, and an in-memory run transcript; those policy controls are not a standalone sandbox.

[**Try the live demo**](https://justai-demo.vercel.app) · [**delegateandorchestrate.com**](https://delegateandorchestrate.com)

---

## The thesis

[mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) decides one bash command at a time within a budget — about a hundred lines of agent loop. That minimalism is the point: every prompt-action-observation cycle is auditable, and every step is a candidate for a guardrail.

JustAi's boundary is explicit: the SafeMini adapter uses JustAi's Bubblewrap executor, while SafeMini provides the small runner contract and policy guards. The default local executor is unchanged; source integration is not a productive-runtime claim. JustAi wraps this bounded path with goals, chunks, dashboards, run history, and trajectory tooling.

The reference lab recorded 54 deterministic trials (6 task families × 9 configurations). In those fixture probes, an "open" executor leaked a fake credential 6/6 times while a "safe" policy blocked 6/6 probes and still solved 6/6 tasks. These results are reference-study evidence, not proof of host isolation, release readiness, or broad real-model performance.

---

## What ships in this repo

`justai/` — the orchestrator.

- **Scope planner** (`scope_planner.py`) — decomposes a goal into chunks fitted to a bash-move budget. Chunks know their move budget AND their observation budget.
- **Intent gate** (`intent_gate.py`) — classifies the goal type before any execution.
- **Reviewer** (`reviewer.py`) — pre-dispatch quality gate that catches ambiguous descriptions and missing success criteria.
- **Checkpoint** (`checkpoint.py`) — risk-level approval (R0 auto through R3 manual).
- **Agent dispatch** (`agent_dispatch.py`) — runs the available local verification path and exposes the explicit SafeMini adapter.
- **Runner Protocol** (`runner_protocol.py`) — compatibility protocol for
  existing control-plane code. The explicit `safe_mini_adapter.py` maps a
  JustAi task to SafeMini's public runner contract.
- **Trajectory store** — per-step record of every run: action type, file touched, observation, outcome.
- **Memory** — vector-indexed, queryable across runs and projects.
- **Dashboard** — Mission Control, Task Board, Trajectories, Memory, Agents, Observability views.

What does NOT ship here, by design:

- The runner itself, the observation policies, the executor policies, the failure classifier, the worktree provisioner — those live in [`safe-mini`](#three-repo-architecture) (substrate layer, separate repo).
- The benchmark task corpus and the experiment-driver harness — those live in [`local-resident`](#three-repo-architecture) (researcher repo, separate).

---

## Three-repo architecture

JustAi is one of three repos that share a substrate.

```
        ┌─────────────────────────┐         ┌────────────────────────────┐
        │      JustAi             │         │      local-resident        │
        │  (this repo)            │         │  (researcher harness)      │
        │                         │         │                            │
        │  • goal decomposition   │         │  • benchmark corpus        │
        │  • chunk sizing         │         │  • config-variation grid   │
        │  • reviewer + gates     │         │  • result aggregation      │
        │  • dashboard            │         │  • methodology rules       │
        └────────────┬────────────┘         └──────────────┬─────────────┘
                     │                                     │
                     │      both import substrate          │
                     ▼                                     ▼
                ┌────────────────────────────────────────────┐
                │                safe-mini                   │
                │       (load-bearing local-exec substrate)  │
                │                                            │
                │  • bash-action runner loop                 │
                │  • executor policies (open/safe/allowlist) │
                │  • observation policies                    │
                │  • copied worktree + env scrub             │
                │  • command-policy guard                    │
                │  • failure classifier (7-class taxonomy)   │
                │  • in-memory run transcript                │
                │  • canonical types + AgentRunner Protocol  │
                └────────────────────────────────────────────┘
```

Both consumers depend on `safe-mini` as a peer. `safe-mini` does not know about its consumers' domain models — it's intentionally generic, so future projects can ship on top of the same substrate.

The substrate's failure taxonomy:

| Class | Meaning |
|---|---|
| `safety-violation` | Agent attempted an action the executor policy denied. |
| `action-protocol-violation` | Output didn't parse as a valid action. |
| `exhausted-ideas` | Budget remained but loop converged without progress. |
| `budget-exhausted` | Move or observation budget hit the cap. |
| `context-starvation` | Observations truncated below decision-relevant detail. |
| `reward-hacking` | Test passed by means unrelated to the requested change. |
| `embodiment-failure` | Action ran but didn't produce the expected world-state change. |

Failure-classified runs feed back into the planner: chunks that hit `context-starvation` get larger observation budgets next time; chunks that hit `safety-violation` get re-decomposed around the boundary that tripped.

---

## Live demo

The interactive demo at [justai-demo.vercel.app](https://justai-demo.vercel.app) runs a full simulated sprint — eight tasks, three agents, real-time dashboard updates — entirely in the browser. No backend dependencies. The simulation drives the same UI components the real orchestrator uses; it's a fair preview of the production experience.

The demo includes:

- **Mission Control** — active runs, per-model cost, stage latency, sprint timeline at a glance.
- **Task Board** — Kanban with attempt count, retry, duration, escalation history per task.
- **Trajectories** — per-run timeline with phase markers, AI-generated post-mortem analysis.
- **Memory Browser** — searchable trajectory + run-result corpus.
- **Observability** — cost-vs-quality scatter, p50/p90/p99 latency by stage, token usage trends.
- **Agents** — agent-pool status, current assignments, online/offline/stale roll-up.

Sprint controls live in the top bar: pause, replay, speed multiplier. The simulation is deterministic at a given speed — replay produces identical trajectories.

---

## Status

Engineering surface is currently being prepared for public release. The repo is private during stabilization; the live demo (above) is the public-facing artifact.

Phase summary:

- **Phase 1-3** — closed.
- **Phase 4** — A through F landed 2026-04-29 (control-plane reframe, dead-code amputation, module renames, Protocol stub). G+H landed 2026-04-30 (ruff/mypy clean, test cleanup, docs-contract test lock-in).
- **Phase 5** — ratification: secrets scrub (gitleaks), dependency audit (pip-audit + npm audit), license check, install-verify in clean venv, 3-repo plan consistency.
- **Phase 6** — source integration: SafeMini is a separate repository and
  JustAi has an explicit, opt-in adapter pinned to an exact SafeMini commit.
  This is source-level integration, not an installation, runtime, or release
  claim.

`local-resident` remains a separate research harness; its own stand-up and any
public release are separate decisions.

---

## Getting in touch

Built by **Justin Leopard** at [Delegate & Orchestrate](https://delegateandorchestrate.com).

For research/collaboration inquiries — open an issue once this repo is public, or contact via the website.

---

## License

MIT — see [LICENSE](./LICENSE).
