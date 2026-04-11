# JustAi — Testing Guide

## Running Tests

```bash
cd ~/projects/JustAi

# Full suite
python3 -m pytest tests/ -v

# With coverage report
python3 -m pytest tests/ --cov=justai --cov=tools --cov-report=term-missing

# Single file
python3 -m pytest tests/test_orchestrator.py -v

# relay-room tests
python3 -m pytest relay-room/tests/ -v
```

## Test Suites

| File | Components Covered | Tests |
|---|---|---|
| `tests/test_orchestrator.py` | intent_gate, planner, reviewer, checkpoint | 24 |
| `tests/test_delegator_orchestrator.py` | delegator, orchestrator, CLI run command | 21 |
| `tests/test_coverage_gaps.py` | All components — LiteLLM paths, gate files, CLI commands, runtime | 45 |
| `tests/test_coverage_final.py` | planner/reviewer HTTP calls, Discord notify, delegator edge cases | 18 |
| `tests/test_justai_cli.py` | CLI routing, env setup | 6 |
| `tests/test_root_scripts.py` | start_justai.sh, check_justai.sh | 4 |

Total: **118 tests** across `justai/` and `tools/` packages.

## Coverage

As of Sprint 2.5:

| File | Coverage |
|---|---|
| `justai/__init__.py` | 95% |
| `justai/checkpoint.py` | 96% |
| `justai/delegator.py` | 93% |
| `justai/intent_gate.py` | 87% |
| `justai/orchestrator.py` | 90% |
| `justai/planner.py` | 94% |
| `justai/reviewer.py` | 83% |
| `tools/justai_cli.py` | 92% |
| `tools/justai_runtime.py` | 100% |
| **TOTAL** | **92%** |

Remaining uncovered lines are `__main__` blocks and print statements — intentionally excluded.

## Design Principles

**All tests run offline.** External calls (LiteLLM, SpacetimeDB, Discord, relay CLI)
are mocked. No API key or running service needed to run the test suite.

**Mock at the boundary.** We mock `urllib.request.urlopen` for HTTP calls and
`subprocess.run` / `_relay` for CLI calls. We do not mock internal logic.

**Every component has:**
- Happy path test (normal successful execution)
- Failure/fallback test (what happens when external call fails)
- Edge case test (empty input, malformed response, timeout)

## Standing Rule (from JUSTAI_V1_SPEC.md §0)

Every sprint ends with tests covering everything built in that sprint,
committed in the same PR as the feature code. No exceptions.

`python3 -m pytest tests/` must pass cleanly before any sprint is closed.
