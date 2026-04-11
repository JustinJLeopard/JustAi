#!/usr/bin/env bash
set -euo pipefail

JUSTAI_ROOT="${JUSTAI_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
JUSTAI_LOCALMANUS_ROOT="${JUSTAI_LOCALMANUS_ROOT:-$JUSTAI_ROOT/LocalManus}"
JUSTAI_RELAY_ROOT="${JUSTAI_RELAY_ROOT:-$JUSTAI_ROOT/relay-room}"
JUSTAI_RUNTIME_ROOT="${JUSTAI_RUNTIME_ROOT:-/tmp/justai}"
JUSTAI_RELAY_DISPATCH_PID_FILE="${JUSTAI_RELAY_DISPATCH_PID_FILE:-$JUSTAI_RUNTIME_ROOT/relay_dispatch.pid}"
JUSTAI_RELAY_DISPATCH_LOG_FILE="${JUSTAI_RELAY_DISPATCH_LOG_FILE:-$JUSTAI_RUNTIME_ROOT/relay_dispatch.log}"
JUSTAI_RELAY_HEALTH_PID_FILE="${JUSTAI_RELAY_HEALTH_PID_FILE:-$JUSTAI_RUNTIME_ROOT/relay_health_server.pid}"
JUSTAI_RELAY_HEALTH_LOG_FILE="${JUSTAI_RELAY_HEALTH_LOG_FILE:-$JUSTAI_RUNTIME_ROOT/relay_health_server.log}"
JUSTAI_RELAY_WEB_PID_FILE="${JUSTAI_RELAY_WEB_PID_FILE:-$JUSTAI_RUNTIME_ROOT/relay_web.pid}"
JUSTAI_RELAY_WEB_LOG_FILE="${JUSTAI_RELAY_WEB_LOG_FILE:-$JUSTAI_RUNTIME_ROOT/relay_web.log}"
JUSTAI_RELAY_BOT_PID_DIR="${JUSTAI_RELAY_BOT_PID_DIR:-$JUSTAI_RUNTIME_ROOT/bots}"
JUSTAI_RELAY_BOT_LOG_DIR="${JUSTAI_RELAY_BOT_LOG_DIR:-$JUSTAI_RUNTIME_ROOT/bots}"

MODE="all"
WITH_BOTS=1
WITH_CODEX=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --status-only) MODE="status"; shift ;;
    --health-only) MODE="health"; shift ;;
    --all) MODE="all"; shift ;;
    --with-bots) WITH_BOTS=1; shift ;;
    --with-codex) WITH_CODEX=1; shift ;;
    -h|--help)
      cat <<'USAGE'
Usage: check_justai.sh [--status-only|--health-only|--all] [--with-bots] [--with-codex]

  --status-only   Show process/runtime status only
  --health-only   Show service health only
  --all          Show both status and health (default)
  --with-bots    Include relay bot status in the status view
  --with-codex   Include codex bot status in the status view
USAGE
      exit 0
      ;;
    *)
      printf '[JustAi] unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

export JUSTAI_ROOT JUSTAI_LOCALMANUS_ROOT JUSTAI_RELAY_ROOT
export JUSTAI_RUNTIME_ROOT JUSTAI_RELAY_DISPATCH_PID_FILE JUSTAI_RELAY_DISPATCH_LOG_FILE JUSTAI_RELAY_HEALTH_PID_FILE JUSTAI_RELAY_HEALTH_LOG_FILE JUSTAI_RELAY_WEB_PID_FILE JUSTAI_RELAY_WEB_LOG_FILE JUSTAI_RELAY_BOT_PID_DIR JUSTAI_RELAY_BOT_LOG_DIR
export LOCALMANUS_ROOT="$JUSTAI_LOCALMANUS_ROOT"
export RELAY_ROOT="$JUSTAI_RELAY_ROOT"
export PATH="${JUSTAI_PATH:-$HOME/.local/bin:$HOME/.openfang/bin:$HOME/.cargo/bin:$PATH}"

printf '[JustAi] root=%s\n' "$JUSTAI_ROOT"

if [[ "$MODE" != "health" ]] && [[ -x "$JUSTAI_LOCALMANUS_ROOT/tools/ml_cli.py" ]]; then
  python3 "$JUSTAI_LOCALMANUS_ROOT/tools/ml_cli.py" status || true
fi

if [[ -x "$JUSTAI_RELAY_ROOT/scripts/daemon_ctl.sh" ]]; then
  if [[ "$MODE" != "health" ]]; then
    status_args=(status)
    if [[ "$WITH_BOTS" -eq 1 ]]; then
      status_args+=(--with-bots)
      if [[ "$WITH_CODEX" -eq 1 ]]; then
        status_args+=(--with-codex)
      fi
    fi
    (cd "$JUSTAI_RELAY_ROOT" && bash scripts/daemon_ctl.sh "${status_args[@]}") || true
  fi
  if [[ "$MODE" != "status" ]]; then
    printf '\n'
    (cd "$JUSTAI_RELAY_ROOT" && bash scripts/daemon_ctl.sh health) || true
  fi
fi

case "$MODE" in
  status) printf '\n[JustAi] status check complete\n' ;;
  health) printf '\n[JustAi] health check complete\n' ;;
  *) printf '\n[JustAi] health check complete\n' ;;
esac
