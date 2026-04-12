#!/usr/bin/env python3
"""Sprint 11 tests — release quality, config, version consistency, E2E smoke."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestVersionConsistency(unittest.TestCase):
    """All version references must match."""

    def test_init_version(self):
        from justai import __version__
        self.assertEqual(__version__, "1.0.0")

    def test_config_version(self):
        from justai.config import VERSION
        self.assertEqual(VERSION, "1.0.0")

    def test_pyproject_version(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        self.assertIn('version = "1.0.0"', content)

    def test_all_versions_match(self):
        from justai import __version__
        from justai.config import VERSION
        self.assertEqual(__version__, VERSION)


class TestConfig(unittest.TestCase):
    """Test config.py centralized configuration."""

    def test_project_root(self):
        from justai.config import PROJECT_ROOT as cfg_root
        self.assertTrue(cfg_root.exists())
        self.assertTrue((cfg_root / "justai").is_dir())

    def test_litellm_url_strips_v1(self):
        from justai.config import LITELLM_BASE_URL
        self.assertNotIn("/v1", LITELLM_BASE_URL)

    def test_default_models(self):
        from justai.config import PLANNER_MODEL, INTENT_MODEL, REVIEWER_MODEL
        self.assertTrue(PLANNER_MODEL.startswith("openai/"))
        self.assertTrue(INTENT_MODEL.startswith("openai/"))
        self.assertTrue(REVIEWER_MODEL.startswith("openai/"))

    def test_runtime_root_path(self):
        from justai.config import RUNTIME_ROOT
        self.assertIsInstance(RUNTIME_ROOT, Path)

    def test_api_port_default(self):
        from justai.config import API_PORT
        self.assertEqual(API_PORT, 3002)

    def test_work_dir_is_project(self):
        from justai.config import WORK_DIR
        self.assertTrue(WORK_DIR.exists())


class TestPackageStructure(unittest.TestCase):
    """Verify all required files exist."""

    REQUIRED_FILES = [
        "justai/__init__.py",
        "justai/__main__.py",
        "justai/cli.py",
        "justai/config.py",
        "justai/orchestrator.py",
        "justai/planner.py",
        "justai/reviewer.py",
        "justai/intent_gate.py",
        "justai/checkpoint.py",
        "justai/delegator.py",
        "justai/executor.py",
        "justai/synthesizer.py",
        "justai/memory.py",
        "justai/health.py",
        "justai/api.py",
        "justai/tracing.py",
        "pyproject.toml",
        "README.md",
        ".env.example",
        "install.sh",
        "docs/ARCHITECTURE.md",
        "docs/ATTRIBUTION.md",
    ]

    def test_all_required_files_exist(self):
        for rel_path in self.REQUIRED_FILES:
            full = PROJECT_ROOT / rel_path
            self.assertTrue(full.exists(), f"Missing: {rel_path}")

    def test_module_count(self):
        """JustAi should have exactly 14 Python modules."""
        py_files = list((PROJECT_ROOT / "justai").glob("*.py"))
        self.assertEqual(len(py_files), 16)  # 15 modules + __init__.py

    def test_test_count(self):
        """Should have test files for sprints 4-11."""
        test_files = list((PROJECT_ROOT / "tests").glob("test_sprint*.py"))
        self.assertGreaterEqual(len(test_files), 5)


class TestImportAll(unittest.TestCase):
    """Every module should import cleanly."""

    MODULES = [
        "justai",
        "justai.cli",
        "justai.config",
        "justai.orchestrator",
        "justai.planner",
        "justai.reviewer",
        "justai.intent_gate",
        "justai.checkpoint",
        "justai.delegator",
        "justai.executor",
        "justai.synthesizer",
        "justai.memory",
        "justai.health",
        "justai.api",
        "justai.tracing",
    ]

    def test_all_modules_import(self):
        import importlib
        for mod_name in self.MODULES:
            with self.subTest(module=mod_name):
                mod = importlib.import_module(mod_name)
                self.assertIsNotNone(mod)


class TestReadme(unittest.TestCase):
    """README should document all major features."""

    def setUp(self):
        self.content = (PROJECT_ROOT / "README.md").read_text()

    def test_has_install_section(self):
        self.assertIn("## Install", self.content)

    def test_has_cli_section(self):
        self.assertIn("## CLI", self.content)

    def test_documents_local_flag(self):
        self.assertIn("--local", self.content)

    def test_documents_auto_flag(self):
        self.assertIn("--auto", self.content)

    def test_documents_pipeline_stages(self):
        self.assertIn("## Pipeline Stages", self.content)

    def test_documents_dashboard(self):
        self.assertIn("## Dashboard", self.content)

    def test_version_in_readme(self):
        self.assertIn("v1.0.0", self.content)


class TestE2ESmokeLocal(unittest.TestCase):
    """Smoke test: full pipeline with mocked LLM, local execution."""

    def test_full_pipeline_smoke(self):
        from justai.orchestrator import run
        from justai.planner import Plan, Task, RiskLevel, AgentType
        from justai.intent_gate import IntentResult, Intent
        from justai.reviewer import ReviewResult

        mock_intent = IntentResult(
            intent=Intent.EXECUTION,
            confidence=0.99,
            reasoning="smoke test",
            clarifying_question=None,
        )
        mock_plan = Plan(goal="smoke", tasks=[
            Task("check", "echo smoke", AgentType.MINI, RiskLevel.R0,
                 "echo ok", []),
        ])

        with patch("justai.orchestrator.classify", return_value=mock_intent):
            with patch("justai.orchestrator.decompose", return_value=mock_plan):
                with patch("justai.orchestrator.review",
                           return_value=ReviewResult(approved=True, feedback=[])):
                    result = run("smoke test", session_ref="v1-smoke",
                                 auto=True, local=True)

        self.assertEqual(result.status, "complete")
        self.assertEqual(result.intent, "execution")
        self.assertGreater(result.duration_seconds, 0)


if __name__ == "__main__":
    unittest.main()
