#!/usr/bin/env bash
# =============================================================================
# ManusLocal — Main Startup Script
# Starts all ManusLocal components in the correct order.
# Usage: bash ./scripts/start_manuslocal.sh [--background]
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
LOG_FILE="$LOG_DIR/startup_${TIMESTAMP}.log"
BACKGROUND=${1:-""}

RED='[0;31m'; GREEN='[0;32m'; YELLOW='[1;33m'; BLUE='[0;34m'; NC='[0m'

log() { echo -e "${GREEN}[ManusLocal]${NC} $1" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"; }
err() { echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"; }

mkdir -p "$LOG_DIR"

echo -e "${BLUE}"
cat << 'EOF'
  __  __                        _                    _
 |  \/  | __ _ _ __  _   _ ___| |    ___   ___ __ _| |
 | |\/| |/ _` | '_ \| | | / __| |   / _ \ / __/ _` | |
 | |  | | (_| | | | | |_| \__ \ |__| (_) | (_| (_| | |
 |_|  |_|\__,_|_| |_|\__,_|___/_____\___/ \___\__,_|_|

  Manus's Local Instance — Persistent. Free. Forever.
EOF
echo -e "${NC}"

log "Starting ManusLocal at $TIMESTAMP"

ENV_FILE="$PROJECT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
    log "Loading environment from .env"
    set -a; source "$ENV_FILE"; set +a
else
    warn ".env file not found. Run: bash $SCRIPT_DIR/setup_manuslocal.sh"
fi

log "Detecting Windows host IP..."
WINDOWS_HOST=$(ip route | grep default | awk '{print $3}' 2>/dev/null || grep nameserver /etc/resolv.conf | awk '{print $2}')
log "Windows host: $WINDOWS_HOST"

if curl -sf --max-time 3 "http://$WINDOWS_HOST:11434/" > /dev/null 2>&1; then
    log "✓ Ollama reachable at http://$WINDOWS_HOST:11434"
    export OLLAMA_HOST="http://$WINDOWS_HOST:11434"
else
    warn "⚠ Ollama NOT reachable at http://$WINDOWS_HOST:11434"
    warn "  Run: bash $SCRIPT_DIR/fix_ollama_wsl.sh && restart Ollama on Windows"
    warn "  Continuing with API fallbacks only..."
fi

log "Starting LiteLLM proxy..."
if curl -sf -H "Authorization: Bearer ${LITELLM_KEY:-}" http://localhost:4000/v1/models > /dev/null 2>&1; then
    log "✓ LiteLLM proxy already running at http://localhost:4000"
else
    bash "$SCRIPT_DIR/start_litellm.sh" 2>&1 | tee -a "$LOG_FILE" || warn "LiteLLM startup failed"
fi

log "Starting OpenFang daemon..."
if curl -sf http://localhost:50051/api/health > /dev/null 2>&1; then
    log "✓ OpenFang already running at http://localhost:50051"
else
    nohup "$HOME/.openfang/autostart.sh" >> "$LOG_DIR/openfang.log" 2>&1 &
    sleep 6
    if curl -sf http://localhost:50051/api/health > /dev/null 2>&1; then
        log "✓ OpenFang started"
    else
        warn "⚠ OpenFang may still be starting. Check: $LOG_DIR/openfang.log"
    fi
fi

# Reconcile the primary assistant and core specialist hands every startup.
if bash "$SCRIPT_DIR/reconcile_openfang_assistant.sh" >> "$LOG_FILE" 2>&1; then
    log "✓ Assistant reconciled"
else
    warn "⚠ Assistant reconciliation failed"
fi

if bash "$SCRIPT_DIR/reconcile_openfang_team.sh" >> "$LOG_FILE" 2>&1; then
    log "✓ Specialist hands reconciled"
else
    warn "⚠ Specialist hand reconciliation failed"
fi

log "Checking Honcho memory..."
if python3 "$PROJECT_DIR/memory/honcho_setup.py" --check 2>/dev/null; then
    log "✓ Honcho healthy"
    python3 "$PROJECT_DIR/memory/honcho_setup.py" --resume 2>&1 | head -5 | tee -a "$LOG_FILE" || true
else
    warn "⚠ Honcho check failed. Check HONCHO_API_KEY in .env"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ManusLocal is online.${NC}"
echo -e "${GREEN}  Assistant path: OpenFang assistant -> LiteLLM -> gpt-5.4 (default), gpt-5.3-codex (code), claude-opus-4-6 (deep reasoning)${NC}"
echo -e "${GREEN}  OpenFang: localhost:50051 | LiteLLM: localhost:4000 | Memory: Honcho${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Quick commands:"
echo "    ml task 'your task here'         # Run a task via the reconciled OpenFang assistant"
echo "    ml mini 'your coding task'       # Run via mini-swe-agent"
echo "    ml delegate 'task for Manus'     # Escalate to cloud Manus"
echo "    ml relay send --to claude ...    # Real-time blocker/handoff signal"
echo "    ml relay peek --for claude       # Read pending relay messages"
echo "    ml status                        # Check system status"
echo ""
echo "  Important repair artifacts:"
echo "    config/openfang_assistant.toml"
echo "    scripts/reconcile_openfang_assistant.sh"
echo "    docs/openfang-runtime-repair-2026-04-04.md"
echo ""
echo "  Logs: $LOG_DIR/"
echo ""

if [[ "$BACKGROUND" != "--background" ]]; then
    python3 "$PROJECT_DIR/tools/ml_cli.py" "$@"
fi
