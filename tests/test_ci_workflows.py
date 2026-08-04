"""What a green check on this repository is allowed to mean.

Every check a pull request could show was static analysis (CodeQL), a Node
build (Dashboard CI), or a preview deploy (Vercel). None of them execute a line
of the Python package, so a change that broke the checkpoint's fail-closed
behaviour — or deleted its tests — showed an all-green rollup. "CI is green"
was true and told a reviewer nothing about the code under review.

These assertions are deliberately about the workflow's contract rather than its
formatting: that Python behaviour runs at all, that it runs against the commit
under review rather than a synthesised merge preview, that the actions it uses
are pinned to immutable SHAs, and that the suite this pull request is about is
named rather than reached by accident. Parsed as text, so the check itself
needs no dependency the workflow would then have to install.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"
PYTHON_CI = WORKFLOWS / "python-ci.yml"
DASHBOARD_CI = WORKFLOWS / "dashboard-ci.yml"

#: `uses: owner/repo@<40 hex>`. A tag or a branch is a moving target: the
#: revision that ran is not the revision anyone reviewed.
PINNED_USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)\s*(?:#.*)?$", re.MULTILINE)
SHA_PIN = re.compile(r"\A[^@\s]+@[0-9a-f]{40}\Z")

#: The suites that must run. Each is a file this repository actually has —
#: renaming one without updating CI would otherwise silently stop running it.
REQUIRED_SUITES = [
    "tests/test_gate_run_identity.py",
    "tests/test_gate_identity_collision.py",
    "tests/test_gate_lifecycle.py",
    "tests/test_gate_run_ownership.py",
    "tests/test_gate_retention.py",
]


@pytest.fixture
def python_ci() -> str:
    assert PYTHON_CI.exists(), (
        "the Python package has no CI workflow: every green check on a pull "
        "request would come from a job that never executes Python"
    )
    return PYTHON_CI.read_text(encoding="utf-8")


def test_python_behaviour_runs_on_every_pull_request(python_ci: str) -> None:
    """Unfiltered, because a skipped workflow reports no status at all."""
    assert re.search(r"^on:", python_ci, re.MULTILINE)
    assert re.search(r"^\s{2}pull_request:", python_ci, re.MULTILINE)
    # A key, not the word: the workflow explains in a comment why it has none.
    assert not re.search(r"^\s+paths(-ignore)?:", python_ci, re.MULTILINE), (
        "a paths filter skips the workflow entirely on PRs that miss it, and a "
        "skipped workflow never reports the status a required check waits for"
    )


def test_the_workflow_tests_the_commit_under_review(python_ci: str) -> None:
    """A pull request's default checkout is a merge preview, not its head.

    ``refs/pull/N/merge`` is synthesised from the head and the current base, so
    it is not a revision that exists in the pull request and it changes when
    the base moves. A check pinned to it does not name what was reviewed.
    """
    assert "github.event.pull_request.head.sha" in python_ci, (
        "the workflow does not pin its checkout to the pull request head SHA"
    )


def test_every_action_is_pinned_to_an_immutable_sha(python_ci: str) -> None:
    used = PINNED_USES.findall(python_ci)
    assert used, "the workflow uses no actions at all"
    for reference in used:
        assert SHA_PIN.match(reference), f"{reference} is not pinned to a commit SHA"


def test_the_gate_and_concurrency_suite_is_named(python_ci: str) -> None:
    """The tests this repository's approval gate depends on, run by name.

    They are what proves two processes cannot drive one run and one approval
    cannot release two. Reaching them only through a wildcard means a rename
    silently stops running them.
    """
    for suite in REQUIRED_SUITES:
        assert (REPO / suite).exists(), f"{suite} does not exist to be run"
        assert suite in python_ci, f"CI does not run {suite}"


def test_the_full_suite_and_the_linter_both_run(python_ci: str) -> None:
    assert re.search(r"^\s*run:\s*pytest -q\s*$", python_ci, re.MULTILINE), (
        "CI runs no unrestricted pytest, so only the named suites are covered"
    )
    assert "ruff check" in python_ci


def test_the_workflow_asks_for_no_more_than_it_needs(python_ci: str) -> None:
    """Read the tree, write nothing. A test job needs no other permission."""
    assert re.search(r"^permissions:\s*$", python_ci, re.MULTILINE)
    assert re.search(r"^\s+contents:\s*read\s*$", python_ci, re.MULTILINE)
    assert not re.search(r"^\s+pull_request_target:", python_ci, re.MULTILINE), (
        "pull_request_target runs a fork's code with repository secrets"
    )
    for scope in (r"write-all", r"contents:\s*write", r"id-token:\s*write"):
        assert not re.search(rf"^\s+{scope}\s*$", python_ci, re.MULTILINE), (
            f"the workflow grants {scope}"
        )


def test_the_declared_python_versions_are_the_supported_ones(python_ci: str) -> None:
    """`requires-python` is a promise, so the minimum has to be exercised."""
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    minimum = re.search(r'requires-python\s*=\s*">=(\d+\.\d+)"', pyproject)
    assert minimum, "pyproject.toml declares no minimum Python version"
    assert f"'{minimum.group(1)}'" in python_ci or f'"{minimum.group(1)}"' in python_ci, (
        f"CI never runs the {minimum.group(1)} it promises to support"
    )


def test_dashboard_ci_is_untouched(python_ci: str) -> None:
    """Adding a Python job must not cost the Node one."""
    dashboard = DASHBOARD_CI.read_text(encoding="utf-8")
    assert re.search(r"^\s{2}pull_request:", dashboard, re.MULTILINE)
    for step in ("npm ci", "npm run build", "npm test"):
        assert step in dashboard, f"Dashboard CI no longer runs {step}"
    for reference in PINNED_USES.findall(dashboard):
        assert SHA_PIN.match(reference), f"{reference} is not pinned to a commit SHA"
