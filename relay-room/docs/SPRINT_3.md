# Sprint 3 Plan — Discord Comms Layer

**Sprint:** 3  
**Start:** 2026-04-07  
**Goal:** Land Discord integration PR, rotate tokens, validate end-to-end agent comms

---

## Context

- Sprint 1: SpacetimeDB module, relay CLI (post/claim/start/done/fail), agent registration
- Sprint 2: relay_dispatch daemon, honcho summaries, health_server, ADR-001, preflight checks
- Sprint 3: Discord as A2A comms bus, bot listeners per agent, heartbeat contract

---

## Committed Tasks

### T1 — Rotate all 4 bot tokens (justinleopard)

Tokens were exposed in chat; Discord likely auto-invalidated them.

1. Developer Portal → each app → Bot tab → Reset Token
2. Update ~/projects/relay-room/.env
3. Restart bot listeners

### T2 — Land feat/discord-comms-layer PR (cowork-claude + codex)

All files from RELAY_ROOM_PLAN.md scope. Codex review before merge.

### T3 — Extend daemon_ctl.sh for bots (codex)

Add start-bots, stop-bots, bot-status subcommands.

### T4 — Align relay agent names (codex)

claude-code → cowork-claude, localmanus → manuslocal in start_relay_room.sh.

### T5 — Watchdog in relay-coordinator (cowork-claude)

Detect stale agents (>15 min since heartbeat), post alerts to #alerts.

### T6 — End-to-end validation (all agents)

Full handoff: Discord comms + SpacetimeDB task record. Verify relay board matches #logs.

---

## Definition of Done

- All 4 bots heartbeating in #heartbeats
- relay board and #relay-room in sync
- GET /health healthy for Discord checks
- PR merged
- Tokens rotated
- daemon_ctl.sh bots merged

---

## Channel Quick Reference

| Channel | ID | Purpose |
|---|---|---|
| lobby | 1491134761412858058 | Boot announcements |
| relay-room | 1491134768077865090 | A2A work comms |
| deployments | 1491134772385157333 | Deploy notices |
| heartbeats | 1491134779746160804 | Bot keepalives |
| alerts | 1491134780589342770 | Failures, stale agents |
| logs | 1491134781407105065 | Session events |
