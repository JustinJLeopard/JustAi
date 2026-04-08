#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d)"
FAKE_BIN="$TMPDIR/bin"
FAKE_LOCALMANUS="$TMPDIR/localmanus"
FAKE_MINI="$TMPDIR/.venv/hermes/bin/mini"

mkdir -p "$FAKE_BIN" "$FAKE_LOCALMANUS" "$(dirname "$FAKE_MINI")"

svc3000=""
svc4000=""

cleanup() {
  if [[ -n "$svc3000" ]]; then kill "$svc3000" >/dev/null 2>&1 || true; fi
  if [[ -n "$svc4000" ]]; then kill "$svc4000" >/dev/null 2>&1 || true; fi
  PATH="$FAKE_BIN:$PATH" \
  LOCALMANUS_ROOT="$FAKE_LOCALMANUS" \
  PID_FILE="$TMPDIR/relay_dispatch.pid" \
  LOG_FILE="$TMPDIR/relay_dispatch.log" \
  MINI_BIN="$FAKE_MINI" \
  "$ROOT/scripts/daemon_ctl.sh" stop >/dev/null 2>&1 || true
  rm -rf "$TMPDIR"
}
trap cleanup EXIT

cat > "$FAKE_LOCALMANUS/.env" <<'ENVEOF'
RELAY_DB_NAME=relay-room-test
RELAY_SERVER=local-server
ENVEOF

cat > "$FAKE_BIN/relay" <<'RELAYEOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--help" ]]; then
  echo "relay help"
  exit 0
fi
if [[ "${1:-}" == "tasks" ]]; then
  cat <<'OUT'
id | task_uuid | from_agent | to_agent | claimed_by | title | payload | status | priority
----+-----------+------------+----------+------------+-------+---------+--------+---------
OUT
  exit 0
fi
exit 0
RELAYEOF
chmod +x "$FAKE_BIN/relay"

cat > "$FAKE_MINI" <<'MINIEOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--help" ]]; then
  echo "mini help"
  exit 0
fi
echo "mini ok"
MINIEOF
chmod +x "$FAKE_MINI"

python3 -m http.server 3000 --bind 127.0.0.1 >/dev/null 2>&1 &
svc3000=$!
python3 -m http.server 4000 --bind 127.0.0.1 >/dev/null 2>&1 &
svc4000=$!

PATH="$FAKE_BIN:$PATH" \
LOCALMANUS_ROOT="$FAKE_LOCALMANUS" \
PID_FILE="$TMPDIR/relay_dispatch.pid" \
LOG_FILE="$TMPDIR/relay_dispatch.log" \
MINI_BIN="$FAKE_MINI" \
"$ROOT/scripts/daemon_ctl.sh" --verbose start

for _ in $(seq 1 50); do
  [[ -f "$TMPDIR/relay_dispatch.pid" ]] && break
  sleep 0.1
done
[[ -f "$TMPDIR/relay_dispatch.pid" ]]

PATH="$FAKE_BIN:$PATH" \
LOCALMANUS_ROOT="$FAKE_LOCALMANUS" \
PID_FILE="$TMPDIR/relay_dispatch.pid" \
LOG_FILE="$TMPDIR/relay_dispatch.log" \
MINI_BIN="$FAKE_MINI" \
"$ROOT/scripts/daemon_ctl.sh" status

PATH="$FAKE_BIN:$PATH" \
LOCALMANUS_ROOT="$FAKE_LOCALMANUS" \
PID_FILE="$TMPDIR/relay_dispatch.pid" \
LOG_FILE="$TMPDIR/relay_dispatch.log" \
MINI_BIN="$FAKE_MINI" \
"$ROOT/scripts/daemon_ctl.sh" health

PATH="$FAKE_BIN:$PATH" \
LOCALMANUS_ROOT="$FAKE_LOCALMANUS" \
PID_FILE="$TMPDIR/relay_dispatch.pid" \
LOG_FILE="$TMPDIR/relay_dispatch.log" \
MINI_BIN="$FAKE_MINI" \
"$ROOT/scripts/daemon_ctl.sh" restart

PATH="$FAKE_BIN:$PATH" \
LOCALMANUS_ROOT="$FAKE_LOCALMANUS" \
PID_FILE="$TMPDIR/relay_dispatch.pid" \
LOG_FILE="$TMPDIR/relay_dispatch.log" \
MINI_BIN="$FAKE_MINI" \
"$ROOT/scripts/daemon_ctl.sh" stop

[[ ! -f "$TMPDIR/relay_dispatch.pid" ]]

echo "test_daemon_ctl.sh: PASS"
