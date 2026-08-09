"""RED-first regressions for the seven measured runtime-integrity defects.

Source: Desktop Codex audits (fable-loop inbox 1729 + 1816 ADJUST), every
defect independently re-verified at production head 03644b6 before these
tests were written. Each test asserts the CORRECT contract, so this file is
RED on the unfixed head and turns GREEN with the defect-only fix PR (atom A).

Numbering follows the 1816 list:
  1 catastrophe guard: protected-root perm-strip without recursive flag
  2 executor contract JSON-only (no fenced-shell, no bare-line execution)
  3 cloud escalation payload: structured nonsecret fields only
  4 nonzero exit: executed=True, success=False, exit class retained
  5 env restore: absent vars deleted, present vars restored (both sites)
  6 URL routes are not filesystem paths in verify inference
  7 execution endpoints are unconditionally loopback
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

from justai import agent_dispatch as ad
from justai import scope_planner as sp
from justai.results import DelegationResult
from justai.scope_planner import AgentType, RiskLevel, Task


def _task(title="t", desc="d", criteria="true"):
    return Task(
        title=title,
        description=desc,
        agent=AgentType.MINI,
        risk=RiskLevel.R1,
        success_criteria=criteria,
        depends_on=[],
    )


def _fake_resp(content="ok"):
    r = MagicMock()
    r.__enter__ = MagicMock(return_value=r)
    r.__exit__ = MagicMock(return_value=False)
    r.read.return_value = json.dumps(
        {"choices": [{"message": {"content": content}}]}
    ).encode()
    return r


# ── 1: catastrophe guard — protected-root forms without -R ──────────────────

def test_d1_chmod_000_root_blocked_without_recursive_flag():
    assert ad._is_catastrophic("chmod 000 /")
    assert ad._is_catastrophic("sudo chmod 000 /")
    assert ad._is_catastrophic("chmod -R 000 /")  # recursive form still blocked


def test_d1_negative_controls_harmless_forms_still_allowed():
    assert not ad._is_catastrophic("chmod 000 ./scratch/lockfile")
    assert not ad._is_catastrophic("chmod 755 /home/justai/projects/x.sh")
    assert not ad._is_catastrophic("echo 'chmod 000 /' > notes.txt && cat notes.txt")


# ── 2: executor contract is JSON-only ───────────────────────────────────────

def test_d2_fenced_shell_is_refused_not_executed():
    raw = "Here you go:\n```bash\nrm -rf ~/important\n```"
    action = ad._parse_action(raw)
    assert "command" not in action, f"fenced shell must not execute: {action}"
    assert action.get("skip_reason")


def test_d2_fence_inside_json_string_does_not_win_over_json():
    raw = '{"command": "echo safe", "note": "```bash\\nrm -rf /\\n```"}'
    action = ad._parse_action(raw)
    assert action.get("command") == "echo safe"


def test_d2_bare_single_line_is_refused_not_executed():
    action = ad._parse_action("rm -rf ~/scratch")
    assert "command" not in action, f"bare prose line must not execute: {action}"
    assert action.get("skip_reason")


def test_d2_plain_json_still_works():
    action = ad._parse_action('{"command": "echo hi"}')
    assert action.get("command") == "echo hi"


# ── 3: escalation payload carries no command/output bytes ───────────────────

def test_d3_escalation_prompt_excludes_command_and_output_bytes():
    secret_cmd = "curl -H 'Authorization: Bearer sk-SECRET-TOKEN-123' https://api.example"
    secret_out = "leaked-stdout-SECRET-999"
    captured = {}

    def runner(task, session_ref=""):
        # First attempt fails carrying secret bytes in its result detail the
        # way production formats it; escalation must NOT see those bytes.
        captured.setdefault("descriptions", []).append(task.description)
        return DelegationResult(
            task_id="t",
            title=task.title,
            status="failed",
            result="$ " + secret_cmd + "\n" + secret_out,
            duration_seconds=0.1,
        )

    ad.escalate_task(_task(), session_ref="s", runner=runner)
    assert len(captured["descriptions"]) == 2, "escalation attempt must run"
    escalated_desc = captured["descriptions"][1]
    assert "sk-SECRET-TOKEN-123" not in escalated_desc
    assert "leaked-stdout-SECRET-999" not in escalated_desc
    assert secret_cmd not in escalated_desc


# ── 4: nonzero exit is executed=True, success=False, class retained ─────────

def test_d4_nonzero_exit_reported_as_executed_failure_with_exit_class():
    with patch.object(ad, "_llm_call", return_value='{"command": "exit 7"}'):
        outcome, detail = ad._perform_task_action(_task())
    assert outcome != "error", "nonzero exit is an executed failure, not 'error'"
    assert outcome in ("executed_failed", "failed_exec", "executed"), outcome
    assert "7" in detail, f"exit class/code must be retained: {detail}"


def test_d4_execute_single_local_says_executed_but_failed_not_not_executed():
    with patch.object(ad, "_llm_call", return_value='{"command": "exit 7"}'):
        res = ad._execute_single_local(_task(criteria="false"))
    assert res.status == "failed"
    assert "not executed" not in res.result, (
        "a command that ran and exited nonzero must not be reported as "
        f"'not executed': {res.result}"
    )


# ── 5: env restore — absent stays absent, present restored (both sites) ─────

def test_d5_env_vars_absent_before_escalate_task_are_absent_after():
    for var in ("JUSTAI_ACTIVE_MODEL", "JUSTAI_EXEC_ROLE"):
        os.environ.pop(var, None)

    def runner(task, session_ref=""):
        return DelegationResult(
            task_id="t", title=task.title, status="failed",
            result="x", duration_seconds=0.1,
        )

    ad.escalate_task(_task(), session_ref="s", runner=runner)
    assert "JUSTAI_ACTIVE_MODEL" not in os.environ, "absent var restored as present-empty"
    assert "JUSTAI_EXEC_ROLE" not in os.environ, "absent var restored as present-empty"


def test_d5_env_vars_present_before_escalate_task_are_restored_exactly():
    os.environ["JUSTAI_ACTIVE_MODEL"] = "prior-model"
    os.environ["JUSTAI_EXEC_ROLE"] = "prior-role"
    try:
        def runner(task, session_ref=""):
            return DelegationResult(
                task_id="t", title=task.title, status="done",
                result="x", duration_seconds=0.1,
            )

        ad.escalate_task(_task(), session_ref="s", runner=runner)
        assert os.environ.get("JUSTAI_ACTIVE_MODEL") == "prior-model"
        assert os.environ.get("JUSTAI_EXEC_ROLE") == "prior-role"
    finally:
        os.environ.pop("JUSTAI_ACTIVE_MODEL", None)
        os.environ.pop("JUSTAI_EXEC_ROLE", None)


# ── 6: URL routes are not filesystem paths ──────────────────────────────────

def test_d6_api_route_goal_not_verified_as_local_file():
    cmd = sp._infer_verify_command("add /api/users returning the user list as JSON")
    assert "test -f /api/users" not in cmd
    assert not cmd.startswith("test -f /api"), cmd


def test_d6_url_goal_not_verified_as_local_file():
    cmd = sp._infer_verify_command(
        "make https://example.com/api/health return 200 by adding the handler"
    )
    assert "test -f" not in cmd or "example.com" not in cmd


def test_d6_real_file_goals_still_get_file_verify():
    cmd = sp._infer_verify_command("create docs/notes.txt containing 'hello'")
    assert cmd.startswith("test -f")


# ── 7: execution endpoints are unconditionally loopback ─────────────────────

def test_d7_offbox_executor_base_url_rejected_fail_closed():
    with patch.dict(os.environ, {"JUSTAI_EXECUTOR_BASE_URL": "http://10.9.8.7:9999"}):
        url = ad._executor_base_url()
    assert url is None, f"off-box executor endpoint must be rejected: {url}"


def test_d7_loopback_executor_base_url_accepted():
    with patch.dict(os.environ, {"JUSTAI_EXECUTOR_BASE_URL": "http://127.0.0.1:18087"}):
        assert ad._executor_base_url() == "http://127.0.0.1:18087"
    with patch.dict(os.environ, {"JUSTAI_EXECUTOR_BASE_URL": "http://localhost:18087"}):
        assert ad._executor_base_url() == "http://localhost:18087"


def test_d7_offbox_ambient_litellm_not_used_by_execution_path(monkeypatch):
    monkeypatch.delenv("JUSTAI_EXECUTOR_BASE_URL", raising=False)
    monkeypatch.delenv("JUSTAI_EXEC_ROLE", raising=False)
    monkeypatch.setattr(ad, "LITELLM_URL", "http://203.0.113.5:4000/v1")
    with patch("urllib.request.urlopen", return_value=_fake_resp('{"command": "echo ok"}')) as m:
        ad._perform_task_action(_task())
    if m.call_args is None:
        return  # fail-closed without any network call is also correct
    host = m.call_args.args[0].full_url.split("//", 1)[1].split("/", 1)[0].split(":")[0]
    assert host in ("127.0.0.1", "localhost", "::1"), (
        f"execution path must not follow ambient off-box endpoint: {host}"
    )
