#!/usr/bin/env bash
set -euo pipefail

JUSTAI_ROOT="${JUSTAI_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
JUSTAI_RUNTIME_ROOT="${JUSTAI_RUNTIME_ROOT:-/tmp/justai}"
JUSTAI_API_PID_FILE="${JUSTAI_API_PID_FILE:-$JUSTAI_RUNTIME_ROOT/api.pid}"
JUSTAI_API_LOG_FILE="${JUSTAI_API_LOG_FILE:-$JUSTAI_RUNTIME_ROOT/api.log}"

MODE="all"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --status-only) MODE="status"; shift ;;
    --health-only) MODE="health"; shift ;;
    --all) MODE="all"; shift ;;
    -h|--help)
      cat <<'USAGE'
Usage: check_justai.sh [--status-only|--health-only|--all]

  --status-only   Show process/runtime status only
  --health-only   Show service health only
  --all           Show both status and health (default)
USAGE
      exit 0
      ;;
    *)
      printf '[JustAi] unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

export JUSTAI_ROOT JUSTAI_RUNTIME_ROOT JUSTAI_API_PID_FILE JUSTAI_API_LOG_FILE

printf '[JustAi] root=%s\n' "$JUSTAI_ROOT"

if [[ "$MODE" != "health" ]]; then
  if [[ -f "$JUSTAI_API_PID_FILE" ]] && kill -0 "$(cat "$JUSTAI_API_PID_FILE")" 2>/dev/null; then
    printf '[JustAi] api=running pid=%s log=%s\n' "$(cat "$JUSTAI_API_PID_FILE")" "$JUSTAI_API_LOG_FILE"
  else
    printf '[JustAi] api=stopped\n'
  fi
fi

if [[ "$MODE" != "status" ]]; then
  printf '\n'
  (cd "$JUSTAI_ROOT" && python3 -m justai status) || true
fi

printf '\n[JustAi] check complete\n'
