# Sprint 6 Plan — Relay Room

**Date:** 2026-04-07
**Predecessor:** Sprint 5 (`ml task` E2E validated, failure detection fixed, `make test-e2e` passing)
**Primary Goal:** Dogfood ManusLocal on its own development — use `ml task` to build Sprint 6 features, fix what breaks
**Branch:** `feature/sprint-6`

---

## Sprint 5 Retrospective

### What Worked

- `ml task` E2E pipeline proven: post → SpacetimeDB → dispatch → mini → done
- Real project edit landed via `ml task --route relay` (relay_web.py docstring)
- Failure detection fixed: `detect_failed_tool_call()` added to relay_dispatch.sh reads trajectory JSON for non-zero tool exits, preventing false-positive "done" on failed tasks
- `make test-e2e` passes deterministically using `--once` dispatch mode and `--json` structured output
- relay CLI now has `relay register`, `relay agents`, `relay heartbeat`, `relay agent-status`, `relay show --json`, `relay post --json`
- Dispatch daemon registers itself as an agent on startup and heartbeats each cycle
- All 7 Sprint 5 tasks completed

### What Was Patched (Fragility Signals)

These fixes were made *during* Sprint 5 execution, not before. They indicate areas that need continued attention:

1. **`--route relay` was required** — `ml task` didn't route through relay by default. The default routing path needs verification. If users must always pass `--route relay`, that's a UX gap.
2. **False-positive done on tool failures** — relay_dispatch.sh was marking tasks as done even when mini's tool calls returned non-zero. The `detect_failed_tool_call()` function was added to parse trajectory JSON. This is critical logic that didn't exist before Sprint 5.
3. **"A lot of debugging"** — Codex's own words. The pipeline had multiple rough edges that needed live-fire fixes. This is normal for first-time validation but means we should expect Sprint 6 to surface more issues at the next complexity level.
4. **Historical validation tasks on the board** — No way to clean up or archive completed/failed tasks. The board accumulates noise over time.

### Deferred Items Still Outstanding

Carried from Sprint 4 → Sprint 5 → now Sprint 6:

- Session capture & Honcho writeback (original Sprint 4 Task 4)
- Discord slash commands (original Sprint 4 Task 2)
- relay_web Discord status panel (original Sprint 4 Task 5)
- Discord → SpacetimeDB event sync (original Sprint 4 Task 1)

---

## Sprint 6 Objective

**Use `ml task` to build Sprint 6 itself. The sprint is the test.**

Sprint 5 proved the pipeline works on simple, isolated tasks. Sprint 6 pushes it to the next level: multi-step tasks, concurrent execution, cross-project targeting, and — critically — using ManusLocal to implement its own improvements. Every task that can be submitted via `ml task` should be. If ManusLocal can't build its own features, it's not at 100%.

---

## Sprint 6 Tasks

### Task 1: Board Cleanup — `relay archive` Command

**Priority:** High
**Assignee:** codex
**Execution:** `ml task --route relay`

The relay board has accumulated historical debugging tasks from Sprint 5. There's no way to clean them up without direct SQL.

1. Add `relay archive` CLI subcommand (in `client/src/commands.rs`):
   - `relay archive` — move all done/failed tasks older than 24h to an `archived_tasks` table
   - `relay archive --all` — archive all done/failed tasks regardless of age
   - `relay archive --dry-run` — show what would be archived without doing it
2. Add the `archived_tasks` table to the SpacetimeDB module (same schema as `tasks`, plus `archived_at` timestamp)
3. Add `relay board --active` flag (default behavior) that excludes archived tasks
4. Run `relay archive --all` to clean the current board

**Acceptance:** `relay board` shows only active tasks. `relay archive --dry-run` lists stale tasks. Historical Sprint 5 debugging tasks are archived.

**Dogfood test:** Submit this task via `ml task --route relay "implement relay archive command in client/src/commands.rs that moves done/failed tasks to an archived_tasks table"` and see if mini can scaffold it.

### Task 2: Default Relay Routing for `ml task`

**Priority:** Critical
**Assignee:** manuslocal
**Execution:** manual (requires LocalManus changes)

Sprint 5 revealed that `ml task` required `--route relay` to use the relay pipeline. This should be the default behavior, or at minimum clearly documented.

1. Investigate the `ml` CLI routing logic in LocalManus:
   - What does `ml task "..."` do without `--route relay`?
   - Where is the routing decision made?
   - Is there a config file that sets the default route?
2. If relay is not the default: make it the default (or add a config option `default_route: relay` in LocalManus config)
3. If relay IS the default and `--route relay` was just used for explicitness: document this and remove the flag from Sprint 6 examples
4. Ensure `ml task "..."` (no flags) routes through relay and completes E2E

**Acceptance:** `ml task "create /tmp/s6_routing_test.txt with contents 'routing works'"` succeeds without `--route relay`. Or, if routing is configurable, document the config.

### Task 3: Concurrent Task Stress Test

**Priority:** High
**Assignee:** codex
**Execution:** `ml task --route relay`

The dispatch daemon processes tasks serially in `run_cycle()`. Sprint 5 only tested one task at a time. What happens with a queue of 5?

1. Submit 5 tasks in rapid succession:
   ```bash
   for i in 1 2 3 4 5; do
     relay post --from test-harness --to manuslocal \
       --title "stress-$i" --payload "echo stress-test-$i > /tmp/stress_$i.txt"
   done
   ```
2. Observe dispatch behavior:
   - Do all 5 get claimed and processed?
   - What's the total time to complete all 5?
   - Do any get stuck in "claimed" without completing?
   - Are Discord notifications posted for each?
3. If any issues found: fix them
4. Document the serial processing behavior and add a note about future parallel dispatch

**Acceptance:** All 5 tasks complete (done or failed with correct error). No stuck tasks. Total time is roughly 5× single-task time (confirming serial processing).

### Task 4: Multi-Step Complex Task Validation

**Priority:** Critical
**Assignee:** manuslocal
**Execution:** `ml task --route relay`

Sprint 5 tasks were all single-action. Real work requires multi-step tasks where mini must reason across multiple tool calls.

Run progressively complex tasks:

1. **Two-step task:** `ml task "read the contents of scripts/health_server.py, then add a comment at the top listing how many check functions are defined in it"`
2. **Create + verify task:** `ml task "create a bash script at /tmp/sprint6_validator.sh that checks if relay CLI is in PATH and if SpacetimeDB is reachable on port 3000, then run it and report the results"`
3. **Multi-file task:** `ml task "find all Python files in scripts/ that import discord, and add them to a new file docs/DISCORD_DEPS.md as a bulleted list with their line counts"`

For each, verify:
- mini used multiple tool calls
- the result is correct (not just syntactically valid but semantically right)
- the task result summary in relay is meaningful
- the trajectory JSON captures the full chain

**Acceptance:** At least 2 of 3 multi-step tasks complete correctly without intervention. Failed tasks have clear, actionable error messages.

### Task 5: Session Capture & Honcho Writeback

**Priority:** Medium
**Assignee:** codex
**Execution:** `ml task --route relay` for scaffolding, manual for Honcho integration

Deferred since Sprint 4. Session context doesn't persist between sessions, so every new session starts cold.

1. Implement `scripts/session_capture.py`:
   - On invocation, gather:
     - All relay tasks from current session (filter by `session_ref` or time window)
     - Task outcomes (done/failed/result summaries)
     - Agent heartbeat timeline from `/health/watchdog`
   - Write session summary to Honcho via `honcho_writeback.py`
   - Fallback: write to `logs/session_<timestamp>.json` if Honcho is unreachable
2. Add a `relay session-end` CLI command that triggers session capture
3. Hook into `daemon_ctl.sh stop` to auto-capture on shutdown
4. Test: start a session, run 2-3 tasks, run `relay session-end`, verify Honcho has the summary (or fallback JSON exists)

**Acceptance:** `relay session-end` produces a session summary. Summary is written to Honcho or fallback JSON. Next session can reference previous session's context.

### Task 6: Log Rotation & Housekeeping

**Priority:** Medium
**Assignee:** codex
**Execution:** `ml task --route relay`

All logs go to `/tmp/` and grow forever. Bot logs, dispatch logs, and run logs accumulate.

1. Add `scripts/log_archive.sh` (or extend existing one):
   - Rotate `/tmp/relay_dispatch.log` → timestamped archive in `archives/`
   - Rotate `/tmp/relay_bot_*.log` → archives
   - Compress archives older than 24h
   - Delete archives older than 7 days
   - Clean up `/tmp/relay_dispatch_run_*.txt` and `/tmp/relay_traj_*.json` older than 24h
2. Add `make log-rotate` target to Makefile
3. Add log rotation to `daemon_ctl.sh restart` (rotate before restarting)
4. Optionally: add a cron-friendly `--cron` flag that skips interactive output

**Acceptance:** `make log-rotate` cleans up stale logs. Archives directory has compressed historical logs. `/tmp` doesn't accumulate unbounded relay artifacts.

### Task 7: Dogfood Sprint — Use `ml task` for Real Relay-Room Improvements

**Priority:** Critical
**Assignee:** manuslocal + codex
**Execution:** exclusively `ml task`

This is the most important task. Use `ml task` to make at least **3 real improvements** to relay-room. These should be genuine, useful changes — not contrived test tasks.

Suggested improvements (pick any 3+, or propose better ones):

1. `ml task "add --format json flag to relay agents command in client/src/commands.rs, similar to how relay show --json works"`
2. `ml task "add a startup banner to relay_dispatch.sh that prints the RELAY_DB_NAME, RELAY_SERVER, AGENT name, and INTERVAL_SECONDS when the daemon starts"`
3. `ml task "add a /metrics endpoint to health_server.py that returns task counts by status (pending, in_progress, done, failed) as JSON by querying relay tasks"`
4. `ml task "update the README.md to include a Quick Start section with the 5 commands needed to go from clone to running relay board"`
5. `ml task "add input validation to relay post in client/src/commands.rs that rejects empty --title or --payload arguments with a helpful error message"`

For each:
- Submit via `ml task`
- Do NOT intervene manually
- Record whether it succeeded or failed
- If it failed, record WHY and whether the error message was useful
- Log the task ID and result

**Acceptance:** At least 3 real improvements landed via `ml task` with no manual intervention. Any failures have clear root causes documented.

---

## Task Dependency Graph

```
Task 2 (default routing)             [do first — affects all other ml task calls]
  │
  ├── Task 1 (board cleanup)          [after routing is clear]
  ├── Task 3 (concurrent stress)      [after routing is clear]
  ├── Task 4 (multi-step tasks)       [after routing is clear]
  └── Task 7 (dogfood sprint)         [after routing + multi-step validated]

Task 5 (session capture)             [independent, but benefits from Task 1 cleanup]
Task 6 (log rotation)                [independent]
```

Task 2 should be resolved first since every other task's `ml task` invocation depends on knowing the correct routing.
Tasks 1, 3, 4, 5, 6 can proceed in parallel once routing is settled.
Task 7 should run last (or continuously alongside others) as the integration test of everything.

---

## Success Criteria

1. `ml task "..."` works without `--route relay` (or routing is clearly documented/configured)
2. Board can be cleaned up: `relay archive` removes stale tasks
3. 5 concurrent tasks all complete correctly
4. Multi-step tasks (2+ tool calls) complete without intervention
5. Session context captures to Honcho or fallback on shutdown
6. Logs rotate; `/tmp` doesn't accumulate unbounded artifacts
7. **At least 3 real relay-room improvements landed entirely via `ml task`**

---

## The Dogfooding Rule

**Sprint 6 has one meta-rule: if a task CAN be done via `ml task`, it MUST be done via `ml task`.**

The only exceptions are:
- Task 2 (investigating LocalManus routing internals — requires reading LocalManus code, not relay-room)
- Any fix that requires restarting the daemon (chicken-and-egg)

Everything else — code changes, new scripts, test additions, documentation — should go through the pipeline. If ManusLocal can't do it, that's a bug to file, not a reason to do it manually.

---

## Out of Scope (Sprint 7 Candidates)

- Discord slash commands (`/relay status`, `/relay post`)
- relay_web Discord status panel
- Discord → SpacetimeDB event sync
- Parallel dispatch (run multiple mini instances concurrently)
- Per-agent web dashboards
- OpenFang integration
- Cross-project targeting (ml task aimed at a project other than relay-room)

---

## Execution Notes for ManusLocal

Start with Task 2. Figure out if `--route relay` is required or not. Once routing is clear, immediately jump to Task 7 — the dogfood tasks — because they exercise everything else. Tasks 1, 3, 4, 5, 6 are features; Task 7 is the proof that ManusLocal is a real tool.

When a dogfood task fails, the failure IS the sprint work. Don't just log it — fix whatever broke and resubmit. The goal is to end Sprint 6 with ManusLocal capable of building its own features reliably.

Track every `ml task` submission:
```bash
# After each ml task run, log it:
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | task_id=$ID | status=$STATUS | description='$DESC'" >> /tmp/sprint6_dogfood_log.txt
```

At sprint end, this log is the scorecard. Aim for >80% success rate on first submission.
