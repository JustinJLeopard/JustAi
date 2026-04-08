#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

FAKE_BIN="$TMPDIR/bin"
FAKE_LOCALMANUS="$TMPDIR/localmanus"
mkdir -p "$FAKE_BIN" "$FAKE_LOCALMANUS/scripts"

cat >"$FAKE_LOCALMANUS/scripts/mini_local_cloud.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" != "-t" ]]; then
  echo "unexpected args" >&2
  exit 2
fi
sleep 2
printf 'handled: %s\n' "$2"
EOF
chmod +x "$FAKE_LOCALMANUS/scripts/mini_local_cloud.sh"

cat >"$FAKE_BIN/relay" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
log_file="${RELAY_TEST_LOG:?}"
state_dir="${RELAY_TEST_STATE:?}"
printf '%s\n' "$*" >>"$log_file"

case "$1" in
  register|agent-status|heartbeat)
    ;;
  tasks)
    shift
    if [[ "$*" == "--to manuslocal --status pending" ]]; then
      if [[ ! -f "$state_dir/pending_served" ]]; then
        touch "$state_dir/pending_served"
        cat <<'OUT'
id | task_uuid | from_agent | to_agent | claimed_by | title | payload | status | priority
----+-----------+------------+----------+------------+-------+---------+--------+---------
 7  | "uuid-7"  | "codex"    | "manuslocal" | "" | "demo" | "sum A and B" | "pending" | 5
OUT
      else
        cat <<'OUT'
id | task_uuid | from_agent | to_agent | claimed_by | title | payload | status | priority
----+-----------+------------+----------+------------+-------+---------+--------+---------
OUT
      fi
    elif [[ "$*" == "--to manuslocal --status in_progress" ]]; then
      cat <<'OUT'
id | task_uuid | from_agent | to_agent | claimed_by | title | payload | status | priority
----+-----------+------------+----------+------------+-------+---------+--------+---------
OUT
    else
      echo "unexpected tasks args: $*" >&2
      exit 9
    fi
    ;;
  show)
    shift
    [[ "$*" == "7" ]] || {
      echo "unexpected show args: $*" >&2
      exit 13
    }
    cat <<'OUT'
id | task_uuid | from_agent | to_agent | claimed_by | title | payload | status | priority
----+-----------+------------+----------+------------+-------+---------+--------+---------
 7  | "uuid-7"  | "codex"    | "manuslocal" | "manuslocal" | "demo" | "sum A and B" | "in_progress" | 5
OUT
    ;;
  claim|start)
    ;;
  done)
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

RELAY_TEST_LOG="$TMPDIR/relay.log"
DISPATCH_LOG="$TMPDIR/dispatch.log"
PID_FILE="$TMPDIR/relay_dispatch.pid"
mkdir -p "$TMPDIR/state"
touch "$RELAY_TEST_LOG"

PATH="$FAKE_BIN:$PATH" \
LOCALMANUS_ROOT="$FAKE_LOCALMANUS" \
RELAY_TEST_LOG="$RELAY_TEST_LOG" \
RELAY_TEST_STATE="$TMPDIR/state" \
PID_FILE="$PID_FILE" \
LOG_FILE="$DISPATCH_LOG" \
bash "$ROOT/scripts/relay_dispatch.sh" --daemon --interval 1 &

daemon_pid=$!

for _ in $(seq 1 30); do
  [[ -f "$PID_FILE" ]] && break
  sleep 0.1
done
[[ -f "$PID_FILE" ]]
grep -Fqx "$daemon_pid" "$PID_FILE"

for _ in $(seq 1 30); do
  grep -Fq 'start 7 --as manuslocal' "$RELAY_TEST_LOG" && break
  sleep 0.1
done
grep -Fq 'start 7 --as manuslocal' "$RELAY_TEST_LOG"

kill -TERM "$daemon_pid"
wait "$daemon_pid"

[[ ! -f "$PID_FILE" ]]
grep -Fq 'done 7 --as manuslocal' "$RELAY_TEST_LOG"
grep -Fq '[dispatch] daemon start pid=' "$DISPATCH_LOG"
grep -Fq '[dispatch] task 7 done' "$DISPATCH_LOG"
grep -Fq '[dispatch] daemon exit' "$DISPATCH_LOG"
