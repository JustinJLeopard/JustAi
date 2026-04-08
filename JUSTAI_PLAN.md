# JustAi Integration Plan

## Goal

Build a new combined workspace at `/home/justinleopard/projects/JustAi` that merges the useful runtime and developer workflows from the copied `LocalManus` and `relay-room` repos without editing the originals under `/home/justinleopard/projects/LocalManus` or `/home/justinleopard/projects/relay-room`.

The first pass should produce a working scaffold for a single integrated project named `JustAi` with its own startup path, runtime config, relay integration, and tests. The copied repos inside this workspace are reference material and migration sources, not the long-term product boundary.

## Workspace Layout

Current isolated copies:

- `/home/justinleopard/projects/JustAi/LocalManus`
- `/home/justinleopard/projects/JustAi/relay-room`

Target long-term shape:

- `/home/justinleopard/projects/JustAi/README.md`
- `/home/justinleopard/projects/JustAi/.env.example`
- `/home/justinleopard/projects/JustAi/config/`
- `/home/justinleopard/projects/JustAi/scripts/`
- `/home/justinleopard/projects/JustAi/tools/`
- `/home/justinleopard/projects/JustAi/runtime/`
- `/home/justinleopard/projects/JustAi/tests/`
- `/home/justinleopard/projects/JustAi/docs/`
- `/home/justinleopard/projects/JustAi/vendor/localmanus/` or equivalent
- `/home/justinleopard/projects/JustAi/vendor/relay_room/` or equivalent

The first scaffold pass does not need to fully relocate all code, but it should establish the new root-level `JustAi` entrypoints and route them into the copied code deliberately.

## High-Value Integration Targets

### 1. Unified startup path

Primary source files:

- `/home/justinleopard/projects/JustAi/LocalManus/scripts/start_manuslocal.sh:3`
- `/home/justinleopard/projects/JustAi/LocalManus/scripts/start_manuslocal.sh:64`
- `/home/justinleopard/projects/JustAi/LocalManus/scripts/start_manuslocal.sh:68`
- `/home/justinleopard/projects/JustAi/LocalManus/scripts/start_manuslocal.sh:81`
- `/home/justinleopard/projects/JustAi/LocalManus/scripts/start_manuslocal.sh:87`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/start_relay_room.sh:49`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/daemon_ctl.sh:46`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/daemon_ctl.sh:106`

Required JustAi outcome:

- Add a root startup script such as `/home/justinleopard/projects/JustAi/scripts/start_justai.sh`
- Start services in this order:
  1. SpacetimeDB
  2. LiteLLM
  3. OpenFang
  4. assistant reconciliation
  5. relay-room database bootstrap if needed
  6. relay dispatcher
  7. optional Discord bots and health/web processes
- Make the new startup script depend on paths under `JustAi`, not the original repos
- Avoid hard-coded `/home/justinleopard/projects/LocalManus` and `/home/justinleopard/projects/relay-room` where possible

### 2. Unified operator CLI

Primary source files:

- `/home/justinleopard/projects/JustAi/LocalManus/tools/ml_cli.py:484`
- `/home/justinleopard/projects/JustAi/LocalManus/tools/ml_cli.py:491`
- `/home/justinleopard/projects/JustAi/LocalManus/tools/ml_cli.py:705`
- `/home/justinleopard/projects/JustAi/LocalManus/tools/ml_cli.py:789`
- `/home/justinleopard/projects/JustAi/relay-room/README.md:314`

Required JustAi outcome:

- Add a new CLI entrypoint such as `/home/justinleopard/projects/JustAi/tools/justai_cli.py`
- Keep the familiar `ml`-style developer ergonomics, but expose integrated commands at the JustAi root
- First pass commands should cover:
  - `status`
  - `start`
  - `task`
  - `relay`
  - `mini`
  - `health`
- In the first scaffold pass, it is acceptable for some commands to delegate into copied implementations while paths are being normalized

### 3. Assistant and model runtime

Primary source files:

- `/home/justinleopard/projects/JustAi/LocalManus/scripts/reconcile_openfang_assistant.sh:10`
- `/home/justinleopard/projects/JustAi/LocalManus/scripts/reconcile_openfang_assistant.sh:24`
- `/home/justinleopard/projects/JustAi/LocalManus/tools/ml_cli.py:221`
- `/home/justinleopard/projects/JustAi/LocalManus/tools/ml_cli.py:230`
- `/home/justinleopard/projects/JustAi/LocalManus/tools/ml_cli.py:386`
- `/home/justinleopard/projects/JustAi/LocalManus/tools/ml_cli.py:437`
- `/home/justinleopard/projects/JustAi/LocalManus/README.md:142`

Required JustAi outcome:

- Preserve the stable LocalManus task path:
  - task request
  - OpenFang assistant
  - LiteLLM
  - `gpt-5.4` default
  - direct `gpt-5.3-codex` path for code-heavy prompts
  - `claude-opus-4-6` for deep reasoning
- Move manifest/config references toward JustAi-owned config files over time
- First pass can reuse copied LocalManus config files if wrapped through new JustAi root scripts

### 4. Relay task lifecycle and mini execution

Primary source files:

- `/home/justinleopard/projects/JustAi/relay-room/scripts/relay_dispatch.sh:416`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/relay_dispatch.sh:543`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/relay_dispatch.sh:580`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/relay_dispatch.sh:588`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/relay_dispatch.sh:611`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/relay_dispatch.sh:618`
- `/home/justinleopard/projects/JustAi/relay-room/README.md:240`

Required JustAi outcome:

- Preserve relay task operations:
  - post
  - claim
  - start
  - done
  - fail
  - heartbeat
  - status
- Preserve the mini execution loop that runs tasks and writes summaries/trajectory artifacts
- Refactor path assumptions so the dispatcher can treat `JustAi` as the repo root
- Ensure the dispatcher does not reach back into the original repos

### 5. Discord and bot listeners

Primary source files:

- `/home/justinleopard/projects/JustAi/relay-room/scripts/bot_listener.py:397`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/bot_listener.py:848`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/bot_listener.py:900`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/bot_listener.py:1020`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/bot_listener.py:1217`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/daemon_ctl.sh:267`
- `/home/justinleopard/projects/JustAi/relay-room/scripts/daemon_ctl.sh:353`

Required JustAi outcome:

- Keep bot support as a feature of JustAi, but make it optional and modular
- First pass should wire bot start/stop/status through the new JustAi runtime script rather than expose relay-room directly as the product boundary
- Defer deep behavior changes unless required for path normalization

## Testing Expectations

Write strong tests for every major integrated feature, not only smoke tests.

High-priority existing tests to study and adapt:

- `/home/justinleopard/projects/JustAi/relay-room/tests/test_daemon_ctl.sh:72`
- `/home/justinleopard/projects/JustAi/relay-room/tests/test_daemon_ctl.sh:92`
- `/home/justinleopard/projects/JustAi/relay-room/tests/test_relay_dispatch.sh:106`
- `/home/justinleopard/projects/JustAi/relay-room/tests/test_relay_dispatch.sh:188`
- `/home/justinleopard/projects/JustAi/relay-room/tests/test_e2e_pipeline.sh:37`
- `/home/justinleopard/projects/JustAi/relay-room/tests/test_e2e_pipeline.sh:47`
- `/home/justinleopard/projects/JustAi/relay-room/tests/test_health_server.py:117`
- `/home/justinleopard/projects/JustAi/relay-room/tests/test_health_server.py:147`

Add new JustAi-owned tests under `/home/justinleopard/projects/JustAi/tests/` for:

1. unified startup orchestration
2. status and health reporting
3. relay database bootstrap behavior
4. task routing through the integrated CLI
5. mini task execution wrapper behavior
6. assistant reconciliation path behavior

Prefer stable tests with local fakes/mocks over tests that require external cloud calls.

## First Pass Deliverables

The first mini pass should produce at least this scaffold:

1. A new root README for JustAi
2. A root `.env.example`
3. A `scripts/start_justai.sh`
4. A `scripts/check_justai.sh`
5. A `tools/justai_cli.py`
6. A first-pass `tests/` suite for startup and health
7. Path normalization so the new scripts operate from the `JustAi` root

It is acceptable for the first pass to keep using copied `LocalManus` and `relay-room` code internally while gradually consolidating ownership at the JustAi root.

## Constraints

- Do not modify the original repos:
  - `/home/justinleopard/projects/LocalManus`
  - `/home/justinleopard/projects/relay-room`
- Make all edits only inside `/home/justinleopard/projects/JustAi`
- Prefer moving shared entrypoints to the new root instead of editing the copied repos blindly
- Keep paths deterministic and repo-local
- Do not route the supported execution path through the broken OpenFang `orchestrator`
- When in doubt, preserve the stable assistant-first LocalManus behavior

## Suggested Implementation Sequence

1. Create root JustAi docs, env template, and scripts directories
2. Add `start_justai.sh` that wraps the copied startup/relay logic
3. Add `check_justai.sh` that summarizes service health
4. Add `tools/justai_cli.py` with minimal `start`, `status`, and `task` commands
5. Update copied runtime scripts only where required to parameterize repo root paths
6. Add tests for the new root scripts and CLI
7. Run targeted tests first, then broader regression checks

## Mini Execution Request

Use this plan to scaffold the first integrated JustAi root. Prefer bounded path-safe changes that establish the new project skeleton and root command surface quickly. Do not spend the first pass on polishing. Land the new root structure, minimal working orchestration, and the first meaningful tests.
