#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUDIT_SCRIPT="$ROOT/scripts/model_audit.sh"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

prefs="$tmpdir/model_preferences.yaml"
mini_sh="$tmpdir/mini_local_cloud.sh"
mini_yaml="$tmpdir/mini_cloud.yaml"
codex_sh="$tmpdir/codex_delegate.sh"
openfang="$tmpdir/config.toml"

cat > "$prefs" <<'YAML'
mini_model: gpt-5.3-codex
codex_delegate_model: gpt-5.4
openfang_default: claude-opus-4-6
max_sonnet_count: 1
YAML

cat > "$mini_sh" <<'EOF1'
#!/usr/bin/env bash
MODEL="gpt-4o-mini"
echo "$MODEL"
EOF1

cat > "$mini_yaml" <<'EOF2'
model: gpt-4.1
EOF2

cat > "$codex_sh" <<'EOF3'
#!/usr/bin/env bash
DELEGATE_MODEL="gpt-4.1"
echo "$DELEGATE_MODEL"
EOF3

cat > "$openfang" <<'EOF4'
default = "claude-3-5-sonnet"
fallback_models = ["claude-3-5-sonnet","claude-3-7-sonnet","gpt-4o"]
EOF4

chmod +x "$mini_sh" "$codex_sh"

set +e
out_fail="$(
  MODEL_PREFS_CONFIG="$prefs" \
  MINI_LOCAL_CLOUD_SH="$mini_sh" \
  MINI_CLOUD_YAML="$mini_yaml" \
  CODEX_DELEGATE_SH="$codex_sh" \
  OPENFANG_CONFIG="$openfang" \
  "$AUDIT_SCRIPT" 2>&1
)"
rc_fail=$?
set -e

if [[ "$rc_fail" -eq 0 ]]; then
  echo "Expected initial audit to FAIL but got rc=0"
  echo "$out_fail"
  exit 1
fi

echo "$out_fail" | grep -q "FAIL"

set +e
out_json_fail="$(
  MODEL_PREFS_CONFIG="$prefs" \
  MINI_LOCAL_CLOUD_SH="$mini_sh" \
  MINI_CLOUD_YAML="$mini_yaml" \
  CODEX_DELEGATE_SH="$codex_sh" \
  OPENFANG_CONFIG="$openfang" \
  "$AUDIT_SCRIPT" --json 2>&1
)"
rc_json_fail=$?
set -e

if [[ "$rc_json_fail" -eq 0 ]]; then
  echo "Expected JSON audit to FAIL before fix but got rc=0"
  echo "$out_json_fail"
  exit 1
fi

echo "$out_json_fail" | grep -q '"summary":"FAIL"'

set +e
out_fix="$(
  MODEL_PREFS_CONFIG="$prefs" \
  MINI_LOCAL_CLOUD_SH="$mini_sh" \
  MINI_CLOUD_YAML="$mini_yaml" \
  CODEX_DELEGATE_SH="$codex_sh" \
  OPENFANG_CONFIG="$openfang" \
  "$AUDIT_SCRIPT" --fix 2>&1
)"
rc_fix=$?
set -e

if [[ "$rc_fix" -ne 0 ]]; then
  echo "Expected --fix run to PASS but got rc=$rc_fix"
  echo "$out_fix"
  exit 1
fi

echo "$out_fix" | grep -q "PASS"

set +e
out_pass="$(
  MODEL_PREFS_CONFIG="$prefs" \
  MINI_LOCAL_CLOUD_SH="$mini_sh" \
  MINI_CLOUD_YAML="$mini_yaml" \
  CODEX_DELEGATE_SH="$codex_sh" \
  OPENFANG_CONFIG="$openfang" \
  "$AUDIT_SCRIPT" --json 2>&1
)"
rc_pass=$?
set -e

if [[ "$rc_pass" -ne 0 ]]; then
  echo "Expected post-fix JSON audit to PASS but got rc=$rc_pass"
  echo "$out_pass"
  exit 1
fi

echo "$out_pass" | grep -q '"summary":"PASS"'
grep -q "gpt-5.3-codex" "$mini_sh"
grep -q "gpt-5.3-codex" "$mini_yaml"
grep -q "gpt-5.4" "$codex_sh"
grep -q 'default = "claude-opus-4-6"' "$openfang"

sonnet_count="$(grep -oi 'sonnet' "$openfang" | wc -l | tr -d ' ')"
if [[ "$sonnet_count" -gt 1 ]]; then
  echo "Expected sonnet count <= 1 after fix, got $sonnet_count"
  cat "$openfang"
  exit 1
fi

echo "test_model_audit.sh: PASS"
