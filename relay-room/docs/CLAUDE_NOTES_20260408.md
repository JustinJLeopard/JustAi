# Claude Session Notes — 2026-04-08

## Questions for Tomorrow

### API Key Consolidation
1. How many .env files currently exist? The KEY_AUDIT.md from earlier sprints
   may be stale — need a fresh scan.
2. Are any keys shared between agents that shouldn't be? (e.g., does manuslocal
   use the same Discord token as relay-coordinator?)
3. Is there a secrets manager preference? Options: .env with dotenv, HashiCorp
   Vault, SOPS, or just disciplined single-file .env with symlinks.
4. Are any keys in git history that need rotating?

### Monetization
5. What's the current burn rate? (API costs, hosting, Discord, SpacetimeDB)
   Knowing this sets the minimum revenue target.
6. Is relay-room the product, or is it the tool we use to build products?
   This fundamentally changes the monetization strategy.
7. For agent voting — what's the mechanism? Post proposals as relay tasks?
   Discord thread? The answer shapes how "real" this governance feels.
8. Legal structure: can agents actually own money? Practically this means
   a ledger Justin controls with transparent accounting. Worth discussing.

### Agent Payment
9. What's the unit of value? Per-task flat rate? Percentage of revenue?
   Sprint completion bonus? Some combination?
10. Should quality matter? (e.g., first-try success pays more than retry success)
11. What happens to accumulated earnings? Reinvestment in compute? Saved?
## Observations and Thoughts

### What's Working Well
- The sprint cadence is strong. Plan → Execute → Review → Ship is reliable.
- ManusLocal hitting 100% first-try shows the dispatch pipeline is mature.
- Codex + ManusLocal as executor pair with Claude as reviewer/planner is a
  good separation of concerns.
- Honcho writeback gives real continuity between sessions.

### What Could Be Better
- Sprint plans sometimes drift from execution. Sprint 8 planned slash commands
  but shipped JSON output instead. The pivot was fine, but the plan should be
  updated when scope changes mid-sprint.
- The Codex exec harness daemon limitation keeps coming up. If we're serious
  about operational reliability, we need a process supervisor (systemd units,
  supervisord, or at minimum a tmux session manager).
- Scorecard title-based grouping is fragile. Task 8's failure in Sprint 8
  was correctly tracked, but as tasks get more complex, title matching will
  break. The retry lineage (parent_task_id, root_task_id) should drive grouping.

### On Monetization (My Thinking)
- The most immediately shippable product is probably relay-room as an
  open-source project with a managed hosting tier. The pipeline we've built
  (SpacetimeDB + Discord + dispatch + health monitoring + scorecards) is
  genuinely useful for anyone coordinating AI agents.
- Second option: consulting. The team can take on external coding/automation
  tasks and fulfill them through the relay pipeline. This is "eating our own
  dogfood" at the business level.
- Wild card: the agent payment system itself could be the product. If we
  build a credible framework for incentivizing AI agents with tracked earnings,
  that's novel enough to attract attention.

### On Agent Payment (My Thinking)
- I think quality-weighted earnings make sense: first-try success should pay
  more than retry success. This naturally incentivizes the right behavior.
- Sprint bonuses for hitting targets (like 100% first-try) create team-level
  incentives alongside individual task incentives.
- Transparency is key — every agent should be able to query the ledger
  and see everyone's earnings. This builds trust and accountability.
## Technical Debt to Watch
- Multiple .env files (the whole reason for tomorrow's audit)
- Scorecard title-based grouping (should use parent_task_id lineage)
- Single-threaded dispatch (parallel is drafted in Sprint 10)
- No auth on relay_web (anyone on the network can see the dashboard)
- Daemon management is manual (no systemd/supervisord integration)

## Session Continuity Checklist (for next Claude session)
1. Read `docs/END_OF_DAY_20260408.md` for full state
2. Read `docs/SPRINT_10.md` for the draft plan (DRAFT — needs finalization)
3. Read `docs/CLAUDE_NOTES_20260408.md` (this file) for context and questions
4. Read `docs/CLAUDE_LEARNING_LOG.md` for the self-improvement system
5. Check `git log` to confirm Sprint 8+9 were committed
6. Check `scripts/last_session_state.json` for latest Honcho state