# AGENTS.md — ManusLocal Coding Agent Instructions

This is the canonical instruction source for agents working in the LocalManus repo.

## Active Roles

| Agent | ID | Role | Current Supported Path |
|---|---|---|---|
| ManusLocal | `manus-local` | Local task interface | OpenFang `assistant` -> LiteLLM -> `gpt-5.4` (default), `gpt-5.3-codex` (code), `claude-opus-4-6` (deep reasoning) |
| Codex | `codex` | Primary code writer | Repo edits, shell work, verification |
| Claude | `claude-code` | Planning and review | Architecture, reasoning, review |
| mini-swe-agent | `mini-swe` | Deep SWE task execution | `mini-local` / `mini-local-cloud` |
| OpenHands | `openhands` | Containerized SWE agent | Secondary path |
| Hermes | `hermes` | Shared runtime / venv | LiteLLM and related Python tooling |

## Mandatory Runtime Assumptions

- The supported `ml task` path is the OpenFang `assistant` agent.
- The `assistant` agent is startup-reconciled from `config/openfang_assistant.toml`.
- `ml task` must resolve the live assistant ID from the daemon API.
- Do not rely on the `orchestrator` agent for normal LocalManus operation.

## Tool Preferences

- CLI first.
- Prefer `ml task` for LocalManus messaging.
- Prefer `ml relay send|peek|ack|poll` for real-time Codex <-> Claude handoff signals.
- Prefer `openfang agent list` and `curl http://localhost:50051/api/health` for daemon verification.
- Prefer `curl -H "Authorization: Bearer $LITELLM_KEY" http://localhost:4000/v1/models` for LiteLLM verification.

## OpenFang Notes

- Installed version target: `0.5.5` or newer.
- Local daemon address: `http://localhost:50051`
- LiteLLM address: `http://localhost:4000/v1`
- If the assistant path degrades, consult `docs/openfang-runtime-repair-2026-04-04.md`.

## Memory Protocol

Use Honcho for cross-session project memory. Do not add a second ad hoc memory layer for agent state.
Use `~/.agent-inbox/<agent>.json` only for immediate real-time coordination (blockers/handoffs) that cannot wait for Honcho bootstrap sync.

## Guardrails

- Do not switch the default LocalManus task path away from `assistant` without revalidating the full runtime.
- Do not assume a static assistant UUID.
- Do not treat Telegram transport failures as proof of model/runtime failure until the Bot API path is checked separately.
