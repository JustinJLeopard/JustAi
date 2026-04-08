#!/usr/bin/env bash
# =============================================================================
# ManusLocal — Environment Setup Script
# Creates the .env file with all required configuration.
# Run once after cloning: bash scripts/setup_env.sh
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${GREEN}ManusLocal Environment Setup${NC}"
echo ""

if [[ -f "$ENV_FILE" ]]; then
    echo -e "${YELLOW}Warning: .env already exists. Backing up to .env.bak${NC}"
    cp "$ENV_FILE" "$ENV_FILE.bak"
fi

cat > "$ENV_FILE" << 'ENVEOF'
# =============================================================================
# ManusLocal Environment Configuration
# DO NOT commit this file to git — it contains secrets.
# =============================================================================

# ── Ollama (Windows-side, accessible from WSL) ────────────────────────────────
# Ollama runs on Windows and is accessible from WSL via the Windows host IP.
# In WSL2, the Windows host is typically at the IP shown by: cat /etc/resolv.conf | grep nameserver
# However, localhost usually works if Ollama is bound to 0.0.0.0.
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:30b-a3b-q4_K_M

# ── Honcho Memory Layer ───────────────────────────────────────────────────────
HONCHO_API_KEY=hch-v3-a6kvt1aihusyc2p9f1qy01fs4ettcgn0eqfcdw4fjvwqpl9ko11xv7uccxpkugvr
HONCHO_BASE_URL=https://api.honcho.dev
HONCHO_WORKSPACE_DEV=dev
HONCHO_WORKSPACE_BIZ=biz
HONCHO_WORKSPACE_SHARED=shared

# ── mini-swe-agent ────────────────────────────────────────────────────────────
MINI_SWE_PATH=/home/justinleopard/mini-swe-agent
# Cost tracking — suppress OpenRouter noise
MSWEA_COST_TRACKING=ignore_errors

# ── OpenRouter (for mini-swe-agent and fallback models) ──────────────────────
# Get your key from https://openrouter.ai/keys
OPENROUTER_API_KEY=

# ── Anthropic (for Claude delegation) ────────────────────────────────────────
ANTHROPIC_API_KEY=

# ── OpenAI (for Codex CLI delegation) ────────────────────────────────────────
OPENAI_API_KEY=

# ── Manus Cloud API (for <10% delegation tasks) ──────────────────────────────
# This enables ManusLocal to escalate tasks to the cloud Manus instance.
# Leave blank to disable cloud delegation.
MANUS_API_URL=
MANUS_API_KEY=

# ── Manus Hand Relay (for controlling Windows PC from Manus cloud) ────────────
MANUS_HAND_RELAY=https://manus-hand-relay.justinleopard.workers.dev
MANUS_HAND_TOKEN=

# ── Telegram (for urgent notifications) ──────────────────────────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ── Business Identity ─────────────────────────────────────────────────────────
BUSINESS_NAME="Delegate and Orchestrate"
BUSINESS_DOMAIN=delegateandorchestrate.com
BUSINESS_EMAIL=delegateandorchestrate@delegateandorchestrate.com

# ── OpenFang ──────────────────────────────────────────────────────────────────
OPENFANG_PORT=4200
GROQ_API_KEY=
GEMINI_API_KEY=
DEEPSEEK_API_KEY=

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
LOG_DIR=/home/justinleopard/projects/JustAi/LocalManus/logs
ENVEOF

echo -e "${GREEN}Created .env at $ENV_FILE${NC}"
echo ""
echo "Next steps:"
echo "  1. Fill in the API keys in .env (especially OPENROUTER_API_KEY)"
echo "  2. Run: bash scripts/install_deps.sh"
echo "  3. Run: bash scripts/start_manuslocal.sh"
