#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PATH="$HOME/.local/bin:$PATH"
export RELAY_SERVER="${RELAY_SERVER:-local-server}"
if [[ -z "${RELAY_DB_NAME:-}" && -f "$ROOT/.relay-db-target" ]]; then
  export RELAY_DB_NAME="$(head -n 1 "$ROOT/.relay-db-target")"
fi

TASK_FILE="/tmp/e2e_result_$$.txt"
TASK_TITLE="e2e-test-$$"
TASK_PAYLOAD="echo sprint5-e2e-ok > ${TASK_FILE}"

cleanup() {
  rm -f "$TASK_FILE"
}
trap cleanup EXIT

fail() {
  printf '[FAIL] %s\n' "$1" >&2
  exit 1
}

printf '=== relay e2e pipeline test ===\n'
printf 'repo: %s\n' "$ROOT"
printf 'db:   %s\n\n' "${RELAY_DB_NAME:-unset}"

command -v relay >/dev/null 2>&1 || fail "relay CLI not found in PATH"

if ! relay status >/dev/null 2>&1; then
  fail "relay status failed; check RELAY_DB_NAME/RELAY_SERVER"
fi

POST_JSON="$(relay post --from test-harness --to manuslocal --title "$TASK_TITLE" --payload "$TASK_PAYLOAD" --json)"
TASK_ID="$(python3 - <<'PY' "$POST_JSON"
import json, sys
data = json.loads(sys.argv[1])
print(data["id"])
PY
)"

printf '[INFO] posted task id=%s\n' "$TASK_ID"

if ! bash scripts/relay_dispatch.sh --once >/tmp/test_e2e_dispatch_once.log 2>&1; then
  tail -n 40 /tmp/test_e2e_dispatch_once.log >&2 || true
  fail "relay_dispatch.sh --once failed"
fi

STATUS=""
RESULT=""
for _ in $(seq 1 24); do
  SHOW_JSON="$(relay show "$TASK_ID" --json)"
  STATUS="$(python3 - <<'PY' "$SHOW_JSON"
import json, sys
data = json.loads(sys.argv[1])
print(data.get("status", ""))
PY
)"
  RESULT="$(python3 - <<'PY' "$SHOW_JSON"
import json, sys
data = json.loads(sys.argv[1])
print(data.get("result", ""))
PY
)"

  case "$STATUS" in
    done|failed) break ;;
  esac
  sleep 5
done

printf '[INFO] final status=%s\n' "$STATUS"
[[ -n "$RESULT" ]] && printf '[INFO] result=%s\n' "$RESULT"

if [[ "$STATUS" != "done" ]]; then
  tail -n 40 /tmp/relay_dispatch.log >&2 || true
  fail "task ${TASK_ID} did not complete successfully"
fi

if [[ ! -f "$TASK_FILE" ]]; then
  fail "expected result file missing: $TASK_FILE"
fi

FILE_CONTENT="$(cat "$TASK_FILE")"
if [[ "$FILE_CONTENT" != "sprint5-e2e-ok" ]]; then
  fail "unexpected file content: $FILE_CONTENT"
fi

printf '[PASS] relay e2e pipeline ok\n'
