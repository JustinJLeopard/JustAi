#!/usr/bin/env bash
# mini-local-cloud — ManusLocal cloud agent wrapper
# Uses claude-opus-4-6 via gameron.me with Honcho memory integration
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_SRC="$PROJECT_DIR/config/mini_cloud.yaml"
CONFIG_TMP="/tmp/mini_cloud_patched.yaml"
MEMORY_SCRIPT="$PROJECT_DIR/memory/honcho_memory.py"
export PATH="$PATH:$HOME/.local/bin:$HOME/.cargo/bin"

# Default model
MODEL="openai/claude-opus-4-6"
LM_DIR="${LOCALMANUS_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
TASK=""
TASK_INPUT=""
TASK_PREFIX="${MINI_TASK_PREFIX:-}"
WORK_CWD="${MINI_CWD:-/home/justinleopard/projects}"
HONCHO_TIMEOUT_SECONDS="${HONCHO_TIMEOUT_SECONDS:-12}"
TRAJ_FILE="${MINI_TRAJ_FILE:-$PROJECT_DIR/logs/last_mini_run.traj.json}"
HONCHO_POST_FILE="${MINI_HONCHO_POST_FILE:-$PROJECT_DIR/logs/last_honcho_post_task.txt}"
EXTRA_ARGS=()

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--model) MODEL="$2"; shift 2 ;;
        -t|--task)  TASK="$2"; shift 2 ;;
        *)          EXTRA_ARGS+=("$1"); shift ;;
    esac
done

# All models use /v1 through gameron.me (OpenAI-compatible proxy)
BASE_URL="https://api.gameron.me/v1"

echo "Model: $MODEL | Base URL: $BASE_URL"

# Load .env
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a; source "$PROJECT_DIR/.env"; set +a
fi

GAMERON_API_KEY="${GAMERON_API_KEY:-sk-user-e65550a3cd582639241fdb153dfaca4e}"

# ── Step 1: Pre-task Honcho context ────────────────────────────────────────
HONCHO_CONTEXT=""
if [[ -n "$TASK" ]] && [[ -f "$MEMORY_SCRIPT" ]]; then
    HONCHO_CONTEXT=$(timeout --foreground "${HONCHO_TIMEOUT_SECONDS}s" python3 "$MEMORY_SCRIPT" --pre-task --task "$TASK" 2>/dev/null || true)
fi

# ── Step 2: Patch config ──────────────────────────────────────────────────
# FIX: Use env vars + quoted heredoc to prevent shell expansion breaking Python.
# The old approach (unquoted <<PYEOF with """$HONCHO_CONTEXT""") broke when
# Honcho returned text containing triple-quotes or Python-like syntax.
export _PATCH_CONFIG_SRC="$CONFIG_SRC"
export _PATCH_CONFIG_TMP="$CONFIG_TMP"
export _PATCH_MODEL="$MODEL"
export _PATCH_BASE_URL="$BASE_URL"
export _PATCH_API_KEY="$GAMERON_API_KEY"
export _PATCH_HONCHO_CTX="$HONCHO_CONTEXT"
export _PATCH_WORK_CWD="$WORK_CWD"

python3 - <<'PYEOF'
import os, re, sys

config_src = os.environ["_PATCH_CONFIG_SRC"]
config_tmp = os.environ["_PATCH_CONFIG_TMP"]
model = os.environ["_PATCH_MODEL"]
base_url = os.environ["_PATCH_BASE_URL"]
api_key = os.environ["_PATCH_API_KEY"]
honcho_ctx = os.environ.get("_PATCH_HONCHO_CTX", "")
work_cwd = os.environ.get("_PATCH_WORK_CWD", "/home/justinleopard/projects")

with open(config_src) as f:
    content = f.read()

content = re.sub(r'model_name:.*', f'model_name: {model}', content, count=1)
content = re.sub(r'api_base:.*', f'api_base: {base_url}', content, count=1)
content = re.sub(r'api_key:.*', f'api_key: {api_key}', content, count=1)
content = re.sub(
    r'^(\s*)cwd:.*$',
    lambda m: f"{m.group(1)}cwd: {work_cwd}",
    content,
    count=1,
    flags=re.MULTILINE,
)

# Inject Honcho context into system_template if available
if honcho_ctx.strip():
    indented = '\n'.join('    ' + l for l in honcho_ctx.strip().splitlines())
    content = content.replace(
        '    You are ManusLocal',
        indented + '\n\n    You are ManusLocal',
        1
    )

with open(config_tmp, "w") as f:
    f.write(content)

print("Config patched OK")
PYEOF

# ── Step 3: Run mini ────────────────────────────────────────────────────────
mkdir -p "$PROJECT_DIR/logs"

if [[ -n "$TASK" ]]; then
    TASK_INPUT="$TASK"
    if [[ -n "$TASK_PREFIX" ]]; then
        TASK_INPUT="${TASK_PREFIX}"$'\n\n'"${TASK}"
    fi
fi

if [[ -n "$TASK" ]]; then
    
# Dynamically inject available CLI-Anything SKILL.md content into instance_template
SKILL_CONTENT=""
for skill_file in /home/justinleopard/cli-harnesses/*/agent-harness/cli_anything/*/skills/SKILL.md; do
    if [ -f "$skill_file" ]; then
        tool_name=$(echo "$skill_file" | sed 's|.*/cli_anything/||;s|/skills/SKILL.md||')
        SKILL_CONTENT="${SKILL_CONTENT}### ${tool_name} CLI\\n$(head -30 "$skill_file" | tail -n +5)\\n\\n"
    fi
done
export _PATCH_SKILL_CONTENT="$SKILL_CONTENT"

	set +e
	OPENAI_API_KEY="$GAMERON_API_KEY" OPENAI_BASE_URL="$BASE_URL" mini --exit-immediately -c "$CONFIG_TMP" -t "$TASK_INPUT" -o "$TRAJ_FILE" "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
	    EXIT_CODE=$?
	set -e
else
    
# Dynamically inject available CLI-Anything SKILL.md content into instance_template
SKILL_CONTENT=""
for skill_file in /home/justinleopard/cli-harnesses/*/agent-harness/cli_anything/*/skills/SKILL.md; do
    if [ -f "$skill_file" ]; then
        tool_name=$(echo "$skill_file" | sed 's|.*/cli_anything/||;s|/skills/SKILL.md||')
        SKILL_CONTENT="${SKILL_CONTENT}### ${tool_name} CLI\\n$(head -30 "$skill_file" | tail -n +5)\\n\\n"
    fi
done
export _PATCH_SKILL_CONTENT="$SKILL_CONTENT"

	set +e
	OPENAI_API_KEY="$GAMERON_API_KEY" OPENAI_BASE_URL="$BASE_URL" mini --exit-immediately -c "$CONFIG_TMP" -o "$TRAJ_FILE" "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
	    EXIT_CODE=$?
	set -e
fi

# ── Step 4: Post-task Honcho storage ───────────────────────────────────────
if [[ -n "$TASK" ]] && [[ -f "$MEMORY_SCRIPT" ]]; then
    POST_TASK_ARGS=(--post-task --task "$TASK" --traj "$TRAJ_FILE")
    if [[ $EXIT_CODE -ne 0 ]]; then
        POST_TASK_ARGS+=(--failed)
    fi

    HONCHO_OUTPUT=""
    if ! HONCHO_OUTPUT=$(timeout --foreground "${HONCHO_TIMEOUT_SECONDS}s" python3 "$MEMORY_SCRIPT" "${POST_TASK_ARGS[@]}" 2>&1); then
        :
    fi

    printf '%s\n' "$HONCHO_OUTPUT" > "$HONCHO_POST_FILE"
    if [[ -n "$HONCHO_OUTPUT" ]]; then
        printf '%s\n' "$HONCHO_OUTPUT"
    fi
fi

exit $EXIT_CODE
