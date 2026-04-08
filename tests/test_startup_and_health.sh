#!/usr/bin/env bash
set -euo pipefail

ROOT="${JUSTAI_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

test -x "$ROOT/scripts/start_justai.sh"
test -x "$ROOT/scripts/check_justai.sh"
test -f "$ROOT/.env.example"

printf 'startup scripts present\n'
