# Sprint 7 Review Report (Pre-Commit)

Date: 2026-04-08
Repo: /home/justinleopard/projects/relay-room
Also touched: /home/justinleopard/projects/LocalManus

## Executive Summary

Sprint 7 is in a "ready to commit" state but not committed yet. The main outcomes are:

1. Install drift mitigations are now enforced in the dispatch path: if a relay-room Rust dogfood task changes Rust source, dispatch auto-runs `make install` before marking the task done.
2. Archive UX is finished and the board output is usable at scale:
   - `relay board` shows active-only by default.
   - `relay board --all` also prints done/failed tasks and archived history.
   - Recent Events are now sanitized/truncated so long task results do not spam the board.
3. Sprint-level scorecard exists and is operational: `make sprint-scorecard SPRINT=7` generates `docs/SPRINT_7_SCORECARD.md` from real task history tagged `sprint-7`.
4. `honcho_writeback.py` no longer leaks an aiohttp connector; the script run completes without the prior warning.

## Current DB Target (Important)

Active `.relay-db-target` now points to `relay-room-s7-dev` (local-server).
Reason: the older copied board could not be updated (403 on publish). Sprint 7 work was validated against the owned board.

## Dogfood Evidence (Sprint 7)

All tasks below were submitted through `ml task --session sprint-7` and processed via foreground `scripts/relay_dispatch.sh --once`.

- Task 4: Added `relay board --all` (CLI + command behavior) and verified `relay board --help` shows `--all`.
- Task 5: Fixed `Archived Tasks` view under `--all` to query `archived_tasks` (not `tasks status='archived'`).
- Task 6: Recent Events `detail` sanitization: whitespace collapsed, newlines/tabs removed, truncated to 140 chars with `...` and unit tests added.
- Task 7: `relay board --all` now prints count lines:
  - `--- Total done/failed tasks: N ---`
  - `--- Total archived tasks: N ---`
  - `--- Total active tasks: N ---`

Scorecard currently shows 80.0% first-try success.

## Key File Changes (relay-room)

- /home/justinleopard/projects/relay-room/client/src/main.rs
  - Adds `--all` to `relay board` CLI args.
- /home/justinleopard/projects/relay-room/client/src/commands.rs
  - `board(db, all)` implements `--all` output sections.
  - Recent Events rendering is client-side sorted and now sanitizes `detail`.
  - Adds/updates unit tests for sanitization and recent-event rendering.
- /home/justinleopard/projects/relay-room/scripts/relay_dispatch.sh
  - Auto-installs relay CLI after Rust-source changes.
  - Derives task workdir/prefix from absolute paths in payload for cross-project tasks.
- /home/justinleopard/projects/relay-room/scripts/preflight_check.sh
  - PATH bootstrapping and check-install included; check runner accumulates results instead of aborting early.
- /home/justinleopard/projects/relay-room/Makefile
  - `check-install` and install-stamp support.
  - `sprint-scorecard` target added.
- /home/justinleopard/projects/relay-room/scripts/sprint_scorecard.sh
  - Generates `docs/SPRINT_7_SCORECARD.md` from tasks tagged `sprint-7`.
- /home/justinleopard/projects/relay-room/scripts/honcho_writeback.py
  - Explicitly awaits/cleans Discord client task to avoid "Unclosed connector".
- /home/justinleopard/projects/relay-room/.gitignore
  - Ignores `archives/*.log{,.gz}`, session JSON artifacts, and throwaway sprint scripts.
- /home/justinleopard/projects/relay-room/tests/__pycache__/*.pyc
  - Previously tracked `.pyc` files are deleted from git.

## LocalManus Change (Needed for Scorecard Tagging)

- /home/justinleopard/projects/LocalManus/tools/ml_cli.py
  - Adds `ml task --session <tag>` which forwards to `relay post --session <tag>` when routed via relay.

Note: user pushes LocalManus themselves; do not include in relay-room commit.

## Verification Commands

Run these from `/home/justinleopard/projects/relay-room`:

1. `cargo test --manifest-path client/Cargo.toml`
2. `make check-install`
3. `relay board`
4. `relay board --all`
5. `make sprint-scorecard SPRINT=7`

## Commit Recommendations

Include in relay-room commit:
- All modified tracked files listed above.
- `scripts/sprint_scorecard.sh`
- `docs/SPRINT_7_SCORECARD.md` (decision: keep as sprint artifact; otherwise add to `.gitignore` and regenerate on demand)

Exclude from relay-room commit:
- `docs/SPRINT_5.md`, `docs/SPRINT_6.md`, `docs/SPRINT_7.md` (currently untracked planning docs)
- `archives/` and `logs/` artifacts (already ignored)

## Open Risks / Follow-Ups

- Publishing/upgrading the older `relay-room-dev` board is still blocked by ownership; Sprint 7 is validated on `relay-room-s7-dev`.
- Scorecard grouping is currently title-based (attempts grouped by identical title); acceptable for now, but a future improvement is an explicit retry/attempt counter in schema.

