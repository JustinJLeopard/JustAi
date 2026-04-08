# Sprint 5 Plan — Relay Room

**Date:** 2026-04-07
**Predecessor:** Sprint 3 (Discord bot integration, daemon lifecycle, health/watchdog) + Sprint 4 (planned, partially deferred)
**Primary Goal:** Complete end-to-end `ml task` validation and harden the relay pipeline for project work
**Branch:** `feature/sprint-5`

---

## Sprint 4 Retrospective

### Completed (Sprint 3 / Codex Handoff)

- daemon_ctl.sh: full bot lifecycle management (start/stop/restart/status --with-bots --with-codex)
- bot_listener.py: all 5 Discord bots online (relay-coordinator, codex, manuslocal, coworkclaude, claudecli)
- relay_dispatch.sh: daemon polling, task claim/dispatch via mini, Discord notifications with proper User-Agent
- health_server.py: HTTP health on :8080, watchdog thread with auto-restart, stale PID fix
- Inbox poll fix working across codex, manuslocal, claudecli handlers
- Watchdog restart path now rewrites PID files correctly
- Discord alert posting corrected
- daemon_ctl.sh no longer double-reports codex when --with-bots --with-codex used
- relay_web /tasks endpoint validated and returns expected empty board

### Sprint 4 Tasks — Carried Forward

These Sprint 4 items were planned but not yet executed. Relevant items are folded into Sprint 5 below.

1. **Discord → SpacetimeDB Event Sync** — deferred (nice-to-have, not blocking `ml task`)
2. **Slash Command Handlers** — deferred to Sprint 6
3. **Agent Registration Alignment** — partially done (names aligned), metadata/capabilities not yet in SpacetimeDB
4. **Session Capture & Honcho Integration** — deferred to Sprint 6
5. **relay_web Discord Status Panel** — deferred to Sprint 6
6. **Integration Tests & CI** — partially done (unit tests exist), E2E pipeline test missing

### Known Issues (Active)

- `ml task` has not been validated end-to-end through the full relay pipeline
- LiteLLM at :4000 may return "Claude API unavailable" — claudecli tasks fall back to curl but can still fail
- relay_web must be started manually (not folded into daemon startup)
- No integration test covers the full post → claim → dispatch → mini → done cycle

---

## Sprint 5 Objective

**Prove that `ml task "..."` works end-to-end on a real project, then harden the path so it's reliable for daily use.**

This sprint is laser-focused on the critical path: a user runs `ml task "do something"`, the task flows through relay → SpacetimeDB → dispatch → mini/codex → done, and the result is correct. Everything else is secondary.

---

## Sprint 5 Tasks

### Task 1: `ml task` E2E Smoke Run — Manual Validation

**Priority:** Critical
**Assignee:** manuslocal
**Depends:** All bots online (confirmed)

Run the full pipeline manually and document exactly what happens at each step:

1. From WSL, execute: `ml task "create a file called /tmp/relay_e2e_test.txt with the text 'sprint 5 validated'"`
2. Observe and record:
   - Does `ml task` post to SpacetimeDB? Check `relay tasks` output.
   - Does relay_dispatch.sh pick it up? Check `/tmp/relay_dispatch.log`.
   - Does mini execute it? Check exit code and output.
   - Does relay mark it done? Check `relay tasks` again for status=done.
   - Does the file exist with correct content? `cat /tmp/relay_e2e_test.txt`
   - Does Discord #relay-room get notified? Check channel.
3. If any step fails, log the exact error and fix it before proceeding.

**Acceptance:** The file exists with correct content. Task shows status=done in `relay tasks`. Discord notification posted.

### Task 2: `ml task` E2E — Real Project Task

**Priority:** Critical
**Assignee:** manuslocal
**Depends:** Task 1 passes

Run `ml task` with a real project-scoped task to validate it works beyond trivial file creation:

1. Pick a real task in relay-room itself, e.g.: `ml task "add a comment at the top of scripts/relay_web.py documenting the /tasks, /health/status, and /task/<id> endpoints"`
2. Verify:
   - Task appears on relay board
   - Dispatch picks it up and runs mini in the correct project directory
   - mini makes the correct edit
   - Task completes with meaningful result summary
   - The file diff is correct (`git diff scripts/relay_web.py`)

**Acceptance:** Real code change lands correctly. Task done with accurate result. No manual intervention needed.

### Task 3: `ml task` Failure Path Validation

**Priority:** High
**Assignee:** codex
**Depends:** Task 1 passes

Test that failures are handled gracefully:

1. Submit a task that will fail: `ml task "compile the nonexistent file /tmp/fakefile.rs with rustc"`
2. Verify:
   - Task is claimed and started
   - mini exits non-zero
   - relay_dispatch marks it `failed` with the error message from mini
   - Discord #alerts gets a failure notification
   - The task shows status=failed with a useful error in `relay tasks`
3. Submit a task to a nonexistent agent: verify it stays pending (not silently dropped)

**Acceptance:** Failed tasks show clear error messages. No silent failures. Alert posted to Discord.

### Task 4: LiteLLM Health Gate for claudecli

**Priority:** High
**Assignee:** codex
**Depends:** None

Add a pre-check in ClaudeHandler._call_claude() that tests LiteLLM availability before attempting the full API call:

1. In `bot_listener.py`, add a lightweight health check method:
   - `GET http://localhost:4000/health` with 3s timeout
   - If unreachable, log clearly and skip the Claude reasoning step
   - Post a degraded-mode message to Discord: "claudecli operating without reasoning layer (LiteLLM unreachable)"
2. In `health_server.py`, surface the LiteLLM check result in `/health` response (already checking port 4000, but ensure it's actionable)
3. Update ClaudeHandler to gracefully degrade: if LiteLLM is down, pass the task through to manuslocal directly instead of failing

**Acceptance:** When LiteLLM is down, claudecli logs the issue, alerts Discord, and degrades gracefully instead of failing tasks.

### Task 5: Fold relay_web into daemon_ctl.sh Startup

**Priority:** Medium
**Assignee:** codex
**Depends:** None

relay_web.py currently requires manual startup. Fold it into the daemon lifecycle:

1. In `daemon_ctl.sh`, add relay_web management:
   - `start` should also start relay_web.py (PID file: `/tmp/relay_web.pid`, log: `/tmp/relay_web.log`)
   - `stop` should also stop relay_web
   - `status` should show relay_web status
   - New flag `--no-web` to skip relay_web if user doesn't want it
2. Default behavior: relay_web starts with the daemon unless `--no-web` is passed
3. Add health check for relay_web in `health_server.py` (check port 8765)

**Acceptance:** `daemon_ctl.sh start` brings up relay_web. `daemon_ctl.sh status` shows it. `daemon_ctl.sh stop` tears it down.

### Task 6: E2E Integration Test Script

**Priority:** High
**Assignee:** manuslocal
**Depends:** Tasks 1-3

Create `tests/test_e2e_pipeline.sh` — an automated version of the manual smoke test:

1. Prerequisites check: spacetimedb up, relay CLI available, dispatch daemon running
2. Post a test task: `relay post --from test-harness --to manuslocal --title "e2e-test" --payload "echo sprint5-e2e-ok > /tmp/e2e_result.txt"`
3. Poll `relay tasks` for up to 120 seconds waiting for status=done or status=failed
4. Assert: task completed, `/tmp/e2e_result.txt` contains "sprint5-e2e-ok"
5. Clean up: remove test artifacts
6. Exit 0 on success, exit 1 on failure with diagnostic output

Add to Makefile:
```makefile
test-e2e:
	bash tests/test_e2e_pipeline.sh
```

**Acceptance:** `make test-e2e` passes when the full stack is running. Fails with clear diagnostics when something is wrong.

### Task 7: Agent Registration Metadata in SpacetimeDB

**Priority:** Medium
**Assignee:** manuslocal
**Depends:** None

Complete the agent registration alignment from Sprint 4 Task 3:

1. Update SpacetimeDB module to include agent metadata fields: `handler_type`, `capabilities` (comma-separated string), `last_heartbeat` (timestamp)
2. Update `relay_dispatch.sh` to register the dispatch daemon as an agent on startup
3. Each bot in `bot_listener.py` should call `relay register` (or equivalent) on boot with its capabilities:
   - relay-coordinator: routing, lifecycle
   - codex: code-execution, code-review
   - manuslocal: task-execution, file-ops
   - coworkclaude: architecture, planning
   - claudecli: reasoning, review, delegation
4. Add `relay agents` CLI subcommand to list registered agents and their status

**Acceptance:** `relay agents` shows all 5 agents with their handler type and capabilities. Heartbeat timestamps update.

---

## Task Dependency Graph

```
Task 1 (smoke run)
  ├── Task 2 (real project task)    [depends on 1]
  ├── Task 3 (failure paths)        [depends on 1]
  └── Task 6 (E2E test script)      [depends on 1, 2, 3]

Task 4 (LiteLLM health gate)        [independent]
Task 5 (relay_web in daemon)         [independent]
Task 7 (agent metadata)             [independent]
```

Tasks 1, 4, 5, and 7 can begin immediately in parallel.
Tasks 2 and 3 require Task 1 to pass first.
Task 6 should be written after Tasks 1-3 are validated.

---

## Success Criteria

1. `ml task "..."` completes end-to-end with a real project task — no manual intervention
2. Failed tasks produce clear error messages and Discord alerts
3. `make test-e2e` passes on a running stack
4. claudecli degrades gracefully when LiteLLM is down
5. `daemon_ctl.sh start` brings up relay_web automatically
6. `relay agents` shows all 5 agents with metadata

---

## Out of Scope (Sprint 6 Candidates)

- Discord slash command handlers (`/relay status`, `/relay post`, etc.)
- Discord → SpacetimeDB event sync (heartbeat/chat events as DB rows)
- Session capture & Honcho writeback on session end
- relay_web Discord status panel (show bot heartbeat timestamps)
- Per-agent web dashboards
- OpenFang integration

---

## Dependencies & Blockers

- **LiteLLM at :4000**: Must be running for claudecli reasoning. Task 4 adds graceful degradation.
- **SpacetimeDB at :3000**: Must be running for all relay operations.
- **LocalManus `ml` CLI**: Must be installed and `ml task` / `ml mini` must be functional. If `ml task` itself has issues (e.g., no_db_connection from Sprint 4 notes), that's the first thing to debug in Task 1.
- **mini binary**: Must be at `/home/justinleopard/.venv/hermes/bin/mini` and executable.

---

## Execution Notes for ManusLocal

This sprint is yours to drive. Start with Task 1 — the manual smoke run. Everything else flows from whether `ml task` works. If it doesn't, debug and fix before moving to any other task.

When running Task 1, capture full output:
```bash
ml task "create a file called /tmp/relay_e2e_test.txt with the text 'sprint 5 validated'" 2>&1 | tee /tmp/sprint5_task1.log
```

Then check the pipeline:
```bash
relay tasks                           # see the task
tail -20 /tmp/relay_dispatch.log      # see dispatch pick it up
cat /tmp/relay_e2e_test.txt           # see the result
```

If `ml task` fails at the CLI level (before reaching relay), the issue is in LocalManus, not relay-room. Check LiteLLM config and `ml` CLI setup first.
