#!/usr/bin/env bash
# =============================================================================
# ManusLocal — Start LiteLLM Proxy
# Starts the LiteLLM proxy that bridges WSL tools to Ollama on Windows.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG="$PROJECT_DIR/config/litellm_config.yaml"
LOG_DIR="$PROJECT_DIR/logs"
LITELLM_LOG="$LOG_DIR/litellm.log"

mkdir -p "$LOG_DIR"

[[ -f "$PROJECT_DIR/.env" ]] && { set -a; source "$PROJECT_DIR/.env"; set +a; }

WINDOWS_HOST=$(ip route | grep default | awk '{print $3}' || true)
if [[ -z "${WINDOWS_HOST:-}" ]]; then
    WINDOWS_HOST=$(grep nameserver /etc/resolv.conf | awk '{print $2}' | head -1)
fi

echo "Windows host IP detected: $WINDOWS_HOST"

if curl -sf --max-time 3 "http://$WINDOWS_HOST:11434/" > /dev/null 2>&1; then
    echo "Ollama is reachable at http://$WINDOWS_HOST:11434"
else
    echo "WARNING: Ollama not reachable at http://$WINDOWS_HOST:11434"
    echo "Run: bash scripts/fix_ollama_wsl.sh and restart Ollama on Windows."
    echo "Continuing with fallback models only..."
fi

PATCHED_CONFIG="/tmp/litellm_config_patched.yaml"
sed "s|WINDOWS_HOST_IP|$WINDOWS_HOST|g" "$CONFIG" > "$PATCHED_CONFIG"

check_litellm() {
    curl -sf -H "Authorization: Bearer ${LITELLM_KEY:-}" http://localhost:4000/v1/models > /dev/null 2>&1
}

if check_litellm; then
    echo "LiteLLM proxy already running at http://localhost:4000"
    exit 0
fi

echo "Starting LiteLLM proxy on port 4000..."
if [[ -f "$HOME/.venv/hermes/bin/litellm" ]]; then
    source "$HOME/.venv/hermes/bin/activate"
    nohup litellm --config "$PATCHED_CONFIG" --port 4000 >> "$LITELLM_LOG" 2>&1 &
    LITELLM_PID=$!
    echo $LITELLM_PID > /tmp/litellm.pid
    sleep 3
    if check_litellm; then
        echo "LiteLLM proxy started successfully (PID: $LITELLM_PID)"
    else
        echo "WARNING: LiteLLM proxy may still be starting. Check: $LITELLM_LOG"
    fi
else
    echo "ERROR: LiteLLM not found in ~/.venv/hermes/bin/"
    echo "Install with: source ~/.venv/hermes/bin/activate && pip install litellm[proxy]"
    exit 1
fi
