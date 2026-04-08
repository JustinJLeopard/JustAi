#!/usr/bin/env bash
set -euo pipefail

API_URL="${OPENFANG_API_URL:-http://127.0.0.1:50051}"

# Load env
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
[[ -f "$PROJECT_DIR/.env" ]] && { set -a; source "$PROJECT_DIR/.env"; set +a; }

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

# Ensure specialist hands are activated.
for hand in browser researcher; do
  if ! openfang hand active | rg -q "[[:space:]]${hand}[[:space:]]"; then
    openfang hand activate "$hand" >/dev/null || true
  fi
done

# If either specialist is crashed, cycle the hand instance.
for hand in browser researcher; do
  agent_name="${hand}-hand"
  state=$(curl -fsS -H "Authorization: Bearer ${OPENFANG_API_KEY:-}" "$API_URL/api/agents" | python3 -c 'import json,sys; name=sys.argv[1]; agents=json.load(sys.stdin); m=next((a for a in agents if a.get("name")==name), {}); print(m.get("state", ""))' "$agent_name")

  if [ "$state" = "Crashed" ]; then
    openfang hand deactivate "$hand" >/dev/null || true
    sleep 1
    openfang hand activate "$hand" >/dev/null || true
  fi
done
