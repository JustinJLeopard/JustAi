#!/usr/bin/env bash
# preflight_mini — LocalManus cloud-mini prerequisite check.
# Exit 0 when checks only produce PASS/WARN. Exit nonzero only for hard local
# failures that block the cloud-mini path.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"

if [[ -n "${LOCALMANUS_ROOT:-}" && -d "${LOCALMANUS_ROOT}" ]]; then
    LOCALMANUS_ROOT="$(cd -- "$LOCALMANUS_ROOT" && pwd -P)"
else
    LOCALMANUS_ROOT="$REPO_ROOT"
fi

pass_count=0
warn_count=0
fail_count=0

pass() {
    printf '[PASS] %s\n' "$1"
    pass_count=$((pass_count + 1))
}

warn() {
    printf '[WARN] %s\n' "$1"
    warn_count=$((warn_count + 1))
}

fail() {
    printf '[FAIL] %s\n' "$1"
    fail_count=$((fail_count + 1))
}

pass "Resolved LOCALMANUS_ROOT: $LOCALMANUS_ROOT"

mini_launcher="$LOCALMANUS_ROOT/scripts/mini_local_cloud.sh"
if [[ -x "$mini_launcher" ]]; then
    pass "Cloud mini launcher ready: $mini_launcher"
else
    fail "Cloud mini launcher missing or not executable: $mini_launcher"
fi

seed_config="$LOCALMANUS_ROOT/config/mini_cloud.yaml"
if grep -Eq 'api_key:\s*sk-[A-Za-z0-9_-]+' "$mini_launcher" "$seed_config" 2>/dev/null; then
    warn "Hardcoded API key material detected in wrapper or seed config; prefer env/.env as the canonical source"
else
    pass "No hardcoded API key material detected in wrapper or seed config"
fi

if mini_path="$(command -v mini 2>/dev/null)"; then
    pass "mini binary on PATH: $mini_path"
else
    fail "mini binary not found on PATH"
fi

runtime_openai_api_key_present=0
runtime_gameron_api_key_present=0
runtime_openai_base_url_present=0
runtime_openai_api_key="${OPENAI_API_KEY:-}"
runtime_gameron_api_key="${GAMERON_API_KEY:-}"
runtime_openai_base_url="${OPENAI_BASE_URL:-}"

if [[ ${OPENAI_API_KEY+x} ]]; then
    runtime_openai_api_key_present=1
fi
if [[ ${GAMERON_API_KEY+x} ]]; then
    runtime_gameron_api_key_present=1
fi
if [[ ${OPENAI_BASE_URL+x} ]]; then
    runtime_openai_base_url_present=1
fi

for env_file in "$LOCALMANUS_ROOT/.env" "$LOCALMANUS_ROOT/.env.gameron"; do
    if [[ -f "$env_file" ]]; then
        # shellcheck disable=SC1090
        source "$env_file"
    fi
done

if [[ "$runtime_openai_api_key_present" -eq 1 ]]; then
    OPENAI_API_KEY="$runtime_openai_api_key"
fi
if [[ "$runtime_gameron_api_key_present" -eq 1 ]]; then
    GAMERON_API_KEY="$runtime_gameron_api_key"
fi
if [[ "$runtime_openai_base_url_present" -eq 1 ]]; then
    OPENAI_BASE_URL="$runtime_openai_base_url"
fi

api_key_source=""
api_key_value=""
if [[ "$runtime_openai_api_key_present" -eq 1 && -n "$runtime_openai_api_key" ]]; then
    api_key_source="runtime OPENAI_API_KEY"
    api_key_value="$runtime_openai_api_key"
elif [[ "$runtime_gameron_api_key_present" -eq 1 && -n "$runtime_gameron_api_key" ]]; then
    api_key_source="runtime GAMERON_API_KEY"
    api_key_value="$runtime_gameron_api_key"
elif [[ -n "${OPENAI_API_KEY:-}" ]]; then
    api_key_source="dotenv OPENAI_API_KEY"
    api_key_value="$OPENAI_API_KEY"
elif [[ -n "${GAMERON_API_KEY:-}" ]]; then
    api_key_source="dotenv GAMERON_API_KEY"
    api_key_value="$GAMERON_API_KEY"
fi

if [[ -n "$api_key_source" ]]; then
    pass "API key source available via $api_key_source"
else
    fail "No usable API key found (expected OPENAI_API_KEY or GAMERON_API_KEY in env or .env)"
fi

base_url="${OPENAI_BASE_URL:-https://api.gameron.me/v1}"
models_url="${base_url%/}/models"
if [[ -n "$api_key_value" ]]; then
    if curl -fsS --connect-timeout 3 --max-time 6 \
        -H "Authorization: Bearer $api_key_value" \
        "$models_url" >/dev/null 2>&1; then
        pass "Gameron/OpenAI-compatible endpoint reachable: $models_url"
    else
        warn "Gameron/OpenAI-compatible endpoint not reachable: $models_url"
    fi
else
    warn "Skipped endpoint check because no API key was found"
fi

honcho_setup="$LOCALMANUS_ROOT/memory/honcho_setup.py"
if [[ -f "$honcho_setup" ]]; then
    if python3 "$honcho_setup" --check >/dev/null 2>&1; then
        pass "Honcho available"
    else
        warn "Honcho check failed"
    fi
else
    warn "Honcho helper missing: $honcho_setup"
fi

printf 'Summary: %d PASS, %d WARN, %d FAIL\n' "$pass_count" "$warn_count" "$fail_count"

if [[ "$fail_count" -gt 0 ]]; then
    exit 1
fi
