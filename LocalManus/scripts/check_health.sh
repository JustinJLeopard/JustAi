#!/usr/bin/env bash
# =============================================================================
# ManusLocal — Health Check Script
# Checks the status of all ManusLocal components.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS="${GREEN}[PASS]${NC}"; FAIL="${RED}[FAIL]${NC}"; WARN="${YELLOW}[WARN]${NC}"

echo ""
echo "=== ManusLocal Health Check ==="
echo ""

# Load env
[[ -f "$PROJECT_DIR/.env" ]] && { set -a; source "$PROJECT_DIR/.env"; set +a; }
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"

# 1. Ollama
printf "Ollama (Windows)... "
if curl -sf "$OLLAMA_HOST/" > /dev/null 2>&1; then
    echo -e "$PASS running at $OLLAMA_HOST"
else
    echo -e "$FAIL not reachable at $OLLAMA_HOST"
fi

# 2. Model availability
printf "Model qwen3:30b-a3b-q4_K_M... "
if curl -sf "$OLLAMA_HOST/api/tags" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print([m['name'] for m in d.get('models',[])])" 2>/dev/null | grep -q "qwen3"; then
    echo -e "$PASS available"
else
    echo -e "$WARN not confirmed (Ollama may be starting)"
fi

# 3. OpenFang (listens on 127.0.0.1:50051)
printf "OpenFang daemon... "
if curl -sf http://127.0.0.1:50051/ > /dev/null 2>&1 || curl -sf http://localhost:50051/ > /dev/null 2>&1; then
    echo -e "$PASS running at http://127.0.0.1:50051"
elif command -v openfang &>/dev/null || [[ -x "$HOME/.openfang/bin/openfang" ]]; then
    echo -e "$WARN installed but daemon not running (run: ~/.openfang/bin/openfang start)"
else
    echo -e "$WARN not installed (run: bash scripts/install_openfang.sh)"
fi

# 4. Honcho
printf "Honcho memory... "
if python3 -c "
import os, sys
sys.path.insert(0, '$PROJECT_DIR')
try:
    from honcho import Honcho
    h = Honcho(api_key=os.environ.get('HONCHO_API_KEY',''), workspace_id='dev')
    print('ok')
except Exception as e:
    print(f'error: {e}')
    sys.exit(1)
" 2>/dev/null | grep -q "ok"; then
    echo -e "$PASS connected"
else
    echo -e "$WARN check HONCHO_API_KEY in .env"
fi

# 5. mini-swe-agent
printf "mini-swe-agent... "
MINI_PATH="${MINI_SWE_PATH:-$HOME/mini-swe-agent}"
if command -v mini &>/dev/null; then
    echo -e "$PASS found at $(which mini)"
elif [[ -d "$MINI_PATH" ]]; then
    echo -e "$WARN found at $MINI_PATH but 'mini' not in PATH (run: pip install -e $MINI_PATH)"
else
    echo -e "$FAIL not found (expected at $MINI_PATH)"
fi

# 6. OpenHands
printf "OpenHands... "
if command -v openhands &>/dev/null; then
    echo -e "$PASS installed"
elif command -v docker &>/dev/null; then
    if docker ps 2>/dev/null | grep -qi "openhands"; then
        echo -e "$PASS running in Docker"
    else
        echo -e "$WARN not running (see docs/openhands_setup.md or run: ml openhands start)"
    fi
elif command -v docker.exe &>/dev/null; then
    if docker.exe ps 2>/dev/null | grep -qi "openhands"; then
        echo -e "$PASS running in Docker Desktop"
    else
        echo -e "$WARN Docker Desktop available but not integrated with WSL (enable WSL integration, then run: ml openhands start)"
    fi
else
    echo -e "$WARN Docker not available in WSL (enable Docker Desktop WSL integration)"
fi

# 7. Python dependencies
printf "Python dependencies... "
if python3 -c "import honcho, requests, rich, typer" 2>/dev/null; then
    echo -e "$PASS all core deps present"
else
    echo -e "$WARN some deps missing (run: pip install -r requirements.txt)"
fi

# 8. Manus delegation endpoint
printf "Manus delegation endpoint... "
MANUS_API="${MANUS_API_URL:-}"
if [[ -n "$MANUS_API" ]]; then
    echo -e "$PASS configured at $MANUS_API"
else
    echo -e "$WARN MANUS_API_URL not set in .env (delegation to cloud Manus disabled)"
fi

echo ""
echo "=== Health Check Complete ==="
echo ""
