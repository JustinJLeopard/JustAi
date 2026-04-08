#!/usr/bin/env bash
# =============================================================================
# ManusLocal — Dependency Installation Script
# Installs all required Python packages and tools.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log() { echo -e "${GREEN}[install]${NC} $1"; }
warn() { echo -e "${YELLOW}[warn]${NC} $1"; }

log "Installing ManusLocal Python dependencies..."

# Core Python packages
pip install --quiet \
    honcho-ai \
    requests \
    rich \
    typer \
    python-dotenv \
    httpx \
    pydantic \
    litellm \
    openai \
    anthropic \
    python-telegram-bot \
    schedule \
    watchdog \
    psutil

log "Core Python packages installed."

# Install mini-swe-agent if not already installed
MINI_PATH="${MINI_SWE_PATH:-$HOME/mini-swe-agent}"
if [[ -d "$MINI_PATH" ]]; then
    log "Installing mini-swe-agent from $MINI_PATH..."
    pip install --quiet -e "$MINI_PATH" || warn "mini-swe-agent install failed — check $MINI_PATH"
else
    warn "mini-swe-agent not found at $MINI_PATH. Skipping."
    warn "Clone it: git clone https://github.com/justinleopard/mini-swe-agent $MINI_PATH"
fi

# Install OpenFang if not present
if ! command -v openfang &>/dev/null; then
    log "Installing OpenFang..."
    curl -fsSL https://openfang.sh/install | sh || warn "OpenFang install failed. Try manually: curl -fsSL https://openfang.sh/install | sh"
else
    log "OpenFang already installed: $(openfang --version 2>/dev/null || echo 'version unknown')"
fi

# Set up ManusLocal CLI as a command
log "Setting up 'ml' CLI command..."
ML_CLI="$PROJECT_DIR/tools/ml_cli.py"
if [[ -f "$ML_CLI" ]]; then
    # Create a wrapper script in ~/.local/bin
    mkdir -p "$HOME/.local/bin"
    cat > "$HOME/.local/bin/ml" << MLEOF
#!/usr/bin/env bash
python3 "$ML_CLI" "\$@"
MLEOF
    chmod +x "$HOME/.local/bin/ml"
    log "'ml' command installed at ~/.local/bin/ml"
    
    # Also add to PATH if not already there
    if ! grep -q 'HOME/.local/bin' "$HOME/.bashrc" 2>/dev/null; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        log "Added ~/.local/bin to PATH in .bashrc"
    fi
else
    warn "ml_cli.py not found at $ML_CLI"
fi

# Initialize Honcho workspaces
log "Initializing Honcho memory workspaces..."
python3 "$PROJECT_DIR/memory/honcho_setup.py" --init 2>/dev/null || warn "Honcho init failed — check HONCHO_API_KEY in .env"

log ""
log "Installation complete!"
log "Run: source ~/.bashrc && bash scripts/start_manuslocal.sh"
