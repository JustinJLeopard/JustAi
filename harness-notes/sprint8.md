# Harness Notes — Sprint 8

## Sprint Focus
CLI overhaul — make `justai` a proper command with subcommands.

## What We Ran

```bash
source ~/.ruv_env && ~/ruv_start.sh

cd ~/projects/JustAi

# Run sprint 8 tests
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_sprint8.py -v

# Test CLI live
python3 -m justai version          # justai 0.8.0
python3 -m justai status           # checks LiteLLM, SpacetimeDB, MCP
python3 -m justai history --limit 3  # shows recent runs from memory
python3 -m justai plan "add endpoint"  # plan-only mode

# Install as proper package (makes `justai` command available)
pip install -e .
justai run --auto "your goal"
```

## New CLI Subcommands

| Command | Description |
|---------|-------------|
| `justai run "goal"` | Full orchestrator pipeline |
| `justai run --auto "goal"` | Same, but skip R1 checkpoint wait |
| `justai plan "goal"` | Decompose into tasks (no execution) |
| `justai status` | Service health + memory stats |
| `justai history` | Recent runs from MCP memory |
| `justai version` | Print version (0.8.0) |

### Entry Points
- `python3 -m justai <command>` — module entry via `__main__.py`
- `justai <command>` — after `pip install -e .` via pyproject.toml scripts

## Live CLI Output

```
$ python3 -m justai status
JustAi Service Status
============================================================
  Service preflight:
    ✓ LiteLLM              http://localhost:4000               reachable (http 401)
    ✓ SpacetimeDB          http://127.0.0.1:3000               http 404
    ✓ claude-flow MCP      http://127.0.0.1:3100               healthy

  Memory: MemoryStats(total_entries=26, backend='sql.js + HNSW',
          namespaces={'justai': 16, 'default': 10})

$ python3 -m justai history --limit 3
Recent runs (showing 3 of 7):
----------------------------------------------------------------------
  sprint-7-live-...: goal=add a /ready endpoint... | tasks=2 | done=0
  sprint-6-live6-...: goal=add a /ready endpoint... | tasks=2 | done=0
```

## Files Changed This Sprint

```
justai/cli.py           — NEW: argparse CLI with 5 subcommands
justai/__main__.py      — NEW: entry point for python3 -m justai
justai/__init__.py      — added __version__ = "0.8.0"
pyproject.toml          — NEW: package config, scripts entry, pytest config
tests/test_sprint8.py   — NEW: 24 tests (parser, commands, version, pyproject)
```

## Test Results

| Suite | Tests | Status |
|-------|-------|--------|
| Sprint 8 (new) | 24 | 24 passed |
| Full suite | 227 | 227 passed |
