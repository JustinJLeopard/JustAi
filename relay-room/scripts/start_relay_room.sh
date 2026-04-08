#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELAY_DB_REQUESTED="${RELAY_DB_NAME:-relay-room-dev}"
RELAY_SERVER="${RELAY_SERVER:-local-server}"
TARGET_FILE="$ROOT/.relay-db-target"

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

if [ -f "$HOME/.cargo/env" ]; then
  # Ensure rustup-managed targets are visible in non-interactive shells.
  . "$HOME/.cargo/env"
fi

require spacetime
require cargo

cd "$ROOT"

resolve_existing_target() {
  if [ -n "${RELAY_DB_NAME:-}" ] && spacetime sql --no-config "$RELAY_DB_NAME" "select * from agents" --server "$RELAY_SERVER" --anonymous -y >/dev/null 2>&1; then
    printf '%s\n' "$RELAY_DB_NAME"
    return 0
  fi

  if [ -f "$TARGET_FILE" ]; then
    local saved_target
    saved_target="$(head -n 1 "$TARGET_FILE")"
    if [ -n "$saved_target" ] && spacetime sql --no-config "$saved_target" "select * from agents" --server "$RELAY_SERVER" --anonymous -y >/dev/null 2>&1; then
      printf '%s\n' "$saved_target"
      return 0
    fi
  fi

  if spacetime sql --no-config "$RELAY_DB_REQUESTED" "select * from agents" --server "$RELAY_SERVER" --anonymous -y >/dev/null 2>&1; then
    printf '%s\n' "$RELAY_DB_REQUESTED"
    return 0
  fi

  return 1
}

echo "[1/4] Building Relay Room module"
spacetime build --module-path spacetimedb

RELAY_DB_TARGET=""
if RELAY_DB_TARGET="$(resolve_existing_target)"; then
  echo "[2/4] Using existing database target: $RELAY_DB_TARGET"
else
  echo "[2/4] Publishing new local database: $RELAY_DB_REQUESTED"
  publish_output="$(spacetime publish --no-config --server "$RELAY_SERVER" --anonymous --module-path "$ROOT/spacetimedb" "$RELAY_DB_REQUESTED" -y 2>&1)"
  printf '%s\n' "$publish_output"
  RELAY_DB_TARGET="$(printf '%s\n' "$publish_output" | sed -n 's/.*identity: \([a-f0-9]\{16,\}\).*/\1/p' | tail -n 1)"
  if [ -z "$RELAY_DB_TARGET" ]; then
    RELAY_DB_TARGET="$RELAY_DB_REQUESTED"
  fi
fi

printf '%s\n' "$RELAY_DB_TARGET" > "$TARGET_FILE"

echo "[3/4] Regenerating Rust bindings"
spacetime generate --module-path "$ROOT/spacetimedb" --lang rust --out-dir "$ROOT/client/src/module_bindings" -y

echo "[4/4] Installing relay CLI"
cargo install --path "$ROOT/client" --force --root "$HOME/.local"

cat <<EOF

Relay Room is ready.

Environment:
  export RELAY_DB_NAME=$RELAY_DB_TARGET
  export RELAY_SERVER=$RELAY_SERVER
  export PATH="$HOME/.local/bin:$PATH"

The active database target is saved in:
  $TARGET_FILE

Suggested first commands:
  relay register claude-code --caps planner,review
  relay register codex --caps execution,verification
  relay register localmanus --caps delegation,assistant
  relay board
EOF


