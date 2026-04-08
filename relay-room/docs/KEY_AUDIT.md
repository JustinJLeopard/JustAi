# Key Audit — relay-room / LocalManus / OpenFang
**Written:** 2026-04-07
**Purpose:** Single reference for consolidating key sprawl later

---

## Current State

Keys are duplicated across 4+ files with no single source of truth.

### 1. LITELLM_KEY (LiteLLM proxy master key)

| Location | Format | Notes |
|---|---|---|
| `~/projects/LocalManus/.env` | `LITELLM_KEY=sk-user-...` | Source of truth today |
| `~/.openfang/.env` | `LITELLM_KEY=sk-user-...` | Was stale `sk-litellm-...` until 2026-04-07 fix |
| `~/.openfang/config.toml` `[default_model]` | `api_key_env = "LITELLM_KEY"` | Was HARDCODED until 2026-04-07 fix |
| `~/.openfang/config.toml` `[fallback_providers]` | `api_key_env = "LITELLM_KEY"` | 3 entries, all use env var (good) |

### 2. OPENAI_API_KEY / GAMERON_API_KEY (Gameron.me API)

**Same value as LITELLM_KEY.** Three names for one key.

| Location | Format |
|---|---|
| `~/projects/LocalManus/.env` | `OPENAI_API_KEY=sk-user-...` |
| `~/projects/LocalManus/.env` | `GAMERON_API_KEY=sk-user-...` |
| `~/.openfang/config.toml` fallback | `api_key_env = "OPENAI_API_KEY"` (ollama provider) |
| `litellm_config.yaml` model entries | `api_key: "os.environ/OPENAI_API_KEY"` (all Gameron models) |

### 3. Discord Bot Tokens (5 bots)

All in `~/projects/relay-room/.env`:
- RELAY_COORDINATOR_TOKEN
- CODEX_TOKEN
- MANUSLOCAL_TOKEN
- COWORKCLAUDE_TOKEN
- CLAUDECLI_TOKEN

`bot_listener.py` TOKEN_OVERRIDES maps agent names to env var names (code, not values).

### 4. Other API Keys (in LocalManus/.env)

| Key | Used by |
|---|---|
| DEEPSEEK_API_KEY | litellm_config.yaml, openfang.toml |
| GEMINI_API_KEY | litellm_config.yaml, openfang.toml |
| GROQ_API_KEY | litellm_config.yaml, openfang.toml, ~/.openfang/config.toml |
| OPENROUTER_API_KEY | litellm_config.yaml |
| HONCHO_API_KEY | openfang.toml |
| TELEGRAM_BOT_TOKEN | openfang.toml, ~/.openfang/config.toml |
| GITHUB_TOKEN | openfang.toml MCP server |

### 5. Honcho URLs (inconsistent naming)

| Location | Variable |
|---|---|
| `~/projects/relay-room/.env` | HONCHO_URL |
| `~/projects/LocalManus/.env` | HONCHO_BASE_URL, HONCHO_WORKSPACE_DEV |
| openfang.toml | `honcho_base_url = "${HONCHO_BASE_URL}"` |

---

## The Problem

- Same key appears in 3-4 files — rotation requires a scavenger hunt
- OpenFang daemonizes and reads its own `.env`, not LocalManus's
- Some configs hardcode values, others use env var references — inconsistent
- LITELLM_KEY = OPENAI_API_KEY = GAMERON_API_KEY — triple duplication of one key

## Recommended Fix

1. **Single .env file:** ~/projects/LocalManus/.env as the ONE source of truth
2. **Symlink:** ~/.openfang/.env -> ~/projects/LocalManus/.env (or source it in start script)
3. **relay-room/.env:** only Discord-specific tokens; source LocalManus/.env for shared keys
4. **Eliminate hardcoded keys:** all config.toml entries should use api_key_env, never api_key
5. **Consolidate aliases:** pick ONE name for the Gameron key and alias the rest
6. **Consider OpenFang's encrypted vault** for sensitive keys instead of plaintext .env
7. **Preflight check:** script that verifies all key references resolve and match across all files
