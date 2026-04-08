#!/usr/bin/env bash
set -euo pipefail

JUSTAI_ROOT="${JUSTAI_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
JUSTAI_LOCALMANUS_ROOT="${JUSTAI_LOCALMANUS_ROOT:-$JUSTAI_ROOT/LocalManus}"
JUSTAI_RELAY_ROOT="${JUSTAI_RELAY_ROOT:-$JUSTAI_ROOT/relay-room}"

export JUSTAI_ROOT JUSTAI_LOCALMANUS_ROOT JUSTAI_RELAY_ROOT
export LOCALMANUS_ROOT="$JUSTAI_LOCALMANUS_ROOT"
export RELAY_ROOT="$JUSTAI_RELAY_ROOT"
export PATH="${JUSTAI_PATH:-$HOME/.local/bin:$HOME/.openfang/bin:$HOME/.cargo/bin:$PATH}"

printf '[JustAi] root=%s\n' "$JUSTAI_ROOT"

if [[ -x "$JUSTAI_LOCALMANUS_ROOT/tools/ml_cli.py" ]]; then
  python3 "$JUSTAI_LOCALMANUS_ROOT/tools/ml_cli.py" status || true
fi

if [[ -x "$JUSTAI_RELAY_ROOT/scripts/daemon_ctl.sh" ]]; then
  (cd "$JUSTAI_RELAY_ROOT" && bash scripts/daemon_ctl.sh status --with-bots --with-codex) || true
  printf '\n'
  (cd "$JUSTAI_RELAY_ROOT" && bash scripts/daemon_ctl.sh health) || true
fi

printf '\n[JustAi] health check complete\n'
