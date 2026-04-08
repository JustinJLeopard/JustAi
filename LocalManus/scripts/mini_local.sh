#!/usr/bin/env bash
# mini-local — ManusLocal local Qwen3 agent wrapper
# Uses qwen3:30b-a3b-q4_K_M via direct Ollama with Honcho memory integration
set -euo pipefail

# ── Load LocalManus Skills ────────────────────────────────────────────────────
if [[ -f "$HOME/skills/inject_skills_wrapper.sh" ]]; then
    source "$HOME/skills/inject_skills_wrapper.sh"
fi


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_SRC="$PROJECT_DIR/config/mini_qwen3.yaml"
CONFIG_TMP="/tmp/mini_qwen3_patched.yaml"
TRAJ_FILE="$PROJECT_DIR/logs/last_mini_run.traj.json"
HONCHO_POST_FILE="$PROJECT_DIR/logs/last_honcho_post_task.txt"
MEMORY_SCRIPT="$PROJECT_DIR/memory/honcho_memory.py"

TASK=""
EXTRA_ARGS=()

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        -t|--task) TASK="$2"; shift 2 ;;
        *)         EXTRA_ARGS+=("$1"); shift ;;
    esac
done

# Detect Windows host IP for Ollama
WINDOWS_HOST=$(ip route show default 2>/dev/null | awk '{print $3}' | head -1)
if [[ -z "$WINDOWS_HOST" ]]; then
    WINDOWS_HOST="172.31.224.1"
fi

# Verify Ollama is reachable
if ! curl -s --connect-timeout 3 "http://$WINDOWS_HOST:11434/api/tags" > /dev/null 2>&1; then
    echo "[mini-local] ERROR: Ollama not reachable at http://$WINDOWS_HOST:11434"
    echo "Start Ollama on Windows first: ollama serve"
    exit 1
fi

# Load .env
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a; source "$PROJECT_DIR/.env"; set +a
fi

# ── Step 1: Pre-task Honcho context ────────────────────────────────────────
HONCHO_CONTEXT=""
if [[ -n "$TASK" ]] && [[ -f "$MEMORY_SCRIPT" ]]; then
    HONCHO_CONTEXT=$(python3 "$MEMORY_SCRIPT" --pre-task --task "$TASK" 2>/dev/null || true)
fi

# ── Step 2: Patch config ────────────────────────────────────────────────────
python3 - <<PYEOF
import re

with open("$CONFIG_SRC") as f:
    content = f.read()

content = re.sub(r'api_base:.*', f'api_base: http://$WINDOWS_HOST:11434', content, count=1)

honcho_ctx = """$HONCHO_CONTEXT"""
if honcho_ctx.strip():
    content = content.replace(
        'You are ManusLocal',
        honcho_ctx.strip() + '\n\nYou are ManusLocal',
        1
    )

with open("$CONFIG_TMP", "w") as f:
    f.write(content)

print("Config patched OK (Ollama: $WINDOWS_HOST)")
PYEOF

# ── Step 3: Run mini ────────────────────────────────────────────────────────
mkdir -p "$PROJECT_DIR/logs"

if [[ -n "$TASK" ]]; then
    mini -c "$CONFIG_TMP" -t "$TASK" "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
    EXIT_CODE=$?
else
    mini -c "$CONFIG_TMP" "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
    EXIT_CODE=$?
fi

# ── Step 4: Post-task Honcho storage ───────────────────────────────────────
if [[ -n "$TASK" ]] && [[ -f "$MEMORY_SCRIPT" ]]; then
    POST_TASK_ARGS=(--post-task --task "$TASK" --traj "$TRAJ_FILE")
    if [[ $EXIT_CODE -ne 0 ]]; then
        POST_TASK_ARGS+=(--failed)
    fi

    HONCHO_OUTPUT=""
    if ! HONCHO_OUTPUT=$(python3 "$MEMORY_SCRIPT" "${POST_TASK_ARGS[@]}" 2>&1); then
        :
    fi

    printf '%s\n' "$HONCHO_OUTPUT" > "$HONCHO_POST_FILE"
    if [[ -n "$HONCHO_OUTPUT" ]]; then
        printf '%s\n' "$HONCHO_OUTPUT"
    fi
fi

exit $EXIT_CODE
