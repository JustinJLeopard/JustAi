# INSTRUCTIONTODEV.md — ManusLocal Developer Instructions

This document is the operator/developer guide for LocalManus.

## Project Context

LocalManus lives at `~/projects/LocalManus/` and uses:
- Ollama on Windows for local inference
- LiteLLM in WSL as the OpenAI-compatible bridge
- OpenFang as the local agent daemon and Telegram bridge
- Honcho as the shared memory layer
- file relay inboxes at `~/.agent-inbox/*.json` for real-time Codex <-> Claude coordination

## Critical Runtime Decisions

### 1. Ollama stays on Windows

The local Qwen model runs on Windows Ollama. WSL tools should not call Ollama directly unless they are explicitly built for that route.

### 2. LiteLLM is the main bridge

All OpenAI-compatible local calls should go through `http://localhost:4000/v1`.

### 3. OpenFang assistant is the supported ingress

The supported LocalManus message path is:
- `ml task`
- OpenFang `assistant`
- LiteLLM
- `gpt-5.4` (default), with dynamic routing to `gpt-5.3-codex` for code-heavy prompts and `claude-opus-4-6` for deep-reasoning prompts

The `orchestrator` agent remains outside the supported path.

### 4. OpenFang runtime repair is now part of startup

OpenFang can preserve broken assistant state across restarts. To prevent that, startup now replaces the assistant with a clean manifest:
- `config/openfang_assistant.toml`
- `scripts/reconcile_openfang_assistant.sh`

### 5. `ml task` must resolve a live assistant ID

OpenFang can replace the assistant at startup. Because of that, `tools/ml_cli.py` now resolves the assistant through `/api/agents` instead of trusting parsed CLI output.

## Operational Runbook

### Start everything

```bash
bash scripts/start_manuslocal.sh
```

### Verify LiteLLM

```bash
curl -s -H "Authorization: Bearer $LITELLM_KEY" http://localhost:4000/v1/models
```

### Verify OpenFang

```bash
openfang --version
curl -s http://localhost:50051/api/health
openfang agent list
```

### Verify LocalManus task path

```bash
ml task 'Reply with exactly READY.'
```

### Real-time relay (Codex <-> Claude)

```bash
ml relay send --to claude --from codex --kind blocker 'Need a decision now'
ml relay peek --for claude
ml relay ack <message-id> --for claude --by claude
ml relay poll --for claude --timeout 120 --interval 2
```

## Known-Good State (April 4, 2026)

- OpenFang `0.5.5`
- LiteLLM running locally on port `4000`
- OpenFang daemon on port `50051`
- assistant reconciled to a clean manifest at startup
- Telegram bot transport validated independently

## Troubleshooting

### `ml task` fails or hangs

1. Check daemon health:
```bash
curl -s http://localhost:50051/api/health
```
2. Check assistant identity:
```bash
openfang agent list
```
3. If the assistant path looks wrong, rerun startup:
```bash
bash scripts/start_manuslocal.sh --background
```
4. If needed, consult:
- `docs/openfang-runtime-repair-2026-04-04.md`

### LiteLLM health confusion

Do not treat unauthenticated `/health` failures as proof the proxy is down. Prefer authenticated `/v1/models` checks.

### Telegram vs runtime failures

Bot API delivery and assistant runtime are separate checks. Verify both independently before changing config.
