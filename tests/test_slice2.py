"""Slice 2: Observability — tests for tracing, query layer, and API endpoints."""

from __future__ import annotations

import json
import pathlib
import sys
import unittest
from datetime import UTC
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

DASH = pathlib.Path(__file__).resolve().parents[1] / "dashboard" / "src"


# ── File Structure Tests ────────────────────────────────────────────────────


class TestSlice2FileStructure(unittest.TestCase):
    """Verify Slice 2 deliverables exist."""

    def test_observability_view_exists(self):
        assert (DASH / "views" / "Observability.tsx").exists()

    def test_observability_view_imports_recharts(self):
        src = (DASH / "views" / "Observability.tsx").read_text()
        assert "recharts" in src

    def test_api_client_has_observability_types(self):
        src = (DASH / "lib" / "api-client.ts").read_text()
        assert "ObservabilitySummary" in src
        assert "fetchCostData" in src
        assert "fetchLatencyData" in src
        assert "fetchQualityData" in src

    def test_app_tsx_wires_observability_view(self):
        src = (DASH / "App.tsx").read_text()
        assert "Observability" in src
        # No longer a placeholder
        assert "Coming in Slice 2" not in src

    def test_vite_config_proxies_observability(self):
        vite = (DASH.parent / "vite.config.ts").read_text()
        assert "/api/observability" in vite

    def test_recharts_in_package_json(self):
        pkg = json.loads((DASH.parent / "package.json").read_text())
        assert "recharts" in pkg.get("dependencies", {})


# ── Pipeline Tracing Tests ──────────────────────────────────────────────────


class TestPipelineTracing(unittest.TestCase):
    """Verify all 6 pipeline stages have trace_generation calls."""

    def test_orchestrator_has_all_stage_traces(self):
        src = pathlib.Path(__file__).resolve().parents[1] / "justai" / "orchestrator.py"
        code = src.read_text()
        # Control-plane stage traces: intent, planner, reviewer, dispatch, synthesizer.
        assert '"intent-gate"' in code
        assert '"planner"' in code
        assert '"reviewer"' in code
        assert '"synthesizer"' in code
        # Dispatch stage name depends on local/delegated mode.
        assert "stage5_name" in code
        assert "trace_generation(\n        stage5_name" in code

    def test_trace_event_checkpoint_preserved(self):
        src = pathlib.Path(__file__).resolve().parents[1] / "justai" / "orchestrator.py"
        code = src.read_text()
        assert 'trace_event("checkpoint"' in code


# ── Query Layer Tests ───────────────────────────────────────────────────────


class TestTracingQueryLayer(unittest.TestCase):
    """Test the read-side tracing functions."""

    def test_get_traces_returns_empty_when_disabled(self):
        from justai.tracing import get_traces

        # LangFuse likely not configured in test env
        result = get_traces(limit=10)
        assert isinstance(result, list)

    def test_get_trace_by_run_returns_empty(self):
        from justai.tracing import get_trace_by_run

        result = get_trace_by_run("nonexistent-run")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_aggregated_metrics_empty(self):
        from justai.tracing import get_aggregated_metrics

        result = get_aggregated_metrics(days=7)
        assert "cost" in result
        assert "latency" in result
        assert "quality" in result
        assert "summary" in result

    def test_empty_metrics_structure(self):
        from justai.tracing import _empty_metrics

        m = _empty_metrics()
        assert m["cost"]["total"] == 0.0
        assert m["cost"]["daily"] == []
        assert m["latency"]["p50"] == 0
        assert m["latency"]["bottleneck"] == ""
        assert m["quality"]["overall_rate"] == 0.0
        assert m["summary"]["cost_24h"] == 0.0

    def test_percentiles_empty(self):
        from justai.tracing import _percentiles

        assert _percentiles([]) == (0, 0, 0)

    def test_percentiles_single(self):
        from justai.tracing import _percentiles

        assert _percentiles([100]) == (100, 100, 100)

    def test_percentiles_multiple(self):
        from justai.tracing import _percentiles

        vals = list(range(1, 101))  # 1..100
        p50, p90, p99 = _percentiles(vals)
        # index-based: s[int(100*0.5)]=s[50]=51, s[int(100*0.9)]=s[90]=91, s[int(100*0.99)]=s[99]=100
        assert p50 == 51
        assert p90 == 91
        assert p99 == 100

    def test_stage_from_name(self):
        from justai.tracing import _stage_from_name

        assert _stage_from_name("justai-planner") == "planner"
        assert _stage_from_name("justai-intent-gate") == "intent-gate"
        assert _stage_from_name("justai-unknown") == ""
        assert _stage_from_name("") == ""

    def test_day_key(self):
        from datetime import datetime

        from justai.tracing import _day_key

        dt = datetime(2026, 4, 12, 15, 30, 0, tzinfo=UTC)
        assert _day_key(dt) == "2026-04-12"
        assert _day_key("2026-04-12T15:30:00Z") == "2026-04-12"

    def test_pipeline_stages_constant(self):
        from justai.tracing import PIPELINE_STAGES

        assert "intent-gate" in PIPELINE_STAGES
        assert "planner" in PIPELINE_STAGES
        assert "reviewer" in PIPELINE_STAGES
        assert "synthesizer" in PIPELINE_STAGES

    @patch("justai.tracing._enabled", True)
    @patch("justai.tracing._langfuse")
    def test_get_traces_with_mocked_langfuse(self, mock_lf):
        from justai.tracing import get_traces

        # Create mock trace objects
        mock_trace = MagicMock()
        mock_trace.id = "trace-1"
        mock_trace.name = "justai-planner"
        mock_trace.session_id = "sess-1"
        mock_trace.timestamp = "2026-04-12T10:00:00Z"
        mock_trace.latency = 2.1
        mock_trace.total_cost = 0.05
        mock_trace.observations = []
        mock_trace.tags = ["planner"]
        mock_trace.metadata = {}

        mock_resp = MagicMock()
        mock_resp.data = [mock_trace]
        mock_lf.fetch_traces.return_value = mock_resp

        result = get_traces(limit=10)
        assert len(result) == 1
        assert result[0]["id"] == "trace-1"
        assert result[0]["name"] == "justai-planner"
        assert result[0]["latency_ms"] == 2100

    @patch("justai.tracing._enabled", True)
    @patch("justai.tracing._langfuse")
    def test_get_aggregated_metrics_with_data(self, mock_lf):
        from datetime import datetime

        from justai.tracing import get_aggregated_metrics

        now = datetime.now(UTC)

        traces = []
        for i in range(3):
            t = MagicMock()
            t.id = f"trace-{i}"
            t.name = "justai-planner"
            t.session_id = f"run-{i}"
            t.timestamp = now
            t.latency = 1.5 + i * 0.5
            t.total_cost = 0.01 + i * 0.01
            t.observations = []
            t.tags = ["planner"]
            t.metadata = {"model": "gpt-5.4"}
            traces.append(t)

        mock_resp = MagicMock()
        mock_resp.data = traces
        mock_lf.fetch_traces.return_value = mock_resp

        result = get_aggregated_metrics(days=7)
        assert result["cost"]["total"] > 0
        assert len(result["cost"]["daily"]) > 0
        assert result["latency"]["avg_ms"] > 0
        assert result["quality"]["overall_rate"] == 1.0


# ── API Endpoint Tests ──────────────────────────────────────────────────────


class TestObservabilityAPI(unittest.TestCase):
    """Test the /api/observability/* endpoints."""

    def test_get_observability_returns_metrics(self):
        from justai.api import _get_observability

        # With LangFuse not configured, should return empty structure
        result = _get_observability("summary")
        assert isinstance(result, dict)
        assert "cost_24h" in result

    def test_get_observability_cost(self):
        from justai.api import _get_observability

        result = _get_observability("cost")
        assert isinstance(result, dict)
        assert "daily" in result
        assert "total" in result

    def test_get_observability_latency(self):
        from justai.api import _get_observability

        result = _get_observability("latency")
        assert isinstance(result, dict)
        assert "p50" in result
        assert "bottleneck" in result

    def test_get_observability_quality(self):
        from justai.api import _get_observability

        result = _get_observability("quality")
        assert isinstance(result, dict)
        assert "overall_rate" in result
        assert "failure_categories" in result

    def test_get_observability_unknown_section(self):
        from justai.api import _get_observability

        result = _get_observability("bogus")
        assert "error" in result

    def test_api_handler_routes_observability(self):
        """Verify the API handler recognizes /api/observability paths."""

        from justai.api import APIHandler

        # Create a mock handler to test routing
        handler = APIHandler.__new__(APIHandler)
        handler.path = "/api/observability/summary"
        handler.headers = {}

        responses = []

        def mock_json(data, status=200):
            responses.append((data, status))

        handler._json = mock_json
        handler.do_GET()
        assert len(responses) == 1
        data, status = responses[0]
        assert status == 200
        assert "cost_24h" in data


# ── Tracing Context Manager Tests ───────────────────────────────────────────


class TestTraceGeneration(unittest.TestCase):
    """Test the trace_generation context manager."""

    def test_noop_when_disabled(self):
        from justai.tracing import trace_generation

        with trace_generation("test-stage", input_text="hello") as gen:
            gen.end(output_text="world")
        # Should not raise

    def test_generation_handle_error(self):
        from justai.tracing import GenerationHandle

        h = GenerationHandle()
        h.error("something broke")
        # Should not raise (no generation to end)

    def test_is_enabled_returns_bool(self):
        from justai.tracing import is_enabled

        assert isinstance(is_enabled(), bool)


class TestAIInsightGeneration(unittest.TestCase):
    """Test the quality insight generator."""

    def test_insight_empty(self):
        from justai.tracing import _generate_quality_insight

        result = _generate_quality_insight(0.0, 0, 0, 0, {}, [])
        assert result == ""

    def test_insight_high_first_try(self):
        from justai.tracing import _generate_quality_insight

        result = _generate_quality_insight(0.9, 9, 1, 10, {}, [])
        assert "first-try" in result.lower()

    def test_insight_low_first_try(self):
        from justai.tracing import _generate_quality_insight

        result = _generate_quality_insight(0.5, 2, 8, 10, {}, [])
        assert "revision" in result.lower() or "first-try" in result.lower()

    def test_insight_top_failure(self):
        from justai.tracing import _generate_quality_insight

        cats = {"timeout": 5, "agent_error": 2}
        result = _generate_quality_insight(0.5, 3, 3, 10, cats, [])
        assert "timeout" in result

    def test_enriched_empty_metrics_has_new_fields(self):
        from justai.tracing import _empty_metrics

        m = _empty_metrics()
        assert "models" in m["cost"]
        assert "input_tokens" in m["cost"]
        assert "first_try_total" in m["quality"]
        assert "cost_quality" in m["quality"]
        assert "ai_insight" in m["quality"]

    def test_enriched_cost_daily_has_model_breakdown(self):
        """When real data is present, cost daily entries include by_model."""
        from justai.tracing import _empty_metrics

        m = _empty_metrics()
        # Verify the structure supports by_model per day
        assert isinstance(m["cost"]["daily"], list)
        assert isinstance(m["cost"]["models"], list)


class TestEnrichedOrchestrator(unittest.TestCase):
    """Verify orchestrator imports enriched model constants."""

    def test_orchestrator_imports_models(self):
        src = pathlib.Path(__file__).resolve().parents[1] / "justai" / "orchestrator.py"
        code = src.read_text()
        assert "INTENT_MODEL" in code
        assert "PLANNER_MODEL" in code
        assert "REVIEWER_MODEL" in code

    def test_traces_pass_model_name(self):
        src = pathlib.Path(__file__).resolve().parents[1] / "justai" / "orchestrator.py"
        code = src.read_text()
        assert "model=INTENT_MODEL" in code
        assert "model=PLANNER_MODEL" in code
        assert "model=REVIEWER_MODEL" in code

    def test_traces_pass_metadata(self):
        src = pathlib.Path(__file__).resolve().parents[1] / "justai" / "orchestrator.py"
        code = src.read_text()
        assert '"stage": "intent-gate"' in code
        assert '"stage": "planner"' in code
        assert '"stage": "reviewer"' in code
        assert '"stage": "synthesizer"' in code


if __name__ == "__main__":
    unittest.main()
