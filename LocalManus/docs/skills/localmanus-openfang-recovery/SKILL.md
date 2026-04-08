---
name: localmanus-openfang-recovery
summary: Recover the LocalManus assistant path when OpenFang startup, agent state, or ml task routing degrades.
---

# LocalManus OpenFang Recovery

Use this when:
- Telegram assistant replies fail
- `ml task` fails or hangs
- `openfang message` fails
- the assistant is present but the daemon is behaving inconsistently

## Goal

Restore the supported LocalManus task path:

```text
ml task -> OpenFang assistant -> LiteLLM -> gpt-5.4 (default), gpt-5.3-codex (code), claude-opus-4-6 (deep reasoning)
```

## Files to inspect first

- `~/projects/LocalManus/config/openfang_assistant.toml`
- `~/projects/LocalManus/scripts/reconcile_openfang_assistant.sh`
- `~/projects/LocalManus/tools/ml_cli.py`
- `~/projects/LocalManus/config/litellm_config.yaml`
- `~/.openfang/autostart.sh`

## Minimum verification sequence

```bash
openfang --version
curl -s http://localhost:50051/api/health
curl -s -H "Authorization: Bearer $LITELLM_KEY" http://localhost:4000/v1/models
openfang agent list
ml task 'Reply with exactly READY.'
```

## Recovery order

1. Confirm daemon health.
2. Confirm LiteLLM health.
3. Confirm the live `assistant` exists.
4. Restart via `scripts/start_manuslocal.sh --background`.
5. Re-check `ml task`.
6. Only after the local runtime works, check Telegram transport.

## Guardrails

- Do not switch the supported task path to `orchestrator` as a quick fix.
- Do not assume the assistant UUID is stable across startup.
- Do not treat Telegram delivery failures as proof of model/runtime failure without checking the Bot API path separately.
