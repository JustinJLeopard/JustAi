"""Tests for justai.learning — trajectory context enrichment + run recording."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from justai.results import DelegationResult


def _make_result(title: str, status: str = "done", result: str = "ok") -> DelegationResult:
    return DelegationResult(
        task_id=f"test-{title[:10]}",
        title=title,
        status=status,
        result=result,
        duration_seconds=1.5,
    )


class TestEnrichContext:
    def test_empty_store_returns_empty_string(self):
        """When trajectory store has no matches, enrich_context returns ''."""
        from justai.learning import enrich_context

        with patch("justai.learning._store") as mock_store:
            mock_store.search.return_value = []
            result = enrich_context("implement REST API")
        assert result == ""

    def test_low_similarity_filtered_out(self):
        """Matches below 0.6 similarity are excluded."""
        from justai.learning import enrich_context
        from justai.trajectory import TrajectoryMatch

        low_match = TrajectoryMatch(
            key="traj/old",
            goal="unrelated task",
            steps=["step1"],
            outcome="success",
            similarity=0.4,
        )
        with patch("justai.learning._store") as mock_store:
            mock_store.search.return_value = [low_match]
            result = enrich_context("implement REST API")
        assert result == ""

    def test_high_similarity_returns_context(self):
        """Matches above 0.6 similarity produce formatted context."""
        from justai.learning import enrich_context
        from justai.trajectory import TrajectoryMatch

        good_match = TrajectoryMatch(
            key="traj/rest-api",
            goal="build REST API with auth",
            steps=["scaffold", "add routes", "add tests"],
            outcome="success",
            similarity=0.82,
        )
        with patch("justai.learning._store") as mock_store:
            mock_store.search.return_value = [good_match]
            result = enrich_context("implement REST API")
        assert "Similar past trajectories" in result
        assert "build REST API with auth" in result
        assert "0.82" in result

    def test_mcp_failure_returns_empty(self):
        """If MCP is unreachable, enrich_context returns '' without raising."""
        from justai.learning import enrich_context

        with patch("justai.learning._store") as mock_store:
            mock_store.search.side_effect = Exception("MCP unreachable")
            result = enrich_context("any goal")
        assert result == ""


class TestRecordRun:
    def test_stores_successful_run(self):
        """record_run calls TrajectoryStore.store with correct outcome."""
        from justai.learning import record_run

        results = [_make_result("task A"), _make_result("task B")]
        with patch("justai.learning._store") as mock_store:
            mock_store.store.return_value = True
            ok = record_run("build feature X", results, duration=12.5)
        assert ok is True
        call_args = mock_store.store.call_args
        assert call_args.kwargs["goal"] == "build feature X"
        assert call_args.kwargs["outcome"] == "success"
        assert call_args.kwargs["duration"] == 12.5
        assert len(call_args.kwargs["steps"]) == 2

    def test_partial_run_outcome(self):
        """When some tasks fail, outcome is 'partial'."""
        from justai.learning import record_run

        results = [_make_result("ok task"), _make_result("bad task", status="failed")]
        with patch("justai.learning._store") as mock_store:
            mock_store.store.return_value = True
            record_run("mixed goal", results, duration=5.0)
        assert mock_store.store.call_args.kwargs["outcome"] == "partial"

    def test_all_failed_outcome(self):
        """When all tasks fail, outcome is 'failed'."""
        from justai.learning import record_run

        results = [_make_result("fail1", status="failed"), _make_result("fail2", status="error")]
        with patch("justai.learning._store") as mock_store:
            mock_store.store.return_value = True
            record_run("doomed goal", results, duration=3.0)
        assert mock_store.store.call_args.kwargs["outcome"] == "failed"

    def test_mcp_failure_returns_false(self):
        """If store raises, record_run returns False without raising."""
        from justai.learning import record_run

        results = [_make_result("task")]
        with patch("justai.learning._store") as mock_store:
            mock_store.store.side_effect = Exception("MCP down")
            ok = record_run("goal", results, duration=1.0)
        assert ok is False

    def test_records_execution_evidence_from_run_result_actions_and_results(self):
        """RunResult actions/results produce action_id -> result_id evidence."""
        from justai.learning import record_run

        action = SimpleNamespace(action_id="act-1", action_type="bash", args={})
        result = SimpleNamespace(
            result_id="res-1",
            action_id="act-1",
            status="ok",
            evidence_ref="traj://step/1",
        )
        run_result = SimpleNamespace(
            title="run tests",
            status="done",
            actions=[action],
            results=[result],
        )
        with patch("justai.learning._store") as mock_store:
            mock_store.store.return_value = True
            record_run("verify feature", [run_result], duration=2.0)

        assert mock_store.store.call_args.kwargs["execution_evidence"] == [
            {
                "step": "run tests",
                "action_id": "act-1",
                "result_id": "res-1",
                "evidence_ref": "traj://step/1",
                "status": "ok",
            }
        ]

    def test_derives_timeout_failure_class_from_run_result_records(self):
        """Nested ResultRecord status has priority over generic top-level failure."""
        from justai.learning import record_run

        run_result = SimpleNamespace(
            title="slow command",
            status="failed",
            actions=[SimpleNamespace(action_id="act-timeout")],
            results=[
                SimpleNamespace(
                    result_id="res-timeout",
                    action_id="act-timeout",
                    status="timeout",
                    evidence_ref=None,
                )
            ],
        )
        with patch("justai.learning._store") as mock_store:
            mock_store.store.return_value = True
            record_run("run slow thing", [run_result], duration=99.0)

        assert mock_store.store.call_args.kwargs["outcome"] == "failed"
        assert mock_store.store.call_args.kwargs["failure_class"] == "timeout"

    def test_records_strategy_used_with_explicit_ignored_outcome(self):
        """Strategy metadata includes catalog choice and accepted/ignored outcome."""
        from justai.learning import record_run

        with patch("justai.learning._store") as mock_store:
            mock_store.store.return_value = True
            record_run(
                "try risky strategy",
                [_make_result("bad task", status="failed")],
                duration=3.0,
                strategy_used="catalog:fast-path",
                strategy_outcome="ignored",
            )

        assert mock_store.store.call_args.kwargs["strategy_used"] == {
            "name": "catalog:fast-path",
            "outcome": "ignored",
        }

    def test_computes_did_next_plan_change_from_focus_and_experiment(self):
        """Next-plan change is true when focus or next experiment shifts."""
        from justai.learning import record_run

        with patch("justai.learning._store") as mock_store:
            mock_store.store.return_value = True
            record_run(
                "learn from prior run",
                [_make_result("task")],
                duration=1.0,
                prior_chosen_focus="implementation",
                chosen_focus="verification",
                prior_next_experiment="unit-test",
                next_experiment="browser-test",
            )

        assert mock_store.store.call_args.kwargs["did_next_plan_change"] is True
