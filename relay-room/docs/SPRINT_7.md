# Sprint 7 Plan — Relay Room

**Date:** 2026-04-08
**Predecessor:** Sprint 6 (dogfood proven, archive landed, session capture integrated, fresh owned DB live)
**Primary Goal:** Eliminate install drift by design, clean up repo hygiene, finish archive UX, and push dogfooding to cross-project work
**Branch:** `feature/sprint-7`

---

## Sprint 6 Retrospective

### What Sprint 6 Proved

- ManusLocal can build its own features through `ml task` dogfooding
- Multi-step tasks (read → reason → write) work reliably
- Concurrent serial dispatch handles burst load correctly (5 tasks)
- Archive support works at the schema and CLI level on an owned DB
- Session capture and Honcho writeback are integrated into the relay lifecycle
- Log rotation is automated via `make log-rotate` and `daemon_ctl.sh restart`
- `/metrics` endpoint added to health_server.py
- `relay agents --format table` and `relay post` input validation landed
- Fresh owned SpacetimeDB target resolved the copied-DB ownership blocker

### What Was Patched During Sprint 6 (Fragility Signals)

1. **Install drift** — the most dangerous issue. Codex completed a Rust CLI task successfully via `ml task`, but the user couldn't see the change until running `make install`. Source-level correctness meant nothing because the installed binary was stale. Git hooks (`post-merge`, `post-checkout`) were added as mitigation, but they only help on git operations, not on relay-dispatched changes.
2. **DB ownership** — the old copied board couldn't accept writes. Codex correctly pivoted to a fresh owned DB, but this cost time and required re-registering all agents.
3. **`/mnt/c/home/...` path drift** — mini was roaming the filesystem instead of staying anchored in the target repo. Fixed with `MINI_CWD` / `MINI_TASK_PREFIX` in `mini_local_cloud.sh`.
4. **False-positive on recoverable tool errors** — dispatch was sometimes classifying an intermediate recoverable tool error as a task failure. Fixed by checking final task outcome, not first error.

### Residuals Carried Forward

1. **Install drift** — hooks mitigate but don't solve. Needs a design-level fix.
2. **`relay board --active`** — planned in Sprint 6 Task 1, not implemented.
3. **60+ untracked archive log files** — `archives/` not in `.gitignore`, making `git status` noisy.
4. **Stale throwaway scripts** — `explore_openfang*.sh`, `sprint5_close.sh`, `sprint6_review.sh` should be cleaned up.
5. **`honcho_writeback.py` Unclosed connector warning** — aiohttp cleanup debt.
6. **Session JSON fallbacks** in `logs/` — accumulate over time.

### Deferred Items Still Outstanding (from Sprint 4)

- Discord slash commands
- relay_web Discord status panel
- Discord → SpacetimeDB event sync
- Cross-project targeting for `ml task`

---

## Sprint 7 Objective

**Eliminate the gap between "source-correct" and "user-correct" (install drift), clean up the repo so `git status` is quiet, finish archive UX, and push dogfooding to a project outside relay-room.**

Sprint 6 proved ManusLocal works. Sprint 7 makes it reliable enough that you don't have to think about whether changes are actually live.

---

## Sprint 7 Tasks

### Task 1: Eliminate Install Drift by Design

**Priority:** Critical
**Assignee:** codex
**Execution:** `ml task` where possible, manual for relay_dispatch.sh changes (chicken-and-egg)

Install drift is the #1 operational risk. A relay task can change `client/src/commands.rs` successfully, but the binary at `~/.local/bin/relay` stays stale. The user runs `relay` and sees old behavior. This has already bitten us in Sprint 6.

**Approach — auto-install after relay-room Rust changes:**

1. In `relay_dispatch.sh`, after a successful mini run on a relay-room task, check if any Rust source files changed:
   ```bash
   # After mini completes successfully:
   cd "$RR_DIR"
   if git diff --name-only | grep -q '^client/src\|^spacetimedb/src'; then
     echo "[dispatch] Rust source changed — rebuilding relay CLI..."
     make install 2>&1 | tail -5
   fi
   ```
2. This catches the exact case that caused the Sprint 6 incident: a dogfood task edits Rust source, dispatch detects it, and auto-installs before marking the task done.
3. Keep the existing git hooks as a secondary safety net.
4. Add a `make check-install` target that compares the binary version/hash against source:
   ```makefile
   check-install:
   	@src_hash=$$(cd client && cargo metadata --format-version=1 2>/dev/null | md5sum | cut -c1-8); \
   	bin_hash=$$(md5sum $(HOME)/.local/bin/relay 2>/dev/null | cut -c1-8); \
   	if [ "$$src_hash" != "$$bin_hash" ]; then \
   	  echo "⚠ relay binary may be stale — run make install"; \
   	else \
   	  echo "✔ relay binary is current"; \
   	fi
   ```
5. Add `make check-install` to the preflight_check.sh script.

**Acceptance:** After a dogfood task that edits Rust source, `relay --help` immediately reflects the change without manual `make install`.

### Task 2: Repo Hygiene — .gitignore and Cleanup

**Priority:** High
**Assignee:** codex
**Execution:** `ml task`

The working tree is noisy. `git status` shows 60+ untracked archive files and stale scripts.

1. Add to `.gitignore`:
   ```
   /archives/*.log
   /archives/*.log.gz
   /logs/session_*.json
   /logs/pre_switch_snapshot_*.json
   /scripts/explore_openfang*.sh
   /scripts/sprint*_close.sh
   /scripts/sprint*_review.sh
   ```
2. Delete the stale throwaway scripts:
   - `scripts/explore_openfang.sh`
   - `scripts/explore_openfang2.sh`
   - `scripts/explore_openfang3.sh`
   - `scripts/sprint5_close.sh`
   - `scripts/sprint6_review.sh`
   - `scripts/Ok, onto Sprint 5!.txt` (yes, this file exists)
3. Clean up the `archives/` directory: compress any `.log` files older than 1 hour, delete empty ones
4. Verify: `git status --short` should show only intentional changes after cleanup

**Acceptance:** `git status` is quiet. Untracked operational artifacts are gitignored. No throwaway scripts in `scripts/`.

### Task 3: Finish Archive UX — `relay board --active`

**Priority:** Medium
**Assignee:** codex
**Execution:** `ml task`

Planned in Sprint 6 Task 1 but not implemented. As tasks accumulate on the fresh DB, this will matter.

1. Add `--active` flag to `relay board` (in `client/src/main.rs` / `commands.rs`):
   - When set (or by default): filter board output to exclude tasks with status `done` or `failed` that have been archived
   - Since archived tasks are in a separate table, `relay board` already shows only active tasks by default
   - The real need is: `relay board --all` to include archived tasks, and default behavior stays clean
2. Add `relay archive --list` to show what's in the `archived_tasks` table
3. Add `relay archive --count` for a quick tally

**Acceptance:** `relay board` shows only live tasks. `relay archive --list` shows archived history. `relay archive --count` returns a number.

### Task 4: Cross-Project Dogfood — `ml task` on LocalManus

**Priority:** Critical
**Assignee:** manuslocal
**Execution:** `ml task`

Every sprint so far has dogfooded on relay-room itself. Sprint 7 needs to prove ManusLocal works on a different project.

1. Submit a task that targets LocalManus:
   `ml task "add a comment at the top of /home/justinleopard/projects/LocalManus/tools/ml_cli.py documenting the three supported --route options: relay, openfang, auto"`
2. Verify:
   - Dispatch picks it up
   - mini runs in the correct directory (not relay-room)
   - The edit is correct
   - `git diff` in LocalManus shows the expected change
3. Submit a second cross-project task:
   `ml task "list all Python files in /home/justinleopard/projects/LocalManus/scripts/ and write their names and line counts to /tmp/localmanus_scripts_inventory.txt"`
4. If `MINI_CWD` / `MINI_TASK_PREFIX` from Sprint 6 handles this correctly, great. If not, fix the pathing.

**Acceptance:** At least 2 tasks targeting LocalManus (not relay-room) complete correctly via `ml task`.

### Task 5: Fix honcho_writeback.py Connector Warning

**Priority:** Low
**Assignee:** codex
**Execution:** `ml task`

The `Unclosed connector` warning from aiohttp on exit is cleanup debt.

1. In `honcho_writeback.py`, ensure the aiohttp session is properly closed:
   ```python
   async with aiohttp.ClientSession() as session:
       # ... use session ...
   # Session auto-closes here
   ```
   Or if the issue is in the Discord client, ensure `await reader.close()` is called before the event loop exits.
2. The DiscordReader already calls `await self.close()` in `on_ready`, but the connector may linger if the event loop doesn't drain properly. Add explicit connector cleanup.

**Acceptance:** `honcho_writeback.py` runs without the `Unclosed connector` warning.

### Task 6: Scorecard System — Sprint-Level Success Tracking

**Priority:** High
**Assignee:** codex
**Execution:** `ml task`

Codex mentioned a scorecard system. Formalize it so every sprint has a machine-readable outcome.

1. Create `scripts/sprint_scorecard.sh`:
   - Reads the sprint plan (e.g., `docs/SPRINT_7.md`)
   - Queries `relay tasks` for tasks tagged with the sprint
   - Produces a summary: tasks submitted, succeeded on first try, succeeded after retry, failed permanently
   - Calculates success rate percentage
   - Writes scorecard to `docs/SPRINT_7_SCORECARD.md`
2. Add `relay post --session "sprint-7"` convention so tasks are tagged
3. Integrate into the sprint-close procedure: before Honcho writeback, generate scorecard

**Acceptance:** `bash scripts/sprint_scorecard.sh 7` produces a scorecard. Success rate is calculated. Scorecard is written to docs.

### Task 7: Dogfood Sprint — 3+ Real Improvements via `ml task`

**Priority:** Critical
**Assignee:** manuslocal + codex
**Execution:** exclusively `ml task`

Continue the Sprint 6 tradition. Use `ml task` for at least 3 genuine improvements:

Suggested (pick any 3+):

1. `ml task "add a --since flag to relay tasks that filters to tasks created after a given ISO timestamp, implemented in client/src/commands.rs"`
2. `ml task "add a summary line at the bottom of relay board output showing total tasks and breakdown by status"`
3. `ml task "add a /health/agents endpoint to health_server.py that returns the output of relay agents --json"`
4. `ml task "update scripts/preflight_check.sh to verify that the installed relay binary matches the source by comparing cargo metadata output"`
5. `ml task "add a --quiet flag to relay_dispatch.sh that suppresses the no pending tasks log line to reduce log noise in production"`

For each, track:
- Task ID
- First-try success or retry needed
- If failed: root cause
- Time from submission to completion

**Acceptance:** At least 3 improvements landed. Scorecard shows >80% first-try success.

---

## Task Dependency Graph

```
Task 1 (install drift fix)           [do first — affects all dogfood tasks]
Task 2 (repo hygiene)                [do early — clean slate for the sprint]
  │
  ├── Task 3 (board --active)         [after cleanup, so git status stays clean]
  ├── Task 4 (cross-project)          [after install drift fix]
  ├── Task 6 (scorecard)              [after a few tasks are completed]
  └── Task 7 (dogfood sprint)         [continuous, after Tasks 1-2]

Task 5 (honcho connector fix)        [independent, low priority]
```

Tasks 1 and 2 should be done first to establish a clean, reliable working environment.
Tasks 3, 4, 5, 6, 7 can proceed in parallel after that.

---

## Success Criteria

1. Rust source changes via dogfood are auto-installed — no manual `make install` needed
2. `git status` is quiet after sprint work (operational artifacts gitignored)
3. `relay board` shows only active work; `relay archive --list` shows history
4. At least 2 cross-project tasks (on LocalManus) complete successfully
5. `honcho_writeback.py` runs without warnings
6. Sprint scorecard is generated automatically at close
7. At least 3 real improvements landed via `ml task` with >80% first-try success

---

## The Dogfooding Rule (Continued)

Same as Sprint 6: **if a task CAN be done via `ml task`, it MUST be.**

Exceptions:
- Task 1's relay_dispatch.sh changes (the install-drift fix itself is the chicken-and-egg)
- Daemon restarts
- .gitignore changes (trivially small, no point routing through relay)

---

## Sprint-Close Procedure (Standard)

At the end of Sprint 7, before handoff:

1. **Generate scorecard:** `bash scripts/sprint_scorecard.sh 7` (if Task 6 lands)
2. **Run Honcho writeback:** `python3 scripts/honcho_writeback.py --summary "Sprint 7 summary..." --accomplished "..." --pending "..." --blockers "..."`
3. **Run relay session-end:** `relay session-end`
4. **Verify both succeeded.** If Honcho fails, report the failure explicitly and confirm fallback JSON was written.
5. **Report results** to Justin with: scorecard, Honcho session ID, and any fallback details.

---

## Out of Scope (Sprint 8 Candidates)

- Discord slash commands (`/relay status`, `/relay post`)
- relay_web Discord status panel
- Discord → SpacetimeDB event sync
- Parallel dispatch (multiple concurrent mini instances)
- OpenFang integration
- Per-agent web dashboards

---

## Execution Notes for ManusLocal

Start with Tasks 1 and 2 in parallel. Install drift is the most dangerous operational issue — once it's fixed, every subsequent dogfood task is more trustworthy. Repo hygiene is fast and clears the noise so you can see what actually matters in `git status`.

Then hit Task 4 (cross-project) early. This is the next frontier: proving ManusLocal works beyond relay-room. If the `MINI_CWD` fix from Sprint 6 handles it, great. If not, that's the main debugging target.

Task 7 (dogfood improvements) should run continuously alongside everything else. Every feature task IS a dogfood task.
