#!/usr/bin/env bash
# relay_dispatch.sh — polls relay board for pending localmanus tasks, runs mini, posts result
# Usage: ./scripts/relay_dispatch.sh [--once] [--daemon] [--interval N]
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RR_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
JUSTAI_ROOT="${JUSTAI_ROOT:-$(cd "$RR_DIR/.." && pwd)}"
JUSTAI_LOCALMANUS_ROOT="${JUSTAI_LOCALMANUS_ROOT:-$JUSTAI_ROOT/LocalManus}"

export PATH="$PATH:$HOME/.local/bin:$HOME/.cargo/bin"
LM_DIR="${LOCALMANUS_ROOT:-$JUSTAI_LOCALMANUS_ROOT}"
source "$LM_DIR/.env" 2>/dev/null || true
TARGET_FILE="${TARGET_FILE:-$RR_DIR/.relay-db-target}"
if [[ -z "${RELAY_DB_NAME:-}" && -f "$TARGET_FILE" ]]; then
    RELAY_DB_NAME="$(head -n 1 "$TARGET_FILE")"
fi
export RELAY_DB_NAME="${RELAY_DB_NAME:-relay-room-dev}"
export RELAY_SERVER="${RELAY_SERVER:-local-server}"

AGENT="manuslocal"
DISPATCH_AGENT="relay-dispatch"
# ── Discord notification helper ──────────────────────────────────────────────
# Fires a message to #relay-room if DISCORD_RELAY_CHANNEL_ID + a bot token are set.
# Completely optional — if vars are unset the function is a no-op.
DISCORD_RELAY_CHANNEL_ID="1491134768077865090"  # #relay-room
DISCORD_ALERTS_CHANNEL_ID="1491134780589342770" # #alerts
DISCORD_BOT_TOKEN="${RELAY_COORDINATOR_TOKEN:-}"
DISCORD_BOT_USER_AGENT="DiscordBot (relay-room, 0.1)"

discord_notify() {
    local channel_id="${1:-$DISCORD_RELAY_CHANNEL_ID}"
    local message="${2:-}"
    local agent_channel="${3:-}"
    [[ -z "$DISCORD_BOT_TOKEN" ]] && return 0
    [[ -z "$message" ]] && return 0
    local payload="{\"content\":\"$message\"}"
    curl -s -o /dev/null -X POST \
        -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
        -H "User-Agent: $DISCORD_BOT_USER_AGENT" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "https://discord.com/api/v10/channels/$channel_id/messages" || true
    # Sprint 3 Task 5: Also post to per-agent channel if specified
    if [[ -n "$agent_channel" ]]; then
        local guild_id="${DISCORD_GUILD_ID:-1491110247299944641}"
        local agent_ch_name="agent-$agent_channel"
        local agent_ch_id
        agent_ch_id=$(curl -s -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
            -H "User-Agent: $DISCORD_BOT_USER_AGENT" \
            "https://discord.com/api/v10/guilds/$guild_id/channels" 2>/dev/null \
            | python3 -c "import sys,json;[print(c['id']) for c in json.load(sys.stdin) if c.get('name')==sys.argv[1]]" "$agent_ch_name" 2>/dev/null \
            | head -1)
        [[ -n "$agent_ch_id" ]] && curl -s -o /dev/null -X POST \
            -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
            -H "User-Agent: $DISCORD_BOT_USER_AGENT" \
            -H "Content-Type: application/json" \
            -d "$payload" \
            "https://discord.com/api/v10/channels/$agent_ch_id/messages" || true
    fi
}

discord_alert() {
    local message="${1:-}"
    discord_notify "$DISCORD_ALERTS_CHANNEL_ID" "$message"
}
# ─────────────────────────────────────────────────────────────────────────────

PID_FILE="${PID_FILE:-/tmp/relay_dispatch.pid}"
LOG_FILE="${LOG_FILE:-/tmp/relay_dispatch.log}"
INTERVAL_SECONDS=5
STALE_TASK_THRESHOLD_SECONDS="${STALE_TASK_THRESHOLD_SECONDS:-900}"
MAX_RETRIES="${MAX_RETRIES:-2}"
MODE="daemon"
PARALLEL_LIMIT=1
STOP_REQUESTED=0
AUTO_INSTALL_LAST_ERROR=""

log_line() {
    local message="$1"
    printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$message" >>"$LOG_FILE"
}

copy_traj_for_task() {
    local task_id="$1"
    local traj_source="${2:-$LM_DIR/logs/last_mini_run.traj.json}"
    local traj_copy="/tmp/relay_traj_${task_id}.json"

    if [[ -f "$traj_source" ]]; then
        cp "$traj_source" "$traj_copy"
        printf '%s\n' "$traj_copy"
    fi
}

read_honcho_summary() {
    local honcho_file="${1:-$LM_DIR/logs/last_honcho_post_task.txt}"

    if [[ -f "$honcho_file" ]]; then
        python3 - "$honcho_file" <<'PY'
import sys

path = sys.argv[1]
summary = ""

try:
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("[honcho] Summary: "):
                summary = line[len("[honcho] Summary: "):]
except Exception:
    print("")
    raise SystemExit(0)

print(summary[:200])
PY
    fi
}

summarize_success() {
    local run_log="$1"
    local traj_copy="${2:-}"
    local honcho_summary="${3:-}"

    if [[ -n "$honcho_summary" ]]; then
        printf '%s\n' "$honcho_summary"
        return 0
    fi

    if [[ -n "$traj_copy" && -f "$traj_copy" ]]; then
        local traj_summary=""
        traj_summary=$(python3 - "$traj_copy" <<'PY'
import json
import sys

path = sys.argv[1]

try:
    with open(path) as f:
        data = json.load(f)
except Exception:
    print("")
    raise SystemExit(0)

steps = data.get("trajectory", [])
last_action = ""
last_observation = ""

for step in reversed(steps):
    action = step.get("action", {})
    if not last_action:
        last_action = (
            action.get("bash_command")
            or action.get("command")
            or action.get("content")
            or ""
        )
    observation = step.get("observation", {})
    if not last_observation:
        last_observation = (
            observation.get("output")
            or observation.get("content")
            or observation.get("message")
            or ""
        )
    if last_action and last_observation:
        break

parts = []
if last_action:
    parts.append(f"action: {last_action}")
if last_observation:
    parts.append(f"observation: {last_observation}")

summary = "; ".join(parts).replace("\n", " ").strip()
print(summary[:200])
PY
)
        if [[ -n "$traj_summary" ]]; then
            printf '%s\n' "$traj_summary"
            return 0
        fi
    fi

    tail -3 "$run_log" | tr '\n' ' ' | sed 's/[[:space:]]*$//' | cut -c1-200
}

rust_source_digest() {
    (
        cd "$RR_DIR"
        {
            find client/src spacetimedb/src -type f -print 2>/dev/null
            for extra in client/Cargo.toml spacetimedb/Cargo.toml; do
                [[ -f "$extra" ]] && printf '%s\n' "$extra"
            done
        } | sort | xargs sha256sum 2>/dev/null | sha256sum | cut -d' ' -f1
    )
}

derive_task_workdir() {
    local payload="${1:-}"

    python3 - "$payload" "$RR_DIR" <<'PY'
import re
import sys

payload = sys.argv[1]
default_root = sys.argv[2]

matches = re.findall(r'(/[^ \n\t\r"\'`]+)', payload)
for raw in matches:
    path = raw.rstrip('.,:;)]}')
    if path.startswith("/home/justinleopard/projects/"):
        parts = path.split("/")
        if len(parts) >= 5:
            print("/".join(parts[:5]))
            raise SystemExit(0)

print(default_root)
PY
}

build_task_prefix() {
    local work_cwd="${1:-$RR_DIR}"

    cat <<EOF
Repository root: $work_cwd
Working directory: $work_cwd
Operate only inside $work_cwd unless the task explicitly names another absolute path such as /tmp.
Use Linux paths exactly as given. Do not translate repo paths to /mnt/c/home.
For repository tasks, start by reading files under $work_cwd rather than scanning /home/justinleopard.
EOF
}

auto_install_relay_cli_if_needed() {
    local before_digest="${1:-}"
    local task_id="${2:-unknown}"
    local after_digest=""
    local install_output=""

    AUTO_INSTALL_LAST_ERROR=""
    after_digest="$(rust_source_digest || true)"
    [[ -n "$before_digest" && -n "$after_digest" ]] || return 0
    [[ "$before_digest" != "$after_digest" ]] || return 0

    echo "[dispatch] Rust source changed - rebuilding relay CLI..."
    log_line "[dispatch] task $task_id rust source changed; running make install"

    if ! install_output="$(cd "$RR_DIR" && make install 2>&1)"; then
        AUTO_INSTALL_LAST_ERROR="$(printf '%s\n' "$install_output" | tail -5 | tr '\n' ' ' | sed 's/[[:space:]]*$//' | cut -c1-200)"
        printf '%s\n' "$install_output" | tail -5
        log_line "[dispatch] task $task_id make install failed: ${AUTO_INSTALL_LAST_ERROR:-unknown error}"
        return 1
    fi

    printf '%s\n' "$install_output" | tail -5
    log_line "[dispatch] task $task_id make install completed"
}

detect_failed_tool_call() {
    local traj_copy="${1:-}"
    [[ -n "$traj_copy" && -f "$traj_copy" ]] || return 1

    python3 - "$traj_copy" <<'PY'
import json
import sys
from collections.abc import Mapping, Sequence
import re

path = sys.argv[1]

try:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    raise SystemExit(1)

failures = []
submitted = False

def walk(value):
    global submitted
    if isinstance(value, Mapping):
        exit_status = str(value.get("exit_status") or "").strip().lower()
        if exit_status == "submitted":
            submitted = True

        raw_output = value.get("raw_output") or value.get("output") or ""
        if isinstance(raw_output, Mapping):
            raw_output = json.dumps(raw_output, ensure_ascii=True)
        text = str(raw_output).replace("\n", " ").strip()
        exception_info = str(value.get("exception_info") or "").strip()

        if "returncode" in value:
            try:
                rc = int(value.get("returncode"))
            except Exception:
                rc = 0
            if rc != 0:
                if rc < 0 and not text and "action was not executed" in exception_info.lower():
                    pass
                else:
                    detail = text or exception_info
                    failures.append((2 if detail else 1, f"tool exit {rc}: {detail}".strip()))

        if text:
            match = re.search(r"(?:EXIT_CODE|Exit code):\s*([1-9][0-9]*)", text)
            if match:
                failures.append((3, f"tool exit {match.group(1)}: {text}".strip()))

        for nested in value.values():
            walk(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            walk(nested)

walk(data)
if submitted:
    raise SystemExit(1)
if not failures:
    raise SystemExit(1)

failures.sort(key=lambda item: item[0], reverse=True)
print(failures[0][1][:200])
PY
}

cleanup_pid() {
    relay agent-status "$DISPATCH_AGENT" --status offline --task 0 >/dev/null 2>&1 || true
    if [[ -f "$PID_FILE" && "$(cat "$PID_FILE" 2>/dev/null)" == "$$" ]]; then
        rm -f "$PID_FILE"
    fi
}

has_active_mini_process() {
    pgrep -af "mini-swe-agent|mini --exit-immediately|mini " >/dev/null 2>&1
}

recover_stale_in_progress() {
    has_active_mini_process && return 0

    local threshold_ms=$((STALE_TASK_THRESHOLD_SECONDS * 1000))
    local now_ms
    now_ms="$(python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
)"

    while IFS='|' read -r task_id claimed_by updated_at claimed_at; do
        [[ -n "$task_id" ]] || continue
        [[ "$claimed_by" == "$AGENT" ]] || continue

        local last_touch="$updated_at"
        [[ "$last_touch" =~ ^[0-9]+$ ]] || last_touch="$claimed_at"
        [[ "$last_touch" =~ ^[0-9]+$ ]] || continue

        local age_ms=$((now_ms - last_touch))
        (( age_ms >= threshold_ms )) || continue

        local age_seconds=$((age_ms / 1000))
        local reason="stale in_progress recovered after ${age_seconds}s with no active mini process"
        record_task_failure "$task_id" "$reason" 1
    done < <(
        relay tasks --to "$AGENT" --status in_progress 2>/dev/null \
            | awk -F'|' 'NR>2 && $1 ~ /^ *[0-9]/ {
                id=$1; claimed=$5; updated=$12; touched=$13;
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", id);
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", claimed);
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", updated);
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", touched);
                gsub(/"/, "", id);
                gsub(/"/, "", claimed);
                gsub(/"/, "", updated);
                gsub(/"/, "", touched);
                print id "|" claimed "|" updated "|" touched;
            }'
    )
}

print_startup_banner() {
    local db_name="${RELAY_DB_NAME:-}"
    local server_name="${RELAY_SERVER:-}"
    cat <<EOF
[dispatch] startup
[dispatch]   repo: $RR_DIR
[dispatch]   agent: $DISPATCH_AGENT
[dispatch]   relay target: $AGENT
[dispatch]   RELAY_DB_NAME: $db_name
[dispatch]   RELAY_SERVER: $server_name
[dispatch]   INTERVAL_SECONDS: $INTERVAL_SECONDS
[dispatch]   MAX_RETRIES: $MAX_RETRIES
[dispatch]   PARALLEL_LIMIT: $PARALLEL_LIMIT
[dispatch]   STALE_TASK_THRESHOLD_SECONDS: $STALE_TASK_THRESHOLD_SECONDS
EOF
    log_line "[dispatch] startup agent=$DISPATCH_AGENT relay_target=$AGENT db=$db_name server=$server_name interval=${INTERVAL_SECONDS}s max_retries=${MAX_RETRIES} parallel=${PARALLEL_LIMIT} stale_threshold=${STALE_TASK_THRESHOLD_SECONDS}s repo=$RR_DIR"
}

handle_signal() {
    STOP_REQUESTED=1
    log_line "[dispatch] shutdown requested"
}

usage() {
    cat <<'EOF'
Usage: relay_dispatch.sh [--once] [--daemon] [--interval N]

Options:
  --once        Run a single poll cycle and exit
  --daemon      Poll continuously until SIGTERM/SIGINT
  --interval N  Poll interval in seconds (default: 5)
  --max-retries N  Retry failed tasks up to N times (default: 2)
  --parallel N  Run up to N tasks concurrently (default: 1, max: 4)
EOF
}

register_dispatch_agent() {
    relay register "$DISPATCH_AGENT" --handler-type daemon --caps task-dispatch,mini-execution >/dev/null 2>&1 || true
    relay agent-status "$DISPATCH_AGENT" --status online --task 0 >/dev/null 2>&1 || true
}

heartbeat_dispatch_agent() {
    relay heartbeat "$DISPATCH_AGENT" >/dev/null 2>&1 || true
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --once)
            MODE="once"
            shift
            ;;
        --daemon)
            MODE="daemon"
            shift
            ;;
        --interval)
            [[ $# -ge 2 ]] || {
                echo "--interval requires a value" >&2
                exit 2
            }
            INTERVAL_SECONDS="$2"
            shift 2
            ;;
        --max-retries)
            [[ $# -ge 2 ]] || {
                echo "--max-retries requires a value" >&2
                exit 2
            }
            MAX_RETRIES="$2"
            shift 2
            ;;
        --parallel)
            [[ $# -ge 2 ]] || {
                echo "--parallel requires a value" >&2
                exit 2
            }
            PARALLEL_LIMIT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if ! [[ "$MAX_RETRIES" =~ ^[0-9]+$ ]]; then
    echo "--max-retries must be a non-negative integer" >&2
    exit 2
fi

if ! [[ "$PARALLEL_LIMIT" =~ ^[0-9]+$ ]] || (( PARALLEL_LIMIT < 1 || PARALLEL_LIMIT > 4 )); then
    echo "--parallel must be an integer from 1 to 4" >&2
    exit 2
fi

get_pending_ids() {
    relay tasks --to "$AGENT" --status pending 2>/dev/null \
        | awk -F'|' 'NR>2 && $1 ~ /^ *[0-9]/ {
            id = $1; gsub(/ /, "", id); print id
          }'
}

get_payload() {
    local task_id="$1"
    relay show "$task_id" 2>/dev/null \
        | awk -F'|' '
            NR>2 && $1 ~ /^ *[0-9]/ {
                payload = $7
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", payload)
                gsub(/"/, "", payload)
                print payload
                exit
            }'
}

get_retry_count() {
    local task_id="$1"
    relay show "$task_id" --json 2>/dev/null | python3 -c '
import json
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    print(0)
    raise SystemExit(0)

value = payload.get("retry_count", 0)
try:
    print(int(value))
except Exception:
    print(0)
'
}

record_task_failure() {
    local task_id="$1"
    local error="$2"
    local retriable="${3:-1}"
    local retry_count=0

    if [[ "$retriable" == "1" ]]; then
        retry_count="$(get_retry_count "$task_id")"
        if [[ "$retry_count" =~ ^[0-9]+$ ]] && (( retry_count < MAX_RETRIES )); then
            if relay requeue "$task_id" --as "$AGENT" --error "$error" >/dev/null 2>&1; then
                echo "[dispatch] task $task_id REQUEUED (retry $((retry_count + 1))/$MAX_RETRIES)"
                log_line "[dispatch] task $task_id requeued retry=$((retry_count + 1))/$MAX_RETRIES error=$error"
                return 0
            fi
        fi
    fi

    relay fail "$task_id" --as "$AGENT" --error "$error" >/dev/null 2>&1 || true
    echo "[dispatch] task $task_id FAILED"
    log_line "[dispatch] task $task_id failed: $error"
}

process_task() {
    local id="$1"
    local run_log="$2"
    local payload
    local traj_copy=""
    local honcho_summary=""
    local tool_failure=""
    local rust_digest_before=""
    local work_cwd=""
    local honcho_file="$LM_DIR/logs/last_honcho_post_task.txt"
    local traj_file="$LM_DIR/logs/last_mini_run.traj.json"
    local task_artifact_dir="$LM_DIR/logs/relay_dispatch"
    local task_traj_file=""
    local task_honcho_file=""

    echo "[dispatch] found task $id, claiming..."
    relay claim "$id" --as "$AGENT" 2>/dev/null || {
        echo "[dispatch] claim $id failed (already claimed?), skipping"
        log_line "[dispatch] claim failed for task $id"
        return 0
    }
    relay start "$id" --as "$AGENT" 2>/dev/null || true

    payload=$(get_payload "$id")
    if [[ -z "$payload" ]]; then
        record_task_failure "$id" "empty payload" 0
        return 0
    fi

    echo "[dispatch] running mini on task $id: ${payload:0:80}..."
    log_line "[dispatch] task $id started"

    mkdir -p "$task_artifact_dir"
    task_traj_file="$task_artifact_dir/task_${id}.traj.json"
    task_honcho_file="$task_artifact_dir/task_${id}.honcho.txt"
    rm -f "$task_honcho_file" "$task_traj_file"
    rust_digest_before="$(rust_source_digest || true)"
    work_cwd="$(derive_task_workdir "$payload")"
    local task_prefix
    task_prefix="$(build_task_prefix "$work_cwd")"

    cd "$LM_DIR"
    local exit_code=0
    set +e
    MINI_CWD="$work_cwd" \
    MINI_TASK_PREFIX="$task_prefix" \
    MINI_TRAJ_FILE="$task_traj_file" \
    MINI_HONCHO_POST_FILE="$task_honcho_file" \
    bash scripts/mini_local_cloud.sh -t "$payload" < /dev/null > "$run_log" 2>&1
    exit_code=$?
    set -e
    cd "$RR_DIR"

    if [[ $exit_code -eq 0 ]]; then
        honcho_summary="$(read_honcho_summary "$task_honcho_file" || true)"
        traj_copy="$(copy_traj_for_task "$id" "$task_traj_file" || true)"
        tool_failure="$(detect_failed_tool_call "$traj_copy" || true)"
        if [[ -n "$tool_failure" ]]; then
            record_task_failure "$id" "$tool_failure" 1
            return 0
        fi
        if ! auto_install_relay_cli_if_needed "$rust_digest_before" "$id"; then
            local install_err="${AUTO_INSTALL_LAST_ERROR:-make install failed after Rust source changes}"
            record_task_failure "$id" "$install_err" 1
            return 0
        fi
        local result
        result=$(summarize_success "$run_log" "$traj_copy" "$honcho_summary")
        relay done "$id" --as "$AGENT" --result "${result:-completed ok}"
        rm -f "$run_log"
        echo "[dispatch] task $id DONE"
        log_line "[dispatch] task $id done"
    else
        local err
        err="mini exited $exit_code: $(tail -2 "$run_log" | tr '\n' ' ' | sed 's/[[:space:]]*$//' | cut -c1-150)"
        log_line "[dispatch] task $id nonzero exit=$exit_code"
        record_task_failure "$id" "$err" 1
    fi
}

prune_active_pids() {
    local -n active_ref="$1"
    local -a remaining=()
    local pid

    for pid in "${active_ref[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            remaining+=("$pid")
        fi
    done

    active_ref=("${remaining[@]}")
}

run_cycle() {
    local ids
    heartbeat_dispatch_agent
    recover_stale_in_progress
    ids=$(get_pending_ids)

    if [[ -z "$ids" ]]; then
        echo "[dispatch] no pending tasks"
        log_line "[dispatch] poll cycle: no pending tasks"
        return 0
    fi

    log_line "[dispatch] poll cycle: processing tasks"
    if [[ "$PARALLEL_LIMIT" -le 1 ]]; then
        for id in $ids; do
            local run_log="/tmp/relay_dispatch_task_${id}.log"
            : >"$run_log"
            (process_task "$id" "$run_log") >"$run_log" 2>&1
            if [[ "$STOP_REQUESTED" -eq 1 ]]; then
                log_line "[dispatch] stop honored after task $id"
                break
            fi
        done
        return 0
    fi

    local -a active_pids=()
    local id
    for id in $ids; do
        while [[ "${#active_pids[@]}" -ge "$PARALLEL_LIMIT" ]]; do
            wait -n || true
            prune_active_pids active_pids
        done

        local run_log="/tmp/relay_dispatch_task_${id}.log"
        : >"$run_log"
        (process_task "$id" "$run_log") >"$run_log" 2>&1 &
        local pid=$!
        active_pids+=("$pid")
        echo "[dispatch] launched task $id (pid $pid)"
        log_line "[dispatch] task $id launched pid=$pid log=$run_log"
    done

    while [[ "${#active_pids[@]}" -gt 0 ]]; do
        wait -n || true
        prune_active_pids active_pids
    done
}

if [[ "$MODE" == "once" ]]; then
    register_dispatch_agent
    print_startup_banner
    run_cycle
else
    trap handle_signal SIGTERM SIGINT
    trap cleanup_pid EXIT
    printf '%s\n' "$$" >"$PID_FILE"
    register_dispatch_agent
    log_line "[dispatch] daemon start pid=$$ interval=${INTERVAL_SECONDS}s"
    print_startup_banner
    echo "[dispatch] starting poll loop every ${INTERVAL_SECONDS}s (Ctrl+C to stop)..."
    while [[ "$STOP_REQUESTED" -eq 0 ]]; do
        run_cycle
        [[ "$STOP_REQUESTED" -eq 0 ]] || break
        sleep "$INTERVAL_SECONDS"
    done
    log_line "[dispatch] daemon exit"
fi
