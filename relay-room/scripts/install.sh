#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"
cargo install --path "$ROOT/client" --force --root "$HOME/.local"

cat <<EOF
Installed relay to:
  $HOME/.local/bin/relay

Make sure this is on PATH:
  export PATH="$HOME/.local/bin:$PATH"
EOF
