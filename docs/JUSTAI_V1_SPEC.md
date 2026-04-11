# JustAi v1 — Product Specification

**Version:** 1.1 (Evidence-updated)
**Date:** 2026-04-11
**Status:** Pre-build — approved for implementation

> *"The best code agent in the world was missing one thing. We built it."*
> *JustAi — orchestration, memory, and control for mini-swe-agent.*
> *Built on research from Princeton & Stanford, powered by rUv's agent infrastructure.*

---

## 1. What JustAi Is

JustAi is a self-hostable AI development orchestrator. It gives mini-swe-agent —
the world's highest-performing open-source coding agent — the planning, memory,
control, and real-time visibility it was missing.

JustAi is not a chat interface. It is not another AI wrapper. It is an agent
harness system backed by actual curriculum: a system that takes goals, decomposes
them into tasks, delegates execution to the best available agent (mini-swe-agent,
mini-swe-agent configured for the particular task, or a particular specialty agent),
persists all decisions and outcomes across sessions, and gives the human operator
full visibility and control at every step.

---

## 2. Positioning

**Primary tagline:**
> "The best code agent in the world was missing one thing. We built it."

**Sub-headline:**
> JustAi — orchestration, memory, and control for the world-class, benchmark-leading
> mini-swe-agent. Built on research from Princeton & Stanford, powered by rUv's
> agent infrastructure.

**Credibility stack:**
- mini-swe-agent: 74% SWE-bench Verified — world's highest-performing open-source
  coding agent. Built by Princeton & Stanford researchers.
- Ruflo (rUv): 6,000+ commit agent orchestration platform. Used by Meta, NVIDIA,
  IBM, Essential AI, Anyscale.
- SpacetimeDB: Real-time distributed database 1000x faster than leading DB platforms,
  full task lifecycle, built in Rust.
- JustAi: The orchestration layer that makes all of it production-usable and directed.

---

## 3. Target Audience

### Tier 1 — Primary (convert immediately)
Solo developers and small dev teams (1-5 people) hitting the ceiling of AI coding
tools like Cursor, Copilot, and Claude Code. They want autonomous multi-step
execution, not just autocomplete. Technical enough to run a terminal. Done with
babysitting agents.

### Tier 2 — Secondary (convert after proof)
Indie hackers and micro-SaaS builders who measure success in shipping velocity.
"AI co-founder that actually executes" resonates deeply. They will pay for anything
that compresses calendar time.

### Tier 3 — Expansion (enterprise, post-v1)
Dev shops and agencies building agentic workflows for clients. Need stability,
documentation, and brandable infrastructure. The Princeton/Stanford/rUv credibility
stack lands hardest here.

---

## 4. Core Architecture

```
+----------------------------------------------------------+
|                    Human (operator)                      |
|          Discord (natural language + remote control)     |
|          Web Dashboard (real-time visualization)         |
+-----------------------------+----------------------------+
                              |
+-----------------------------v----------------------------+
|                  JustAi Orchestrator                     |
|    Intent Gate -> Planner -> Delegator -> Synthesizer    |
|    Reviewer (planning quality gate, evidence-backed)     |
|    claude-flow memory (cross-session persistence)        |
+-------+----------------------------------+---------------+
        |                                  |
+-------v--------+              +----------v---------+
|  mini-swe      |              |   Ruflo Swarm      |
|  -agent v2     |              |   (specialist      |
|  (executor)    |              |    agents)         |
+-------+--------+              +----------+---------+
        |                                  |
+-------v----------------------------------v---------------+
|                    SpacetimeDB                           |
|    Task lifecycle  Agent registry  Ledger                |
|    Real-time subscriptions  Audit trail  Trajectories    |
+------------------------------+---------------------------+
                               |
+------------------------------v---------------------------+
|                    LiteLLM                               |
|    Gameron -> Gemma-4 local -> DeepSeek ->               |
|    Gemini Flash -> Groq (fallback chain)                 |
+----------------------------------------------------------+
```

### Component Responsibilities

| Component | Role | Source |
|---|---|---|
| JustAi Orchestrator | Intent -> Plan -> Delegate -> Synthesize | Built - new |
| Reviewer | Planning quality gate (pre-execution, not runtime) | Built - new |
| mini-swe-agent v2 | Bash-only execution, 74% SWE-bench, any task type | Princeton/Stanford, MIT |
| Ruflo / claude-flow | Agent swarm coordination + memory | rUv, MIT |
| SAFLA | Safety validation | rUv, MIT |
| SpacetimeDB | Task lifecycle, agent registry, ledger, trajectories | Clockwork Labs, BSL |
| Discord bot | Human-in-the-loop, A2A comms (swappable for enterprise) | Built - existing relay-room |
| Web Dashboard | Real-time visualization, observability, trajectory viewer | Built - new |
| LiteLLM | Model routing + fallback (customer-configurable) | Open source |

---

## 5. What Exists vs What to Build

### Already Built (relay-room, 10 sprints)
- SpacetimeDB Rust module: full task lifecycle reducers (post, claim, start,
  complete, fail, requeue, archive, heartbeat, agent registration)
- Discord bot infrastructure: 1,200+ line bot_listener.py, proven in production,
  per-agent channels, slash commands, watchdog, retry resilience
- relay_dispatch.sh: 100% first-try success rate at Sprint 9
- Health server, relay web, session capture, log archive
- Agent naming and routing conventions (ADR-001)
- Test suite across all major components

**Evidence note (from traj/log analysis):** The 80%->90%->100% success curve was
driven by: (1) coworkclaude improving task decomposition quality each sprint,
(2) retry logic added in Sprint 8, (3) tasks becoming more granular. mini-swe-agent
v2.2.8 running claude-opus-4-6 via Gameron at 35 msgs/task avg. Model switching
was a designed fallback that never triggered because Opus never failed enough to
need it. The recipe for 100% is well-scoped, unambiguous tasks — not model switching.

### Already Built (LocalManus / JustAi scaffold)
- justai_cli.py + justai_runtime.py: clean Python CLI, env-var-driven paths
- mini-swe-agent integration via mini_local_cloud.sh (Opus) and mini_local.sh (Qwen3)
- LiteLLM config with full model routing and fallback chain
- start_justai.sh with SpacetimeDB + LocalManus + relay startup sequence

**Warning:** SpacetimeDB or OpenFang daemon had memory issues on start/stop cycles.
Workaround was to inject/extract necessary context before start/stop. Investigate
and resolve properly in Sprint 1 before building on top of it.

### To Build - New in v1
1. JustAi Orchestrator core: intent intake, goal decomposition into mini-sized
   tasks, delegation, result synthesis, checkpoint/approval gates
2. Reviewer component: planning quality gate that validates task decomposition
   before any tasks are posted to SpacetimeDB (pre-execution, not runtime)
3. Web Dashboard: React frontend on SpacetimeDB real-time subscriptions,
   task board, agent status, trajectory viewer, memory browser, LangFuse integration
4. Memory bridge: claude-flow memory write on decisions/outcomes, surface at start
5. Clean naming: remove LocalManus, ManusLocal references throughout
6. Attribution layer: README, docs, landing page copy with proper credits
7. Installer: single-command setup

### To Remove / Deprecate
- Honcho references (relay-room honcho_writeback.py, LocalManus/memory/)
  — replace with claude-flow memory. Audit .venv usage before removing.
- relay-room .venv committed to repo — gitignore + remove from tracking
- OpenFang orchestrator routing — config files kept as future reference only
- Hard-coded /home/justinleopard/ paths and any other machine-specific hardcoding
- Unused configs/files/code — surface via log analysis vs. actual usage in Sprint 1

---

## 6. v1 Feature Scope

### In Scope
- CLI-first operation: justai run "goal description"
- Goal decomposition into sequenced, mini-sized tasks
- mini-swe-agent as primary executor — any task type, not just code
- Human-in-the-loop checkpoints at configurable risk levels (default: autonomous)
- Full task audit trail + trajectory storage in SpacetimeDB
- Discord integration: natural language control, per-agent channels, notifications,
  remote access from anywhere. Discord bot tokens require manual setup per bot.
- Stunning web dashboard with real-time observability. LangFuse integration for
  LLM cost/latency/quality tracking per task.
- Cross-session memory via claude-flow
- Self-hosted only, single-user (operator) mode

### Out of Scope for v1
- Multi-user / team features
- Cloud hosting / SaaS
- Fine-tuning or model training
- Mobile app
- Payment / billing
- Agent payment ledger (Sprint 10 design, v2 implementation)
  Note: reinforcement learning reward signals are the right mechanism here
- Parallel dispatch at scale (foundation exists, wire in v2)
- OpenFang integration (deferred — was not operational during sprint history)

---

## 7. Web Dashboard Specification

Must be genuinely beautiful — not vibe-coded, not generic dev tool aesthetic.
Real design quality. Dark theme default. Every view should feel like a product.

### Core Views

**Mission Control (home)**
- Live agent status grid: name, current task, last heartbeat, success rate
- Active task pipeline: pending -> claimed -> running -> done, real-time
- System health: LiteLLM status, SpacetimeDB connection, harness services

**Task Board**
- Kanban columns: Pending / Claimed / Running / Done / Failed
- Task cards: title, assignee, model, duration, retry count
- Click-through: full task detail, prompt, trajectory, bash commands, output, tokens

**Trajectory Viewer**
- Step-by-step replay of any mini-swe-agent run
- Exact bash commands executed at each step
- File diff view of changes made
- Model reasoning at each step
- Sourced directly from .traj.json files mini produces on completion

**Memory Browser**
- Browse claude-flow memory keys
- Semantic search
- View/edit session notes
- Agent context carried into each session

**Agent Registry**
- Registered agents with capability tags
- Heartbeat history
- Task history per agent
- Earnings ledger placeholder (read-only v1, active v2)

### Tech Stack
- React + TypeScript + TailwindCSS
- SpacetimeDB TypeScript client SDK (live subscriptions, no polling)
- LangFuse SDK for LLM observability overlay
- http://localhost:3001
- Dark theme default

---

## 8. JustAi Orchestrator Specification

The orchestrator is the brain. Evidence-based design from 10 sprints of prior work.

### Core Insight (from traj analysis)
The proven recipe for 100% first-try success is not model switching or runtime
judgment. It is: **well-scoped, unambiguous, mini-sized tasks fed to a capable
model**. The orchestrator's entire job is task decomposition quality.

### Intake
```
justai run "Build a FastAPI endpoint that accepts a GitHub webhook
            and posts a summary to Discord"
```

### Intent Gate
Classify the goal:
- execution-task: single well-scoped action, delegate directly to mini
- multi-step: decompose into ordered subtasks first
- research-task: delegate to Ruflo researcher agent
- ambiguous: ask one clarifying question before proceeding

### Planner
Decompose goal into ordered tasks. Each task must be:
- Completable by mini in ~35 messages (empirically validated limit)
- Unambiguous — zero decisions left to the executor
- Scoped to one directory or one concern
- Verifiable — has a concrete success condition

Each task record:
- Title and full description
- Assigned agent type
- Dependencies on prior tasks
- Risk level (R0-R3)
- Success criteria (testable)

### Reviewer (pre-execution quality gate)
Before any tasks are posted to SpacetimeDB, the Reviewer validates the plan:
- Are tasks small enough? (can each be done in ~35 steps?)
- Are tasks unambiguous? (zero open decisions?)
- Is the sequence correct? (dependencies ordered?)
- Are success criteria testable?

Evidence basis: coworkclaude's role as reviewer/planner was the primary driver
of sprint success improvement. Its value was at planning time, not runtime.

### Delegator
Post validated tasks to SpacetimeDB. Agents claim and execute. Orchestrator
monitors heartbeats and handles failures: retry same task up to 2x, then escalate.

### Synthesizer
Aggregate results into a final summary. Store outcome in claude-flow memory.
Surface to operator via Discord and dashboard.

### Checkpoints (Human-in-the-loop gates)
Default posture: autonomous. Bother the human only when genuinely necessary.

- R0: no gate — proceed immediately
- R1: notify only — post to Discord, auto-proceed after 60s unless vetoed
- R2: hard gate — pause, wait for explicit Discord or dashboard approval
- R3: blocked — operator must manually unlock before anything proceeds

---

## 9. File Structure (Target)

```
~/projects/JustAi/
  justai/                    <- orchestrator core (new)
    __init__.py
    orchestrator.py          <- main loop: intake -> plan -> review -> delegate -> synthesize
    intent_gate.py           <- classify incoming goals
    planner.py               <- goal decomposition into mini-sized tasks
    reviewer.py              <- pre-execution plan quality gate
    delegator.py             <- SpacetimeDB task posting + monitoring
    synthesizer.py           <- result aggregation
    checkpoint.py            <- R0-R3 gate logic (default: autonomous)
    memory.py                <- claude-flow memory bridge
  dashboard/                 <- web UI (new)
    src/
      App.tsx
      views/
        MissionControl.tsx
        TaskBoard.tsx
        TrajectoryViewer.tsx
        MemoryBrowser.tsx
        AgentRegistry.tsx
      components/
      lib/
        spacetime.ts         <- SpacetimeDB TypeScript client
        langfuse.ts          <- LangFuse observability client
  tools/                     <- existing CLI (evolve)
    justai_cli.py
    justai_runtime.py
  agents/                    <- agent integration configs
    mini_swe.py              <- mini-swe-agent v2 wrapper
    ruflo.py                 <- Ruflo swarm bridge
  relay-room/                <- existing (keep, clean naming)
  LocalManus/                <- existing (reference only, deprecate gradually)
  docs/
    JUSTAI_V1_SPEC.md        <- this file
    ARCHITECTURE.md
    ATTRIBUTION.md
    CONTRIBUTING.md
    EVIDENCE.md              <- findings from prior sprint log/traj analysis
  tests/
  README.md                  <- marketing landing page copy
  .env.example
  install.sh                 <- single-command installer
```

---

## 10. Attribution (Legal + Marketing)

```
JustAi is built on the shoulders of giants:

- mini-swe-agent by the SWE-agent team at Princeton & Stanford University
  (https://github.com/SWE-agent/mini-swe-agent) -- MIT License
  74% SWE-bench Verified. The world's best open-source code agent.

- Ruflo / claude-flow / SAFLA / agentic-flow by rUv (Reuven Cohen)
  (https://github.com/ruvnet) -- MIT License
  6,000+ commit agent orchestration infrastructure.

- SpacetimeDB by Clockwork Labs
  (https://spacetimedb.com) -- BSL License
  Real-time distributed database powering our task backbone.

- LiteLLM by BerriAI
  (https://github.com/BerriAI/litellm) -- MIT License
  Model routing and fallback chain.

- LangFuse (https://langfuse.com) -- MIT License
  LLM observability and cost tracking.
```

---

## 11. Installer Design

```bash
curl -fsSL https://get.justai.dev | bash
```

Or locally: `./install.sh`

Steps:
1. Check dependencies (Python 3.11+, Node 22+, Rust, tmux)
2. Clone or verify repo
3. Install Python deps
4. Install Node deps for dashboard
5. Start SpacetimeDB in tmux session
6. Publish SpacetimeDB module
7. Configure .env from .env.example (prompt for API keys)
8. Start LiteLLM proxy
9. Start JustAi dashboard
10. Start Discord bot (optional, prompts for tokens — one token per bot, manual Discord setup)
11. Run preflight health check
12. Print access URLs

---

## 12. Build Order (Sprint Plan)

### Sprint 1 - Clean Foundation
- Kill zombie LiteLLM processes, verify clean harness startup
- Investigate and resolve SpacetimeDB/OpenFang memory issue on start/stop
- Gitignore and remove relay-room .venv (audit usage in sprint logs first)
- Replace all Honcho references with claude-flow memory
- Normalize all hard-coded paths to env-var-driven
- Add logging to all ambiguous code paths
- Source prior runtime logs and match against code — verify actual vs intended behavior
- Document findings in docs/EVIDENCE.md
- Update README with tagline and attribution
- Verify existing mini + relay pipeline end-to-end

### Sprint 2 - Orchestrator Core
- justai/intent_gate.py
- justai/planner.py (mini-sized task decomposition)
- justai/reviewer.py (pre-execution quality gate)
- justai/delegator.py (SpacetimeDB posting + heartbeat monitoring)
- justai/checkpoint.py (R0-R3, default autonomous)
- Wire: justai run "goal" -> intent -> plan -> review -> tasks in SpacetimeDB
- Security and safety measures baseline

### Sprint 3 - Dashboard Foundation
- SpacetimeDB TypeScript client setup
- Mission Control (agent status + active pipeline)
- Task Board (Kanban, real-time)
- LangFuse integration baseline

### Sprint 4 - Dashboard Depth + Memory
- Trajectory Viewer (from .traj.json files)
- Memory Browser
- justai/memory.py bridge to claude-flow
- Session context surfacing
- Security hardening, enterprise-readiness thinking

### Sprint 5 - Polish + Installer
- install.sh
- .env.example
- docs/ARCHITECTURE.md + docs/ATTRIBUTION.md
- README.md landing page copy
- End-to-end dogfood: justai run a real task, watch in dashboard

### Sprint 6 - v1 Release
- Public GitHub repo
- Landing page
- Demo video
- Product Hunt submission
- Marketing plan
- Business-side planning

---

## 13. Success Criteria for v1

- [ ] justai run "goal" produces working result with full audit trail
- [ ] Dashboard shows real-time task progress without manual refresh
- [ ] Human-in-the-loop gates function at all four risk levels
- [ ] Cross-session memory surfaces relevant prior context at session start
- [ ] Single-command installer works on fresh Ubuntu 24.04 + WSL2
- [ ] README attribution is accurate and complete
- [ ] mini-swe-agent benchmarks above 70% first-try on representative task set
- [ ] Discord remote control works from mobile
- [ ] LangFuse shows cost and latency per task in dashboard

---

*End of JustAi v1 Specification — v1.1*
*Next step: Sprint 1 kickoff — Clean Foundation*
