#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JUSTAI_ROOT="$(cd "$ROOT/.." && pwd)"
TMPDIR="$(mktemp -d)"
FAKE_BIN="$TMPDIR/bin"
ENV_PATH="$JUSTAI_ROOT/LocalManus/.env"
ENV_DIR="$(dirname "$ENV_PATH")"
BACKUP_ENV="$TMPDIR/original_localmanus.env"
HAD_ENV=0
PID3000=""
PID4000=""

cleanup() {
  if [[ -n "$PID3000" ]]; then kill "$PID3000" 2>/dev/null || true; fi
  if [[ -n "$PID4000" ]]; then kill "$PID4000" 2>/dev/null || true; fi

  if [[ "$HAD_ENV" -eq 1 ]]; then
    cp "$BACKUP_ENV" "$ENV_PATH"
  else
    rm -f "$ENV_PATH"
  fi

  rm -rf "$TMPDIR"
}
trap cleanup EXIT

mkdir -p "$FAKE_BIN" "$ENV_DIR"

if [[ -f "$ENV_PATH" ]]; then
  HAD_ENV=1
  cp "$ENV_PATH" "$BACKUP_ENV"
fi

cat > "$ENV_PATH" <<'ENVEOF'
GAMERON_API_KEY=fake-gameron-key
LITELLM_API_KEY=fake-litellm-key
ENVEOF

cat > "$FAKE_BIN/mini" <<'EOF_MINI'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--help" ]]; then
  echo "Usage: mini [options]"
  exit 0
fi
echo "mini fake ok"
EOF_MINI

cat > "$FAKE_BIN/relay" <<'EOF_RELAY'
#!/usr/bin/env bash
set -euo pipefail
echo "relay fake"
EOF_RELAY

cat > "$FAKE_BIN/pgrep" <<'EOF_PGREP'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-f" ]] && [[ "${2:-}" == "relay_dispatch.sh --daemon" ]]; then
  echo "12345"
  exit 0
fi
exit 1
EOF_PGREP

cat > "$FAKE_BIN/curl" <<'EOF_CURL'
#!/usr/bin/env bash
set -euo pipefail

url=""
for arg in "$@"; do
  case "$arg" in
    http://*) url="$arg" ;;
  esac
done

if [[ "$*" == *"%{http_code}"* ]]; then
  case "$url" in
    http://localhost:50051/api/agents|http://localhost:4000/v1/models)
      printf '200'
      ;;
    *)
      printf '404'
      ;;
  esac
  exit 0
fi

if [[ "$url" == "http://localhost:4000/v1/models" ]]; then
  printf '{"data":[{"id":"gpt-5.4"},{"id":"gpt-5.3-codex"},{"id":"claude-opus-4-6"}]}'
  exit 0
fi

printf '{}'
EOF_CURL

chmod +x "$FAKE_BIN/mini" "$FAKE_BIN/relay" "$FAKE_BIN/pgrep" "$FAKE_BIN/curl"

python3 -m http.server 3000 --bind 127.0.0.1 --directory "$TMPDIR" >"$TMPDIR/http3000.log" 2>&1 &
PID3000=$!
python3 -m http.server 4000 --bind 127.0.0.1 --directory "$TMPDIR" >"$TMPDIR/http4000.log" 2>&1 &
PID4000=$!
sleep 1

set +e
PATH="$FAKE_BIN:/usr/bin:/bin" HOME="/home/justinleopard" JUSTAI_ROOT="$JUSTAI_ROOT" JUSTAI_LOCALMANUS_ROOT="$JUSTAI_ROOT/LocalManus" /usr/bin/bash "$ROOT/scripts/preflight_check.sh" >"$TMPDIR/pass.out" 2>&1
rc=$?
set -e
test "$rc" -eq 0

set +e
PATH="$FAKE_BIN:/usr/bin:/bin" HOME="/home/justinleopard" JUSTAI_ROOT="$JUSTAI_ROOT" JUSTAI_LOCALMANUS_ROOT="$JUSTAI_ROOT/LocalManus" /usr/bin/bash "$ROOT/scripts/preflight_check.sh" --json >"$TMPDIR/json.out" 2>&1
rc=$?
set -e
test "$rc" -eq 0
python3 - "$TMPDIR/json.out" <<'PYEOF'
import json, sys
p = sys.argv[1]
with open(p, "r", encoding="utf-8") as f:
    d = json.load(f)
required = {"timestamp", "passed", "failed", "total", "status", "checks"}
missing = sorted(required - set(d.keys()))
if missing:
    raise SystemExit(f"Missing JSON keys: {missing}")
if not isinstance(d["checks"], list):
    raise SystemExit("checks must be a list")
PYEOF

set +e
PATH="$FAKE_BIN:/usr/bin:/bin" HOME="/home/justinleopard" JUSTAI_ROOT="$JUSTAI_ROOT" JUSTAI_LOCALMANUS_ROOT="$JUSTAI_ROOT/LocalManus" /usr/bin/bash "$ROOT/scripts/preflight_check.sh" --verbose >"$TMPDIR/verbose.out" 2>&1
rc=$?
set -e
test "$rc" -eq 0
grep -q "PASS" "$TMPDIR/verbose.out"

cat > "$FAKE_BIN/mini" <<'EOF_BAD_MINI'
#!/usr/bin/env bash
set -euo pipefail
exit 1
EOF_BAD_MINI
chmod +x "$FAKE_BIN/mini"
set +e
PATH="$FAKE_BIN:/usr/bin:/bin" HOME="/home/justinleopard" JUSTAI_ROOT="$JUSTAI_ROOT" JUSTAI_LOCALMANUS_ROOT="$JUSTAI_ROOT/LocalManus" /usr/bin/bash "$ROOT/scripts/preflight_check.sh" --verbose >"$TMPDIR/fail.out" 2>&1
rc=$?
set -e
test "$rc" -eq 1
grep -q "FAIL" "$TMPDIR/fail.out"

! grep -q "sk-litellm" "$ROOT/scripts/preflight_check.sh"
! grep -Ev '^[[:space:]]*#' "$ROOT/scripts/preflight_check.sh" | grep -Eq '\beval\b'
