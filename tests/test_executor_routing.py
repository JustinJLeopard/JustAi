"""Executor routing (JUSTAI_EXECUTOR_BASE_URL) — default-off, mini/executor only.

Covers Desktop Codex's review contract: absent == byte-for-byte equivalent;
present routes ONLY mini/executor calls; escalation + pseudocode stay on the
primary LITELLM_BASE_URL; endpoint chosen by call site (not model text);
fail-closed URL shape. Deliberately narrow — no adversarial family.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from justai import agent_dispatch as ad

EXEC = "http://127.0.0.1:18087"


def _fake_resp():
    r = MagicMock()
    r.__enter__ = MagicMock(return_value=r)
    r.__exit__ = MagicMock(return_value=False)
    r.read.return_value = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
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
