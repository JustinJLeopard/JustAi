#!/usr/bin/env bash
set -euo pipefail

API_URL="${OPENFANG_API_URL:-http://127.0.0.1:50051}"

# Load env
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
[[ -f "$PROJECT_DIR/.env" ]] && { set -a; source "$PROJECT_DIR/.env"; set +a; }
MANIFEST="${1:-$PROJECT_DIR/config/openfang_assistant.toml}"

for _ in $(seq 1 30); do
  if curl -fsS "$API_URL/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "$API_URL/api/health" >/dev/null 2>&1; then
  echo "OpenFang API did not become healthy at $API_URL" >&2
  exit 1
fi

ASSISTANT_ID=$(curl -fsS -H "Authorization: Bearer ${OPENFANG_API_KEY:-}" "$API_URL/api/agents" | python3 -c 'import sys, json; agents=json.load(sys.stdin); print(next((a["id"] for a in agents if a["name"] == "assistant"), ""))')
if [ -n "$ASSISTANT_ID" ]; then
  openfang agent kill "$ASSISTANT_ID" >/dev/null || true
  sleep 1
fi

openfang agent spawn "$MANIFEST" >/dev/null
