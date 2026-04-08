#!/usr/bin/env bash
set -euo pipefail

JUSTAI_ROOT="${JUSTAI_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
JUSTAI_LOCALMANUS_ROOT="${JUSTAI_LOCALMANUS_ROOT:-$JUSTAI_ROOT/LocalManus}"
JUSTAI_RELAY_ROOT="${JUSTAI_RELAY_ROOT:-$JUSTAI_ROOT/relay-room}"
JUSTAI_RELAY_SERVER="${JUSTAI_RELAY_SERVER:-local-server}"
JUSTAI_SPACETIME_SESSION="${JUSTAI_SPACETIME_SESSION:-spacetime}"
JUSTAI_PATH="${JUSTAI_PATH:-$HOME/.local/bin:$HOME/.openfang/bin:$HOME/.cargo/bin:$PATH}"

export JUSTAI_ROOT JUSTAI_LOCALMANUS_ROOT JUSTAI_RELAY_ROOT JUSTAI_RELAY_SERVER JUSTAI_SPACETIME_SESSION
export LOCALMANUS_ROOT="$JUSTAI_LOCALMANUS_ROOT"
export RELAY_ROOT="$JUSTAI_RELAY_ROOT"
export PATH="$JUSTAI_PATH"

info() { printf '[JustAi] %s\n' "$*"; }

check_port() {
  local host="$1"
  local port="$2"
  timeout 1 bash -lc ">/dev/tcp/${host}/${port}" >/dev/null 2>&1
}

ensure_spacetime() {
  if check_port 127.0.0.1 3000; then
    info 'SpacetimeDB already reachable on 127.0.0.1:3000'
    return 0
  fi

  info "Starting SpacetimeDB in tmux session ${JUSTAI_SPACETIME_SESSION}"
  if tmux has-session -t "$JUSTAI_SPACETIME_SESSION" 2>/dev/null; then
    tmux kill-session -t "$JUSTAI_SPACETIME_SESSION" 2>/dev/null || true
  fi

  tmux new-session -d -s "$JUSTAI_SPACETIME_SESSION" 'spacetime start'

  local i
  for i in $(seq 1 25); do
    if check_port 127.0.0.1 3000; then
      info 'SpacetimeDB started'
      return 0
    fi
    sleep 1
  done

  printf '[JustAi] SpacetimeDB did not come up on 127.0.0.1:3000\n' >&2
  return 1
}

start_localmanus() {
  info "Starting LocalManus from ${JUSTAI_LOCALMANUS_ROOT}"
  bash "$JUSTAI_LOCALMANUS_ROOT/scripts/start_manuslocal.sh" --background
}

bootstrap_relay() {
  info "Bootstrapping relay-room from ${JUSTAI_RELAY_ROOT}"
  (
    cd "$JUSTAI_RELAY_ROOT"
    bash scripts/start_relay_room.sh
  )
}

start_relay_daemon() {
  info 'Restarting relay daemon'
  (
    cd "$JUSTAI_RELAY_ROOT"
    bash scripts/daemon_ctl.sh restart --with-bots --with-codex
  )
}

main() {
  ensure_spacetime
  start_localmanus
  bootstrap_relay
  start_relay_daemon
  info 'JustAi startup complete'
}

main "$@"
