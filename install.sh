#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# JustAi Installer
# ──────────────────────────────────────────────────────────────────────────────
# Single-command setup for Ubuntu 24.04 / WSL2.
#
# Usage:
#   bash install.sh              # full install
#   bash install.sh --check      # preflight only (no changes)
#   bash install.sh --skip-npm   # skip npm global installs
#
# What it does:
#   1. Preflight checks (Python 3.12+, Node 20+, npm, pip, spacetime CLI)
#   2. pip install requirements (litellm, langfuse, etc.)
#   3. npm install for dashboard
#   4. Create .env from .env.example if missing
#   5. Validate SpacetimeDB is reachable
#   6. Run pytest to verify everything works
#
# What it does NOT do:
#   - Install system packages (you need Python, Node, npm already)
#   - Install SpacetimeDB (follow https://spacetimedb.com/install)
#   - Install claude-flow (npm i -g @claude-flow/cli)
#   - Configure API keys (edit .env after install)
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

JUSTAI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
ERRORS=0
CHECK_ONLY=0
SKIP_NPM=0

for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --skip-npm) SKIP_NPM=1 ;;
  esac
done

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; ERRORS=$((ERRORS + 1)); }

# ── Preflight ────────────────────────────────────────────────────────────────
echo ""
echo "JustAi Installer"
echo "═══════════════════════════════════════════"
echo ""
echo "[1/6] Preflight checks..."

# Python
if command -v python3 &>/dev/null; then
  PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
  PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
  if [[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 12 ]]; then
    ok "Python $PY_VER"
  else
    fail "Python $PY_VER (need 3.12+)"
  fi
else
  fail "python3 not found"
fi

# Node
if command -v node &>/dev/null; then
  NODE_VER=$(node -v | sed 's/v//')
  NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
  if [[ "$NODE_MAJOR" -ge 20 ]]; then
    ok "Node $NODE_VER"
  else
    fail "Node $NODE_VER (need 20+)"
  fi
else
  fail "node not found"
fi

# npm
if command -v npm &>/dev/null; then
  ok "npm $(npm -v)"
else
  fail "npm not found"
fi

# pip
if python3 -m pip --version &>/dev/null 2>&1; then
  ok "pip available"
else
  fail "pip not available (python3 -m pip)"
fi

# SpacetimeDB CLI
if command -v spacetime &>/dev/null; then
  ok "spacetime CLI found"
else
  warn "spacetime CLI not found (optional — needed for relay task system)"
fi

# relay CLI
if command -v relay &>/dev/null || [[ -f "$HOME/.local/bin/relay" ]]; then
  ok "relay CLI found"
else
  warn "relay CLI not found (optional — needed for task delegation)"
fi

# claude-flow
if command -v claude-flow &>/dev/null; then
  ok "claude-flow CLI found"
else
  warn "claude-flow not found (optional — install with: npm i -g @claude-flow/cli)"
fi

echo ""
if [[ $ERRORS -gt 0 ]]; then
  echo -e "${RED}$ERRORS required check(s) failed.${NC} Fix the issues above and retry."
  exit 1
fi

if [[ $CHECK_ONLY -eq 1 ]]; then
  echo -e "${GREEN}All preflight checks passed.${NC}"
  exit 0
fi

# ── Python Dependencies ─────────────────────────────────────────────────────
echo "[2/6] Installing Python dependencies..."

if [[ -f "$JUSTAI_ROOT/requirements.txt" ]]; then
  python3 -m pip install --quiet --break-system-packages -r "$JUSTAI_ROOT/requirements.txt" 2>/dev/null \
    || python3 -m pip install --quiet -r "$JUSTAI_ROOT/requirements.txt"
  ok "Python packages installed"
else
  warn "requirements.txt not found, skipping"
fi

# ── Dashboard Dependencies ───────────────────────────────────────────────────
echo "[3/6] Installing dashboard dependencies..."

if [[ $SKIP_NPM -eq 0 && -f "$JUSTAI_ROOT/dashboard/package.json" ]]; then
  (cd "$JUSTAI_ROOT/dashboard" && npm install --silent 2>/dev/null)
  ok "Dashboard npm packages installed"
else
  warn "Skipped dashboard npm install"
fi

# ── Environment File ─────────────────────────────────────────────────────────
echo "[4/6] Checking environment file..."

if [[ -f "$JUSTAI_ROOT/.env" ]]; then
  ok ".env exists"
else
  if [[ -f "$JUSTAI_ROOT/.env.example" ]]; then
    cp "$JUSTAI_ROOT/.env.example" "$JUSTAI_ROOT/.env"
    ok ".env created from .env.example — edit it with your API keys"
  else
    warn "No .env or .env.example found"
  fi
fi

# ── SpacetimeDB Check ────────────────────────────────────────────────────────
echo "[5/6] Checking SpacetimeDB..."

if curl -s --max-time 3 http://localhost:3000/database/sql/relay-room-dev -X POST \
     -H 'Content-Type: application/json' \
     -d '{"query":"SELECT 1"}' &>/dev/null; then
  ok "SpacetimeDB reachable at :3000"
else
  warn "SpacetimeDB not reachable at :3000 (start it before running tasks)"
fi

# ── Tests ────────────────────────────────────────────────────────────────────
echo "[6/6] Running tests..."

if (cd "$JUSTAI_ROOT" && python3 -m pytest tests/ -q --tb=short 2>&1); then
  ok "All tests passed"
else
  fail "Some tests failed — check output above"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
if [[ $ERRORS -gt 0 ]]; then
  echo -e "${RED}Install completed with $ERRORS error(s).${NC}"
  exit 1
else
  echo -e "${GREEN}JustAi installed successfully.${NC}"
  echo ""
  echo "Next steps:"
  echo "  1. Edit .env with your API keys"
  echo "  2. Start services:  source ~/.ruv_env && ~/ruv_start.sh"
  echo "  3. Run a task:      python3 -m justai.orchestrator \"your goal\""
  echo "  4. Open dashboard:  cd dashboard && npm run dev"
  echo ""
fi
