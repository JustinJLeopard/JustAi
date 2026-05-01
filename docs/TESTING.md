# JustAi Testing Guide

## Running Tests

```bash
cd ~/projects/JustAi

.venv/bin/pytest -q
.venv/bin/ruff check justai tests
.venv/bin/mypy justai
```

## Test Scope

The current suite covers the control plane:

- intent classification
- scope planning
- plan review
- checkpoints
- local dispatch/error handling
- trajectory, ledger, memory, and tracing helpers
- CLI and script wrappers
- dashboard/API support
- docs contract checks

## Design Principles

All tests run offline. External calls are mocked at the boundary: HTTP clients, subprocess calls, and optional observability clients.

Every behavior change should include a focused regression test when it affects public CLI behavior, orchestration decisions, docs contracts, or run accounting.
