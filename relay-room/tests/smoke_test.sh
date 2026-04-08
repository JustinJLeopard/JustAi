#!/usr/bin/env bash
# smoke_test.sh — end-to-end relay dispatch pipeline smoke test
# Usage: bash tests/smoke_test.sh
# Exit 0 = all assertions pass, exit 1 = one or more failures
set -uo pipefail

export PATH="$HOME/.local/bin:$PATH"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PASS=0; FAIL=0

assert() {
    local desc="$1" result="$2"
    if [[ "$result" == "ok" ]]; then
        echo "[PASS] $desc"
        PASS=$((PASS+1))
    else
        echo "[FAIL] $desc — $result"
        FAIL=$((FAIL+1))
    fi
}

echo "=== relay dispatch smoke test ==="
echo "repo: $REPO_ROOT"
echo ""

# 1. Post a sentinel task
echo "[1] Posting sentinel task..."
POST_OUT=$(relay post --from smoke-test --to localmanus \
    --title "smoke: write sentinel file" \
    --payload "Write the text 'smoke ok' to /tmp/smoke_sentinel_test.txt" 2>&1)
echo "    $POST_OUT"

TASK_UUID=$(echo "$POST_OUT" | grep -oE 'task_uuid=[0-9a-f-]{36}' | cut -d= -f2)
if [[ -z "$TASK_UUID" ]]; then
    echo "[FAIL] could not parse task UUID from relay post output"
    exit 1
fi
echo "    task UUID: $TASK_UUID"
TASK_ID=$(relay tasks --status pending 2>/dev/null \
    | awk -F'|' '{gsub(/"/, "", $2); gsub(/ /, "", $2); if ($2 == "'"$TASK_UUID"'") print $1}' \
    | tr -d ' ')
echo "    task ID: ${TASK_ID:-unknown}"

# 2. Run dispatch once
echo ""
echo "[2] Running relay_dispatch --once..."
DISPATCH_EXIT=0
bash scripts/relay_dispatch.sh --once 2>&1 | sed 's/^/    /' || DISPATCH_EXIT=$?

# 3. Assertions
echo ""
echo "[3] Assertions..."

# A: dispatch exit code
if [[ "$DISPATCH_EXIT" -eq 0 ]]; then
    assert "A: dispatch exit=0" "ok"
else
    assert "A: dispatch exit=0" "exit was $DISPATCH_EXIT"
fi

# B: task status = done
SHOW_OUT=$(relay show "$TASK_ID" 2>/dev/null || echo "")
if echo "$SHOW_OUT" | grep -q '"done"'; then
    assert "B: task status=done" "ok"
else
    assert "B: task status=done" "status not done (id=$TASK_ID)"
fi

# C: result non-empty
RESULT_COL=$(echo "$SHOW_OUT" | awk -F'|' '{print $NF}' | tail -2 | head -1 | tr -d ' "')
if [[ -n "$RESULT_COL" ]]; then
    assert "C: result non-empty" "ok"
else
    assert "C: result non-empty" "result is empty"
fi

# D: traj artifact exists
if [[ -f "/tmp/relay_traj_${TASK_ID}.json" ]]; then
    assert "D: traj artifact exists" "ok"
else
    assert "D: traj artifact /tmp/relay_traj_${TASK_ID}.json" "not found"
fi

# E: run_log cleaned up on success
if [[ ! -f "/tmp/relay_dispatch_run_${TASK_ID}.txt" ]]; then
    assert "E: run_log cleaned up" "ok"
else
    assert "E: run_log cleaned up" "file still exists"
fi

# F: sentinel file (informational)
if [[ -f "/tmp/smoke_sentinel_test.txt" ]]; then
    echo "[INFO] F: sentinel file created"
else
    echo "[INFO] F: sentinel file not found"
fi

# 4. Summary
echo ""
echo "Smoke: $PASS/5 assertions passed"
if [[ $FAIL -eq 0 ]]; then
    echo "Pipeline is healthy"
    exit 0
else
    echo "$FAIL assertion(s) failed"
    exit 1
fi
