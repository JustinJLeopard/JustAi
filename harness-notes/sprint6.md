# Harness Notes — Sprint 6

## Sprint Focus
Make it actually work. Run `justai run "goal"` end-to-end against live services.

## What We Ran

```bash
# Start harness services
source ~/.ruv_env && ~/ruv_start.sh

# Start SpacetimeDB (not managed by ruv-start)
nohup spacetime start --listen-addr 127.0.0.1:3000 > /tmp/spacetimedb.log 2>&1 &

# Run the orchestrator
cd ~/projects/JustAi
JUSTAI_SESSION_REF=sprint-6-live python3 -m justai.orchestrator \
  'add a /ready endpoint to health_server.py returning json ready true'
```

## End-to-End Results

| Stage | Status | Notes |
|-------|--------|-------|
| Intent Gate | **Working** | LLM classified "execution" at 0.97 confidence |
| Planner | **Working** | LLM decomposed into 2 tasks with real verify commands |
| Reviewer | **Working** | LLM approved the plan |
| Checkpoint | **Working** | R0 auto-approved, R1 waited 60s then auto-approved |
| Delegator | **Working** | Tasks posted to SpacetimeDB, UUID returned |
| Agent claim | **Timeout** | No mini-swe-agent running to claim — expected |

The full pipeline runs. Tasks land in SpacetimeDB with correct `from_agent`, `to_agent`, status.

## Bugs Found and Fixed

### 1. Double `/v1/v1/` URL path (planner, intent_gate, reviewer)
**Symptom:** LLM calls returned 404.
**Cause:** `LITELLM_BASE_URL=http://localhost:4000/v1` in env, code appended `/v1/chat/completions`.
**Fix:** Strip trailing `/v1` from env value: `.rstrip("/").removesuffix("/v1")`.
**Command to reproduce:**
```bash
curl http://localhost:4000/v1/v1/chat/completions  # 404
curl http://localhost:4000/v1/chat/completions      # 200
```

### 2. relay post returns UUID, not numeric ID (delegator)
**Symptom:** `[delegator] could not parse task ID` — task was posted but ID wasn't captured.
**Cause:** relay v2 prints `posted task_uuid=<uuid>`, old parser looked for `#N`.
**Fix:** Added UUID parsing: `line.split("task_uuid=")[1]`.

### 3. Payload with double quotes breaks spacetime call (delegator)
**Symptom:** `Error: Invalid arguments for reducer post_task` at column 245.
**Cause:** relay CLI passes payload as positional arg to `spacetime call`. Inner double quotes and backslashes break the SpacetimeDB JSON parser.
**Fix:** Added `_sanitize_payload()` — replaces `"` with `'`, strips `$`, converts `\` to `/`.

### 4. SpacetimeDB not started by ruv-start
**Symptom:** `Connection refused` on port 3000.
**Cause:** `ruv_start.sh` doesn't start SpacetimeDB — it's a separate service.
**Note:** Need to start it manually: `spacetime start --listen-addr 127.0.0.1:3000`.

### 5. Python bytecode cache (PYTHONDONTWRITEBYTECODE)
**Symptom:** Code changes not taking effect in orchestrator.
**Cause:** `.pyc` files were being loaded instead of updated `.py` files.
**Fix:** Set `PYTHONDONTWRITEBYTECODE=1` or clear `__pycache__` directories.

## Harness Performance This Sprint

| Metric | Value |
|--------|-------|
| MCP memory store/retrieve | ~5ms (confirmed working) |
| LiteLLM intent classification | ~2s (Opus via Gameron) |
| LiteLLM plan decomposition | ~4s |
| LiteLLM plan review | ~3s |
| R1 checkpoint wait | 60s (hardcoded) |
| relay post to SpacetimeDB | <1s |
| Full pipeline (no agent) | ~75s (mostly the R1 wait) |
| Test suite (172 tests) | 10s |

## What Still Doesn't Work

1. **No agent claiming tasks.** mini-swe-agent (manuslocal) needs to be running as a daemon that polls SpacetimeDB for pending tasks. This is handled by `relay_dispatch.sh` but it requires configuration.

2. **SpacetimeDB not in ruv-start.** Needs manual start. Should be added to the harness.

3. **R1 checkpoint always waits 60s.** Discord integration not wired — checkpoint just sleeps. Could add a `--auto` flag to skip the wait for local dev.

4. **LangFuse still no-op.** Need to set keys to enable tracing.

## Files Changed This Sprint

```
justai/planner.py      — LITELLM_URL .removesuffix("/v1")
justai/intent_gate.py  — same URL fix
justai/reviewer.py     — same URL fix
justai/delegator.py    — _sanitize_payload(), UUID parsing, --from/--to/--title/--payload args
```
