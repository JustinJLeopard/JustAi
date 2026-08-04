#!/usr/bin/env python3
"""
JustAi — Service Health Preflight
===================================
Quick checks for required services before running the pipeline.
Returns structured results so the orchestrator can degrade gracefully.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class ServiceStatus:
    name: str
    url: str
    ok: bool
    detail: str = ""


def _read_response(resp) -> tuple[int, dict[str, str], bytes]:
    headers = {k.lower(): v for k, v in dict(getattr(resp, "headers", {})).items()}
    return getattr(resp, "status", 0), headers, resp.read()


def _json_body(body: bytes) -> dict | list | None:
    try:
        return json.loads(body.decode() or "{}")
    except Exception:
        return None


def _is_litellm_response(status: int, headers: dict[str, str], body: bytes) -> bool:
    data = _json_body(body)
    if status == 200 and isinstance(data, dict) and isinstance(data.get("data"), list):
        return True

    body_text = body.decode(errors="ignore").lower()
    content_type = headers.get("content-type", "").lower()
    if status in (401, 403) and "json" in content_type:
        return any(token in body_text for token in ("litellm", "api key", "auth"))
    return False


def check_litellm() -> ServiceStatus:
    """Check LiteLLM proxy is reachable and speaks the OpenAI models API."""
    url = (
        os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/").removesuffix("/v1")
    )
    models_url = f"{url}/v1/models"
    try:
        req = urllib.request.Request(
            models_url,
            headers={"Authorization": f"Bearer {os.environ.get('LITELLM_KEY', '')}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            status, headers, body = _read_response(resp)
            if _is_litellm_response(status, headers, body):
                return ServiceStatus("LiteLLM", url, True, "models API reachable")
            return ServiceStatus("LiteLLM", url, False, "responded but not LiteLLM")
    except urllib.error.HTTPError as e:
        body = e.read()
        headers = {k.lower(): v for k, v in dict(e.headers).items()}
        if _is_litellm_response(e.code, headers, body):
            return ServiceStatus("LiteLLM", url, True, f"models API reachable (http {e.code})")
        return ServiceStatus("LiteLLM", url, False, f"http {e.code}")
    except Exception as e:
        return ServiceStatus("LiteLLM", url, False, str(e)[:120])


def check_safe_mini_boundary() -> ServiceStatus:
    """Report whether a concrete safe-mini runner is integrated."""
    try:
        from justai.runner_protocol import AgentRunner

        _ = AgentRunner
        return ServiceStatus(
            "safe-mini boundary",
            "justai.runner_protocol",
            False,
            "protocol present; concrete runner not integrated",
        )
    except Exception as e:
        return ServiceStatus("safe-mini boundary", "justai.runner_protocol", False, str(e)[:120])


def check_memory() -> ServiceStatus:
    """Check claude-flow MCP memory service."""
    url = os.environ.get("CLAUDE_FLOW_MCP_URL", "http://127.0.0.1:3100")
    try:
        req = urllib.request.Request(f"{url}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            status, _headers, body = _read_response(resp)
            data = _json_body(body)
            ok = status == 200 and isinstance(data, dict) and data.get("status") == "ok"
            return ServiceStatus(
                "claude-flow MCP",
                url,
                ok,
                "healthy" if ok else "responded but health signature invalid",
            )
    except Exception as e:
        return ServiceStatus("claude-flow MCP", url, False, str(e)[:120])


def check_swarm() -> ServiceStatus:
    """Check claude-flow swarm status via MCP."""
    url = os.environ.get("JUSTAI_MCP_URL", "http://127.0.0.1:3100")
    rpc_url = f"{url}/rpc"
    try:
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "swarm_status", "arguments": {}},
            }
        ).encode()
        req = urllib.request.Request(
            rpc_url, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            content = data.get("result", {}).get("content", [])
            for item in content:
                if item.get("type") == "text":
                    info = json.loads(item["text"])
                    status = info.get("status", "unknown")
                    agents = info.get("agentCount", 0)
                    return ServiceStatus("Swarm", url, True, f"{status} ({agents} agents)")
        return ServiceStatus("Swarm", url, True, "reachable")
    except Exception as e:
        return ServiceStatus("Swarm", url, False, str(e)[:120])


def preflight() -> list[ServiceStatus]:
    """Run all service checks. Returns list of statuses."""
    return [check_litellm(), check_safe_mini_boundary(), check_memory()]


#: The probe that gates model-backed planning. Without it the planner and
#: reviewer fall back to heuristics, so planning degrades but stays usable.
PLANNING_SERVICE = "LiteLLM"

#: The probe that gates task execution. No concrete runner is integrated, so
#: this is currently always down — which is the honest reading, not a bug.
EXECUTION_SERVICE = "safe-mini boundary"


@dataclass
class Readiness:
    """What the control plane can actually do right now.

    Readiness is deliberately not one bit. Collapsing it lets a caller read
    "planning works" as "the whole system works" — which is how `justai status`
    came to exit 0 while the execution probe was down and the API's own
    ``all_ok`` was false.
    """

    statuses: list[ServiceStatus]
    planning_ready: bool
    execution_ready: bool
    all_ok: bool


def readiness(statuses: list[ServiceStatus] | None = None) -> Readiness:
    """Derive explicit readiness from probe results.

    Args:
        statuses: probe results; runs :func:`preflight` when omitted.
    """
    statuses = list(statuses) if statuses is not None else preflight()
    by_name = {s.name: s for s in statuses}
    planning = by_name.get(PLANNING_SERVICE)
    execution = by_name.get(EXECUTION_SERVICE)

    return Readiness(
        statuses=statuses,
        planning_ready=bool(planning and planning.ok),
        execution_ready=bool(execution and execution.ok),
        # An empty probe set is not evidence of health. `all(())` is True, and
        # that default would report a system nobody checked as fully ready.
        all_ok=bool(statuses) and all(s.ok for s in statuses),
    )


def print_preflight(statuses: list[ServiceStatus]) -> bool:
    """Print preflight results. Returns whether *planning* can proceed.

    This is the orchestrator's question — "can the planner reach a model, or
    must it fall back to heuristics?" — and not a verdict on the whole system.
    Use :func:`readiness` for that.
    """
    print("  Service preflight:")
    all_ok = True
    for s in statuses:
        icon = "✓" if s.ok else "✗"
        print(f"    {icon} {s.name:<20} {s.url:<35} {s.detail}")
        if not s.ok and s.name == PLANNING_SERVICE:
            all_ok = False  # LiteLLM is critical — planner/reviewer need it
    print()
    return all_ok


def print_readiness(r: Readiness) -> None:
    """Print probe results followed by an explicit capability breakdown."""
    print_preflight(r.statuses)
    print("  Readiness:")
    print(
        f"    planning   {'ready' if r.planning_ready else 'degraded':<12}"
        + (
            "model-backed planning available"
            if r.planning_ready
            else "model routing unreachable; `justai plan` falls back to heuristics"
        )
    )
    print(
        f"    execution  {'ready' if r.execution_ready else 'unavailable':<12}"
        + (
            "an execution backend is integrated"
            if r.execution_ready
            else "no concrete runner is integrated; `justai run` fails closed"
        )
    )
    print(
        f"    overall    {'ready' if r.all_ok else 'not ready':<12}exit 0 requires every probe ok"
    )
    print()
