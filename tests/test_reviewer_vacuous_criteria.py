"""Success criteria that cannot fail must be rejected before execution.

Observed in the installed-executor productive trial: the planner emitted
    grep -Fxq 'Hello from JustAi' greeting.py && echo 'success' || echo 'failure'
which exits 0 whether or not the grep matches. Verification therefore passed
vacuously -- any artifact, including a wrong one, would have been marked done --
and the receipt read "done: failure".
"""

from __future__ import annotations

import pytest

from justai.reviewer import _heuristic_review
from justai.scope_planner import AgentType, Plan, RiskLevel, Task


def _plan(criteria: str, goal: str = "Create greeting.py that prints Hello") -> Plan:
    return Plan(
        goal=goal,
        tasks=[Task(title="t", description="do it", agent=AgentType.MINI,
                    risk=RiskLevel.R0, success_criteria=criteria, depends_on=[])],
        session_ref="t",
    )


@pytest.mark.parametrize("criteria", [
    "grep -Fxq 'Hello from JustAi' greeting.py && echo 'success' || echo 'failure'",
    "test -f out.txt || true",
    "test -f out.txt || :",
    "python3 build.py; true",
    "test -f out.txt || exit 0",
    "test -f out.txt || printf 'missing'",
])
def test_criteria_that_cannot_fail_are_rejected(criteria):
    result = _heuristic_review(_plan(criteria))
    assert result.approved is False, criteria
    assert any("cannot fail" in f.lower() for f in result.feedback), result.feedback


@pytest.mark.parametrize("criteria", [
    "test -f greeting.py",
    "grep -Fxq 'Hello from JustAi' greeting.py",
    "python3 greeting.py | grep -Fxq 'Hello from JustAi'",
    "test -f out.txt || exit 1",
    "test -s a.txt && test -s b.txt",
    "cmp -s a.txt b.txt",
])
def test_real_criteria_are_kept(criteria):
    result = _heuristic_review(_plan(criteria))
    assert result.approved is True, result.feedback


@pytest.mark.parametrize("criteria", [
    # A no-op fallback on a SETUP step, with a real check last: legitimate.
    "mkdir -p out || true; test -f out/app.js",
    "docker stop c || true && test -f result.txt",
    "npm audit || echo 'warn' >&2; test -f dist/app.js",
    # The idiom appears only inside a quoted search pattern: legitimate.
    "grep -Fq '|| echo' deploy.sh",
    "grep -q '|| true' Makefile",
])
def test_no_op_fallback_before_a_real_check_is_kept(criteria):
    result = _heuristic_review(_plan(criteria))
    assert result.approved is True, result.feedback


@pytest.mark.parametrize("criteria", [
    "echo done",
    "true",
    "printf 'ok'",
    "pytest -q\nexit 0",
    "if grep -q x f; then echo yes; else echo no; fi",
])
def test_other_always_zero_shapes_are_rejected(criteria):
    result = _heuristic_review(_plan(criteria))
    assert result.approved is False, criteria
    assert any("cannot fail" in f.lower() for f in result.feedback), result.feedback


def test_if_else_that_can_fail_is_kept():
    result = _heuristic_review(_plan("if test -f a.txt; then echo ok; else exit 1; fi"))
    assert result.approved is True, result.feedback
