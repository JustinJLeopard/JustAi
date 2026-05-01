#!/usr/bin/env python3
"""
Tests for JustAi Sprint 4 modules: memory, tracing

Uses mocking for MCP HTTP and LangFuse so tests run offline.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure justai package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ── Memory Client ────────────────────────────────────────────────────────────


class MemoryClientTests(unittest.TestCase):
    """Tests for justai.memory.Memory client."""

    def test_memory_init_defaults(self):
        from justai.memory import Memory

        mem = Memory()
        self.assertEqual(mem.namespace, "justai")
        self.assertIsNotNone(mem._rpc)

    def test_memory_init_no_http(self):
        from justai.memory import Memory

        mem = Memory(use_http=False)
        self.assertIsNone(mem._rpc)

    def test_memory_entry_dataclass(self):
        from justai.memory import MemoryEntry

        e = MemoryEntry(key="k", value="v", namespace="ns", similarity=0.9)
        self.assertEqual(e.key, "k")
        self.assertEqual(e.similarity, 0.9)
        self.assertEqual(e.tags, [])

    def test_memory_stats_dataclass(self):
        from justai.memory import MemoryStats

        s = MemoryStats(total_entries=10, backend="sql.js")
        self.assertEqual(s.total_entries, 10)
        self.assertEqual(s.namespaces, [])

    @patch("justai.memory._RPCClient.call_tool")
    @patch("justai.memory._RPCClient.health", return_value=True)
    def test_store_via_rpc(self, mock_health, mock_call):
        from justai.memory import Memory

        mock_call.return_value = {"success": True}
        mem = Memory()
        result = mem.store("test-key", "test-value")
        self.assertTrue(result)
        mock_call.assert_called_once()
        args = mock_call.call_args[0]
        self.assertEqual(args[0], "memory_store")
        self.assertIn("key", args[1])

    @patch("justai.memory._RPCClient.call_tool")
    @patch("justai.memory._RPCClient.health", return_value=True)
    def test_retrieve_via_rpc(self, mock_health, mock_call):
        from justai.memory import Memory

        mock_call.return_value = {"value": "hello"}
        mem = Memory()
        result = mem.retrieve("test-key")
        self.assertEqual(result, "hello")

    @patch("justai.memory._RPCClient.call_tool")
    @patch("justai.memory._RPCClient.health", return_value=True)
    def test_search_returns_entries(self, mock_health, mock_call):
        from justai.memory import Memory

        mock_call.return_value = {
            "results": [
                {"key": "k1", "value": "v1", "similarity": 0.95},
                {"key": "k2", "value": "v2", "similarity": 0.80},
            ]
        }
        mem = Memory()
        results = mem.search("query")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].key, "k1")
        self.assertAlmostEqual(results[0].similarity, 0.95)

    @patch("justai.memory._RPCClient.call_tool")
    def test_delete_via_rpc(self, mock_call):
        from justai.memory import Memory

        mock_call.return_value = {"success": True}
        mem = Memory()
        result = mem.delete("test-key")
        self.assertTrue(result)
        mock_call.assert_called_once_with(
            "memory_delete", {"key": "test-key", "namespace": "justai"}
        )

    @patch("justai.memory._RPCClient.call_tool")
    def test_list_keys_via_rpc(self, mock_call):
        from justai.memory import Memory

        mock_call.return_value = {"entries": [{"key": "a"}, {"key": "b"}, {"key": "c"}]}
        mem = Memory()
        keys = mem.list_keys()
        self.assertEqual(keys, ["a", "b", "c"])

    @patch("justai.memory._RPCClient.call_tool")
    def test_stats_via_rpc(self, mock_call):
        from justai.memory import Memory

        mock_call.return_value = {
            "totalEntries": 42,
            "backend": "sql.js + HNSW",
            "namespaces": ["justai", "session"],
        }
        mem = Memory()
        stats = mem.stats()
        self.assertEqual(stats.total_entries, 42)
        self.assertEqual(stats.backend, "sql.js + HNSW")
        self.assertEqual(len(stats.namespaces), 2)

    @patch("justai.memory._RPCClient.call_tool", side_effect=Exception("connection refused"))
    @patch("justai.memory._cli_store", return_value=True)
    def test_store_falls_back_to_cli(self, mock_cli, mock_call):
        from justai.memory import Memory

        mem = Memory()
        result = mem.store("k", "v")
        self.assertTrue(result)
        mock_cli.assert_called_once()

    @patch("justai.memory._RPCClient.call_tool", side_effect=Exception("connection refused"))
    @patch("justai.memory._cli_retrieve", return_value="fallback-value")
    def test_retrieve_falls_back_to_cli(self, mock_cli, mock_call):
        from justai.memory import Memory

        mem = Memory()
        result = mem.retrieve("k")
        self.assertEqual(result, "fallback-value")

    def test_connected_property_no_rpc(self):
        from justai.memory import Memory

        mem = Memory(use_http=False)
        self.assertFalse(mem.connected)


# ── RPC Client ───────────────────────────────────────────────────────────────


class RPCClientTests(unittest.TestCase):
    """Tests for justai.memory._RPCClient internals."""

    def test_next_id_increments(self):
        from justai.memory import _RPCClient

        client = _RPCClient()
        id1 = client._next_id()
        id2 = client._next_id()
        self.assertEqual(id2, id1 + 1)

    @patch("urllib.request.urlopen")
    def test_initialize_sets_flag(self, mock_urlopen):
        from justai.memory import _RPCClient

        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}).encode()
        mock_urlopen.return_value = mock_resp

        client = _RPCClient()
        self.assertFalse(client._initialized)
        client.initialize()
        self.assertTrue(client._initialized)


# ── Tracing ───────────────────────────────────────────────────────────────────


class TracingTests(unittest.TestCase):
    """Tests for justai.tracing — should be no-op when LangFuse not configured."""

    def test_is_enabled_without_langfuse(self):
        from justai.tracing import is_enabled

        # In test env, LANGFUSE keys are not set, so tracing should be disabled
        # (unless test env happens to have them)
        # Just verify the function returns a bool
        self.assertIsInstance(is_enabled(), bool)

    def test_trace_generation_noop_without_langfuse(self):
        from justai.tracing import trace_generation

        with trace_generation("test", input_text="hello") as gen:
            gen.end(output_text="world")
        # Should not raise

    def test_trace_generation_error_noop(self):
        from justai.tracing import trace_generation

        with trace_generation("test-error") as gen:
            gen.error("something broke")
        # Should not raise

    def test_trace_event_noop(self):
        from justai.tracing import trace_event

        trace_event("test-event", metadata={"key": "value"})
        # Should not raise

    def test_flush_noop(self):
        from justai.tracing import flush_traces

        flush_traces()
        # Should not raise

    def test_generation_handle_defaults(self):
        from justai.tracing import GenerationHandle

        h = GenerationHandle()
        self.assertIsNone(h._trace)
        self.assertIsNone(h._generation)
        h.end(output_text="test")  # should not raise
        h.error("test")  # should not raise


# ── Orchestrator + Memory Integration ─────────────────────────────────────────


class OrchestratorMemoryTests(unittest.TestCase):
    """Verify orchestrator uses Memory client instead of subprocess."""

    def test_orchestrator_imports_memory(self):
        import justai.orchestrator as orch

        self.assertTrue(hasattr(orch, "_memory"))
        from justai.memory import Memory

        self.assertIsInstance(orch._memory, Memory)

    def test_orchestrator_imports_tracing(self):
        import justai.orchestrator as orch

        # Verify tracing functions are importable in orchestrator context
        self.assertTrue(hasattr(orch, "trace_generation"))
        self.assertTrue(hasattr(orch, "flush_traces"))

    @patch("justai.orchestrator._memory")
    def test_store_memory_uses_memory_client(self, mock_mem):
        from justai.orchestrator import _store_memory

        mock_mem.store.return_value = True
        _store_memory("test-key", "test-value")
        mock_mem.store.assert_called_once_with("test-key", "test-value")

    @patch("justai.orchestrator._memory")
    def test_store_memory_swallows_exceptions(self, mock_mem):
        from justai.orchestrator import _store_memory

        mock_mem.store.side_effect = Exception("MCP down")
        _store_memory("test-key", "test-value")  # should not raise


if __name__ == "__main__":
    unittest.main()
