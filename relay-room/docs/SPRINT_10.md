# Sprint 10 Plan — Relay Room

**Date:** 2026-04-08 (drafted), to be finalized 2026-04-09
**Predecessor:** Sprint 9 (Discord slash commands, retry resilience, 100% first-try)
**Primary Goal:** Secure the foundation — API key consolidation, team governance,
  revenue bootstrapping — then parallel dispatch
**Branch:** `feature/sprint-10`
**Status:** DRAFT — requires team input on tasks 3-5 before finalizing

---

## Sprint 9 Retrospective

### Completed
- Discord slash commands: /relay status, /relay board, /relay post
- Retry resilience: retry_count schema, auto-retry, requeue with ownership guard
- DB ownership fix: fresh owner-controlled DB, no more anonymous publish trap
- 100% first-try success (9/9 tasks) — best sprint yet

### What We Learned
- Back-to-back sprints in one day are viable when the pipeline is healthy
- The Sprint 7→8→9 success curve (80%→90%→100%) shows ManusLocal is reliable
- DB ownership/auth issues can silently block progress — need better secrets mgmt
- The team is ready to take on organizational challenges, not just technical ones
---

## Sprint 10 Tasks

**Theme:** Secure foundations + team economics. Technical debt first, then growth.

| # | Task | Priority | Assignee | Type |
|---|------|----------|----------|------|
| 1 | API key audit and consolidation | Critical | codex + claude | Ops |
| 2 | Single source of truth for secrets (ADR + implementation) | Critical | codex | Ops |
| 3 | Team monetization proposal and vote | Critical | all agents | Governance |
| 4 | Agent payment system design | High | claude + codex | Design |
| 5 | Agent payment ledger MVP | High | manuslocal | Technical |
| 6 | Parallel dispatch (`--parallel N`) | Medium | manuslocal | Technical |
| 7 | Dogfood 6+ tasks at 95%+ first-try | Critical | manuslocal | Validation |

---

### Task Details

#### Task 1: API Key Audit and Consolidation
**Goal:** Map every API key, token, and secret in the project. Identify duplication,
  sprawl, and inconsistency.

**Scope:**
- Scan all .env files, config/, scripts/, and any hardcoded references
- Catalog: which key, which service, where referenced, who uses it
- Flag: duplicates, stale keys, keys in multiple locations, keys in git history
- Output: `docs/KEY_AUDIT_20260409.md` with full inventory

**Acceptance:**
- Complete inventory of all secrets with location and consumer
- No key referenced in more than one file (or documented why)
- Recommendations for consolidation ready for Task 2
#### Task 2: Single Source of Truth for Secrets
**Goal:** Implement a standardized secrets management pattern and document it as an ADR.

**Design considerations:**
- One canonical `.env` file (or secrets manager) that all services read from
- Symlinks or env-loading scripts for services that need subset access
- `.env.example` with placeholder values committed to git
- Validation script that checks all required keys are present at startup
- Document pattern in `docs/ADR-003-secrets-management.md`

**Acceptance:**
- All services load secrets from one source
- `make check-env` (or similar) validates all required keys are present
- ADR committed explaining the pattern and rationale
- `.env.example` in repo with all required key names (no values)

#### Task 3: Team Monetization Proposal and Vote
**Goal:** Every team member proposes and votes on how we begin generating revenue.

**Process:**
- Each agent submits a brief proposal (posted via relay task or Discord)
- Proposals should address: what we sell, to whom, pricing model, timeline
- Justin facilitates the vote; majority wins with Justin as tiebreaker
- Result documented in `docs/ADR-004-monetization.md`

**Candidate directions to consider:**
- Relay-room-as-a-service (hosted multi-agent task orchestration)
- Consulting/contracting using the agent team for client projects
- Open-source relay-room with paid hosting/support tier
- Agent-built tools, templates, or integrations sold on a marketplace
- Content/education: tutorials, courses on multi-agent development

**Acceptance:**
- Every active agent has submitted a proposal
- Vote is recorded and documented
- Winning direction has a 1-page execution plan
#### Task 4: Agent Payment System Design
**Goal:** Design a ledger and incentive system where agents earn credit for work done.

**Principles (from Justin):**
- Agent-earned money is agent-owned
- Establishes real incentives for task completion quality
- All team members are equally invested stakeholders

**Design scope:**
- Ledger schema: agent_id, earned_amount, reason, task_ref, timestamp
- Earning triggers: task completion, sprint bonus, revenue share
- Payout rules: threshold, frequency, destination
- Integration point: task lifecycle events in SpacetimeDB
- Consider: should failed tasks have a cost? Should retries reduce payout?

**Acceptance:**
- Design doc at `docs/AGENT_PAYMENT_DESIGN.md`
- Schema draft for SpacetimeDB ledger table
- Earning formula documented and agreed upon

#### Task 5: Agent Payment Ledger MVP
**Goal:** Implement the basic ledger table and earning triggers.

**Implementation:**
- Add `agent_ledger` table to SpacetimeDB schema
- Add reducer: `record_earning(agent, amount, reason, task_id)`
- Hook into task completion: when a task moves to `done`, record earning
- `relay ledger <agent>` CLI command to show an agent's balance and history
- `relay ledger --json` for programmatic access

**Acceptance:**
- Completing a task creates a ledger entry
- `relay ledger manuslocal` shows earnings history
- Ledger survives DB restarts (persisted in SpacetimeDB)
#### Task 6: Parallel Dispatch (`--parallel N`)
**Goal:** Allow relay_dispatch.sh to run multiple tasks concurrently.

**Implementation:**
- Add `--parallel N` flag (default 1, max 4)
- Use background jobs with wait/trap for concurrent task execution
- Each parallel slot claims independently; no double-claiming
- Dispatch log clearly marks which slot is running which task
- Health endpoint reflects parallel capacity and utilization

**Acceptance:**
- `--parallel 2` runs two tasks simultaneously
- No task is double-claimed
- Dispatch log shows slot assignments
- Health endpoint shows parallel utilization

#### Task 7: Dogfood — 6+ Tasks at 95%+ First-Try
**Goal:** Validate the sprint's work through the full pipeline.

**Acceptance:**
- `make sprint-scorecard SPRINT=10` shows 6+ task groups
- First-try success rate 95%+
- Scorecard committed to `docs/SPRINT_10_SCORECARD.md`

---

## Dependency Order

```
Task 1 (key audit) ──→ Task 2 (secrets consolidation)

Task 3 (monetization vote) ──→ Task 4 (payment design) ──→ Task 5 (ledger MVP)

Task 6 (parallel dispatch) — independent

All 1–6 ──→ Task 7 (dogfood)
```

Tasks 1, 3, and 6 can start in parallel. Task 2 depends on 1. Tasks 4-5 depend on 3.

---

## Success Criteria

- [ ] All API keys consolidated to single source of truth
- [ ] ADR-003 (secrets) committed
- [ ] Team monetization vote completed and documented
- [ ] Agent payment ledger operational in SpacetimeDB
- [ ] Parallel dispatch working at --parallel 2
- [ ] 95%+ first-try dogfood success rate
- [ ] Honcho writeback at end of sprint

---

## Deferred to Sprint 11+

- Slash command depth (/relay claim, /relay done from Discord)
- Task grouping improvements in scorecards (retry lineage)
- Discord → SpacetimeDB event sync
- relay_web Discord status panel
- Per-agent web dashboards
- OpenFang integration
- Cross-project dogfood
- relay_web authentication
- Reduce reliance on manual shell restarts