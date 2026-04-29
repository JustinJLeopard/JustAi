#!/usr/bin/env python3
"""
Tests for JustAi Sprint 5: installer, preflight, env, docs.

Validates install.sh logic, .env.example completeness, and
documentation file existence.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# Ensure justai package is importable
JUSTAI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(JUSTAI_ROOT))
sys.path.insert(0, str(JUSTAI_ROOT / "tools"))


class InstallerTests(unittest.TestCase):
    """Tests for install.sh structure and preflight logic."""

    def test_install_script_exists(self):
        self.assertTrue((JUSTAI_ROOT / "install.sh").exists())

    def test_install_script_is_bash(self):
        content = (JUSTAI_ROOT / "install.sh").read_text()
        self.assertTrue(content.startswith("#!/usr/bin/env bash"))

    def test_install_script_has_check_flag(self):
        content = (JUSTAI_ROOT / "install.sh").read_text()
        self.assertIn("--check", content)

    def test_install_script_checks_python(self):
        content = (JUSTAI_ROOT / "install.sh").read_text()
        self.assertIn("python3", content)

    def test_install_script_checks_node(self):
        content = (JUSTAI_ROOT / "install.sh").read_text()
        self.assertIn("node", content)

    def test_install_script_runs_tests(self):
        content = (JUSTAI_ROOT / "install.sh").read_text()
        self.assertIn("pytest", content)

    def test_install_script_has_set_euo(self):
        content = (JUSTAI_ROOT / "install.sh").read_text()
        self.assertIn("set -euo pipefail", content)


class EnvExampleTests(unittest.TestCase):
    """Tests for .env.example completeness."""

    def test_env_example_exists(self):
        self.assertTrue((JUSTAI_ROOT / ".env.example").exists())

    def test_env_example_has_litellm(self):
        content = (JUSTAI_ROOT / ".env.example").read_text()
        self.assertIn("LITELLM_BASE_URL", content)
        self.assertIn("LITELLM_KEY", content)

    def test_env_example_has_mcp(self):
        content = (JUSTAI_ROOT / ".env.example").read_text()
        self.assertIn("JUSTAI_MCP_URL", content)

    def test_env_example_has_langfuse(self):
        content = (JUSTAI_ROOT / ".env.example").read_text()
        self.assertIn("LANGFUSE_PUBLIC_KEY", content)
        self.assertIn("LANGFUSE_SECRET_KEY", content)

    def test_env_example_has_session_ref(self):
        content = (JUSTAI_ROOT / ".env.example").read_text()
        self.assertIn("JUSTAI_SESSION_REF", content)

    def test_env_example_has_relay(self):
        content = (JUSTAI_ROOT / ".env.example").read_text()
        self.assertIn("RELAY_DB_NAME", content)


class DocumentationTests(unittest.TestCase):
    """Tests for required documentation files."""

    def test_readme_exists(self):
        self.assertTrue((JUSTAI_ROOT / "README.md").exists())

    def test_readme_has_install_section(self):
        content = (JUSTAI_ROOT / "README.md").read_text()
        self.assertIn("install.sh", content)

    def test_readme_has_quick_start(self):
        content = (JUSTAI_ROOT / "README.md").read_text()
        self.assertIn("Quick Start", content)

    def test_architecture_doc_exists(self):
        self.assertTrue((JUSTAI_ROOT / "docs" / "ARCHITECTURE.md").exists())

    def test_architecture_has_diagram(self):
        content = (JUSTAI_ROOT / "docs" / "ARCHITECTURE.md").read_text()
        self.assertIn("Orchestrator", content)
        self.assertIn("SpacetimeDB", content)

    def test_attribution_doc_exists(self):
        self.assertTrue((JUSTAI_ROOT / "docs" / "ATTRIBUTION.md").exists())

    def test_attribution_credits_mini_swe_agent(self):
        content = (JUSTAI_ROOT / "docs" / "ATTRIBUTION.md").read_text()
        self.assertIn("mini-swe-agent", content)
        self.assertIn("Princeton", content)

    def test_attribution_credits_ruflo(self):
        content = (JUSTAI_ROOT / "docs" / "ATTRIBUTION.md").read_text()
        self.assertIn("Ruflo", content)
        self.assertIn("rUv", content)

    def test_evidence_doc_exists(self):
        self.assertTrue((JUSTAI_ROOT / "docs" / "EVIDENCE.md").exists())

    def test_spec_doc_exists(self):
        self.assertTrue((JUSTAI_ROOT / "docs" / "JUSTAI_V1_SPEC.md").exists())

    def test_requirements_txt_exists(self):
        self.assertTrue((JUSTAI_ROOT / "requirements.txt").exists())


class RequirementsTests(unittest.TestCase):
    """Tests for requirements.txt content."""

    def test_requirements_has_langfuse(self):
        content = (JUSTAI_ROOT / "requirements.txt").read_text()
        self.assertIn("langfuse", content)

    def test_requirements_has_pytest(self):
        content = (JUSTAI_ROOT / "requirements.txt").read_text()
        self.assertIn("pytest", content)


class PackageIntegrityTests(unittest.TestCase):
    """Verify the justai package is importable and complete."""

    def test_justai_package_importable(self):
        import justai
        self.assertTrue(hasattr(justai, '_load_env'))

    def test_all_modules_importable(self):
        from justai import intent_gate
        from justai import planner
        from justai import reviewer
        from justai import checkpoint
        from justai import memory
        from justai import tracing
        # If any import fails, this test fails

    def test_orchestrator_importable(self):
        from justai import orchestrator
        self.assertTrue(hasattr(orchestrator, 'run'))
        self.assertTrue(hasattr(orchestrator, 'OrchestrationResult'))


if __name__ == "__main__":
    unittest.main()
