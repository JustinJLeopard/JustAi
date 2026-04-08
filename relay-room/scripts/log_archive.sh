#!/usr/bin/env bash
# log_archive.sh — Archive relay-room logs and state files, then clear originals
# Usage: ./scripts/log_archive.sh [--keep-originals] [--rotate]
#
# --rotate       Rotate logs, compress old archives, delete stale files
# --keep-originals  Don't truncate logs after archiving
#
# Creates a timestamped tarball in the current relay-room workspace archives/
# containing all bot logs, session state, and handoff docs.
# By default, truncates log files after archiving (keeps PIDs running).

set -euo pipefail

RR_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVE_DIR="${RR_DIR}/archives"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_NAME="relay_logs_${TIMESTAMP}.tar.gz"
KEEP_ORIGINALS=0
ROTATE_MODE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep-originals) KEEP_ORIGINALS=1; shift ;;
    --rotate)         ROTATE_MODE=1; shift ;;
    *) shift ;;
  esac
done

mkdir -p "${ARCHIVE_DIR}"

# ── Log Rotation ──────────────────────────────────────────────────────────────
rotate_logs() {
  local rotated=0

  # Rotate /tmp/relay_dispatch.log
  if [[ -f /tmp/relay_dispatch.log ]]; then
    local dest="${ARCHIVE_DIR}/relay_dispatch_${TIMESTAMP}.log"
    cp /tmp/relay_dispatch.log "${dest}"
    : > /tmp/relay_dispatch.log
    echo "  ✓ Rotated /tmp/relay_dispatch.log → ${dest}"
    rotated=$((rotated + 1))
  fi

  # Rotate /tmp/relay_bot_*.log
  for f in /tmp/relay_bot_*.log; do
    [[ -f "$f" ]] || continue
    local base
    base="$(basename "$f" .log)"
    local dest="${ARCHIVE_DIR}/${base}_${TIMESTAMP}.log"
    cp "$f" "${dest}"
    : > "$f"
    echo "  ✓ Rotated $f → ${dest}"
    rotated=$((rotated + 1))
  done

  # Compress archives older than 24h (uncompressed .log files in archives/)
  find "${ARCHIVE_DIR}" -name '*.log' -mmin +1440 ! -name '*.gz' -print0 2>/dev/null | \
    while IFS= read -r -d '' logfile; do
      gzip -f "${logfile}"
      echo "  ✓ Compressed ${logfile}"
    done

  # Delete archives older than 7 days (.log.gz and .tar.gz)
  find "${ARCHIVE_DIR}" -maxdepth 1 \( -name '*.log.gz' -o -name '*.tar.gz' \) -mtime +7 -print -delete 2>/dev/null | \
    while IFS= read -r deleted; do
      echo "  ✓ Deleted old archive: ${deleted}"
    done

  # Clean /tmp/relay_dispatch_run_*.txt older than 24h
  find /tmp -maxdepth 1 -name 'relay_dispatch_run_*.txt' -mmin +1440 -print -delete 2>/dev/null | \
    while IFS= read -r deleted; do
      echo "  ✓ Cleaned stale run file: ${deleted}"
    done

  # Clean /tmp/relay_traj_*.json older than 24h
  find /tmp -maxdepth 1 -name 'relay_traj_*.json' -mmin +1440 -print -delete 2>/dev/null | \
    while IFS= read -r deleted; do
      echo "  ✓ Cleaned stale trajectory: ${deleted}"
    done

  echo "✓ Log rotation complete (${rotated} log(s) rotated)"
}

if [[ "$ROTATE_MODE" -eq 1 ]]; then
  echo "=== Log Rotation ==="
  rotate_logs
  exit 0
fi

# ── Archive Mode (original behaviour) ────────────────────────────────────────

# Collect files to archive
FILES_TO_ARCHIVE=()

# Bot logs
for f in /tmp/relay_bot_*.log /tmp/relay_web.log; do
    [[ -f "$f" ]] && FILES_TO_ARCHIVE+=("$f")
done

# Dispatch log
[[ -f /tmp/relay_dispatch.log ]] && FILES_TO_ARCHIVE+=("/tmp/relay_dispatch.log")

# Session state and handoff docs
for f in \
    "${RR_DIR}/scripts/last_session_state.json" \
    "${RR_DIR}/HANDOFF_CODEX.md" \
    "${RR_DIR}/HANDOFF.md"; do
    [[ -f "$f" ]] && FILES_TO_ARCHIVE+=("$f")
done

if [[ ${#FILES_TO_ARCHIVE[@]} -eq 0 ]]; then
    echo "No log files found to archive."
    exit 0
fi

# Create archive
tar -czf "${ARCHIVE_DIR}/${ARCHIVE_NAME}" "${FILES_TO_ARCHIVE[@]}" 2>/dev/null || true

ARCHIVE_SIZE="$(du -h "${ARCHIVE_DIR}/${ARCHIVE_NAME}" | cut -f1)"
echo "✓ Archive created: ${ARCHIVE_DIR}/${ARCHIVE_NAME} (${ARCHIVE_SIZE})"
echo "  Files archived: ${#FILES_TO_ARCHIVE[@]}"

# List contents
for f in "${FILES_TO_ARCHIVE[@]}"; do
    SIZE="$(du -h "$f" | cut -f1)"
    echo "    ${f} (${SIZE})"
done

# Truncate logs (not delete — keeps file handles for running processes)
if [[ "$KEEP_ORIGINALS" -eq 0 ]]; then
    for f in /tmp/relay_bot_*.log /tmp/relay_web.log /tmp/relay_dispatch.log; do
        if [[ -f "$f" ]]; then
            : > "$f"
            echo "  ✓ Truncated: $f"
        fi
    done
    echo "✓ Logs truncated (bot processes unaffected)"
else
    echo "  (--keep-originals: logs not truncated)"
fi

# Upload to Google Drive via rclone
if command -v rclone &>/dev/null && rclone listremotes 2>/dev/null | grep -q "gdrive:"; then
    echo "Uploading to Google Drive..."
    if rclone copy "${ARCHIVE_DIR}/${ARCHIVE_NAME}" gdrive:relay-room-logs/ 2>&1; then
        echo "✓ Uploaded to gdrive:relay-room-logs/${ARCHIVE_NAME}"
    else
        echo "⚠ rclone upload failed (archive retained locally)"
    fi
else
    echo "⚠ rclone/gdrive not configured — skipping upload (archive retained locally)"
fi

# Clean up old archives (keep last 14 days)
find "${ARCHIVE_DIR}" -name "relay_logs_*.tar.gz" -mtime +14 -delete 2>/dev/null || true
echo "✓ Archives older than 14 days cleaned up"

# Output the archive path for callers
echo "ARCHIVE_PATH=${ARCHIVE_DIR}/${ARCHIVE_NAME}"
