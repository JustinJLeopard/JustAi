#!/bin/bash
# Phase 2 T2: Preflight Check
# Validates mini, codex, openfang health + database, API, relay board connectivity
# Usage: ./scripts/preflight_check.sh [--verbose] [--json]

set -euo pipefail

VERBOSE=${VERBOSE:-0}
JSON_OUTPUT=${JSON_OUTPUT:-0}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELAY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
JUSTAI_ROOT="${JUSTAI_ROOT:-$(cd "$RELAY_ROOT/.." && pwd)}"
JUSTAI_LOCALMANUS_ROOT="${JUSTAI_LOCALMANUS_ROOT:-$JUSTAI_ROOT/LocalManus}"
export PATH="$PATH:$HOME/.local/bin:$HOME/.cargo/bin"

# Read LiteLLM key from environment or LocalManus .env
LITELLM_KEY="${LITELLM_API_KEY:-}"
if [[ -z "$LITELLM_KEY" ]]; then
  ENV_FILE="${JUSTAI_LOCALMANUS_ROOT}/.env"
  if [[ -f "$ENV_FILE" ]]; then
    LITELLM_KEY=$(grep -oP '^LITELLM_API_KEY=\K.*' "$ENV_FILE" 2>/dev/null || true)
  fi
fi

# Parse args
for arg in "$@"; do
  case "$arg" in
    --verbose) VERBOSE=1 ;;
    --json) JSON_OUTPUT=1 ;;
  esac
done

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CHECKS=()
FAILURES=()
# JSON accumulator: array of {"name":..,"status":..,"detail":..}
JSON_RESULTS=()

check() {
  local name=$1
  shift
  # remaining args are the command + arguments (no eval)

  if [[ $VERBOSE -eq 1 ]] && [[ $JSON_OUTPUT -eq 0 ]]; then
    echo "[CHECK] $name"
  fi

  local output
  if output=$("$@" 2>&1); then
    CHECKS+=("$name")
    [[ $VERBOSE -eq 1 ]] && [[ $JSON_OUTPUT -eq 0 ]] && echo -e "  ${GREEN}+ PASS${NC}"
    JSON_RESULTS+=("{\"name\":\"$name\",\"status\":\"pass\",\"detail\":\"ok\"}")
    return 0
  fi

  FAILURES+=("$name")
  [[ $VERBOSE -eq 1 ]] && [[ $JSON_OUTPUT -eq 0 ]] && echo -e "  ${RED}x FAIL${NC}"
  # escape double quotes in output for JSON safety
  local safe_output
  safe_output=$(echo "$output" | tr '"' "'" | head -c 200)
  JSON_RESULTS+=("{\"name\":\"$name\",\"status\":\"fail\",\"detail\":\"$safe_output\"}")
  return 1
}

# Helper: check command exists
check_cmd() { command -v "$1" >/dev/null 2>&1; }

# Helper: curl returns expected HTTP code
check_http() {
  local url=$1 expected=${2:-200}
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' "$url" 2>/dev/null)
  [[ "$code" == "$expected" ]]
}

# Helper: curl with auth header returns expected HTTP code
check_http_auth() {
  local url=$1 token=$2 expected=${3:-200}
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' "$url" -H "Authorization: Bearer $token" 2>/dev/null)
  [[ "$code" == "$expected" ]]
}

# Helper: curl JSON body contains string
check_model() {
  local url=$1 token=$2 model=$3
  curl -s "$url" -H "Authorization: Bearer $token" 2>/dev/null | grep -q "$model"
}

[[ $JSON_OUTPUT -eq 0 ]] && echo "=== PREFLIGHT CHECK ==="
[[ $JSON_OUTPUT -eq 0 ]] && echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
[[ $JSON_OUTPUT -eq 0 ]] && echo ""

# 1. Mini availability
check "mini binary exists" check_cmd mini || true

# 2. OpenFang API responding
check "openfang api port 50051" check_http "http://localhost:50051/api/agents" || true

# 3. LiteLLM proxy on port 4000
check "litellm proxy port 4000" check_http "http://localhost:4000/v1/models" || true

# 4. Relay dispatch daemon running
check "relay dispatch daemon" pgrep -f "relay_dispatch.sh --daemon" || true

# 5. Installed relay binary matches source
check "relay install current" make -C "$RELAY_ROOT" check-install || true

# 6. API keys in .env
check "gameron api key in .env" grep -q "GAMERON_API_KEY=" "${JUSTAI_LOCALMANUS_ROOT}/.env" || true

# 7-9. Model availability (use key from env, not hardcoded)
if [[ -n "$LITELLM_KEY" ]]; then
  check "gpt-5.4 model available" check_model "http://localhost:4000/v1/models" "$LITELLM_KEY" "gpt-5.4" || true
  check "gpt-5.3-codex model available" check_model "http://localhost:4000/v1/models" "$LITELLM_KEY" "gpt-5.3-codex" || true
  check "claude-opus-4-6 model available" check_model "http://localhost:4000/v1/models" "$LITELLM_KEY" "claude-opus-4-6" || true
else
  FAILURES+=("model checks skipped: LITELLM_API_KEY not found")
  JSON_RESULTS+=('{"name":"model checks","status":"skip","detail":"LITELLM_API_KEY not set"}')
  [[ $JSON_OUTPUT -eq 0 ]] && echo -e "  ${YELLOW}! SKIP model checks: LITELLM_API_KEY not found${NC}"
fi

# 10. Mini --help
check "mini --help works" bash -c "mini --help 2>&1 | grep -q Usage" || true

PASS_COUNT=${#CHECKS[@]}
FAIL_COUNT=${#FAILURES[@]}
TOTAL=$((PASS_COUNT + FAIL_COUNT))

# Output results
if [[ $JSON_OUTPUT -eq 1 ]]; then
  # Build JSON array
  echo -n '{"timestamp":"'
  echo -n "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo -n '","passed":'
  echo -n "$PASS_COUNT"
  echo -n ',"failed":'
  echo -n "$FAIL_COUNT"
  echo -n ',"total":'
  echo -n "$TOTAL"
  STATUS="ok"
  [[ $FAIL_COUNT -gt 0 ]] && STATUS="degraded"
  echo -n ',"status":"'"$STATUS"'"'
  echo -n ',"checks":['
  first=1
  for r in "${JSON_RESULTS[@]}"; do
    [[ $first -eq 0 ]] && echo -n ","
    echo -n "$r"
    first=0
  done
  echo ']}'
else
  echo ""
  echo "Results: $PASS_COUNT / $TOTAL passed"
  if [[ $FAIL_COUNT -eq 0 ]]; then
    echo -e "${GREEN}+ PREFLIGHT OK${NC}"
  else
    echo -e "${RED}x PREFLIGHT DEGRADED${NC}"
    echo "Failed:"
    for fail in "${FAILURES[@]}"; do
      echo "  - $fail"
    done
  fi
fi

[[ $FAIL_COUNT -eq 0 ]] && exit 0 || exit 1
