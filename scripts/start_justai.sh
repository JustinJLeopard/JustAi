#!/usr/bin/env bash
set -euo pipefail

JUSTAI_ROOT="${JUSTAI_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
JUSTAI_RUNTIME_ROOT="${JUSTAI_RUNTIME_ROOT:-/tmp/justai}"
JUSTAI_API_PORT="${JUSTAI_API_PORT:-3002}"
JUSTAI_API_PID_FILE="${JUSTAI_API_PID_FILE:-$JUSTAI_RUNTIME_ROOT/api.pid}"
JUSTAI_API_LOG_FILE="${JUSTAI_API_LOG_FILE:-$JUSTAI_RUNTIME_ROOT/api.log}"

export JUSTAI_ROOT JUSTAI_RUNTIME_ROOT JUSTAI_API_PORT JUSTAI_API_PID_FILE JUSTAI_API_LOG_FILE

info() { printf '[JustAi] %s\n' "$*"; }

mkdir -p "$JUSTAI_RUNTIME_ROOT"

if [[ -f "$JUSTAI_API_PID_FILE" ]] && kill -0 "$(cat "$JUSTAI_API_PID_FILE")" 2>/dev/null; then
  info "API already running on port $JUSTAI_API_PORT"
  exit 0
fi

info "Starting JustAi API on port $JUSTAI_API_PORT"
(
  cd "$JUSTAI_ROOT"
  nohup python3 -m justai.api --port "$JUSTAI_API_PORT" >"$JUSTAI_API_LOG_FILE" 2>&1 &
  printf '%s\n' "$!" >"$JUSTAI_API_PID_FILE"
)

info "JustAi startup complete"
