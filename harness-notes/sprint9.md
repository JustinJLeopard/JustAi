# Harness Notes — Sprint 9

## Sprint Focus
Dashboard live data integration — real health, run history, orchestrator API.

## What We Ran

```bash
source ~/.ruv_env && ~/ruv_start.sh

cd ~/projects/JustAi

# Run sprint 9 tests
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_sprint9.py -v

# Start the API server (new this sprint)
PYTHONDONTWRITEBYTECODE=1 python3 -m justai.api &
# JustAi API server on http://0.0.0.0:3002

# Test API endpoints
curl -s http://localhost:3002/api/health | python3 -m json.tool
curl -s http://localhost:3002/api/runs?limit=3 | python3 -m json.tool
curl -s http://localhost:3002/api/config | python3 -m json.tool

# Trigger a run from API
curl -s -X POST http://localhost:3002/api/run \
  -H 'Content-Type: application/json' \
  -d '{"goal": "add /ready endpoint", "auto": true}' | python3 -m json.tool

# Start dashboard
cd dashboard && npm run dev
# Dashboard on http://localhost:3001
# Runs view shows real history from MCP memory
# MissionControl shows real service health
```

## New Features

### 1. Dashboard API Server (`justai/api.py`)
Lightweight HTTP server (stdlib only, no Flask) on :3002.

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/api/health` | GET | Service health for LiteLLM, SpacetimeDB, MCP |
| `/api/runs` | GET | Recent orchestrator runs from MCP memory |
| `/api/config` | GET | Current config (version, model, auto mode) |
| `/api/run` | POST | Trigger new orchestrator run (async) |
| `/api/run/status` | GET | Active run status |

CORS enabled. Dashboard proxied through Vite.

### 2. Dashboard Run History View (`RunHistory.tsx`)
- Goal input with auto-mode checkbox + Run button
- Active run status card (running/complete/error)
- Run history table showing goal, intent, tasks, success ratio, duration
- 5s polling interval

### 3. MissionControl Real Health
- Fetches `/api/health` every 10s
- LiteLLM and Memory health dots now show real status
- Replaces hardcoded `ok={true}`

### 4. API Client Library (`api-client.ts`)
TypeScript client for all API endpoints. Used by RunHistory and MissionControl.

## Architecture

```
Browser (:3001)
  ├── /api/health   →  Vite proxy  →  Python API (:3002)
  ├── /api/runs     →  Vite proxy  →  Python API (:3002)
  ├── /api/run      →  Vite proxy  →  Python API (:3002)
  ├── /api/memory   →  Vite proxy  →  claude-flow MCP (:3100)
  └── ws://         →  SpacetimeDB (:3000)
```

## Files Changed This Sprint

```
justai/api.py                        — NEW: dashboard API server
dashboard/src/lib/api-client.ts      — NEW: TypeScript API client
dashboard/src/views/RunHistory.tsx    — NEW: run history + trigger view
dashboard/src/views/MissionControl.tsx — real health data from API
dashboard/src/App.tsx                — added Runs nav item + RunHistory view
dashboard/vite.config.ts             — API proxy routes to :3002
tests/test_sprint9.py                — NEW: 22 tests (API, server, dashboard)
```

## Test Results

| Suite | Tests | Status |
|-------|-------|--------|
| Sprint 9 (new) | 22 | 22 passed |
| Full suite | 249 | 249 passed |
