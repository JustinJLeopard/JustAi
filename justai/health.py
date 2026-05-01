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


def _is_spacetimedb_response(status: int, headers: dict[str, str], body: bytes) -> bool:
    body_text = body.decode(errors="ignore").lower()
    if "spacetimedb" in body_text:
        return True

    data = _json_body(body)
    if not isinstance(data, dict):
        return False

    database_keys = {"database_identity", "owner_identity", "host_type", "initial_program"}
    if database_keys.issubset(data.keys()):
        return True

    # SpacetimeDB reports API errors as JSON variants. A 404/400 JSON response
    # from a /v1/database probe still proves this is the SpacetimeDB API, while
    # an arbitrary HTML 200/404 from another service does not.
    known_error_variants = {
        "DatabaseNotFound",
        "PermissionDenied",
        "NoSuchDatabase",
        "NotFound",
        "InvalidDatabaseIdentity",
        "error",
    }
    return status in (400, 401, 403, 404, 405) and any(k in data for k in known_error_variants)


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


def check_spacetimedb() -> ServiceStatus:
    """Check SpacetimeDB is reachable on :3000 and exposes its HTTP API."""
    url = os.environ.get("SPACETIMEDB_URL", "http://127.0.0.1:3000")
    probe_url = f"{url.rstrip('/')}/v1/database/__justai_health_probe__"
    try:
        req = urllib.request.Request(probe_url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            status, headers, body = _read_response(resp)
            if _is_spacetimedb_response(status, headers, body):
                return ServiceStatus("SpacetimeDB", url, True, "database API reachable")
            return ServiceStatus("SpacetimeDB", url, False, "responded but not SpacetimeDB")
    except urllib.error.HTTPError as e:
        body = e.read()
        headers = {k.lower(): v for k, v in dict(e.headers).items()}
        if _is_spacetimedb_response(e.code, headers, body):
            return ServiceStatus(
                "SpacetimeDB", url, True, f"database API reachable (http {e.code})"
            )
        return ServiceStatus("SpacetimeDB", url, False, "responded but not SpacetimeDB")
    except Exception as e:
        return ServiceStatus("SpacetimeDB", url, False, str(e)[:120])


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
    return [check_litellm(), check_spacetimedb(), check_memory()]


def print_preflight(statuses: list[ServiceStatus]) -> bool:
    """Print preflight results. Returns True if all critical services are up."""
    print("  Service preflight:")
    all_ok = True
    for s in statuses:
        icon = "✓" if s.ok else "✗"
        print(f"    {icon} {s.name:<20} {s.url:<35} {s.detail}")
        if not s.ok and s.name == "LiteLLM":
            all_ok = False  # LiteLLM is critical — planner/reviewer need it
    print()
    return all_ok
