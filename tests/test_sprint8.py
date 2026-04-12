#!/usr/bin/env python3
"""Sprint 8 tests — CLI, pyproject.toml, __main__, version."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestCLIParser(unittest.TestCase):
    """Test CLI argument parsing."""

    def test_build_parser(self):
        from justai.cli import build_parser
        parser = build_parser()
        self.assertIsNotNone(parser)

    def test_run_subcommand_parsed(self):
        from justai.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["run", "add", "endpoint"])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.goal, ["add", "endpoint"])
        self.assertFalse(args.auto)

    def test_run_auto_flag(self):
        from justai.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["run", "--auto", "do", "it"])
        self.assertTrue(args.auto)
        self.assertEqual(args.goal, ["do", "it"])

    def test_run_session_flag(self):
        from justai.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["run", "--session", "sprint-8", "goal"])
        self.assertEqual(args.session, "sprint-8")

    def test_plan_subcommand(self):
        from justai.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["plan", "build", "feature"])
        self.assertEqual(args.command, "plan")
        self.assertEqual(args.goal, ["build", "feature"])

    def test_status_subcommand(self):
        from justai.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["status"])
        self.assertEqual(args.command, "status")

    def test_history_subcommand(self):
        from justai.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["history"])
        self.assertEqual(args.command, "history")
        self.assertEqual(args.limit, 10)

    def test_history_limit(self):
        from justai.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["history", "--limit", "5"])
        self.assertEqual(args.limit, 5)

    def test_version_subcommand(self):
        from justai.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["version"])
        self.assertEqual(args.command, "version")

    def test_no_command_returns_zero(self):
        from justai.cli import main
        result = main([])
        self.assertEqual(result, 0)


class TestCLICommands(unittest.TestCase):
    """Test CLI command execution."""

    def test_cmd_version(self):
        from justai.cli import cmd_version
        import argparse
        args = argparse.Namespace()
        result = cmd_version(args)
        self.assertEqual(result, 0)

    def test_cmd_run_no_goal(self):
        from justai.cli import cmd_run
        import argparse
        args = argparse.Namespace(goal=[], auto=False, session="")
        result = cmd_run(args)
        self.assertEqual(result, 1)

    def test_cmd_plan_no_goal(self):
        from justai.cli import cmd_plan
        import argparse
        args = argparse.Namespace(goal=[], session="")
        result = cmd_plan(args)
        self.assertEqual(result, 1)

    def test_cmd_status_runs(self):
        from justai.cli import cmd_status
        import argparse
        args = argparse.Namespace()
        result = cmd_status(args)
        # Returns 0 or 1 depending on service availability
        self.assertIn(result, (0, 1))

    def test_cmd_run_delegates_to_orchestrator(self):
        from justai.cli import cmd_run
        import argparse
        from justai.orchestrator import OrchestrationResult
        mock_result = OrchestrationResult(
            goal="test", intent="execution", task_count=1,
            results=[], duration_seconds=1.0, status="complete"
        )
        args = argparse.Namespace(goal=["test", "goal"], auto=True, session="test-8")
        with patch("justai.orchestrator.run", return_value=mock_result) as mock_run:
            result = cmd_run(args)
        mock_run.assert_called_once_with("test goal", session_ref="test-8", auto=True)
        self.assertEqual(result, 0)

    def test_cmd_plan_calls_decompose(self):
        from justai.cli import cmd_plan
        import argparse
        from justai.planner import Plan
        mock_plan = Plan(goal="test", tasks=[], session_ref="")
        args = argparse.Namespace(goal=["test"], session="s8")
        with patch("justai.planner.decompose", return_value=mock_plan):
            result = cmd_plan(args)
        self.assertEqual(result, 0)


class TestVersion(unittest.TestCase):
    """Test version is exposed properly."""

    def test_version_exists(self):
        from justai import __version__
        self.assertIsInstance(__version__, str)

    def test_version_format(self):
        from justai import __version__
        parts = __version__.split(".")
        self.assertEqual(len(parts), 3)
        for p in parts:
            self.assertTrue(p.isdigit())

    def test_version_matches_pyproject(self):
        from justai import __version__
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            self.assertIn(__version__, content)


class TestMainEntry(unittest.TestCase):
    """Test __main__.py entry point."""

    def test_main_module_importable(self):
        """justai.__main__ should import without error."""
        # We can't easily test sys.exit behavior, but importing should work
        import importlib
        spec = importlib.util.find_spec("justai.__main__")
        self.assertIsNotNone(spec)


class TestPyprojectToml(unittest.TestCase):
    """Test pyproject.toml is valid."""

    def test_pyproject_exists(self):
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        self.assertTrue(pyproject.exists())

    def test_pyproject_has_scripts(self):
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        content = pyproject.read_text()
        self.assertIn("[project.scripts]", content)
        self.assertIn("justai", content)

    def test_pyproject_has_version(self):
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        content = pyproject.read_text()
        self.assertIn('version = "0.8.0"', content)

    def test_pyproject_python_requires(self):
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        content = pyproject.read_text()
        self.assertIn(">=3.12", content)


if __name__ == "__main__":
    unittest.main()
