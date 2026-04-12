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
import urllib.request
from dataclasses import dataclass


@dataclass
class ServiceStatus:
    name: str
    url: str
    ok: bool
    detail: str = ""


def check_litellm() -> ServiceStatus:
    """Check LiteLLM proxy is reachable."""
    url = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/").removesuffix("/v1")
    health_url = f"{url}/health"
    try:
        req = urllib.request.Request(health_url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return ServiceStatus("LiteLLM", url, resp.status == 200, "healthy")
    except urllib.error.HTTPError as e:
        # 401/403 means LiteLLM is up but health endpoint needs auth — still reachable
        if e.code in (401, 403):
            return ServiceStatus("LiteLLM", url, True, f"reachable (http {e.code})")
        return ServiceStatus("LiteLLM", url, False, f"http {e.code}")
    except Exception as e:
        return ServiceStatus("LiteLLM", url, False, str(e)[:120])


def check_spacetimedb() -> ServiceStatus:
    """Check SpacetimeDB is reachable on :3000."""
    url = os.environ.get("SPACETIMEDB_URL", "http://127.0.0.1:3000")
    try:
        req = urllib.request.Request(f"{url}/database/ping", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return ServiceStatus("SpacetimeDB", url, True, "reachable")
    except urllib.error.HTTPError as e:
        # SpacetimeDB returns various codes but if we get a response, it's up
        return ServiceStatus("SpacetimeDB", url, True, f"http {e.code}")
    except Exception as e:
        return ServiceStatus("SpacetimeDB", url, False, str(e)[:120])


def check_memory() -> ServiceStatus:
    """Check claude-flow MCP memory service."""
    url = os.environ.get("CLAUDE_FLOW_MCP_URL", "http://127.0.0.1:3100")
    try:
        req = urllib.request.Request(f"{url}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return ServiceStatus("claude-flow MCP", url, True, "healthy")
    except Exception as e:
        return ServiceStatus("claude-flow MCP", url, False, str(e)[:120])


def check_swarm() -> ServiceStatus:
    """Check claude-flow swarm status via MCP."""
    url = os.environ.get("JUSTAI_MCP_URL", "http://127.0.0.1:3100")
    rpc_url = f"{url}/rpc"
    try:
        payload = json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": "swarm_status", "arguments": {}},
        }).encode()
        req = urllib.request.Request(rpc_url, data=payload, headers={"Content-Type": "application/json"})
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
