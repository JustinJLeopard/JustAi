#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RR_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
JUSTAI_ROOT="${JUSTAI_ROOT:-$(cd "$RR_DIR/.." && pwd)}"
JUSTAI_LOCALMANUS_ROOT="${JUSTAI_LOCALMANUS_ROOT:-$JUSTAI_ROOT/LocalManus}"

PID_FILE="${PID_FILE:-/tmp/relay_dispatch.pid}"
LOG_FILE="${LOG_FILE:-/tmp/relay_dispatch.log}"
LM_DIR="${LOCALMANUS_ROOT:-$JUSTAI_LOCALMANUS_ROOT}"
LM_ENV_FILE="${LM_ENV_FILE:-$LM_DIR/.env}"
MINI_BIN="${MINI_BIN:-/home/justinleopard/.venv/hermes/bin/mini}"

VERBOSE=0
WITH_BOTS=0
WITH_CODEX=0
PARALLEL=1

# Sprint 3 Task 2: Bot management
BOT_AGENTS=("relay-coordinator" "codex" "manuslocal" "coworkclaude" "claudecli")
PYTHON="python3"
BOT_SCRIPT="${SCRIPT_DIR}/bot_listener.py"
HEALTH_SCRIPT="${SCRIPT_DIR}/health_server.py"
HEALTH_PID_FILE="/tmp/relay_health_server.pid"
WEB_SCRIPT="${SCRIPT_DIR}/relay_web.py"
WEB_PID_FILE="/tmp/relay_web.pid"
WEB_LOG_FILE="/tmp/relay_web.log"
WITH_WEB=1

C_RESET='\033[0m'
C_GREEN='\033[32m'
C_RED='\033[31m'
C_YELLOW='\033[33m'
C_BLUE='\033[34m'

ok()   { printf "${C_GREEN}✔${C_RESET} %s\n" "$*"; }
fail() { printf "${C_RED}✖${C_RESET} %s\n" "$*" >&2; }
info() { printf "${C_BLUE}•${C_RESET} %s\n" "$*"; }
warn() { printf "${C_YELLOW}⚠${C_RESET} %s\n" "$*"; }
vlog() { [[ "$VERBOSE" -eq 1 ]] && printf "[verbose] %s\n" "$*"; return 0; }

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--verbose] <start|stop|restart|status|health>

Subcommands:
  start    Launch relay_dispatch.sh --daemon via nohup in background
  stop     SIGTERM, wait up to 10s, SIGKILL if needed, remove PID file
  restart  stop then start
  status   Verify process is alive, show uptime and log tail
  health   Check SpacetimeDB:3000, LiteLLM:4000, relay CLI, mini binary

Options:
  -v, --verbose     Verbose logging
  --with-bots       Also start/stop/status all Discord bot listeners
  --with-codex      Also start/stop/status only the codex bot listener
  --parallel N      Start relay_dispatch.sh with up to N concurrent tasks
  --no-web          Skip relay_web lifecycle management
USAGE
}

is_pid_alive() {
  local pid="${1:-}"
  [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null
}

read_pid() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  printf '%s\n' "$pid"
}

source_localmanus_env() {
  if [[ -f "$LM_ENV_FILE" ]]; then
    vlog "sourcing LocalManus env: $LM_ENV_FILE"
    set -a
    # shellcheck disable=SC1090
    source "$LM_ENV_FILE"
    set +a
    ok "Sourced LocalManus env from $LM_ENV_FILE"
  else
    warn "LocalManus env missing at $LM_ENV_FILE (continuing)"
  fi
}

start_daemon() {
  local pid=""
  if pid="$(read_pid 2>/dev/null || true)" && is_pid_alive "$pid"; then
    warn "Daemon already running (PID $pid)"
    return 0
  fi

  [[ -f "$PID_FILE" ]] && rm -f "$PID_FILE"

  source_localmanus_env

  mkdir -p "$(dirname "$LOG_FILE")"
  touch "$LOG_FILE"

  local dispatch_args=(--daemon)
  if [[ "$PARALLEL" -gt 1 ]]; then
    dispatch_args+=(--parallel "$PARALLEL")
  fi

  vlog "starting relay_dispatch.sh ${dispatch_args[*]}"
  (
    cd "$RR_DIR"
    nohup bash "$SCRIPT_DIR/relay_dispatch.sh" "${dispatch_args[@]}" >>"$LOG_FILE" 2>&1 < /dev/null &
    echo $! > "$PID_FILE"
  )

  sleep 0.3

  if pid="$(read_pid 2>/dev/null || true)" && is_pid_alive "$pid"; then
    ok "Daemon started (PID $pid)"
    return 0
  fi

  fail "Daemon failed to start"
  [[ -f "$LOG_FILE" ]] && tail -n 20 "$LOG_FILE" >&2 || true
  return 1
}

stop_daemon() {
  local pid=""
  if ! pid="$(read_pid 2>/dev/null || true)"; then
    warn "No PID file at $PID_FILE (already stopped)"
    return 0
  fi

  if ! is_pid_alive "$pid"; then
    warn "Stale PID file (PID $pid not running), cleaning"
    rm -f "$PID_FILE"
    return 0
  fi

  # Capture session-end before shutdown (non-fatal)
  info "Invoking relay session-end before shutdown..."
  if command -v relay >/dev/null 2>&1; then
    if relay session-end 2>/dev/null; then
      ok "Session capture completed"
    else
      warn "relay session-end failed (exit $?), continuing shutdown"
    fi
  else
    warn "relay CLI not found, skipping session-end"
  fi

  info "Sending SIGTERM to PID $pid"
  kill -TERM "$pid" 2>/dev/null || true

  local waited=0
  while is_pid_alive "$pid" && [[ "$waited" -lt 10 ]]; do
    sleep 1
    waited=$((waited + 1))
    vlog "waiting for PID $pid to exit (${waited}s/10s)"
  done

  if is_pid_alive "$pid"; then
    warn "PID $pid still alive after 10s; sending SIGKILL"
    kill -KILL "$pid" 2>/dev/null || true
    sleep 0.2
  fi

  if is_pid_alive "$pid"; then
    fail "Failed to stop PID $pid"
    return 1
  fi

  rm -f "$PID_FILE"
  ok "Daemon stopped"
}

status_daemon() {
  local pid=""
  if ! pid="$(read_pid 2>/dev/null || true)"; then
    fail "Daemon not running (missing PID file: $PID_FILE)"
    return 1
  fi

  if ! is_pid_alive "$pid"; then
    fail "Daemon not running (stale PID $pid)"
    return 1
  fi

  local uptime
  uptime="$(ps -p "$pid" -o etime= 2>/dev/null | awk '{$1=$1;print}' || true)"
  [[ -n "$uptime" ]] || uptime="unknown"

  ok "Daemon running (PID $pid, uptime $uptime)"
  info "Recent log output ($LOG_FILE):"
  if [[ -f "$LOG_FILE" ]]; then
    tail -n 20 "$LOG_FILE"
  else
    warn "Log file not found"
  fi
}

check_port() {
  local host="$1"
  local port="$2"
  timeout 1 bash -c ">/dev/tcp/${host}/${port}" 2>/dev/null
}

health_check() {
  local failures=0
  local details=()

  if check_port 127.0.0.1 3000; then
    ok "SpacetimeDB reachable on 127.0.0.1:3000"
  else
    fail "SpacetimeDB unreachable on 127.0.0.1:3000"
    failures=$((failures + 1))
    details+=("SpacetimeDB:3000")
  fi

  if check_port 127.0.0.1 4000; then
    ok "LiteLLM reachable on 127.0.0.1:4000"
  else
    fail "LiteLLM unreachable on 127.0.0.1:4000"
    failures=$((failures + 1))
    details+=("LiteLLM:4000")
  fi

  if command -v relay >/dev/null 2>&1; then
    if relay --help >/dev/null 2>&1; then
      ok "relay CLI is installed and responsive"
    else
      fail "relay CLI found but not responsive"
      failures=$((failures + 1))
      details+=("relay-cli-unresponsive")
    fi
  else
    fail "relay CLI not found in PATH"
    failures=$((failures + 1))
    details+=("relay-cli-missing")
  fi

  if [[ -x "$MINI_BIN" ]]; then
    if "$MINI_BIN" --help >/dev/null 2>&1 || "$MINI_BIN" >/dev/null 2>&1; then
      ok "mini present and runnable at $MINI_BIN"
    else
      fail "mini found at $MINI_BIN but failed to run"
      failures=$((failures + 1))
      details+=("mini-unresponsive")
    fi
  else
    fail "mini not executable at $MINI_BIN"
    failures=$((failures + 1))
    details+=("mini-missing")
  fi

  if [[ "$failures" -eq 0 ]]; then
    ok "All health checks passed"
    return 0
  fi

  printf '%s\n' "Health check failed (${failures}): ${details[*]}" >&2
  return 1
}


# ── Sprint 3 Task 2: Bot Management ─────────────────────────────────────────

start_bots() {
  info "Starting Discord bot listeners..."
  set -a
  # Export Discord tokens and guild id so detached child processes inherit them.
  source "${RR_DIR}/.env"
  set +a
  for agent in "${BOT_AGENTS[@]}"; do
    local pid_file="/tmp/relay_discord_${agent}.pid"
    if [[ -f "${pid_file}" ]] && is_pid_alive "$(cat "${pid_file}")"; then
      warn "${agent} bot already running (PID $(cat "${pid_file}"))"
      continue
    fi
    nohup "${PYTHON}" "${BOT_SCRIPT}" --agent "${agent}" --guild "${DISCORD_GUILD_ID}" >> "/tmp/relay_bot_${agent}.log" 2>&1 &
    echo $! > "${pid_file}"
    ok "${agent} bot started (PID $!)"
  done

  # Start health server with watchdog
  local hp="/tmp/relay_health_server.pid"
  if [[ -f "${hp}" ]] && is_pid_alive "$(cat "${hp}")"; then
    warn "health_server already running"
  else
    nohup "${PYTHON}" "${HEALTH_SCRIPT}" >> /tmp/relay_health_server.log 2>&1 &
    echo $! > "${hp}"
    ok "health_server started (PID $!)"
  fi
}

start_web() {
  if [[ "$WITH_WEB" -eq 0 ]]; then
    info "relay_web startup skipped (--no-web)"
    return 0
  fi

  if [[ -f "$WEB_PID_FILE" ]] && is_pid_alive "$(cat "$WEB_PID_FILE")"; then
    warn "relay_web already running (PID $(cat "$WEB_PID_FILE"))"
    return 0
  fi

  nohup "${PYTHON}" "${WEB_SCRIPT}" >> "${WEB_LOG_FILE}" 2>&1 &
  echo $! > "${WEB_PID_FILE}"
  ok "relay_web started (PID $!)"
}

stop_bots() {
  info "Stopping Discord bot listeners..."
  for agent in "${BOT_AGENTS[@]}"; do
    local pid_file="/tmp/relay_discord_${agent}.pid"
    if [[ -f "${pid_file}" ]]; then
      local pid="$(cat "${pid_file}")"
      if is_pid_alive "${pid}"; then
        kill -TERM "${pid}" 2>/dev/null || true
        ok "${agent} bot stopped (PID ${pid})"
      fi
      rm -f "${pid_file}"
    else
      info "${agent} bot — not running"
    fi
  done

  local hp="/tmp/relay_health_server.pid"
  if [[ -f "${hp}" ]]; then
    local pid="$(cat "${hp}")"
    if is_pid_alive "${pid}"; then
      kill -TERM "${pid}" 2>/dev/null || true
      ok "health_server stopped"
    fi
    rm -f "${hp}"
  fi
}

stop_web() {
  if [[ -f "$WEB_PID_FILE" ]]; then
    local pid
    pid="$(cat "$WEB_PID_FILE")"
    if is_pid_alive "${pid}"; then
      kill -TERM "${pid}" 2>/dev/null || true
      ok "relay_web stopped (PID ${pid})"
    else
      warn "relay_web — stale PID ${pid}"
    fi
    rm -f "${WEB_PID_FILE}"
  elif [[ "$WITH_WEB" -eq 1 ]]; then
    info "relay_web — not running"
  fi
}

status_bots() {
  echo ""
  info "=== Discord Bots ==="
  for agent in "${BOT_AGENTS[@]}"; do
    local pid_file="/tmp/relay_discord_${agent}.pid"
    if [[ -f "${pid_file}" ]] && is_pid_alive "$(cat "${pid_file}")"; then
      ok "${agent} bot — running (PID $(cat "${pid_file}"))"
    else
      fail "${agent} bot — stopped"
    fi
  done
  local hp="/tmp/relay_health_server.pid"
  if [[ -f "${hp}" ]] && is_pid_alive "$(cat "${hp}")"; then
    ok "health_server — running (PID $(cat "${hp}"))"
  else
    fail "health_server — stopped"
  fi
}

status_web() {
  if [[ "$WITH_WEB" -eq 0 ]]; then
    info "relay_web — skipped (--no-web)"
    return 0
  fi

  if [[ -f "${WEB_PID_FILE}" ]] && is_pid_alive "$(cat "${WEB_PID_FILE}")"; then
    ok "relay_web — running (PID $(cat "${WEB_PID_FILE}"))"
  else
    fail "relay_web — stopped"
  fi
}

# ── Sprint 4 Task 2: Codex-only Bot Management ──────────────────────────────

start_codex() {
  info "Starting codex bot..."
  set -a
  source "${RR_DIR}/.env"
  set +a
  local pid_file="/tmp/relay_discord_codex.pid"
  if [[ -f "${pid_file}" ]] && is_pid_alive "$(cat "${pid_file}")"; then
    warn "codex bot already running (PID $(cat "${pid_file}"))"
    return 0
  fi
  nohup "${PYTHON}" "${BOT_SCRIPT}" --agent codex --guild "${DISCORD_GUILD_ID}" \
    >> "/tmp/relay_bot_codex.log" 2>&1 &
  echo $! > "${pid_file}"
  ok "codex bot started (PID $!)"
}

stop_codex() {
  local pid_file="/tmp/relay_discord_codex.pid"
  if [[ -f "${pid_file}" ]]; then
    local pid
    pid="$(cat "${pid_file}")"
    if is_pid_alive "${pid}"; then
      kill -TERM "${pid}" 2>/dev/null || true
      ok "codex bot stopped (PID ${pid})"
    else
      warn "codex bot — stale PID ${pid}"
    fi
    rm -f "${pid_file}"
  else
    info "codex bot — not running"
  fi
}

status_codex() {
  local pid_file="/tmp/relay_discord_codex.pid"
  if [[ -f "${pid_file}" ]] && is_pid_alive "$(cat "${pid_file}")"; then
    ok "codex bot — running (PID $(cat "${pid_file}"))"
  else
    fail "codex bot — stopped"
  fi
}

subcommand=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -v|--verbose) VERBOSE=1; shift ;;
    --with-bots)  WITH_BOTS=1; shift ;;
    --with-codex) WITH_CODEX=1; shift ;;
    --parallel)
      [[ $# -ge 2 ]] || { fail "--parallel requires a value"; exit 2; }
      PARALLEL="$2"
      shift 2
      ;;
    --no-web)     WITH_WEB=0; shift ;;
    start|stop|restart|status|health) subcommand="$1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown argument: $1"; usage >&2; exit 2 ;;
  esac
done

if ! [[ "$PARALLEL" =~ ^[0-9]+$ ]] || (( PARALLEL < 1 || PARALLEL > 4 )); then
  fail "--parallel must be an integer from 1 to 4"
  exit 2
fi

[[ -n "$subcommand" ]] || { usage >&2; exit 2; }

case "$subcommand" in
  start)
    start_daemon
    start_web
    if [[ "$WITH_BOTS" -eq 1 ]]; then
      start_bots
    fi
    if [[ "$WITH_CODEX" -eq 1 && "$WITH_BOTS" -eq 0 ]]; then
      start_codex
    fi
    ;;
  stop)
    if [[ "$WITH_BOTS" -eq 1 ]]; then
      stop_bots
    fi
    if [[ "$WITH_CODEX" -eq 1 && "$WITH_BOTS" -eq 0 ]]; then
      stop_codex
    fi
    stop_web
    stop_daemon
    ;;
  restart)
    if [[ "$WITH_BOTS" -eq 1 ]]; then
      stop_bots
    fi
    if [[ "$WITH_CODEX" -eq 1 && "$WITH_BOTS" -eq 0 ]]; then
      stop_codex
    fi
    stop_web
    stop_daemon
    sleep 2
    # Rotate logs before restarting
    info "Rotating logs..."
    bash "${RR_DIR}/scripts/log_archive.sh" --rotate || warn "Log rotation failed (continuing restart)"
    start_daemon
    start_web
    if [[ "$WITH_BOTS" -eq 1 ]]; then
      start_bots
    fi
    if [[ "$WITH_CODEX" -eq 1 && "$WITH_BOTS" -eq 0 ]]; then
      start_codex
    fi
    ;;
  status)
    status_daemon
    status_web
    if [[ "$WITH_BOTS" -eq 1 ]]; then
      status_bots
    fi
    if [[ "$WITH_CODEX" -eq 1 && "$WITH_BOTS" -eq 0 ]]; then
      status_codex
    fi
    ;;
  health) health_check ;;
esac
