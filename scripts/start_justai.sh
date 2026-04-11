#!/usr/bin/env bash
set -euo pipefail

JUSTAI_ROOT="${JUSTAI_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
JUSTAI_LOCALMANUS_ROOT="${JUSTAI_LOCALMANUS_ROOT:-$JUSTAI_ROOT/LocalManus}"
JUSTAI_RELAY_ROOT="${JUSTAI_RELAY_ROOT:-$JUSTAI_ROOT/relay-room}"
JUSTAI_RELAY_SERVER="${JUSTAI_RELAY_SERVER:-local-server}"
JUSTAI_SPACETIME_SESSION="${JUSTAI_SPACETIME_SESSION:-spacetime}"
JUSTAI_PATH="${JUSTAI_PATH:-$HOME/.local/bin:$HOME/.openfang/bin:$HOME/.cargo/bin:$PATH}"
JUSTAI_RUNTIME_ROOT="${JUSTAI_RUNTIME_ROOT:-/tmp/justai}"
JUSTAI_RELAY_DISPATCH_PID_FILE="${JUSTAI_RELAY_DISPATCH_PID_FILE:-$JUSTAI_RUNTIME_ROOT/relay_dispatch.pid}"
JUSTAI_RELAY_DISPATCH_LOG_FILE="${JUSTAI_RELAY_DISPATCH_LOG_FILE:-$JUSTAI_RUNTIME_ROOT/relay_dispatch.log}"
JUSTAI_RELAY_HEALTH_PID_FILE="${JUSTAI_RELAY_HEALTH_PID_FILE:-$JUSTAI_RUNTIME_ROOT/relay_health_server.pid}"
JUSTAI_RELAY_HEALTH_LOG_FILE="${JUSTAI_RELAY_HEALTH_LOG_FILE:-$JUSTAI_RUNTIME_ROOT/relay_health_server.log}"
JUSTAI_RELAY_WEB_PID_FILE="${JUSTAI_RELAY_WEB_PID_FILE:-$JUSTAI_RUNTIME_ROOT/relay_web.pid}"
JUSTAI_RELAY_WEB_LOG_FILE="${JUSTAI_RELAY_WEB_LOG_FILE:-$JUSTAI_RUNTIME_ROOT/relay_web.log}"
JUSTAI_RELAY_BOT_PID_DIR="${JUSTAI_RELAY_BOT_PID_DIR:-$JUSTAI_RUNTIME_ROOT/bots}"
JUSTAI_RELAY_BOT_LOG_DIR="${JUSTAI_RELAY_BOT_LOG_DIR:-$JUSTAI_RUNTIME_ROOT/bots}"

NO_BOTS=0
NO_CODEX=0
FORCE_BOOTSTRAP=0
SKIP_RELAY_BOOTSTRAP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-bots) NO_BOTS=1; shift ;;
    --no-codex) NO_CODEX=1; shift ;;
    --force-bootstrap) FORCE_BOOTSTRAP=1; shift ;;
    --skip-relay-bootstrap) SKIP_RELAY_BOOTSTRAP=1; shift ;;
    -h|--help)
      cat <<'USAGE'
Usage: start_justai.sh [--no-bots] [--no-codex] [--force-bootstrap] [--skip-relay-bootstrap]

  --no-bots             Start relay-room without Discord bots or watchdog
  --no-codex            Start bots but leave codex out
  --force-bootstrap     Force relay-room bootstrap even if a target exists
  --skip-relay-bootstrap  Skip relay-room bootstrap entirely
USAGE
      exit 0
      ;;
    *)
      printf '[JustAi] unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

export JUSTAI_ROOT JUSTAI_LOCALMANUS_ROOT JUSTAI_RELAY_ROOT JUSTAI_RELAY_SERVER JUSTAI_SPACETIME_SESSION JUSTAI_RUNTIME_ROOT
export JUSTAI_RELAY_DISPATCH_PID_FILE JUSTAI_RELAY_DISPATCH_LOG_FILE JUSTAI_RELAY_HEALTH_PID_FILE JUSTAI_RELAY_HEALTH_LOG_FILE JUSTAI_RELAY_WEB_PID_FILE JUSTAI_RELAY_WEB_LOG_FILE JUSTAI_RELAY_BOT_PID_DIR JUSTAI_RELAY_BOT_LOG_DIR
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

should_bootstrap_relay() {
  local target_file="$JUSTAI_RELAY_ROOT/.relay-db-target"
  if [[ "$SKIP_RELAY_BOOTSTRAP" -eq 1 ]]; then
    info 'Skipping relay-room bootstrap (--skip-relay-bootstrap)'
    return 1
  fi

  if [[ "$FORCE_BOOTSTRAP" -eq 1 ]]; then
    info 'Forcing relay-room bootstrap (--force-bootstrap)'
    return 0
  fi

  if [[ -f "$target_file" ]] && command -v relay >/dev/null 2>&1; then
    info "Skipping relay-room bootstrap; target already exists at $target_file"
    return 1
  fi

  return 0
}

start_relay_daemon() {
  local daemon_args=(restart)
  if [[ "$NO_BOTS" -eq 1 ]]; then
    info 'Starting relay daemon without bots'
  else
    daemon_args+=(--with-bots)
    if [[ "$NO_CODEX" -eq 1 ]]; then
      daemon_args+=(--no-codex)
      info 'Starting relay daemon with bots except codex'
    else
      daemon_args+=(--with-codex)
      info 'Starting relay daemon with bots and codex'
    fi
  fi

  (
    cd "$JUSTAI_RELAY_ROOT"
    bash scripts/daemon_ctl.sh "${daemon_args[@]}"
  )
}

main() {
  ensure_spacetime
  start_localmanus
  if should_bootstrap_relay; then
    bootstrap_relay
  fi
  start_relay_daemon
  info 'JustAi startup complete'
}

main "$@"
