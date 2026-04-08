# Sprint 8 Plan — Relay Room

**Date:** 2026-04-08
**Predecessor:** Sprint 7 (install drift fix, board UX, scorecard, 80% first-try dogfood)
**Primary Goal:** Ship Discord slash commands, add parallel dispatch, and push dogfood success rate toward 90%+
**Branch:** `feature/sprint-8`

---

## Sprint 7 Retrospective

### Completed

- Install drift eliminated: relay_dispatch.sh auto-runs `make install` after Rust source changes
- `relay board` shows active-only by default; `--all` shows full history with counts
- Recent Events detail sanitized/truncated (140 char limit, unit tests)
- Sprint scorecard system operational: `make sprint-scorecard SPRINT=N`
- honcho_writeback.py connector leak fixed (no more `Unclosed connector` warning)
- .gitignore hardened: archives, logs, session JSON, __pycache__, throwaway scripts
- 5 dogfood tasks executed, 80% first-try success rate

### Deferred Items (Accumulated Since Sprint 4)

1. **Discord slash commands** — `/relay status`, `/relay post`, `/relay board` (Sprint 4 → 5 → 6 → 7, always deferred)
2. **Discord → SpacetimeDB event sync** — heartbeat/chat events as DB rows (Sprint 4)
3. **relay_web Discord status panel** — show bot heartbeat timestamps (Sprint 4)
4. **Parallel dispatch** — run multiple tasks concurrently (never attempted)
5. **Per-agent web dashboards** — (Sprint 6)

### Known Issues

- SpacetimeDB board is `relay-room-s7-dev` (local-server owned); older board has 403 on publish
- Scorecard grouping is title-based; no explicit retry counter in schema
- `ml task --session` tag support added to LocalManus but not yet committed there

---
## Sprint 8 Objective

**Ship the two biggest deferred features (Discord slash commands + parallel dispatch), then dogfood them to prove they work. Target 90%+ first-try success rate on dogfood tasks.**

This sprint has two themes: (1) finally deliver user-facing Discord interactivity that's been deferred for 4 sprints, and (2) make the dispatch loop handle concurrent work so agents aren't serialized.

---

## Sprint 8 Tasks

### Task 1: Discord Slash Command — `/relay status`

**Priority:** Critical
**Assignee:** manuslocal
**Depends:** None

Implement the first Discord slash command so users can check relay health from Discord:

1. In `bot_listener.py`, register a Discord slash command `/relay status` on the relay-coordinator bot
2. The command should return:
   - Number of active/pending/in_progress tasks (from `relay board` output)
   - Agent status summary (from `relay agents`)
   - SpacetimeDB connectivity (reachable or not)
   - LiteLLM status (reachable or not)
   - Uptime of relay_dispatch daemon
3. Format the response as a Discord embed with color coding (green=healthy, yellow=degraded, red=down)
4. Register the command with Discord's API on bot startup

**Acceptance:** Type `/relay status` in Discord #relay-room → get a formatted embed showing system health. No errors in bot logs.
### Task 2: Discord Slash Command — `/relay post`

**Priority:** Critical
**Assignee:** manuslocal
**Depends:** Task 1 (slash command registration pattern established)

Enable posting tasks directly from Discord:

1. Register `/relay post` slash command with options:
   - `task` (required string): the task description
   - `to` (optional string): target agent (default: manuslocal)
   - `session` (optional string): session tag for scorecard tracking
2. The command should call `relay post` under the hood and return confirmation with the task ID
3. Post a follow-up message to #relay-room when the task completes or fails (subscribe to task status changes)
4. Handle errors gracefully: if SpacetimeDB is down, return a clear error embed

**Acceptance:** `/relay post task:"add a docstring to health_server.py" to:manuslocal session:sprint-8` creates a task, shows confirmation, and posts result when done.

### Task 3: Discord Slash Command — `/relay board`

**Priority:** High
**Assignee:** manuslocal
**Depends:** Task 1

Show the task board in Discord:

1. Register `/relay board` slash command with options:
   - `all` (optional boolean): show completed/archived tasks too (default: false)
2. Format output as a Discord embed or code block showing active tasks with ID, title (truncated), status, assignee
3. If more than 10 tasks, paginate with Discord buttons (Previous/Next) or truncate with "and N more..."
4. Include the count summary lines from `relay board`

**Acceptance:** `/relay board` in Discord shows active tasks in a readable format. `/relay board all:true` shows full history.
### Task 4: Parallel Dispatch — Concurrent Task Execution

**Priority:** High
**Assignee:** codex
**Depends:** None

Currently relay_dispatch.sh processes one task at a time. Add concurrency:

1. Add a `--parallel N` flag to `relay_dispatch.sh` (default: 1, max: 4)
2. When N > 1, dispatch claims up to N pending tasks and runs them in background subshells
3. Each parallel execution must:
   - Write its own log file (`/tmp/relay_dispatch_task_<id>.log`)
   - Independently call `relay done` or `relay fail` when complete
   - Not interfere with other running tasks (no shared state beyond the DB)
4. The main loop waits for any slot to free before claiming more tasks
5. Add `--parallel` to `daemon_ctl.sh start` passthrough
6. Guard against race conditions: use `relay claim` atomicity (SpacetimeDB reducer already handles this)

**Acceptance:** With `--parallel 2`, submit 3 tasks rapidly → first 2 start concurrently, 3rd starts when a slot frees. All complete correctly. Logs are separate.

### Task 5: Retry Counter in Task Schema

**Priority:** Medium
**Assignee:** codex
**Depends:** None

The scorecard currently groups retries by title matching, which is fragile. Add proper retry tracking:

1. Add `attempt_number` (u32, default 1) and `parent_task_id` (optional u64) fields to the `tasks` table in `spacetimedb/src/lib.rs`
2. Add a `relay retry <task_id>` CLI command that:
   - Reads the failed task's title, payload, and target agent
   - Posts a new task with `parent_task_id` = original ID and `attempt_number` = previous + 1
3. Update `relay board --all` to show retry chains: "Task 5 (retry of #3, attempt 2)"
4. Update `scripts/sprint_scorecard.sh` to use `parent_task_id` for grouping instead of title matching
5. Run `make build-module && make publish` to deploy schema changes
**Acceptance:** `relay retry 5` creates a new task linked to #5 with attempt_number=2. Scorecard groups by parent_task_id. `relay board --all` shows retry relationships.

### Task 6: Dogfood Sprint 8 Features via `ml task`

**Priority:** Critical
**Assignee:** manuslocal
**Depends:** Tasks 1-5 (at least Tasks 1-3 must be done)

Use `ml task --session sprint-8` to dogfood at least 4 real improvements to relay-room itself. Target: 90%+ first-try success.

Suggested dogfood tasks (pick 4+ from this list or invent better ones):
1. Add `/health/agents` endpoint to health_server.py that returns agent heartbeat data as JSON
2. Add `relay task-log <id>` CLI command that prints the dispatch log for a specific task
3. Improve `relay board` formatting: align columns, add color codes for status (if terminal supports it)
4. Add `--json` output flag to `relay board` for programmatic consumption
5. Add a `relay stats` command showing task counts by status and average completion time
6. Update relay_web.py /tasks endpoint to include session_ref in the JSON response

All dogfood tasks must go through the full pipeline: `ml task` → relay → dispatch → mini → done.

**Acceptance:** 4+ tasks completed via `ml task --session sprint-8`. `make sprint-scorecard SPRINT=8` shows 90%+ first-try success. All changes are real, useful improvements.

### Task 7: relay_web Discord Status Panel (Stretch)

**Priority:** Low (stretch goal)
**Assignee:** codex
**Depends:** Tasks 1-3

If time permits after the critical tasks, add Discord bot status to the web dashboard:

1. In relay_web.py, add a `/discord/status` endpoint
2. Query agent heartbeat timestamps from SpacetimeDB
3. Return JSON with each bot's name, status (online/stale/offline), and last heartbeat age
4. Add a simple HTML panel to the web dashboard showing bot status with color indicators

**Acceptance:** `http://localhost:8765/discord/status` returns bot health JSON. Web dashboard shows bot status panel.

---
## Task Dependency Graph

```
Task 1 (slash: /relay status)
  ├── Task 2 (slash: /relay post)     [depends on 1]
  ├── Task 3 (slash: /relay board)    [depends on 1]
  └── Task 7 (web discord panel)      [depends on 1-3, stretch]

Task 4 (parallel dispatch)            [independent]
Task 5 (retry counter in schema)      [independent]
Task 6 (dogfood 4+ tasks at 90%)      [depends on 1-5]
```

Tasks 1, 4, and 5 can begin immediately in parallel.
Tasks 2 and 3 require Task 1's slash command registration pattern.
Task 6 should run after the main features land.
Task 7 is a stretch goal.

---

## Success Criteria

1. `/relay status`, `/relay post`, `/relay board` all work from Discord — no CLI required for basic operations
2. `relay_dispatch.sh --parallel 2` runs concurrent tasks correctly
3. `relay retry <id>` creates linked retry tasks with proper attempt tracking
4. `make sprint-scorecard SPRINT=8` shows 90%+ first-try success on 4+ dogfood tasks
5. (Stretch) relay_web shows Discord bot status panel

---

## Out of Scope (Sprint 9 Candidates)

- Discord → SpacetimeDB event sync (heartbeat/chat events as DB rows)
- Per-agent web dashboards
- OpenFang integration
- Cross-project dogfood on repos outside relay-room/LocalManus
- Task priority/scheduling (beyond FIFO)
- Authentication for relay_web

---
## Dependencies & Blockers

- **Discord.py slash commands:** bot_listener.py uses discord.py — verify it supports `app_commands` (discord.py 2.0+). If not, may need `pip install -U discord.py`.
- **SpacetimeDB schema migration:** Task 5 adds fields to the `tasks` table. `make publish` will apply the migration. Ensure the `relay-room-s7-dev` board accepts the update (owned board, should be fine).
- **Parallel dispatch race conditions:** SpacetimeDB `claim_task` reducer is atomic, but test with rapid concurrent claims to confirm no double-claims.
- **LiteLLM at :4000:** Still required for claudecli reasoning. Health gate from Sprint 5 handles degradation.

---

## Execution Notes for ManusLocal

Start with Task 1 — the `/relay status` slash command. This establishes the pattern for all slash commands (registration, permission setup, embed formatting). Tasks 2 and 3 follow the same pattern.

Task 4 (parallel dispatch) and Task 5 (retry counter) are independent and can run alongside slash command work if Codex takes them.

For Task 6, tag all dogfood tasks with `--session sprint-8` so the scorecard picks them up. The 90% target means at most 1 failure in 4+ tasks on first try.

When running slash command tests, use a test channel if available, or #relay-room directly. Capture screenshots or Discord message links as evidence.

Remember: `make install` after any Rust source changes (dispatch now does this automatically, but verify it triggers for Task 5's schema + CLI changes).
