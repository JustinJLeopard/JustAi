#!/usr/bin/env bash
# codex-delegate — ManusLocal Codex CLI delegation wrapper
# ============================================================
# Called by mini-swe-agent when a task requires code writing.
# mini issues: codex-delegate "write a pygame leapfrog game" ~/projects/mygame
#
# Usage:
#   codex-delegate "task description" [working_dir]
#   codex-delegate --file task.txt [working_dir]
#
# Output: prints what Codex did (for mini to read as observation)
# Exit 0: success, Exit 1: failure
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
MEMORY_SCRIPT="$PROJECT_DIR/memory/honcho_memory.py"

# Load .env
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a; source "$PROJECT_DIR/.env"; set +a
fi

# ── Parse args ──────────────────────────────────────────────────────────────
TASK=""
WORK_DIR=""
TASK_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --file) TASK_FILE="$2"; shift 2 ;;
        --dir)  WORK_DIR="$2"; shift 2 ;;
        -*)     echo "Unknown flag: $1" >&2; exit 1 ;;
        *)
            if [[ -z "$TASK" ]]; then
                TASK="$1"
            elif [[ -z "$WORK_DIR" ]]; then
                WORK_DIR="$1"
            fi
            shift
            ;;
    esac
done

if [[ -n "$TASK_FILE" ]] && [[ -f "$TASK_FILE" ]]; then
    TASK=$(cat "$TASK_FILE")
fi

if [[ -z "$TASK" ]]; then
    echo "Usage: codex-delegate \"task description\" [working_dir]" >&2
    exit 1
fi

# Default working dir to current directory
WORK_DIR="${WORK_DIR:-$(pwd)}"
mkdir -p "$WORK_DIR"

# ── Set up Codex API to use gameron.me ──────────────────────────────────────
# Override OPENAI_API_KEY and OPENAI_BASE_URL to route through gameron.me
# gpt-5.4 is the default model for codex delegation (broader reasoning)
export OPENAI_API_KEY="${GAMERON_API_KEY:-$OPENAI_API_KEY}"
export OPENAI_BASE_URL="https://api.gameron.me/v1"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="$LOG_DIR/codex_delegate_${TIMESTAMP}.log"
mkdir -p "$LOG_DIR"

echo "═══════════════════════════════════════════════"
echo "  codex-delegate — delegating to Codex CLI"
echo "  Task: ${TASK:0:80}..."
echo "  Dir:  $WORK_DIR"
echo "  Model: gpt-5.4 via gameron.me"
echo "═══════════════════════════════════════════════"

# ── Build the full prompt for Codex ─────────────────────────────────────────
# Inject Honcho context if available
HONCHO_CONTEXT=""
if [[ -f "$MEMORY_SCRIPT" ]]; then
    HONCHO_CONTEXT=$(python3 "$MEMORY_SCRIPT" --pre-task --task "$TASK" 2>/dev/null || true)
fi

FULL_PROMPT="$TASK"
if [[ -n "$HONCHO_CONTEXT" ]]; then
    FULL_PROMPT="${HONCHO_CONTEXT}

TASK: ${TASK}"
fi

# ── Run Codex in full-auto mode ──────────────────────────────────────────────
# --full-auto: no confirmation prompts, runs all commands automatically
# --quiet: minimal output noise
# --model: use gpt-5.4 for codex delegation
cd "$WORK_DIR"

EXIT_CODE=0
codex \
    --model "gpt-5.4" \
    --full-auto \
    --quiet \
    "$FULL_PROMPT" \
    2>&1 | tee "$LOG_FILE" || EXIT_CODE=$?

echo ""
echo "═══════════════════════════════════════════════"
if [[ $EXIT_CODE -eq 0 ]]; then
    echo "  Codex completed successfully."
    echo "  Log: $LOG_FILE"
    # Store in Honcho
    if [[ -f "$MEMORY_SCRIPT" ]]; then
        python3 "$MEMORY_SCRIPT" --post-task \
            --task "Codex delegation: $TASK" \
            2>/dev/null || true
    fi
else
    echo "  Codex exited with code $EXIT_CODE"
    echo "  Check log: $LOG_FILE"
fi
echo "═══════════════════════════════════════════════"

exit $EXIT_CODE
