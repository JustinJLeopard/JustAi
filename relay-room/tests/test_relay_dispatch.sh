#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

rm -f /tmp/relay_traj_7.json /tmp/relay_dispatch_task_7.log /tmp/relay_dispatch_task_8.log

FAKE_BIN="$TMPDIR/bin"
FAKE_LOCALMANUS="$TMPDIR/localmanus"
mkdir -p "$FAKE_BIN" "$FAKE_LOCALMANUS/scripts" "$FAKE_LOCALMANUS/logs"

cat >"$FAKE_LOCALMANUS/scripts/mini_local_cloud.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" != "-t" ]]; then
  echo "unexpected args" >&2
  exit 2
fi
traj_path="${MINI_TRAJ_FILE:-$(cd "$(dirname "$0")/.." && pwd)/logs/last_mini_run.traj.json}"
honcho_path="${MINI_HONCHO_POST_FILE:-$(cd "$(dirname "$0")/.." && pwd)/logs/last_honcho_post_task.txt}"
mkdir -p "$(dirname "$traj_path")" "$(dirname "$honcho_path")"
cat >"$traj_path" <<'JSON'
{
  "trajectory": [
    {
      "action": { "bash_command": "python add.py --a 2 --b 3" },
      "observation": { "output": "sum=5" }
    }
  ]
}
JSON
cat >"$honcho_path" <<'TXT'
[honcho] Stored task in session 'task-20260405-080000'
[honcho] Summary: Task: sum A and B | Status: completed | Commands executed: python add.py --a 2 --b 3 | Files/artifacts: sum=5
TXT
printf 'handled: %s\n' "$2"
EOF
chmod +x "$FAKE_LOCALMANUS/scripts/mini_local_cloud.sh"

cat >"$FAKE_BIN/relay" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
log_file="${RELAY_TEST_LOG:?}"

printf '%s\n' "$*" >>"$log_file"

case "$1" in
  register|agent-status|heartbeat)
    ;;
  tasks)
    shift
    if [[ "$*" == *"--to manuslocal"* && "$*" == *"--status pending"* ]]; then
      cat <<'OUT'
id | task_uuid | from_agent | to_agent | claimed_by | title | payload | status | priority
----+-----------+------------+----------+------------+-------+---------+--------+---------
 7  | "uuid-7"  | "codex"    | "manuslocal" | "" | "demo" | "sum A and B" | "pending" | 5
OUT
    elif [[ "$*" == *"--to manuslocal"* && "$*" == *"--status in_progress"* ]]; then
      cat <<'OUT'
id | task_uuid | from_agent | to_agent | claimed_by | title | payload | status | priority
----+-----------+------------+----------+------------+-------+---------+--------+---------
OUT
    elif [[ "$*" == *"--to manuslocal"* ]]; then
      cat <<'OUT'
id | task_uuid | from_agent | to_agent | claimed_by | title | payload | status | priority
----+-----------+------------+----------+------------+-------+---------+--------+---------
 7  | "uuid-7"  | "codex"    | "manuslocal" | "" | "demo" | "sum A and B" | "pending" | 5
OUT
    else
      echo "unexpected tasks args: $*" >&2
      exit 9
    fi
    ;;
  show)
    shift
    if [[ "$*" == "7" ]]; then
      cat <<'OUT'
id | task_uuid | from_agent | to_agent | claimed_by | title | payload | status | priority
----+-----------+------------+----------+------------+-------+---------+--------+---------
 7  | "uuid-7"  | "codex"    | "manuslocal" | "manuslocal" | "demo" | "sum A and B" | "in_progress" | 5
OUT
    else
      echo "unexpected show args: $*" >&2
      exit 13
    fi
    ;;
  claim|start)
    ;;
  done)
    [[ "$*" == done\ 7\ --as\ manuslocal\ --result* ]] || {
      echo "unexpected done args: $*" >&2
      exit 10
    }
    ;;
  fail)
    echo "fail should not be called" >&2
    exit 11
    ;;
  *)
    echo "unexpected command: $*" >&2
    exit 12
    ;;
esac
EOF
chmod +x "$FAKE_BIN/relay"

LOG_FILE="$TMPDIR/relay.log"
SUCCESS_DISPATCH_LOG="$TMPDIR/dispatch-success.log"
touch "$LOG_FILE"

PATH="$FAKE_BIN:$PATH" \
LOCALMANUS_ROOT="$FAKE_LOCALMANUS" \
RELAY_TEST_LOG="$LOG_FILE" \
TARGET_FILE="$TMPDIR/.relay-db-target" \
LOG_FILE="$SUCCESS_DISPATCH_LOG" \
bash "$ROOT/scripts/relay_dispatch.sh" --once

grep -Fqx 'tasks --to manuslocal --status pending' "$LOG_FILE"
grep -Fqx 'claim 7 --as manuslocal' "$LOG_FILE"
grep -Fqx 'start 7 --as manuslocal' "$LOG_FILE"
grep -Fqx 'show 7' "$LOG_FILE"
grep -F 'done 7 --as manuslocal --result' "$LOG_FILE"
test -f /tmp/relay_traj_7.json

FAKE_FAIL_LOCALMANUS="$TMPDIR/localmanus-fail"
mkdir -p "$FAKE_FAIL_LOCALMANUS/scripts"

cat >"$FAKE_FAIL_LOCALMANUS/scripts/mini_local_cloud.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "failing fake mini output"
echo "detailed failure line" >&2
exit 23
EOF
chmod +x "$FAKE_FAIL_LOCALMANUS/scripts/mini_local_cloud.sh"

FAIL_LOG_FILE="$TMPDIR/relay-fail.log"
FAIL_DISPATCH_LOG="$TMPDIR/dispatch-fail.log"
cat >"$FAKE_BIN/relay_fail" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
log_file="${RELAY_TEST_LOG:?}"

printf '%s\n' "$*" >>"$log_file"

case "$1" in
  register|agent-status|heartbeat)
    ;;
  tasks)
    shift
    [[ "$*" == *"--to manuslocal"* && "$*" == *"--status pending"* ]] || {
      if [[ "$*" == *"--to manuslocal"* && "$*" == *"--status in_progress"* ]]; then
        cat <<'OUT'
id | task_uuid | from_agent | to_agent | claimed_by | title | payload | status | priority
----+-----------+------------+----------+------------+-------+---------+--------+---------
OUT
        exit 0
      fi
      echo "unexpected tasks args: $*" >&2
      exit 21
    }
    cat <<'OUT'
id | task_uuid | from_agent | to_agent | claimed_by | title | payload | status | priority
----+-----------+------------+----------+------------+-------+---------+--------+---------
 8  | "uuid-8"  | "codex"    | "manuslocal" | "" | "demo-fail" | "explode" | "pending" | 5
OUT
    ;;
  show)
    shift
    if [[ "$*" == "8 --json" ]]; then
      cat <<'OUT'
{"retry_count": 0}
OUT
      exit 0
    fi
    [[ "$*" == "8" ]] || {
      echo "unexpected show args: $*" >&2
      exit 22
    }
    cat <<'OUT'
id | task_uuid | from_agent | to_agent | claimed_by | title | payload | status | priority
----+-----------+------------+----------+------------+-------+---------+--------+---------
 8  | "uuid-8"  | "codex"    | "manuslocal" | "manuslocal" | "demo-fail" | "explode" | "in_progress" | 5
OUT
    ;;
  claim|start)
    ;;
  requeue)
    echo "requeue should not be called" >&2
    exit 26
    ;;
  fail)
    [[ "$*" == fail\ 8\ --as\ manuslocal\ --error* ]] || {
      echo "unexpected fail args: $*" >&2
      exit 23
    }
    ;;
  done)
    echo "done should not be called" >&2
    exit 24
    ;;
  *)
    echo "unexpected command: $*" >&2
    exit 25
    ;;
esac
EOF
chmod +x "$FAKE_BIN/relay_fail"
mv "$FAKE_BIN/relay_fail" "$FAKE_BIN/relay"

PATH="$FAKE_BIN:$PATH" \
LOCALMANUS_ROOT="$FAKE_FAIL_LOCALMANUS" \
RELAY_TEST_LOG="$FAIL_LOG_FILE" \
TARGET_FILE="$TMPDIR/.relay-db-target" \
LOG_FILE="$FAIL_DISPATCH_LOG" \
MAX_RETRIES=0 \
bash "$ROOT/scripts/relay_dispatch.sh" --once

grep -Fqx 'claim 8 --as manuslocal' "$FAIL_LOG_FILE"
grep -Fqx 'start 8 --as manuslocal' "$FAIL_LOG_FILE"
grep -Fqx 'show 8' "$FAIL_LOG_FILE"
grep -F 'fail 8 --as manuslocal --error mini exited 23:' "$FAIL_LOG_FILE"
test -f /tmp/relay_dispatch_task_8.log
grep -Fq '[dispatch] task 8 nonzero exit=23' "$FAIL_DISPATCH_LOG"
