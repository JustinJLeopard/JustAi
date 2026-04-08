# Sprint 4 Plan — Relay Room
**Date:** 2026-04-07
**Predecessor:** Sprint 3 (Discord bot integration, daemon lifecycle, health/watchdog)
**Branch:** feature/sprint-4

---

## Sprint 3 Retrospective

### Completed
- daemon_ctl.sh: full bot lifecycle management (start/stop/restart/status --with-bots)
- bot_listener.py: 4/5 Discord bots connected and running (relay-coordinator, codex, manuslocal, coworkclaude)
- relay_dispatch.sh: daemon polling, task claim/dispatch via mini, Discord notifications
- health_server.py: HTTP health endpoint on :8080, watchdog thread with auto-restart
- End-to-end pipeline verified: relay post → SpacetimeDB → dispatch → mini → done

### Known Issues (carried forward)
1. **claudecli bot token invalid** — needs regeneration in Discord Developer Portal
2. **`ml task` no_db_connection** — LiteLLM config issue in LocalManus (database_url: null), not relay-room

---

## Sprint 4 Tasks

### Task 1: Discord → SpacetimeDB Event Sync
**Priority:** High
**Assignee:** coworkclaude

Write a bridge in bot_listener.py that captures key Discord events and records them as
SpacetimeDB events via `relay` CLI:
- Bot connect/disconnect → `send_message` with type "heartbeat"
- Channel messages from agents → `send_message` with type "chat"
- Session start/end markers → events table entries

This gives the relay board full visibility into Discord activity.

### Task 2: Slash Command Handlers
**Priority:** High
**Assignee:** codex

Implement Discord slash commands in bot_listener.py:
- `/relay status` — show SpacetimeDB task board summary (pending/in_progress/done counts)
- `/relay health` — run health_server checks and post results to channel
- `/relay post <to> <title> <payload>` — create a new relay task from Discord
- `/relay tasks [--agent <name>]` — list recent tasks, optionally filtered

Register commands via discord.py's app_commands. Each handler calls the `relay` CLI
and formats the output for Discord embed messages.

### Task 3: Agent Registration Alignment
**Priority:** Medium
**Assignee:** manuslocal

Update SpacetimeDB agent registration to align with Discord bot names:
- Register all 5 agents: relay-coordinator, codex, manuslocal, coworkclaude, claudecli
- Add agent metadata: handler_type, capabilities, last_heartbeat
- Update relay_dispatch.sh to register the dispatch daemon as an agent on startup
- Add `relay agents` CLI subcommand to list registered agents and their status

### Task 4: Session Capture & Honcho Integration
**Priority:** Medium
**Assignee:** coworkclaude

Operationalize session_capture.py:
- On session end (detected via Discord presence or explicit command), capture:
  - All relay tasks created/completed during the session
  - Discord message history from session channels
  - Agent heartbeat timeline
- Write session summary to Honcho memory for cross-session context
- Fallback: write to local JSON file if Honcho is unreachable

### Task 5: relay_web.py Discord Status Panel
**Priority:** Low
**Assignee:** codex

Add a Discord status section to the web board:
- Show last heartbeat timestamp per bot
- Show bot online/offline status (from PID checks or Discord presence)
- Show recent Discord messages from #relay-room channel
- Add WebSocket push for real-time updates (optional, stretch goal)

### Task 6: Integration Tests & CI
**Priority:** High
**Assignee:** manuslocal

Create comprehensive integration tests:
- tests/test_bot_lifecycle.sh: start all bots, verify PIDs, check health endpoint, stop
- tests/test_relay_pipeline.sh: post task, wait for dispatch, verify completion
- tests/test_slash_commands.py: mock Discord interaction, verify command responses
- Makefile target: `make test-integration` that runs all integration tests
- Document test requirements in tests/README.md

---

## Success Criteria

1. Discord slash commands work from any channel in the relay-room server
2. SpacetimeDB events table shows Discord heartbeat and message events
3. All 5 agents registered in SpacetimeDB with aligned names
4. Session capture writes to Honcho on session end
5. `make test-integration` passes all suites
6. Web board shows Discord bot status

---

## Dependencies & Blockers

- **claudecli token:** Must be regenerated before Task 1 can include claudecli
- **ml task fix:** LiteLLM database_url config in LocalManus — independent of sprint 4
- **Honcho availability:** Task 4 needs Honcho running (currently passing health check)
