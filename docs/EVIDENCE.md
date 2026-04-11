# JustAi — Evidence & Findings

**Generated:** 2026-04-11 during Sprint 1 — Clean Foundation
**Source:** Trajectory files, session logs, sprint scorecards, relay dispatch logs

---

## 1. mini-swe-agent Execution Profile

**Source:** LocalManus/logs/last_mini_run.traj.json, relay_dispatch task_*.traj.json

| Property | Value |
|---|---|
| mini version | 2.2.8 (v2 native tool calls) |
| Model | openai/claude-opus-4-6 via api.gameron.me/v1 |
| Avg messages per task | ~35 |
| Tool interface | bash only, native tool_use API |
| Exit pattern | COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT echo |
| Trajectory format | mini-swe-agent-1.1 |

**Key finding:** mini is not a "code agent" — it executes any bash-possible task.
Its scope is limited only by what bash can do, which is essentially unlimited.

---

## 2. Sprint Success Curve

**Source:** SPRINT_7_SCORECARD.md, SPRINT_8_SCORECARD.md, SPRINT_9_SCORECARD.md

| Sprint | First-try success | Notes |
|---|---|---|
| 7 | 80% (4/5) | 1 task needed retry |
| 8 | 90% (9/10) | 1 permanent failure, then retry succeeded |
| 9 | 100% (9/9) | Perfect sprint |

**Improvement drivers (evidence-based):**
1. coworkclaude improving task decomposition quality each sprint
2. Retry logic added in Sprint 8 (retry_count field in SpacetimeDB)
3. Tasks becoming more granular and unambiguous over time

**NOT a driver:** Model switching. relay_dispatch.sh hardwires mini_local_cloud.sh
exclusively. The fallback to mini_local.sh (Qwen3) was a manual intervention
designed for failure — it never triggered because Opus never failed enough to need it.

---

## 3. Model Switching — What Actually Happened

**Source:** relay-room/scripts/relay_dispatch.sh line 600, LocalManus/scripts/mini_local_cloud.sh

The robustness harness built during sprint work was designed as:
  Phase 1: justai-cloud (Opus via mini_local_cloud.sh)
  Phase 2: generic-mini (Qwen3 via mini_local.sh)
  Phase 3: justai-cloud again

Phase 2 never triggered across 7+ cloud passes because Opus never accumulated
20 consecutive failures. The test suite grew from 14 → 78 tests autonomously
across those passes. This demonstrates the actual recipe for success:
**well-scoped tasks + capable model = no switching needed.**

**Implication for orchestrator:** Task decomposition quality is the primary lever.
Model fallback is a safety net, not a strategy.

---

## 4. Judgment/Reviewer Agent — What It Actually Did

**Source:** session_20260410T071913Z.json, SPRINT_9_REVIEW_BY_CLAUDE.md

Registered agents in final session:
- manuslocal (task-execution, file-ops) — primary executor
- relay-dispatch (task-dispatch, mini-execution) — dispatcher daemon
- claudecli (reasoning, review, delegation) — Claude CLI instance
- coworkclaude (architecture, planning) — Cowork Claude instance
- codex (code-execution, code-review) — Codex instance

**coworkclaude's actual role:** Post-sprint reviewer and task planner.
Sprint 9 review doc was written by coworkclaude — it approved the sprint,
verified implementations, and identified residual issues.

**Key finding:** The judgment layer operated at PLANNING and POST-EXECUTION,
not during runtime. coworkclaude designed tasks well enough upfront that
manuslocal succeeded first-try without needing runtime intervention.

**Implication for orchestrator:** The Reviewer component belongs between
Planner and Delegator (pre-execution quality gate), not as a runtime signal.

---

## 5. Honcho Usage — What Was Actually Called

**Source:** relay_dispatch.sh, session_capture.py, honcho_writeback.py

Honcho was used in three places:
1. **mini_local_cloud.sh** — pre-task context injection + post-task storage
   via LocalManus/memory/honcho_memory.py
2. **relay_dispatch.sh** — reads last_honcho_post_task.txt to surface
   Honcho summaries in Discord notifications
3. **session_capture.py / honcho_writeback.py** — end-of-session Discord
   state capture written to Honcho (with local JSON fallback)

**Key finding:** Honcho's role was context injection and session state persistence.
Both functions are now covered by claude-flow memory:
- Pre-task context: `claude-flow memory search -q "relevant topic"`
- Post-task storage: `claude-flow memory store -k "key" -v "value"`
- Session persistence: handled by ruv_stop.sh memory snapshot

**Replacement plan:** Replace Honcho calls in active code paths with
claude-flow memory equivalents. The local JSON fallback already exists
in session_capture.py and can be expanded.

---

## 6. SpacetimeDB Memory Issue

**Source:** JUSTAI_V1_SPEC.md warning note, sprint handoff docs

The issue: SpacetimeDB or OpenFang daemon accumulated memory during
start/stop development cycles, causing slowdowns.

**Workaround used:** Inject/extract necessary context before start/stop.
**Root cause:** Not yet definitively identified — needs investigation.
**Sprint 1 action:** Monitor memory during start/stop cycles, identify
whether it's SpacetimeDB, OpenFang, or the relay_dispatch daemon.

---

## 7. .venv Status

**Source:** git ls-files check, .gitignore audit

- relay-room/.venv: NOT tracked in git (already in .gitignore)
- .venv was a development environment for relay-room Python deps
  (discord.py, aiohttp, pytest etc.)
- Safe to leave in place for local dev; already excluded from version control
- No action needed beyond confirming it stays gitignored

---

## 8. Hard-coded Path Inventory

**Source:** grep -rn justinleopard across codebase (33 occurrences)

Files with hard-coded /home/justinleopard/ paths:
- relay-room/scripts/bot_listener.py (3 occurrences — RELAY_BIN, local/cargo bin)
- relay-room/scripts/relay_dispatch.sh (2 occurrences — path validation, prompt)
- relay-room/scripts/model_audit.sh (1 — OpenFang config path)
- relay-room/scripts/sprint7_close.sh (1 — old relay-room path, dead script)
- LocalManus/scripts/mini_local_cloud.sh (3 — WORK_CWD, skill paths)
- LocalManus/config/mini_cloud.yaml (4 — cwd, skill paths, PATH)
- LocalManus/config/mini_qwen3.yaml (1 — cwd)
- LocalManus/config/openfang.toml (1 — filesystem MCP path)
- LocalManus/scripts/setup_env.sh (3 — MINI_SWE_PATH, relay URL, LOG_DIR)
- LocalManus/scripts/setup_manuslocal.sh (2 — usage comment, PROJECT_DIR default)
- LocalManus/scripts/delegate_to_manus.py (1 — machine identifier string)
- LocalManus/scripts/install_deps.sh (1 — clone URL comment)
- LocalManus/mini_reasoning_test.yaml (1 — cwd)
- relay-room/tests/test_preflight_check.sh (4 — HOME env in tests)

Priority for replacement:
- HIGH: bot_listener.py, relay_dispatch.sh (active runtime paths)
- MEDIUM: mini_local_cloud.sh, mini_cloud.yaml (used in task execution)
- LOW: setup_env.sh, tests (setup scripts and test fixtures)
- SKIP: sprint7_close.sh (dead script), docs (historical)
