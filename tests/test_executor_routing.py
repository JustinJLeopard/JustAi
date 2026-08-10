"""Executor routing (JUSTAI_EXECUTOR_BASE_URL) — default-off, mini/executor only.

Covers Desktop Codex's review contract: absent == byte-for-byte equivalent;
present routes ONLY mini/executor calls; escalation + pseudocode stay on the
primary LITELLM_BASE_URL; endpoint chosen by call site (not model text);
fail-closed URL shape. Deliberately narrow — no adversarial family.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

from justai import agent_dispatch as ad

EXEC = "http://127.0.0.1:18087"


def _fake_resp():
    r = MagicMock()
    r.__enter__ = MagicMock(return_value=r)
    r.__exit__ = MagicMock(return_value=False)
    r.read.return_value = json.dumps(
        {"choices": [{"message": {"content": json.dumps({"command": "true"})}}]}
    ).encode()
    return r


def _url_of(call):
    with patch("urllib.request.urlopen", return_value=_fake_resp()) as m:
        call()
    return m.call_args.args[0].full_url


def test_absent_is_equivalent_to_primary(monkeypatch):
    monkeypatch.delenv("JUSTAI_EXECUTOR_BASE_URL", raising=False)
    p = ad.AgentDispatchPipeline()
    assert _url_of(lambda: p._call_mini("x")) == f"{ad.LITELLM_URL}/chat/completions"


def test_present_routes_mini_to_executor(monkeypatch):
    monkeypatch.setenv("JUSTAI_EXECUTOR_BASE_URL", EXEC)
    p = ad.AgentDispatchPipeline()
    assert _url_of(lambda: p._call_mini("x")) == f"{EXEC}/chat/completions"


def test_escalation_stays_primary_when_executor_set(monkeypatch):
    monkeypatch.setenv("JUSTAI_EXECUTOR_BASE_URL", EXEC)
    p = ad.AgentDispatchPipeline()
    assert _url_of(lambda: p._call_escalation("x")) == f"{ad.LITELLM_URL}/chat/completions"


def test_pseudocode_stays_primary_when_executor_set(monkeypatch):
    monkeypatch.setenv("JUSTAI_EXECUTOR_BASE_URL", EXEC)
    p = ad.AgentDispatchPipeline()
    assert _url_of(lambda: p._phase_pseudocode("goal", "spec")) == f"{ad.LITELLM_URL}/chat/completions"


def test_url_shape_strips_v1_and_trailing_slash(monkeypatch):
    monkeypatch.setenv("JUSTAI_EXECUTOR_BASE_URL", f"{EXEC}/v1/")
    assert ad._executor_base_url() == EXEC


def test_empty_or_whitespace_is_none_fail_closed(monkeypatch):
    monkeypatch.setenv("JUSTAI_EXECUTOR_BASE_URL", "   ")
    assert ad._executor_base_url() is None
    monkeypatch.delenv("JUSTAI_EXECUTOR_BASE_URL", raising=False)
    assert ad._executor_base_url() is None


def test_mini_model_env_remains_the_executor_model_selector():
    """The default pipeline config must honor JUSTAI_MINI_MODEL at import."""
    env = os.environ.copy()
    env["JUSTAI_MINI_MODEL"] = "qwen3-coder-next-mxfp4"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from justai.agent_dispatch import AgentDispatchConfig; "
                "print(AgentDispatchConfig().mini_model)"
            ),
        ],
        capture_output=True,
        check=True,
        env=env,
        text=True,
    )
    assert probe.stdout.strip() == "qwen3-coder-next-mxfp4"


def test_local_escalation_uses_primary_not_executor(monkeypatch):
    """Regression: through escalate_task + the real _execute_single_local runner,
    the first (mini) attempt routes to the executor endpoint, but the escalation
    attempt uses the primary endpoint. The role is set explicitly by
    escalate_task per attempt, never inferred from model text.

    test_escalation_stays_primary_when_executor_set covers only
    AgentDispatchPipeline._call_escalation; this covers the local-execution
    fallback that Desktop Codex flagged (both attempts previously hit 18087).
    """
    from justai.scope_planner import AgentType, RiskLevel, Task

    monkeypatch.setenv("JUSTAI_EXECUTOR_BASE_URL", EXEC)
    # Force the first attempt to fail so escalation runs; keep it hermetic
    # (no real shell execution / verification).
    monkeypatch.setattr(
        ad, "_run_local_command_result", lambda *a, **k: ("fail", "forced")
    )
    monkeypatch.setattr(
        ad, "_verify_chunk", lambda chunk: ad._Verification(False, "n/a", "fail", True)
    )

    task = Task(
        title="t",
        description="d",
        agent=AgentType.MINI,
        risk=RiskLevel.R1,
        success_criteria="true",
        depends_on=[],
    )

    with patch("urllib.request.urlopen", return_value=_fake_resp()) as m:
        ad.escalate_task(task, session_ref="s", runner=ad._execute_single_local)

    urls = [c.args[0].full_url for c in m.call_args_list]
    assert urls == [
        f"{EXEC}/chat/completions",
        f"{ad.LITELLM_URL}/chat/completions",
    ], urls
