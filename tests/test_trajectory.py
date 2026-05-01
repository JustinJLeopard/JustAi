"""Tests for trajectory learning — store, search, and inject past runs."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


def _mock_rpc_response(result_text: str):
    resp = MagicMock()
    resp.status = 200
    resp.read.return_value = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": result_text}]}}
    ).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestTrajectoryStore:
    def test_store_trajectory(self):
        from justai.trajectory import TrajectoryStore

        store_resp = json.dumps({"success": True, "key": "trajectory/test-1", "stored": True})
        with patch("urllib.request.urlopen", return_value=_mock_rpc_response(store_resp)):
            ts = TrajectoryStore()
            result = ts.store(
                goal="implement add function",
                steps=["explore", "write tests", "write code"],
                outcome="success",
                duration=12.5,
                tech_stack=["python", "pytest"],
            )
            assert result is True

    def test_search_trajectories(self):
        from justai.trajectory import TrajectoryStore

        search_resp = json.dumps(
            {
                "query": "implement function",
                "results": [
                    {
                        "key": "trajectory/t-1",
                        "value": json.dumps(
                            {
                                "goal": "implement add function",
                                "steps": ["explore", "write tests", "write code"],
                                "outcome": "success",
                            }
                        ),
                        "similarity": 0.85,
                    },
                    {
                        "key": "trajectory/t-2",
                        "value": json.dumps(
                            {
                                "goal": "implement subtract function",
                                "steps": ["explore", "write code"],
                                "outcome": "failed",
                            }
                        ),
                        "similarity": 0.72,
                    },
                ],
                "total": 2,
            }
        )
        with patch("urllib.request.urlopen", return_value=_mock_rpc_response(search_resp)):
            ts = TrajectoryStore()
            results = ts.search("implement multiply function", limit=5)
            assert len(results) == 2
            assert results[0].similarity > results[1].similarity
            assert results[0].goal == "implement add function"

    def test_search_returns_empty_on_no_match(self):
        from justai.trajectory import TrajectoryStore

        search_resp = json.dumps({"query": "something", "results": [], "total": 0})
        with patch("urllib.request.urlopen", return_value=_mock_rpc_response(search_resp)):
            ts = TrajectoryStore()
            results = ts.search("completely unrelated query")
            assert results == []

    def test_format_context_for_agent(self):
        from justai.trajectory import TrajectoryMatch, TrajectoryStore

        matches = [
            TrajectoryMatch(
                key="t-1",
                goal="implement add function",
                steps=["explore", "write tests", "write code"],
                outcome="success",
                similarity=0.85,
                duration=12.5,
                tech_stack=["python"],
            ),
        ]
        context = TrajectoryStore.format_as_context(matches)
        assert "implement add function" in context
        assert "success" in context
        assert "explore" in context

    def test_format_context_empty(self):
        from justai.trajectory import TrajectoryStore

        context = TrajectoryStore.format_as_context([])
        assert context == ""

    def test_store_and_search_roundtrip(self):
        """Store a trajectory, then search for it — verifying data shape."""
        from justai.trajectory import TrajectoryStore

        stored_data = {
            "goal": "build REST API",
            "steps": ["scaffold", "routes", "tests", "deploy"],
            "outcome": "success",
            "duration": 45.0,
            "tech_stack": ["python", "fastapi"],
        }
        store_resp = json.dumps({"success": True, "key": "trajectory/t-api", "stored": True})
        search_resp = json.dumps(
            {
                "query": "build API",
                "results": [
                    {
                        "key": "trajectory/t-api",
                        "value": json.dumps(stored_data),
                        "similarity": 0.92,
                    }
                ],
                "total": 1,
            }
        )
        responses = [_mock_rpc_response(store_resp), _mock_rpc_response(search_resp)]
        with patch("urllib.request.urlopen", side_effect=responses):
            ts = TrajectoryStore()
            ts.store(**stored_data)
            results = ts.search("build API")
            assert len(results) == 1
            assert results[0].tech_stack == ["python", "fastapi"]
