#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELAY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
JUSTAI_ROOT="${JUSTAI_ROOT:-$(cd "$RELAY_ROOT/.." && pwd)}"
JUSTAI_LOCALMANUS_ROOT="${JUSTAI_LOCALMANUS_ROOT:-$JUSTAI_ROOT/LocalManus}"

CONFIG_PATH="${MODEL_PREFS_CONFIG:-$RELAY_ROOT/config/model_preferences.yaml}"

MINI_LOCAL_CLOUD_SH="${MINI_LOCAL_CLOUD_SH:-$JUSTAI_LOCALMANUS_ROOT/scripts/mini_local_cloud.sh}"
MINI_CLOUD_YAML="${MINI_CLOUD_YAML:-$JUSTAI_LOCALMANUS_ROOT/config/mini_cloud.yaml}"
CODEX_DELEGATE_SH="${CODEX_DELEGATE_SH:-$JUSTAI_LOCALMANUS_ROOT/scripts/codex_delegate.sh}"
OPENFANG_CONFIG="${OPENFANG_CONFIG:-/home/justinleopard/.openfang/config.toml}"

FIX=0
JSON=0

for arg in "$@"; do
  case "$arg" in
    --fix) FIX=1 ;;
    --json) JSON=1 ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--fix] [--json]" >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Config file not found: $CONFIG_PATH" >&2
  exit 1
fi

yaml_get() {
  local key="$1"
  awk -F': *' -v k="$key" '$1==k {print $2}' "$CONFIG_PATH" | head -n1 | sed 's/[[:space:]]*$//' | sed 's/^["'\'']//; s/["'\'']$//'
}

MINI_MODEL="$(yaml_get mini_model)"
CODEX_DELEGATE_MODEL="$(yaml_get codex_delegate_model)"
OPENFANG_DEFAULT="$(yaml_get openfang_default)"
MAX_SONNET_COUNT="$(yaml_get max_sonnet_count)"

if [[ -z "${MINI_MODEL}" || -z "${CODEX_DELEGATE_MODEL}" || -z "${OPENFANG_DEFAULT}" || -z "${MAX_SONNET_COUNT}" ]]; then
  echo "Missing required keys in $CONFIG_PATH" >&2
  exit 1
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

RESULT_FILES=()
RESULT_STATUS=()
RESULT_DETAILS=()

json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\r'/\\r}"
  s="${s//$'\t'/\\t}"
  printf '%s' "$s"
}

add_result() {
  local file="$1"
  local status="$2"
  local detail="$3"
  RESULT_FILES+=("$file")
  RESULT_STATUS+=("$status")
  RESULT_DETAILS+=("$detail")
}

file_contains() {
  local file="$1"
  local needle="$2"
  [[ -f "$file" ]] && grep -qF "$needle" "$file"
}

replace_model_token() {
  local file="$1"
  local expected="$2"
  [[ -f "$file" ]] || return 1
  sed -E -i "s/gpt-[A-Za-z0-9._-]+/${expected}/g" "$file"
}

count_sonnet() {
  local file="$1"
  [[ -f "$file" ]] || { echo 0; return; }
  grep -oi 'sonnet' "$file" | wc -l | tr -d ' '
}

fix_openfang_default() {
  local file="$1"
  local expected="$2"
  [[ -f "$file" ]] || return 1
  if grep -Eq '^[[:space:]]*default[[:space:]]*=' "$file"; then
    sed -E -i "s|^[[:space:]]*default[[:space:]]*=.*$|default = \"${expected}\"|g" "$file"
  else
    printf '\ndefault = "%s"\n' "$expected" >> "$file"
  fi
}

fix_openfang_sonnet_limit() {
  local file="$1"
  local max="$2"
  local replacement="$3"
  [[ -f "$file" ]] || return 1
  python3 - "$file" "$max" "$replacement" <<'PY'
import re, sys
path = sys.argv[1]
max_keep = int(sys.argv[2])
replacement = sys.argv[3]

with open(path, "r", encoding="utf-8") as f:
    text = f.read()

counter = [0]
pattern = re.compile(r"[A-Za-z0-9._-]*sonnet[A-Za-z0-9._-]*", re.IGNORECASE)

def repl(match):
    counter[0] += 1
    if counter[0] <= max_keep:
        return match.group(0)
    return replacement

new_text = pattern.sub(repl, text)

with open(path, "w", encoding="utf-8") as f:
    f.write(new_text)
PY
}

audit_generic_model_file() {
  local file="$1"
  local expected="$2"
  local label="$3"

  if [[ ! -f "$file" ]]; then
    add_result "$file" "FAIL" "$label missing file"
    return
  fi

  if file_contains "$file" "$expected"; then
    add_result "$file" "PASS" "$label contains expected model '$expected'"
  else
    if [[ "$FIX" -eq 1 ]]; then
      replace_model_token "$file" "$expected" || true
      if file_contains "$file" "$expected"; then
        add_result "$file" "PASS" "$label mismatch fixed to '$expected'"
      else
        add_result "$file" "FAIL" "$label mismatch and auto-fix failed (expected '$expected')"
      fi
    else
      add_result "$file" "FAIL" "$label mismatch (expected '$expected')"
    fi
  fi
}

audit_openfang() {
  local file="$1"
  local expected_default="$2"
  local max_sonnet="$3"

  if [[ ! -f "$file" ]]; then
    add_result "$file" "FAIL" "openfang config missing file"
    return
  fi

  local default_ok=0
  local sonnet_ok=0
  local sonnet_count
  sonnet_count="$(count_sonnet "$file")"

  file_contains "$file" "$expected_default" && default_ok=1
  [[ "$sonnet_count" -le "$max_sonnet" ]] && sonnet_ok=1

  if [[ "$default_ok" -eq 1 && "$sonnet_ok" -eq 1 ]]; then
    add_result "$file" "PASS" "default model '$expected_default' found; sonnet count $sonnet_count <= $max_sonnet"
    return
  fi

  if [[ "$FIX" -eq 1 ]]; then
    [[ "$default_ok" -eq 1 ]] || fix_openfang_default "$file" "$expected_default" || true
    [[ "$sonnet_ok" -eq 1 ]] || fix_openfang_sonnet_limit "$file" "$max_sonnet" "$expected_default" || true

    sonnet_count="$(count_sonnet "$file")"
    file_contains "$file" "$expected_default" && default_ok=1 || default_ok=0
    [[ "$sonnet_count" -le "$max_sonnet" ]] && sonnet_ok=1 || sonnet_ok=0

    if [[ "$default_ok" -eq 1 && "$sonnet_ok" -eq 1 ]]; then
      add_result "$file" "PASS" "openfang mismatches fixed; default '$expected_default'; sonnet count $sonnet_count <= $max_sonnet"
    else
      add_result "$file" "FAIL" "openfang mismatch remains (default_ok=$default_ok, sonnet_count=$sonnet_count, max=$max_sonnet)"
    fi
  else
    add_result "$file" "FAIL" "openfang mismatch (need default '$expected_default', sonnet count <= $max_sonnet; found sonnet count $sonnet_count)"
  fi
}

audit_generic_model_file "$MINI_LOCAL_CLOUD_SH" "$MINI_MODEL" "mini_local_cloud.sh"
audit_generic_model_file "$MINI_CLOUD_YAML" "$MINI_MODEL" "mini_cloud.yaml"
audit_generic_model_file "$CODEX_DELEGATE_SH" "$CODEX_DELEGATE_MODEL" "codex_delegate.sh"
audit_openfang "$OPENFANG_CONFIG" "$OPENFANG_DEFAULT" "$MAX_SONNET_COUNT"

all_pass=1
for s in "${RESULT_STATUS[@]}"; do
  [[ "$s" == "PASS" ]] || all_pass=0
done

if [[ "$JSON" -eq 1 ]]; then
  printf '{'
  printf '"config":"%s",' "$(json_escape "$CONFIG_PATH")"
  printf '"results":['
  for i in "${!RESULT_FILES[@]}"; do
    [[ "$i" -gt 0 ]] && printf ','
    printf '{'
    printf '"file":"%s",' "$(json_escape "${RESULT_FILES[$i]}")"
    printf '"status":"%s",' "$(json_escape "${RESULT_STATUS[$i]}")"
    printf '"detail":"%s"' "$(json_escape "${RESULT_DETAILS[$i]}")"
    printf '}'
  done
  printf '],'
  if [[ "$all_pass" -eq 1 ]]; then
    printf '"summary":"PASS"'
  else
    printf '"summary":"FAIL"'
  fi
  printf '}\n'
else
  for i in "${!RESULT_FILES[@]}"; do
    if [[ "${RESULT_STATUS[$i]}" == "PASS" ]]; then
      printf "${GREEN}PASS${NC} %s - %s\n" "${RESULT_FILES[$i]}" "${RESULT_DETAILS[$i]}"
    else
      printf "${RED}FAIL${NC} %s - %s\n" "${RESULT_FILES[$i]}" "${RESULT_DETAILS[$i]}"
    fi
  done
  if [[ "$all_pass" -eq 1 ]]; then
    printf "${GREEN}Overall: PASS${NC}\n"
  else
    printf "${YELLOW}Overall: FAIL${NC}\n"
  fi
fi

if [[ "$all_pass" -eq 1 ]]; then
  exit 0
else
  exit 1
fi
