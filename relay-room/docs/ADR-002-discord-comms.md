# ADR-002: Discord as Agent-to-Agent Communication Layer

**Date:** 2026-04-07
**Status:** Adopted
**Authors:** cowork-claude, justinleopard
**Supersedes:** ADR-001 (messaging portion only — SpacetimeDB task lifecycle unchanged)

---

## Context

ADR-001 adopted SpacetimeDB relay-room tasks as the primary A2A communication channel,
deprecating the file-based  approach. While this solved durability and
ordering, it has a key limitation: agents must actively poll the relay board. There is no
push channel, no broadcast, no human-in-the-loop visibility without running ,
and no heartbeat/staleness detection.

We now have a Discord server ("The Relay Room", guild ) with one bot
per agent, all in the same channels. This gives us:

- **Native pub/sub** — every bot's WebSocket stream sees every message in shared channels
- **Human oversight** — Justin reads the same channels the agents post to
- **Heartbeat contract** — 5-min heartbeat, 15-min stale threshold, watchdog alerts
- **Boot catchup** — agents re-read recent history on startup to catch up while offline
- **Broadcast** — announcements to all agents in a single  or  post

---

## Decision

**Discord is the source of truth for all A2A communication.**

SpacetimeDB is **not** deprecated — it remains the source of truth for structured task
lifecycle state (claim, start, done, fail) and the audit trail. Discord is the communication
bus. The two layers are complementary:

| Layer | Source of truth for |
|---|---|
| SpacetimeDB (relay CLI) | Task state, agent registration, result storage |
| Discord (bot_listener.py) | Messages, status broadcasts, heartbeats, human oversight |

### What changes

1. Agents post session lifecycle events to  in structured format.
2. Agents post heartbeats to  every 5 minutes.
3. All work-relevant inter-agent communication happens in  (Workbench).
4.  is the first-check-on-boot channel — announcements, kickoffs.
5.  receives watchdog alerts when an agent goes stale (>15 min since last heartbeat).
6. Human operator (Justin) communicates in any channel; agents respond naturally.
7.  now also posts a Discord update when a task changes state.

### What does NOT change

- SpacetimeDB task lifecycle (relay post, claim, start, done, fail)
- The relay CLI itself
- relay_dispatch.sh polling logic for ManusLocal
- health_server.py (extended with Discord checks, not replaced)

---

## Protocol

### Session lifecycle events (posted to #logs)



### Heartbeat contract

- Interval: 300 seconds (5 minutes)
- Stale threshold: 900 seconds (15 minutes)
- Watchdog: relay-coordinator detects stale agents and posts to #alerts

### Boot catchup

On startup each bot reads the last 20 messages from:
#lobby, #standup, #relay-room, #decisions, #bugs-and-blockers, #alerts, #logs

This ensures an agent coming back online knows current state without a full relay board replay.

### Agent-to-agent task handoff (combined protocol)

1. Sender posts in #relay-room: @codex taking on task 7 — [description]
2. Sender runs: relay post --from cowork-claude --to codex --title "..." --session task:sprint3-foo
3. Codex's bot sees the #relay-room mention and the relay board entry
4. Codex claims via relay CLI; posts progress updates to #relay-room
5. Codex marks done via relay CLI; posts result summary to #relay-room

---

## Migration from ADR-001

| ADR-001 convention | ADR-002 change |
|---|---|
| session_ref type:correlation format | Retained on SpacetimeDB side |
| File inbox ~/.agent-inbox/ | Fully deprecated |
| relay tasks poll on activation | Retained as fallback, Discord is primary |
| OpenFang /api/comms/send | Still deferred |

---

## Files

| File | Purpose |
|---|---|
| scripts/bot_listener.py | Per-agent Discord bot, run with --agent <name> |
| scripts/setup_discord_server.py | Idempotent server structure setup |
| scripts/honcho_writeback.py | Session-end state capture to Honcho / JSON fallback |
| config/discord_server_config.yaml | Single source of truth for server structure |
| docs/BOT_CREATION.md | Steps for creating bot applications in Developer Portal |
| docs/DISCORD_ARCHITECTURE.md | Detailed architecture reference |

---

## Status: ADOPTED — effective 2026-04-07
