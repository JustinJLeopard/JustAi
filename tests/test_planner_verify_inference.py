"""Regression tests for planner verify-inference.

Fixes the `"test" in goal` substring bug (a "create /tmp/x-test-y" goal wrongly
emitted pytest) and gives file-creation goals a verify that actually checks the
file -- so a heuristic plan's success criteria matches the goal.
"""

from __future__ import annotations

from justai.scope_planner import (
    _UNVERIFIED_SENTINEL,
    _extract_exact_text,
    _extract_path,
    _infer_verify_command,
)


def test_file_creation_goal_checks_file_and_exact_contents():
    c = _infer_verify_command(
        "Create a file at /tmp/justai-test-artifact.txt containing exactly HELLO_JUSTAI"
    )
    assert "test -f /tmp/justai-test-artifact.txt" in c
    assert "grep -qxF HELLO_JUSTAI /tmp/justai-test-artifact.txt" in c
    assert "pytest" not in c  # the old substring bug is gone


def test_file_creation_without_exact_text_is_existence_only():
    c = _infer_verify_command("Write a file to /tmp/out/report.md")
    assert c == "test -f /tmp/out/report.md"
    assert "grep" not in c


def test_test_substring_in_path_does_not_trigger_pytest():
    c = _infer_verify_command("Create /tmp/latest-test-results.json with the run data")
    assert "pytest" not in c
    assert c.startswith("test -f /tmp/latest-test-results.json")


def test_genuine_test_goal_runs_pytest():
    assert "pytest" in _infer_verify_command("Add unit tests for the parser and make them pass")
    assert "pytest" in _infer_verify_command("Run the tests")
    assert "pytest" in _infer_verify_command("Fix the failing tests in the suite")


def test_latest_is_not_a_test_goal():
    assert "pytest" not in _infer_verify_command("Fetch the latest release notes into a variable")


def test_endpoint_goal_curls():
    assert "curl" in _infer_verify_command("Add a /health/agents endpoint to the server")


def test_endpoint_beats_file_path():
    # A goal naming both a .py file and an endpoint should curl, not test -f the file.
    c = _infer_verify_command("Add a /status endpoint to scripts/health_server.py")
    assert "curl" in c
    assert "test -f" not in c


def test_named_py_file_is_syntax_checked():
    c = _infer_verify_command("Fix the import bug in ./justai/config.py")
    assert c == "python3 -m py_compile ./justai/config.py"


def test_vague_goal_stays_unverified_sentinel():
    # The sentinel is exactly what _verify_task treats as no-automated-verification.
    assert _infer_verify_command("Improve overall code quality") == _UNVERIFIED_SENTINEL


def test_exact_text_extraction_handles_quotes():
    assert _extract_exact_text('write a file with the text "hello world"') == "hello world"
    assert _extract_exact_text("containing exactly FOO") == "FOO"
    assert _extract_exact_text("just make something") is None


def test_path_extraction_prefers_real_paths():
    assert _extract_path("save to /tmp/a/b.txt now") == "/tmp/a/b.txt"
    assert _extract_path("edit config.py in place") == "config.py"
    assert _extract_path("no path here") is None


def test_sentinel_matches_no_verification_convention():
    # The generic fallback is the exact string _verify_task recognizes as
    # "no automated verification", so a vague goal stays honestly unverified
    # rather than falsely passing. (Independent of the agent_dispatch version.)
    assert _UNVERIFIED_SENTINEL == "echo 'task completed -- verify manually'"
