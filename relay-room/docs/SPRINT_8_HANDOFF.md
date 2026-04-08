# Sprint 8 Handoff — For Next Claude Session

**Date:** 2026-04-08
**From:** Claude (Cowork, Sprint 7 close-out session)
**To:** Claude (next session)

---

## Current State

### Sprint 7: APPROVED ✓

All 7 tasks verified complete via `docs/SPRINT_7_REVIEW_FOR_CLAUDE.md` and `docs/SPRINT_7_SCORECARD.md`:
- Install drift fix (auto `make install` in dispatch)
- Repo hygiene / .gitignore hardened
- `relay board` active-only default + `--all` flag with counts
- Cross-project dogfood: 5 tasks, 80% first-try success
- Honcho connector warning fixed
- Scorecard system operational
- Detail sanitization with unit tests

### Sprint 7 Commit Status
- Review doc recommends commit. Justin may have Codex commit/push before your session.
- Check `git log` on `feature/sprint-7` (or wherever Codex committed) to confirm.

### Sprint 8 Plan: WRITTEN ✓
- Located at `docs/SPRINT_8.md`
- 7 tasks, branch: `feature/sprint-8`
### Honcho Writeback: COMPLETED ✓
- Written to Honcho API (session: writeback-20260408T071434Z)
- Fallback JSON also saved to `scripts/last_session_state.json`
- No connector warnings (Sprint 7 fix confirmed)
- Discord channels captured: relay-room (9), alerts (5), lobby (10), logs (15)
- 6 agents visible: coworkclaude, manus, codex, claudecli, manuslocal, relay-coordinator

---

## Sprint 8 Summary

**Goal:** Ship Discord slash commands, add parallel dispatch, push dogfood to 90%+

| Task | Priority | Assignee | Status |
|------|----------|----------|--------|
| 1. `/relay status` slash command | Critical | manuslocal | Not started |
| 2. `/relay post` slash command | Critical | manuslocal | Not started |
| 3. `/relay board` slash command | High | manuslocal | Not started |
| 4. Parallel dispatch (`--parallel N`) | High | codex | Not started |
| 5. Retry counter in task schema | Medium | codex | Not started |
| 6. Dogfood 4+ tasks at 90% success | Critical | manuslocal | Not started |
| 7. relay_web Discord panel (stretch) | Low | codex | Not started |

**Dependency order:** Tasks 1, 4, 5 can start in parallel. Tasks 2, 3 depend on 1. Task 6 after 1-5. Task 7 is stretch.

---
## Critical Context

### Architecture
- **SpacetimeDB** at :3000 — task lifecycle, agent registry. DB target in `.relay-db-target`: `c200aee2a60c76f74a30fa0ff38562d672b6b0185c00cec3a0c7b03a8761780a` (but Sprint 7 used `relay-room-s7-dev` local-server — check which is active)
- **Discord bots** via `bot_listener.py` — 5 bots: relay-coordinator, codex, manuslocal, coworkclaude, claudecli
- **LiteLLM** at :4000 — Claude reasoning layer for claudecli (health gate added Sprint 5)
- **relay_dispatch.sh** — daemon that polls SpacetimeDB, claims tasks, runs mini
- **relay_web.py** at :8765 — web dashboard (folded into daemon_ctl.sh in Sprint 5)
- **health_server.py** at :8080 — HTTP health + watchdog

### Key Files
- `client/src/commands.rs` — Rust CLI command implementations
- `client/src/main.rs` — CLI entry point (clap)
- `spacetimedb/src/lib.rs` — DB module (tables: agents, tasks, messages, events, archived_tasks)
- `scripts/bot_listener.py` — Discord bot handlers (~600 lines)
- `scripts/relay_dispatch.sh` — dispatch daemon
- `scripts/honcho_writeback.py` — session writeback
- `config/model_preferences.yaml` — model config (mini: gpt-5.3-codex, codex_delegate: gpt-5.4, openfang: claude-opus-4-6)

### Access Patterns (IMPORTANT)
- **Desktop Commander** is locked to `C:\home\justinleopard\projects\relay-room` and `\\wsl.localhost\Ubuntu-24.04\home\justinleopard\projects\relay-room`
- Use `cmd.exe` shell (NOT PowerShell) for WSL commands
- For complex quoting, write a `.sh` runner script to the project and execute via `wsl -d Ubuntu-24.04 -- bash /path/to/script.sh`
- `read_file` often returns metadata only — use `start_process` with `Get-Content` or `cmd.exe /c type` as fallback
### Standing Procedures
1. **At end of every sprint:** Run Honcho writeback via runner script, report success/failure
2. **Sprint workflow:** Claude writes plan → Justin gives to Codex → Codex executes with ManusLocal → Codex reports → Claude reviews and writes next plan
3. **If WSL unreachable:** Check if WSL crashed first (`wsl --list --verbose` via cmd.exe)
4. **Dogfood rule:** Every sprint must include `ml task --session sprint-N` dogfood tasks processed through the full pipeline
5. **Scorecard:** Run `make sprint-scorecard SPRINT=N` to generate metrics after dogfood tasks

### Sprint Success Rate Trend
- Sprint 7: 80% first-try (4/5)
- Sprint 8 target: 90%+ first-try

---

## What To Do First in Next Session

1. Confirm Sprint 7 was committed and pushed (check `git log`)
2. Confirm Justin has served `docs/SPRINT_8.md` to Codex
3. If Sprint 8 work is in progress or complete, read the review document Codex produces
4. If Sprint 8 is not started yet, the plan is ready at `docs/SPRINT_8.md` — no action needed until Codex reports back
5. When Sprint 8 completes: review, approve, run Honcho writeback, write Sprint 9 plan

---

## Deferred to Sprint 9+
- Discord → SpacetimeDB event sync
- Per-agent web dashboards
- OpenFang integration
- Cross-project dogfood beyond relay-room/LocalManus
- Task priority/scheduling
- relay_web authentication
