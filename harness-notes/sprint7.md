# Harness Notes — Sprint 7

## Sprint Focus
Session memory, auto mode, service preflight, planner retry with heuristic fallback.

## What We Ran

```bash
# Start harness services
source ~/.ruv_env && ~/ruv_start.sh

# Start SpacetimeDB
nohup spacetime start --listen-addr 127.0.0.1:3000 > /tmp/spacetimedb.log 2>&1 &

# Run tests first (31 new + 172 existing)
cd ~/projects/JustAi
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_sprint7.py -v

# Run full suite
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/ -v

# Run live E2E with --auto flag (skips R1 60s wait)
PYTHONDONTWRITEBYTECODE=1 JUSTAI_SESSION_REF=sprint-7-live JUSTAI_AUTO_MODE=1 \
  python3 -m justai.orchestrator --auto \
  'add a /ready endpoint to health_server.py returning json ready true'
```

## End-to-End Results

| Stage | Status | Notes |
|-------|--------|-------|
| **Preflight** | **Working** | LiteLLM ✓ (401 = reachable), SpacetimeDB ✓, MCP ✓ |
| **Session context** | **Working** | Loaded prior session from MCP memory |
| Intent Gate | **Working** | execution @ 0.97 confidence |
| Planner | **Working** | 2 tasks with real verify commands |
| Reviewer | **Working** | Approved |
| Checkpoint (auto) | **Working** | R0 auto-approved, R1 auto-approved (auto mode) — **no 60s wait** |
| Delegator | **Timeout** | No agent running — expected |
| **Pipeline time** | **~15s** | vs ~75s in Sprint 6 (saved 60s from R1 skip) |

## New Features

### 1. Service Health Preflight (`justai/health.py`)
Checks LiteLLM, SpacetimeDB, and claude-flow MCP before running pipeline.
- LiteLLM down = warning (heuristic fallback available)
- SpacetimeDB/MCP down = non-critical warning
- 401/403 from LiteLLM treated as "reachable" (health endpoint needs auth)

### 2. Auto Mode (`--auto` / `JUSTAI_AUTO_MODE=1`)
R1 checkpoints approve immediately — no 60s wait. R2/R3 unaffected.

```bash
# Via CLI flag:
python3 -m justai.orchestrator --auto "your goal"

# Via env var:
JUSTAI_AUTO_MODE=1 python3 -m justai.orchestrator "your goal"
```

### 3. Session Memory
Orchestrator loads prior session context at startup and saves after each run.
- Keys: `justai/session/{ref}` and `justai/session/latest`
- Context fed to planner as additional input
- Memory via MCP HTTP (~5ms)

### 4. Planner Retry + Heuristic Fallback
LLM calls retry once before falling back. Fallback generates a 3-task plan:
1. **Explore** — read relevant files (R0)
2. **Execute** — the actual work (R1)
3. **Verify** — check success (R0)

Verify commands are inferred from goal text (curl for endpoints, pytest for tests, etc.)

## Bugs Found and Fixed

### 1. LiteLLM health 401 misclassified as "unreachable"
**Symptom:** Preflight said "LiteLLM unreachable" even though API calls worked fine.
**Cause:** `/health` endpoint returns 401 without auth. Health check treated all errors as down.
**Fix:** HTTP 401/403 classified as "reachable (auth-required)".

### 2. Nested quote syntax error in heuristic verify command
**Symptom:** `SyntaxError: invalid syntax` on planner import.
**Cause:** `"python3 -c 'print("ok")'` — double quotes inside double-quoted string.
**Fix:** Changed to `"python3 -c 'import ast; print(1)'"`.

### 3. Old tests expected single-task fallback
**Symptom:** 3 existing tests failed after Sprint 7 changes.
**Cause:** Tests expected `len(plan.tasks) == 1` on fallback; now heuristic returns 2-3 tasks.
**Fix:** Updated assertions to `assertGreaterEqual(len(plan.tasks), 2)`.

## Test Results

| Suite | Tests | Status |
|-------|-------|--------|
| Sprint 7 (new) | 31 | 31 passed |
| Full suite | 203 | 203 passed |

## Files Changed This Sprint

```
justai/health.py        — NEW: service health preflight checks
justai/orchestrator.py  — session memory, --auto flag, preflight, _parse_args
justai/checkpoint.py    — _is_auto_mode(), R1 instant approval in auto mode
justai/planner.py       — _heuristic_plan(), _infer_verify_command(), retry logic
tests/test_sprint7.py   — NEW: 31 tests (auto mode, preflight, session, retry)
tests/test_orchestrator.py     — updated for heuristic fallback
tests/test_coverage_gaps.py    — updated for heuristic fallback
tests/test_delegator_orchestrator.py — updated for session memory calls
```
