#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"
mkdir -p "$HOOKS_DIR"

install_hook() {
    local hook_name="$1"
    cat > "$HOOKS_DIR/$hook_name" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
make install
EOF
    chmod +x "$HOOKS_DIR/$hook_name"
}

install_hook post-merge
install_hook post-checkout

echo "Installed git hooks: post-merge, post-checkout"
