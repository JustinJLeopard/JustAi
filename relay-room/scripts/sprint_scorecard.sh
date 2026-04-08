#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: $0 <sprint-number>" >&2
  exit 1
fi

SPRINT="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCS_DIR="$ROOT/docs"
OUT_FILE="$DOCS_DIR/SPRINT_${SPRINT}_SCORECARD.md"
TAG="sprint-${SPRINT}"

if [ -f "$HOME/.cargo/env" ]; then
  . "$HOME/.cargo/env"
fi
export PATH="$PATH:$HOME/.local/bin:$HOME/.cargo/bin"

ACTIVE_FILE="$(mktemp)"
ARCHIVE_FILE="$(mktemp)"
cleanup() {
  rm -f "$ACTIVE_FILE" "$ARCHIVE_FILE"
}
trap cleanup EXIT

relay tasks >"$ACTIVE_FILE"
if ! relay archive --list --json >"$ARCHIVE_FILE" 2>/dev/null; then
  printf '[]\n' >"$ARCHIVE_FILE"
fi

python3 - "$SPRINT" "$TAG" "$ACTIVE_FILE" "$ARCHIVE_FILE" "$OUT_FILE" <<'PY'
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def parse_pipe_table(text: str):
    headers = None
    rows = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("WARNING:"):
            continue
        if "|" not in line:
            continue
        stripped = line.replace("-", "").replace("+", "").strip()
        if not stripped:
            continue
        cells = [cell.strip().strip('"') for cell in line.split("|")]
        if headers is None:
            headers = cells
            continue
        row = dict(zip(headers, cells))
        rows.append(row)
    return rows


def as_int(value, default=0):
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return int(text)
    except Exception:
        match = re.search(r"(\\d+)", text)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return default
        return default


def canonical_group_key(row):
    parent = row.get("parent_task_id")
    parent_id = as_int(parent, 0)
    if parent_id:
        return f"parent:{parent_id}"
    return f"id:{row.get('id')}"


def is_internal_smoke(row):
    title = str(row.get("title", "")).strip().lower()
    payload = str(row.get("payload", "")).strip().lower()
    return title.startswith("option smoke") or title.startswith("retry smoke") or "test option encoding" in payload


def status_for_group(row):
    status = row.get("status", "")
    if status == "archived":
        return "done"
    return status


def matches_tag(row, tag: str):
    session_ref = str(row.get("session_ref", ""))
    return session_ref == tag or session_ref.endswith(f":{tag}")


def classify_attempts(rows):
    grouped = defaultdict(list)
    for row in rows:
        if is_internal_smoke(row):
            continue
        key = canonical_group_key(row)
        grouped[key].append(row)

    first_try = 0
    retry_success = 0
    permanent_fail = 0
    open_groups = 0
    details = []

    for key, attempts in grouped.items():
        attempts.sort(
            key=lambda row: (
                as_int(row.get("attempt_number"), 1),
                as_int(row.get("created_at")),
                as_int(row.get("id")),
            )
        )
        first = attempts[0]
        normalized_statuses = [status_for_group(row) for row in attempts]
        final = attempts[-1]
        if normalized_statuses[0] == "done":
            first_try += 1
            outcome = "first_try_success"
        elif "done" in normalized_statuses[1:]:
            retry_success += 1
            outcome = "succeeded_after_retry"
        elif normalized_statuses[-1] in {"failed"}:
            permanent_fail += 1
            outcome = "failed_permanently"
        else:
            open_groups += 1
            outcome = f"open:{normalized_statuses[-1]}"
        details.append(
            {
                "title": first.get("title") or key,
                "attempts": len(attempts),
                "root_task_id": attempts[0].get("parent_task_id") or attempts[0].get("id"),
                "first_task_id": first.get("id", ""),
                "latest_task_id": final.get("id", ""),
                "latest_status": final.get("status", ""),
                "outcome": outcome,
                "created_at": as_int(first.get("created_at")),
            }
        )

    details.sort(key=lambda row: row["created_at"])
    return first_try, retry_success, permanent_fail, open_groups, details


def render_table(rows, headers):
    if not rows:
        return "_No matching tasks found._"
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        values = [str(row.get(header, "")).replace("\n", " ") for header in headers]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main():
    sprint = sys.argv[1]
    tag = sys.argv[2]
    active_path = Path(sys.argv[3])
    archive_path = Path(sys.argv[4])
    out_path = Path(sys.argv[5])

    active_rows = parse_pipe_table(active_path.read_text())
    archived_rows = json.loads(archive_path.read_text() or "[]")

    combined = [row for row in active_rows if matches_tag(row, tag)]
    for row in archived_rows:
        if matches_tag(row, tag):
            normalized = {key: row.get(key, "") for key in row.keys()}
            normalized["id"] = row.get("original_task_id", row.get("id", ""))
            normalized["status"] = "archived"
            combined.append(normalized)

    combined.sort(key=lambda row: as_int(row.get("created_at")))
    combined = [row for row in combined if not is_internal_smoke(row)]

    first_try, retry_success, permanent_fail, open_groups, details = classify_attempts(combined)
    total_groups = first_try + retry_success + permanent_fail + open_groups
    success_rate = 0.0 if total_groups == 0 else (first_try / total_groups) * 100.0

    summary_rows = [
        {"Metric": "Sprint tag", "Value": tag},
        {"Metric": "Generated at", "Value": datetime.now(timezone.utc).isoformat()},
        {"Metric": "Task records matched", "Value": len(combined)},
        {"Metric": "Unique task groups", "Value": total_groups},
        {"Metric": "First-try success", "Value": first_try},
        {"Metric": "Succeeded after retry", "Value": retry_success},
        {"Metric": "Failed permanently", "Value": permanent_fail},
        {"Metric": "Still open", "Value": open_groups},
        {"Metric": "First-try success rate", "Value": f"{success_rate:.1f}%"},
    ]

    content = [
        f"# Sprint {sprint} Scorecard",
        "",
        render_table(summary_rows, ["Metric", "Value"]),
        "",
        "## Task Groups",
        "",
        render_table(
            details,
            [
                "title",
                "attempts",
                "root_task_id",
                "first_task_id",
                "latest_task_id",
                "latest_status",
                "outcome",
            ],
        ),
        "",
        "## Raw Matched Tasks",
        "",
        render_table(
            combined,
            ["id", "title", "status", "from_agent", "to_agent", "session_ref", "created_at"],
        ),
        "",
    ]

    out_path.write_text("\n".join(content))
    print(out_path)


main()
PY

echo "wrote $OUT_FILE"
