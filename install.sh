#!/usr/bin/env bash
set -euo pipefail

JUSTAI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_ONLY=0
SKIP_NPM=0

for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --skip-npm) SKIP_NPM=1 ;;
    -h|--help)
      cat <<'USAGE'
Usage: bash install.sh [--check] [--skip-npm]

  --check      preflight only
  --skip-npm   skip dashboard npm install
USAGE
      exit 0
      ;;
  esac
done

echo "JustAi Installer"
echo "================"

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'
echo "  ok Python 3.12+"

python3 -m pip --version >/dev/null
echo "  ok pip"

if command -v node >/dev/null 2>&1; then
  echo "  ok node $(node -v)"
else
  echo "  warn node not found; dashboard install will be skipped"
  SKIP_NPM=1
fi

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  echo "Preflight checks passed."
  exit 0
fi

python3 -m pip install -e "$JUSTAI_ROOT"
echo "  ok editable Python install"

if [[ "$SKIP_NPM" -eq 0 && -f "$JUSTAI_ROOT/dashboard/package.json" ]]; then
  (cd "$JUSTAI_ROOT/dashboard" && npm install)
  echo "  ok dashboard npm install"
fi

if [[ ! -f "$JUSTAI_ROOT/.env" && -f "$JUSTAI_ROOT/.env.example" ]]; then
  cp "$JUSTAI_ROOT/.env.example" "$JUSTAI_ROOT/.env"
  echo "  ok created .env from .env.example"
fi

(cd "$JUSTAI_ROOT" && python3 -m pytest tests/ -q --tb=short)
echo "JustAi installed successfully."
