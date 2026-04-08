# Sprint 9 Plan — Relay Room

**Date:** 2026-04-08
**Predecessor:** Sprint 8 (CLI JSON output, health agent status, relay_web session_ref, 90% first-try)
**Primary Goal:** Ship Discord slash commands, add error-recovery scaffolding, and push dogfood success rate toward 95%+
**Branch:** `feature/sprint-9`

---

## Sprint 8 Retrospective

### Completed

- `relay board --json` with summary object (active, done_failed, archived counts)
- `relay task-log <id> --json` with structured metadata (task_id, dispatch_match_count, fallback log)
- `relay_web.py` task detail pages expose `session_ref`
- `/health/agents` returns per-agent `status` (online/stale/offline) with summary counts
- Sprint scorecard at 90.0% first-try success (9/10 tasks)
- Honcho writeback operational, no connector warnings
### Deferred Items (Accumulated Since Sprint 4)

1. **Discord slash commands** — `/relay status`, `/relay post`, `/relay board` (deferred Sprint 4 → 5 → 6 → 7 → 8)
2. **Discord → SpacetimeDB event sync** — heartbeat/chat events as DB rows (Sprint 4)
3. **relay_web Discord status panel** — show bot heartbeat timestamps (Sprint 4)
4. **Parallel dispatch** — `--parallel N` concurrent task execution (Sprint 8 plan, not shipped)
5. **Retry counter in task schema** — track attempt count per task (Sprint 8 plan, not shipped)
6. **Per-agent web dashboards** — (Sprint 6)
7. **OpenFang integration** — (Sprint 6)
8. **Cross-project dogfood** — beyond relay-room/LocalManus (Sprint 7)
9. **Task priority/scheduling** — (Sprint 7)
10. **relay_web authentication** — (Sprint 7)

### Known Issues

- Task 8 failure pattern: early `task_log` compile gap. Mitigated by task 11 retry, but root cause (Rust module wiring on first attempt) not formally addressed.
- `relay_dispatch.sh` still single-threaded — one task at a time.

---

## Sprint 9 Tasks

**Theme:** Close the longest-running deferrals (Discord slash commands), add retry resilience, push toward 95%.
| # | Task | Priority | Assignee | Depends On |
|---|------|----------|----------|------------|
| 1 | `/relay status` Discord slash command | Critical | manuslocal | — |
| 2 | `/relay board` Discord slash command | Critical | manuslocal | 1 |
| 3 | `/relay post` Discord slash command | High | manuslocal | 1 |
| 4 | Retry counter in task schema + CLI display | High | manuslocal | — |
| 5 | Auto-retry failed tasks (max 2 retries) | High | manuslocal | 4 |
| 6 | `relay board --json` includes retry_count per task | Medium | manuslocal | 4 |
| 7 | Dogfood 6+ tasks at ≥95% first-try success | Critical | manuslocal | 1–6 |

---

### Task Details

#### Task 1: `/relay status` Discord Slash Command
**Goal:** Users type `/relay status` in Discord and get a formatted embed showing pipeline health — agent count, active tasks, recent errors.

**Implementation:**
- Register a Discord slash command in `bot_listener.py` using discord.py's `app_commands` or the existing command framework
- Handler calls the `/health` and `/health/agents` HTTP endpoints (localhost:8080)
- Format response as a Discord embed: agent summary (online/stale/offline counts), active task count, last heartbeat timestamp
- Return ephemeral response by default (only visible to caller)

**Acceptance:**
- `/relay status` in any Relay Room channel returns a formatted health embed
- Embed includes agent counts, active task count, and overall status (ok/degraded)
- Unit test: mock HTTP response → verify embed fields
#### Task 2: `/relay board` Discord Slash Command
**Goal:** `/relay board` shows the current task board as a Discord embed, pulling from `relay board --json`.

**Implementation:**
- Register `/relay board` slash command with optional `--all` flag
- Handler shells out to `relay board --json` (or calls the SpacetimeDB SQL directly)
- Format as embed: list active tasks (title, assignee, status), summary footer (active/done/archived counts)
- Truncate to Discord's 4096-char embed limit; link to relay_web for full view

**Acceptance:**
- `/relay board` returns an embed with active tasks and summary counts
- `--all` flag shows full history
- Response truncates gracefully if board is large

#### Task 3: `/relay post` Discord Slash Command
**Goal:** `/relay post` creates a new task from Discord, equivalent to `relay post --title "..." --body "..."`.

**Implementation:**
- Register `/relay post` with required `title` parameter and optional `body`, `to`, `session` parameters
- Handler calls `relay post` CLI or writes directly to SpacetimeDB tasks table
- Confirm with an embed showing the created task ID and title
- Validate inputs (non-empty title) before submission

**Acceptance:**
- `/relay post title:"review PR" body:"check tests"` creates a task and returns confirmation embed
- Missing title returns a user-friendly error
- Created task is visible on the board immediately
#### Task 4: Retry Counter in Task Schema + CLI Display
**Goal:** Each task tracks how many times it has been attempted, visible in `relay board` and `relay task-log`.

**Implementation:**
- Add `retry_count` column to the `tasks` table in `spacetimedb/src/lib.rs` (default 0)
- Update dispatch to increment `retry_count` when re-claiming a failed task
- `relay board` human-readable output shows retry count for tasks with retries > 0
- `relay task-log <id>` shows retry count in both human and JSON output

**Acceptance:**
- `relay board` shows `(retry 1)` or similar annotation on retried tasks
- `relay task-log <id> --json` includes `"retry_count": N`
- New tasks start at retry_count = 0
- Schema migration doesn't break existing data

#### Task 5: Auto-Retry Failed Tasks
**Goal:** `relay_dispatch.sh` automatically retries failed tasks up to 2 times before marking them permanently failed.

**Implementation:**
- After a task fails in dispatch, check `retry_count < 2`
- If retriable: reset status to `pending`, increment `retry_count`, log the retry
- If `retry_count >= 2`: mark as `failed` permanently, log exhaustion
- Add `--max-retries N` flag to dispatch (default 2)

**Acceptance:**
- A task that fails once is automatically retried (status goes pending → claimed → done/failed)
- After 2 retries, task is permanently failed
- `relay board` shows the retry count
- Dispatch log clearly shows retry attempts
#### Task 6: `relay board --json` Includes retry_count
**Goal:** The JSON board output includes retry_count per task so downstream consumers (slash commands, web dashboard) can display it.

**Implementation:**
- Update `render_board_json` in `commands.rs` to include `retry_count` in each task object
- Update `relay_web.py` task detail page to show retry count if > 0

**Acceptance:**
- `relay board --json | jq '.active_tasks[0].retry_count'` returns a number
- relay_web task detail shows "Retries: N" when applicable

#### Task 7: Dogfood — 6+ Tasks at ≥95% First-Try
**Goal:** Execute at least 6 ManusLocal dogfood tasks through the full pipeline. Target 95%+ first-try success.

**Implementation:**
- Use `ml task --session sprint-9` for all dogfood tasks
- Tasks should exercise the new slash command and retry features
- Run `make sprint-scorecard SPRINT=9` to generate metrics
- If below 95%, diagnose and fix before closing the sprint

**Acceptance:**
- `make sprint-scorecard SPRINT=9` shows ≥ 6 task groups
- First-try success rate ≥ 95%
- Scorecard committed to `docs/SPRINT_9_SCORECARD.md`

---

## Dependency Order
```
Task 1 (slash cmd foundation) ──→ Task 2 (/relay board)
                                ──→ Task 3 (/relay post)

Task 4 (retry schema) ──→ Task 5 (auto-retry)
                       ──→ Task 6 (JSON retry_count)

All 1–6 ──→ Task 7 (dogfood)
```

Tasks 1 and 4 can start in parallel. Tasks 2, 3 depend on 1. Tasks 5, 6 depend on 4. Task 7 is the integration gate.

---

## Success Criteria

- [ ] All three Discord slash commands functional in The Relay Room server
- [ ] Retry counter visible in CLI, JSON output, and web dashboard
- [ ] Auto-retry working in dispatch (max 2 retries)
- [ ] ≥ 95% first-try dogfood success rate
- [ ] Honcho writeback at end of sprint
- [ ] Clean commit on `feature/sprint-9` branch

---

## Deferred to Sprint 10+

- Discord → SpacetimeDB event sync (heartbeat/chat as DB rows)
- relay_web Discord status panel
- Parallel dispatch (`--parallel N`)
- Per-agent web dashboards
- OpenFang integration
- Cross-project dogfood beyond relay-room
- Task priority/scheduling
- relay_web authentication
---

## Risk Notes

- **Discord slash command registration** can take up to an hour to propagate globally. Use guild-specific commands for dev/test (instant registration).
- **SpacetimeDB schema migration** for retry_count — test with a fresh DB instance first to ensure backward compatibility.
- **95% target is aggressive** — with 6 tasks, only 0 failures are allowed to hit 100%, and 1 failure drops to 83%. Consider 7+ tasks so one failure still lands at ~86%. The real measure is whether the retry mechanism catches what would have been Sprint 8's task-8-style failure.