#!/usr/bin/env python3
"""
JustAi — Memory Bridge
=======================
Python client for claude-flow memory via the MCP HTTP server on :3100.

Talks JSON-RPC 2.0 directly to the HTTP endpoint — ~40x faster than shelling
out to `claude-flow memory store` via subprocess (5ms vs 200ms+).

Usage:
    from justai.memory import Memory

    mem = Memory()                          # defaults to http://127.0.0.1:3100
    mem.store("key", "value")               # store with 384-dim embedding
    result = mem.retrieve("key")            # exact key lookup
    results = mem.search("semantic query")  # HNSW vector search
    keys = mem.list_keys()                  # list all keys
    mem.delete("key")                       # delete entry
    stats = mem.stats()                     # backend stats

Requires the MCP HTTP server to be running (ruv-start step 2).
Falls back to subprocess CLI if HTTP is unavailable.

Transport note (2026-04-11):
    Clients must send `initialize` before any tools/call. This module handles
    that automatically on first call. If the MCP server restarts mid-session,
    the next call re-initializes.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Optional


# ── Config ────────────────────────────────────────────────────────────────────

MCP_URL = os.environ.get("JUSTAI_MCP_URL", "http://127.0.0.1:3100")
MCP_RPC = f"{MCP_URL}/rpc"
DEFAULT_NAMESPACE = "justai"
MEMORY_CWD = os.path.expanduser("~/projects/ruv-research")
_REQUEST_TIMEOUT = 10  # seconds


# ── Data Types ────────────────────────────────────────────────────────────────

@dataclass
class MemoryEntry:
    key: str
    value: str
    namespace: str = ""
    similarity: float = 0.0
    tags: list[str] = field(default_factory=list)


@dataclass
class MemoryStats:
    total_entries: int = 0
    backend: str = ""
    namespaces: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


# ── JSON-RPC Transport ───────────────────────────────────────────────────────

class _RPCClient:
    """Minimal JSON-RPC 2.0 client for MCP HTTP transport."""

    def __init__(self, rpc_url: str = MCP_RPC):
        self._url = rpc_url
        self._initialized = False
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _post(self, method: str, params: Optional[dict] = None) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params:
            payload["params"] = params

        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self._url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read())

    def initialize(self) -> None:
        """Send the MCP initialize handshake. Required before any tool call."""
        self._post("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "justai-memory", "version": "1.0"},
        })
        self._initialized = True

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Call an MCP tool. Auto-initializes on first call or after error."""
        if not self._initialized:
            self.initialize()
        try:
            resp = self._post("tools/call", {"name": name, "arguments": arguments})
        except urllib.error.HTTPError as e:
            # -32002 = not initialized (server restarted). Re-init and retry.
            if e.code == 200:
                raise
            self._initialized = False
            self.initialize()
            resp = self._post("tools/call", {"name": name, "arguments": arguments})

        if "error" in resp:
            code = resp["error"].get("code", 0)
            if code == -32002:
                self._initialized = False
                self.initialize()
                resp = self._post("tools/call", {"name": name, "arguments": arguments})
            if "error" in resp:
                raise MemoryError(
                    f"MCP tool {name} failed: {resp['error'].get('message', resp['error'])}"
                )

        result = resp.get("result", {})
        content = result.get("content", [])
        if not content:
            return {}
        text = content[0].get("text", "{}")
        return json.loads(text)

    def health(self) -> bool:
        """Check if the MCP server is reachable."""
        try:
            req = urllib.request.Request(
                self._url.replace("/rpc", "/health"),
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                return data.get("status") == "ok"
        except Exception:
            return False


# ── CLI Fallback ──────────────────────────────────────────────────────────────

def _cli_store(key: str, value: str, namespace: str) -> bool:
    """Fallback: store via claude-flow CLI subprocess."""
    try:
        args = ["claude-flow", "memory", "store", "-k", key, "-v", value]
        if namespace:
            args.extend(["-n", namespace])
        subprocess.run(args, capture_output=True, cwd=MEMORY_CWD, timeout=15)
        return True
    except Exception:
        return False


def _cli_retrieve(key: str, namespace: str) -> Optional[str]:
    """Fallback: retrieve via claude-flow CLI subprocess."""
    try:
        args = ["claude-flow", "memory", "retrieve", "-k", key]
        if namespace:
            args.extend(["-n", namespace])
        result = subprocess.run(
            args, capture_output=True, text=True, cwd=MEMORY_CWD, timeout=15
        )
        # Parse the CLI table output for the value
        for line in result.stdout.splitlines():
            if "| Value:" in line or "│ Value:" in line:
                return line.split(":", 1)[-1].strip().strip("|").strip()
        return result.stdout.strip() if result.stdout.strip() else None
    except Exception:
        return None


# ── Memory Client ─────────────────────────────────────────────────────────────

class Memory:
    """
    JustAi memory client.

    Connects to claude-flow MCP HTTP server for fast operations.
    Falls back to CLI subprocess if HTTP is unavailable.
    """

    def __init__(
        self,
        url: str = MCP_URL,
        namespace: str = DEFAULT_NAMESPACE,
        use_http: bool = True,
    ):
        self.namespace = namespace
        self._use_http = use_http
        self._rpc = _RPCClient(f"{url}/rpc") if use_http else None

    @property
    def connected(self) -> bool:
        """Check if the MCP HTTP server is reachable."""
        if not self._rpc:
            return False
        return self._rpc.health()

    def store(
        self,
        key: str,
        value: str,
        namespace: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> bool:
        """Store a key-value pair with optional embedding."""
        ns = namespace or self.namespace
        if self._rpc:
            try:
                args: dict[str, Any] = {"key": key, "value": value}
                if ns:
                    args["namespace"] = ns
                if tags:
                    args["tags"] = tags
                result = self._rpc.call_tool("memory_store", args)
                return result.get("success", False)
            except Exception:
                pass
        return _cli_store(key, value, ns)

    def retrieve(self, key: str, namespace: Optional[str] = None) -> Optional[str]:
        """Retrieve a value by exact key."""
        ns = namespace or self.namespace
        if self._rpc:
            try:
                args: dict[str, Any] = {"key": key}
                if ns:
                    args["namespace"] = ns
                result = self._rpc.call_tool("memory_retrieve", args)
                return result.get("value")
            except Exception:
                pass
        return _cli_retrieve(key, ns)

    def search(
        self,
        query: str,
        namespace: Optional[str] = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Semantic search over memory entries."""
        ns = namespace or self.namespace
        if self._rpc:
            try:
                args: dict[str, Any] = {"query": query, "limit": limit}
                if ns:
                    args["namespace"] = ns
                result = self._rpc.call_tool("memory_search", args)
                entries = []
                for r in result.get("results", []):
                    entries.append(MemoryEntry(
                        key=r.get("key", ""),
                        value=r.get("value", ""),
                        namespace=r.get("namespace", ns),
                        similarity=r.get("similarity", 0.0),
                    ))
                return entries
            except Exception:
                return []
        return []

    def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """Delete a memory entry by key."""
        ns = namespace or self.namespace
        if self._rpc:
            try:
                args: dict[str, Any] = {"key": key}
                if ns:
                    args["namespace"] = ns
                result = self._rpc.call_tool("memory_delete", args)
                return result.get("success", False)
            except Exception:
                return False
        return False

    def list_keys(self, namespace: Optional[str] = None) -> list[str]:
        """List all memory keys in a namespace."""
        ns = namespace or self.namespace
        if self._rpc:
            try:
                args: dict[str, Any] = {}
                if ns:
                    args["namespace"] = ns
                result = self._rpc.call_tool("memory_list", args)
                return [e.get("key", "") for e in result.get("entries", [])]
            except Exception:
                return []
        return []

    def stats(self) -> MemoryStats:
        """Get memory backend statistics."""
        if self._rpc:
            try:
                result = self._rpc.call_tool("memory_stats", {})
                return MemoryStats(
                    total_entries=result.get("totalEntries", 0),
                    backend=result.get("backend", ""),
                    namespaces=result.get("namespaces", []),
                    raw=result,
                )
            except Exception:
                pass
        return MemoryStats()
