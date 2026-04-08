# OpenFang Runtime Repair — 2026-04-04

This document records the runtime repair that restored the LocalManus assistant path.

## Symptoms

- Telegram messages to the assistant returned: `Something went wrong processing your request. Please try again.`
- `openfang message` and `ml task` failed or hung.
- OpenFang logs showed either:
  - `No connected db.`
  - stale assistant identity / stale assistant UUID behavior
  - unstable behavior after daemon restart

## Root Causes

1. The persisted OpenFang `assistant` agent had a poisoned model manifest.
2. The assistant could be recreated at startup, invalidating any cached UUID.
3. The old runtime (`0.5.1`) was less reliable than the updated runtime.
4. `ml_cli.py` could route to a stale assistant target because it parsed CLI output instead of resolving the live daemon state.
5. Some Gameron-routed model responses wrapped tool intents as `function` / `function_name`, which OpenFang can reject as unsupported capability names.

## What Was Changed

### OpenFang Runtime

- Upgraded OpenFang to `0.5.5`
- Backup kept at:
  - `~/.openfang/bin/openfang.backup-v0.5.1-20260404`

### Assistant Reconciliation

Added:
- `config/openfang_assistant.toml`
- `config/openfang_assistant_no_tools.toml`
- `scripts/reconcile_openfang_assistant.sh`

Purpose:
- wait for OpenFang health
- kill the stale `assistant` if present
- spawn a clean `assistant` from a known-good manifest

### LocalManus CLI

Updated:
- `tools/ml_cli.py`

Purpose:
- resolve the live `assistant` from `http://localhost:50051/api/agents`
- avoid stale UUID failures after startup repair
- route code-heavy prompts through a direct LiteLLM `gpt-5.3-codex` path before OpenFang delegation
- detect malformed tool wrapper responses and retry through fallback reconciliation when needed

### LiteLLM Config

Updated:
- `config/litellm_config.yaml`

Purpose:
- Claude models now read `ANTHROPIC_API_KEY` from the environment
- Gemini proxy entry corrected to use `OPENAI_API_KEY`
- fallback chain documented in config
- current cloud-first routing uses Gameron via `OPENAI_API_KEY` with `gpt-5.4` default

## Current Supported Path

```text
ml task
  -> OpenFang assistant
  -> LiteLLM localhost:4000/v1
  -> gpt-5.4 (default)
     -> direct gpt-5.3-codex path for code-heavy prompts
     -> claude-opus-4-6 for deep reasoning prompts
```

## Verification Commands

```bash
openfang --version
curl -s http://localhost:50051/api/health
curl -s -H "Authorization: Bearer $LITELLM_KEY" http://localhost:4000/v1/models
openfang agent list
ml task 'Reply with exactly READY.'
```

Expected result:
- `assistant` is running
- `assistant` is the supported path
- `ml task` returns JSON with status output instead of hanging or failing immediately

## Operator Recovery Procedure

If the assistant path breaks again:

1. Verify OpenFang version:
```bash
openfang --version
```

2. Verify daemon health:
```bash
curl -s http://localhost:50051/api/health
```

3. Restart LocalManus cleanly:
```bash
bash ~/projects/LocalManus/scripts/start_manuslocal.sh --background
```

4. Confirm the assistant was reconciled:
```bash
openfang agent list
```

5. Re-test LocalManus:
```bash
ml task 'Reply with exactly READY.'
```

## Telegram Notes

Telegram transport and assistant runtime are separate checks.

Telegram transport check:
```bash
curl -s -X POST "https://api.telegram.org/bot<token>/sendMessage"   -d chat_id="<chat-id>"   -d text="test"
```

If Telegram works but assistant replies fail, debug the OpenFang runtime path before changing bot settings.

## Non-Goals

This repair did not make `orchestrator` a supported execution path. Keep `orchestrator` out of the critical path until it is explicitly repaired and revalidated.

## Upstream Tracking (Workaround Removal)

- Track the upstream OpenFang tool-wrapper bug where responses can emit `function` / `function_name` wrapper names that do not match executable tool capability names.
- Keep a single upstream issue link in this document once filed.
- Remove these workarounds only after upstream is fixed and validated in this repo:
  - direct code route (`ml task` -> LiteLLM `gpt-5.3-codex`)
  - no-tools fallback manifest (`config/openfang_assistant_no_tools.toml`)
  - wrapper mismatch retry logic in `tools/ml_cli.py`
