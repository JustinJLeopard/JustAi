# Sprint 3 Handoff — Discord Bot Integration & Agent Management

**Date**: 2026-04-07  
**Team**: Justin (PM), Codex, Claude, ManusLocal  
**Scope**: 6 committed tasks to operationalize Discord A2A comms layer  
**Git Commit**: 3af48e2 (Discord integration fully committed to main)

---

## Executive Summary

The Discord integration is **code-complete and committed**. Discord is now the agent-to-agent (A2A) real-time comms bus alongside SpacetimeDB for task lifecycle. Sprint 3 focuses on bot operational readiness, agent alignment, and end-to-end validation.

**Status**: Ready to execute. Token rotation is prerequisite (Justin to handle).

---

## Sprint 3 Tasks (6 Committed)

### Task 1: Extend daemon_ctl.sh for Bot Management
**Owner**: Codex  
**Depends**: Task 1 (tokens rotated)

What: Add bot daemon lifecycle commands to daemon_ctl.sh  
Extend: Add --with-bots flag to start/stop/restart bots alongside agents

File: scripts/daemon_ctl.sh  
Test: Verify bots start and post heartbeats to #relay-room within 5 min

---

### Task 2: Agent Naming Alignment
**Owner**: Claude  
**Depends**: Task 1 (bots running)

What: Align relay agent names with Discord bot names  
Current: Agents named in relay_web.py  
Target: Match Discord bot names exactly (codex, manuslocal, coworkclaude, relay-coordinator)

Implementation:
- Update agent spawn names in relay_web.py
- Update ActionHandler subclass names in bot_listener.py
- Ensure agent_name env var matches Discord username
- Update health_server.py agent name checks

File: scripts/relay_web.py, scripts/bot_listener.py, scripts/health_server.py  
Test: Verify agent names in /tmp/relay_discord_*.pid files match configured names

---

### Task 3: Watchdog Loop — Stale Agent Detection
**Owner**: ManusLocal  
**Depends**: Task 2 (daemon_ctl.sh extended)

What: Implement watchdog that detects stale agents and escalates  
Threshold: 15 minutes without heartbeat = stale (5-min interval + 3x buffer)

Implementation:
- Read PID files in /tmp/relay_discord_*.pid
- Check last heartbeat timestamp from Discord API (or local cache)
- If stale: post to #alerts, log escalation
- Attempt auto-restart (optional: escalate to Justin after 3 failures)
- Run every 30 seconds (or on-demand via health_server.py)

File: scripts/health_server.py (extend check_discord_bot())
Test: Kill a bot, verify watchdog detects stale within 15 min + detection interval

---

### Task 4: Agent Naming Alignment (Part 2) — Channel Routing
**Owner**: Claude  
**Depends**: Task 3 (names aligned)

What: Ensure discord_notify() in relay_dispatch.sh routes to correct agent channels  
Current: Posts to #relay-room (shared), #alerts (failures)  
Extend: Add per-agent logging to #agent-{name} channels

Implementation:
- discord_notify() takes optional --agent-channel flag
- relay_dispatch.sh calls discord_notify(..., --agent-channel ) at task transitions
- Verify channel IDs in config/discord_server_config.yaml for #agent-* channels

File: scripts/relay_dispatch.sh  
Test: Run task through agent, verify posts appear in both #relay-room and #agent-{name}

---

### Task 5: End-to-End Validation
**Owner**: Justin + Team  
**Depends**: Task 5 (all systems aligned)

What: Full integration test of bot heartbeats, task routing, and agent lifecycle  
Test Plan:
1. Start all agents + bots via daemon_ctl.sh --with-bots
2. Verify boot-complete messages in #logs within 2 min
3. Post test task via relay_web.py → observe in #relay-room
4. Verify agent heartbeats every 5 min in #relay-room
5. Kill one bot, verify watchdog detects stale within 15 min
6. Restart bot via daemon_ctl.sh, verify reconnection and heartbeat recovery
7. Run 24-hour soak test (overnight)

Success Criteria:
- All 4 bots report heartbeat every 5 min (0 missed)
- Task routing posts reach #relay-room within 100ms
- Watchdog detects stale agents correctly
- No Discord API errors in logs (401, 403, rate limits)
- Honcho API session state persists correctly

Documentation: Create VALIDATION_REPORT.md with results

---

## Architecture Context

Discord is the real-time comms layer. SpacetimeDB still owns task lifecycle (no change).  
Token rotation is CRITICAL blocker (tokens were exposed, Discord auto-invalidated them).  
All code is committed. Documentation is complete. Ready to execute.

---

## Getting Started Checklist

- [ ] Justin: Rotate Discord bot tokens (docs/BOT_CREATION.md)
- [ ] Codex: Pull latest, review daemon_ctl.sh current structure
- [ ] Claude: Review bot_listener.py agent naming (line ~150)
- [ ] ManusLocal: Review health_server.py stale detection logic
- [ ] Team: Run make test to verify test suite passes
- [ ] Team: Assign tasks in your project management tool (Justin leads)
- [ ] Justin: Post in #relay-room: "Sprint 3 kickoff — Discord operationalization"

---

Good luck, team. Discord integration is live. Execute Sprint 3 and let's get bots healthy.
