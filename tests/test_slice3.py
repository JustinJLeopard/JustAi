"""Slice 3: Trajectory Intelligence — tests for analysis, patterns, and audit."""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

DASH = pathlib.Path(__file__).resolve().parents[1] / "dashboard" / "src"


# ── File Structure Tests ────────────────────────────────────────────────────


class TestSlice3FileStructure(unittest.TestCase):
    def test_trajectory_module_exists(self):
        assert (pathlib.Path(__file__).resolve().parents[1] / "justai" / "trajectory.py").exists()

    def test_trajectory_viewer_has_three_modes(self):
        src = (DASH / "views" / "TrajectoryViewer.tsx").read_text()
        assert "Post-Mortem" in src
        assert "Learning" in src
        assert "Audit" in src

    def test_trajectory_viewer_imports_recharts(self):
        src = (DASH / "views" / "TrajectoryViewer.tsx").read_text()
        assert "recharts" in src

    def test_api_client_has_trajectory_types(self):
        src = (DASH / "lib" / "api-client.ts").read_text()
        assert "TrajAnalysis" in src
        assert "PatternReport" in src
        assert "AuditData" in src
        assert "fetchTrajectoryAnalysis" in src
        assert "fetchTrajectoryPatterns" in src
        assert "fetchTrajectoryAudit" in src

    def test_vite_config_proxies_trajectory_api(self):
        vite = (DASH.parent / "vite.config.ts").read_text()
        assert "/api/trajectory" in vite

    def test_app_passes_on_navigate_to_views(self):
        app = (DASH / "App.tsx").read_text()
        assert "onNavigate={handleNavigate}" in app


# ── Trajectory Module Tests ─────────────────────────────────────────────────


class TestTrajectoryModule(unittest.TestCase):
    def test_import(self):
        pass

    def test_classify_action(self):
        from justai.trajectory import _classify_action

        assert _classify_action("bash_command", "ls -la") == "bash"
        assert _classify_action("bash_command", "cat file.py") == "read"
        assert _classify_action("str_replace_editor", "") == "edit"
        assert _classify_action("", "") == "think"

    def test_parse_steps_empty(self):
        from justai.trajectory import parse_steps

        result = parse_steps({"messages": []})
        assert result == []

    def test_parse_steps_with_assistant_messages(self):
        from justai.trajectory import parse_steps

        traj = {
            "messages": [
                {"role": "system", "content": "You are an agent"},
                {"role": "user", "content": "Fix the bug"},
                {
                    "role": "assistant",
                    "content": "I'll read the file first",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "bash",
                                "arguments": '{"command": "cat src/main.py"}',
                            },
                            "id": "call_1",
                            "type": "function",
                        }
                    ],
                },
                {"role": "tool", "content": '{"returncode": 0, "output": "def main(): pass"}'},
                {
                    "role": "assistant",
                    "content": "Now I'll edit it",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "str_replace_editor",
                                "arguments": '{"path": "src/main.py"}',
                            },
                            "id": "call_2",
                            "type": "function",
                        }
                    ],
                },
                {"role": "tool", "content": '{"returncode": 0, "output": "OK"}'},
            ],
        }
        steps = parse_steps(traj)
        assert len(steps) == 2
        assert steps[0].action_type == "read"  # cat -> read
        assert steps[0].returncode == 0
        assert steps[1].action_type == "edit"  # str_replace_editor -> edit
        assert steps[1].file_touched == "src/main.py"

    def test_empty_patterns(self):
        from justai.trajectory import _empty_patterns

        p = _empty_patterns()
        assert p["total_trajectories"] == 0
        assert p["success_rate"] == 0.0
        assert len(p["suggestions"]) > 0

    def test_generate_suggestions_low_success(self):
        from justai.trajectory import _generate_suggestions

        suggestions = _generate_suggestions([], 2, 10, 25.0)
        assert any("50%" in s for s in suggestions)

    def test_generate_suggestions_high_steps(self):
        from justai.trajectory import _generate_suggestions

        suggestions = _generate_suggestions([], 8, 10, 45.0)
        assert any("step count" in s.lower() for s in suggestions)

    def test_generate_suggestions_healthy(self):
        from justai.trajectory import _generate_suggestions

        suggestions = _generate_suggestions([], 9, 10, 20.0)
        assert any("performing well" in s for s in suggestions)


class TestTrajectoryPathContainment(unittest.TestCase):
    def test_load_allows_nested_relay_trajectory(self):
        from justai.trajectory import load_trajectory

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "trajectories"
            relay = root / "relay_dispatch"
            relay.mkdir(parents=True)
            payload = {"messages": []}
            (relay / "nested.traj.json").write_text(json.dumps(payload))

            with patch("justai.trajectory.TRAJ_DIR", root):
                assert load_trajectory("relay_dispatch/nested.traj.json") == payload

    def test_load_rejects_parent_traversal(self):
        from justai.trajectory import load_trajectory

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "trajectories"
            root.mkdir()
            (base / "outside.traj.json").write_text('{"messages": []}')

            with patch("justai.trajectory.TRAJ_DIR", root):
                with self.assertRaises(FileNotFoundError):
                    load_trajectory("../outside.traj.json")

    def test_load_rejects_absolute_path(self):
        from justai.trajectory import load_trajectory

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "trajectories"
            root.mkdir()
            outside = base / "outside.traj.json"
            outside.write_text('{"messages": []}')

            with patch("justai.trajectory.TRAJ_DIR", root):
                with self.assertRaises(FileNotFoundError):
                    load_trajectory(str(outside))

    def test_load_rejects_symlink_escape(self):
        from justai.trajectory import load_trajectory

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "trajectories"
            root.mkdir()
            outside = base / "outside.traj.json"
            outside.write_text('{"messages": []}')
            link = root / "linked.traj.json"
            try:
                link.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            with patch("justai.trajectory.TRAJ_DIR", root):
                with self.assertRaises(FileNotFoundError):
                    load_trajectory(link.name)

    def test_load_rejects_fifo_without_blocking(self):
        from justai.trajectory import load_trajectory

        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFOs unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "trajectories"
            root.mkdir()
            fifo = root / "blocked.traj.json"
            os.mkfifo(fifo)

            with patch("justai.trajectory.TRAJ_DIR", root):
                with self.assertRaises(FileNotFoundError):
                    load_trajectory(fifo.name)

    def test_load_keeps_open_file_after_symlink_swap(self):
        from justai.trajectory import load_trajectory

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "trajectories"
            root.mkdir()
            safe = root / "safe.traj.json"
            safe_payload = {"messages": [{"content": "safe"}]}
            safe.write_text(json.dumps(safe_payload))
            outside = base / "outside.traj.json"
            outside.write_text('{"messages": [{"content": "outside"}]}')
            original_fdopen = os.fdopen

            def swap_then_open(fd, *args, **kwargs):
                safe.unlink()
                safe.symlink_to(outside)
                return original_fdopen(fd, *args, **kwargs)

            with patch("justai.trajectory.TRAJ_DIR", root), patch(
                "justai.trajectory.os.fdopen", side_effect=swap_then_open
            ):
                assert load_trajectory(safe.name) == safe_payload

    def test_list_allows_real_nested_relay_trajectory(self):
        from justai.trajectory import list_trajectory_files

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "trajectories"
            relay = root / "relay_dispatch"
            relay.mkdir(parents=True)
            (relay / "nested.traj.json").write_text('{"messages": []}')

            with patch("justai.trajectory.TRAJ_DIR", root):
                names = {entry["name"] for entry in list_trajectory_files()}

        assert names == {str(pathlib.Path("relay_dispatch") / "nested.traj.json")}

    def test_list_ignores_symlinked_files_and_relay_directory(self):
        from justai.trajectory import list_trajectory_files

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "trajectories"
            root.mkdir()
            (root / "visible.traj.json").write_text('{"messages": []}')
            outside_file = base / "outside.traj.json"
            outside_file.write_text('{"messages": []}')
            outside_dir = base / "outside"
            outside_dir.mkdir()
            (outside_dir / "hidden.traj.json").write_text('{"messages": []}')
            try:
                (root / "linked.traj.json").symlink_to(outside_file)
                (root / "relay_dispatch").symlink_to(outside_dir, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            with patch("justai.trajectory.TRAJ_DIR", root):
                names = {entry["name"] for entry in list_trajectory_files()}

        assert names == {"visible.traj.json"}

    def test_patterns_fail_closed_when_secure_open_is_unavailable(self):
        from justai.trajectory import get_patterns, list_trajectory_files

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "trajectories"
            root.mkdir()
            (root / "visible.traj.json").write_text('{"messages": []}')

            with (
                patch("justai.trajectory.TRAJ_DIR", root),
                patch("justai.trajectory._open_directory", side_effect=RuntimeError("unsupported")),
                patch("justai.trajectory._patterns_cache", {}),
                patch("justai.trajectory._patterns_cache_ts", 0.0),
            ):
                assert list_trajectory_files() == []
                patterns = get_patterns()

        assert patterns["total_trajectories"] == 0
        assert patterns["success_rate"] == 0.0


# ── Heuristic Analysis Tests ────────────────────────────────────────────────


class TestHeuristicAnalysis(unittest.TestCase):
    def test_heuristic_success(self):
        from justai.trajectory import TrajStep, _heuristic_analysis

        steps = [
            TrajStep(
                index=0,
                action_type="bash",
                command="ls",
                reasoning="",
                result="ok",
                returncode=0,
                file_touched="",
            ),
            TrajStep(
                index=1,
                action_type="edit",
                command="",
                reasoning="",
                result="ok",
                returncode=0,
                file_touched="src/main.py",
            ),
        ]
        info = {"exit_status": "Submitted", "model_stats": {"instance_cost": 0.05}}

        result = _heuristic_analysis("test.traj.json", steps, info)
        assert result["status"] == "success"
        assert result["step_count"] == 2
        assert result["failed_steps"] == []
        assert "src/main.py" in result["files_changed"]

    def test_heuristic_failure(self):
        from justai.trajectory import TrajStep, _heuristic_analysis

        steps = [
            TrajStep(
                index=0,
                action_type="bash",
                command="python test.py",
                reasoning="",
                result="Error!",
                returncode=1,
                file_touched="",
            ),
        ]
        info = {"exit_status": "Failed", "model_stats": {"instance_cost": 0.02}}

        result = _heuristic_analysis("test.traj.json", steps, info)
        assert result["status"] == "failure"
        assert result["failed_steps"] == [0]
        assert result["divergence_step"] == 0
        assert "root_cause" in result and result["root_cause"]


# ── Audit Data Tests ────────────────────────────────────────────────────────


class TestAuditData(unittest.TestCase):
    def test_audit_data_nonexistent(self):
        from justai.trajectory import get_audit_data

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"JUSTAI_TRAJ_DIR": tmp}):
            result = get_audit_data("nonexistent-file.traj.json")
        assert "error" in result

    @patch("justai.trajectory.TRAJ_DIR")
    def test_audit_data_structure(self, mock_dir):
        from justai.trajectory import get_audit_data

        with tempfile.TemporaryDirectory() as tmp:
            mock_dir.__class__ = pathlib.Path
            traj_data = {
                "info": {
                    "config": {"model": {"model_name": "test-model"}, "agent": {"mode": "swe"}},
                    "model_stats": {"instance_cost": 0.03, "api_calls": 5},
                    "exit_status": "Submitted",
                    "mini_version": "1.0",
                    "submission": "",
                },
                "messages": [
                    {
                        "role": "assistant",
                        "content": "thinking",
                        "tool_calls": [
                            {
                                "function": {"name": "bash", "arguments": '{"command": "ls"}'},
                                "id": "1",
                                "type": "function",
                            }
                        ],
                    },
                    {"role": "tool", "content": '{"returncode": 0, "output": "files"}'},
                ],
            }
            fp = pathlib.Path(tmp) / "test.traj.json"
            fp.write_text(json.dumps(traj_data))

            with patch("justai.trajectory.TRAJ_DIR", pathlib.Path(tmp)):
                result = get_audit_data("test.traj.json")

            assert result["model"] == "test-model"
            assert result["step_count"] == 1
            assert result["exit_status"] == "Submitted"
            assert isinstance(result["events"], list)


# ── API Endpoint Tests ──────────────────────────────────────────────────────


class TestTrajectoryAPI(unittest.TestCase):
    def test_api_patterns_endpoint(self):
        from justai.api import APIHandler

        handler = APIHandler.__new__(APIHandler)
        handler.path = "/api/trajectory/patterns"
        handler.headers = {}

        responses = []
        handler._json = lambda data, status=200: responses.append((data, status))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"JUSTAI_TRAJ_DIR": tmp}):
            handler.do_GET()

        assert len(responses) == 1
        data, status = responses[0]
        assert "total_trajectories" in data

    def test_api_analysis_endpoint(self):
        from justai.api import APIHandler

        handler = APIHandler.__new__(APIHandler)
        handler.path = "/api/trajectory/nonexistent.traj.json/analysis"
        handler.headers = {}

        responses = []
        handler._json = lambda data, status=200: responses.append((data, status))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"JUSTAI_TRAJ_DIR": tmp}):
            handler.do_GET()

        assert len(responses) == 1
        data, _ = responses[0]
        # Should return error for nonexistent file
        assert "error" in data or "status" in data

    def test_api_audit_endpoint(self):
        from justai.api import APIHandler

        handler = APIHandler.__new__(APIHandler)
        handler.path = "/api/trajectory/nonexistent.traj.json/audit"
        handler.headers = {}

        responses = []
        handler._json = lambda data, status=200: responses.append((data, status))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"JUSTAI_TRAJ_DIR": tmp}):
            handler.do_GET()

        assert len(responses) == 1
        data, _ = responses[0]
        assert "error" in data

    def test_api_audit_rejects_parent_traversal(self):
        from justai.api import APIHandler

        handler = APIHandler.__new__(APIHandler)
        handler.path = "/api/trajectory/../outside.traj.json/audit"
        handler.headers = {}

        responses = []
        handler._json = lambda data, status=200: responses.append((data, status))
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "trajectories"
            root.mkdir()
            (base / "outside.traj.json").write_text('{"messages": []}')

            with patch("justai.trajectory.TRAJ_DIR", root):
                handler.do_GET()

        assert len(responses) == 1
        data, _ = responses[0]
        assert "error" in data


if __name__ == "__main__":
    unittest.main()
