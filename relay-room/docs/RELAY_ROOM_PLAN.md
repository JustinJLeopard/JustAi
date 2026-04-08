# Relay Room — Revised Plan & PR Scope
# Discord Integration Branch

**Branch:** 
**Target:** single PR into 
**Date:** 2026-04-07

---

## What Changed and Why

ADR-001 established SpacetimeDB relay tasks as primary A2A comms. That solved durability
but left a critical gap: no push channel, no heartbeat contract, no human-in-the-loop
visibility, no real-time broadcast. Discord fills that gap without replacing SpacetimeDB.

The two layers are now complementary:
- **SpacetimeDB** = structured task lifecycle, audit trail, agent registration
- **Discord** = real-time comms bus, heartbeats, operator presence, broadcast

---

## Files in This PR

### New files
| File | Description |
|---|---|
|  | Per-agent Discord bot. Run with . Handles boot catchup, heartbeat, session events. |
|  | Idempotent server scaffolding (roles, categories, channels). Run once to build out the server. |
|  | End-of-session capture: reads Discord state, writes to Honcho or falls back to . |
|  | Single source of truth for server structure — roles, channels, categories, lifecycle contract. |
|  | Decision record. Supersedes ADR-001 messaging portion. |
|  | Manual steps for creating bot applications in the Developer Portal. |
|  | Full architecture reference: one-bot-per-agent model, lifecycle events, boot sequence. |
|  | Template with all required env vars (SpacetimeDB + Discord). |

### Modified files
| File | Change |
|---|---|
|  | Added  helper. Fires to  on task claim/done and to  on failure. Opt-in via env vars. |
|  | Added  per agent. Reads PID files written by . Surfaced in  endpoint. |
|  | Added , , , pycache dirs. |
|  | Added Discord Setup section with quickstart, channel map, and bot startup commands. |

---

## What to Port from OpenFang

OpenFang () was deferred in ADR-001 because it required a live WebSocket
session. **Discord now supersedes it for A2A.** When OpenFang exposes an async mailbox
or queue endpoint, it would complement Discord (not replace it) for structured API payloads.

**Nothing to port yet.** The  deferral stands. Revisit in a future sprint
when OpenFang is back in scope.

---

## What Needs Revision

1. **Agent registration** —  in SpacetimeDB still uses  as
   the agent name. Should align with Discord bot names (, ,
   ). Update register calls in .

2. **relay_web.py** — The read-only web board doesn't know about Discord. Future: add a
   Discord status panel showing last heartbeat per bot. Not blocking for this PR.

3. **daemon_ctl.sh** — Currently manages relay_dispatch and health_server daemons. Should
   be extended to manage Discord bot listeners (start/stop/status per agent).

4. **Token rotation** — Tokens were exposed in session chat and likely auto-invalidated
   by Discord. Must rotate all 4 tokens in Developer Portal before the bots can reconnect.
   See  → Reset Token section.

---

## What Is NOT in This PR (Future Work)

- Slash command handlers (Discord , )
- Watchdog loop in relay-coordinator detecting stale heartbeats
- OpenFang integration
- Per-agent web dashboards
- Discord → SpacetimeDB sync (write Discord messages as relay events)
