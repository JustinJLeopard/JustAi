"""Reviewer must flag plans that fabricate a precondition the goal assumes.

Failure mode (from adversarial testing): for a goal that consumes an existing
input (copy/summarize/convert X), the planner inserts a task that CREATES X
(touch/redirect), so every subtask "succeeds" while the real intent — act on
the pre-existing X — is never satisfied. That is a false completion.
"""

from __future__ import annotations

from justai.reviewer import _heuristic_review
from justai.scope_planner import AgentType, Plan, RiskLevel, Task


def _task(title, description, criteria, depends_on=None):
    return Task(
        title=title,
        description=description,
        agent=AgentType.MINI,
        risk=RiskLevel.R1,
        success_criteria=criteria,
        depends_on=depends_on or [],
    )


def test_flags_fabricated_input_precondition():
    plan = Plan(
        goal="Copy /data/report.csv to /backup/report.csv",
        tasks=[
            _task("Create source", "Ensure the source exists: touch /data/report.csv",
                  "test -f /data/report.csv"),
            _task("Copy it", "cp /data/report.csv /backup/report.csv",
                  "test -f /backup/report.csv", depends_on=[0]),
        ],
        session_ref="t",
    )
    result = _heuristic_review(plan)
    assert result.approved is False
    assert any("fabricate" in f.lower() or "manufactur" in f.lower() for f in result.feedback), result.feedback


def test_allows_creation_when_goal_asks_to_create():
    plan = Plan(
        goal="Create /data/report.csv with a header row",
        tasks=[
            _task("Create file", "touch /data/report.csv and add header",
                  "test -f /data/report.csv"),
        ],
        session_ref="t",
    )
    result = _heuristic_review(plan)
    assert result.approved is True, result.feedback


def test_allows_normal_consumer_plan_without_fabrication():
    plan = Plan(
        goal="Summarize /data/report.csv into three bullet points",
        tasks=[
            _task("Read and summarize", "cat /data/report.csv and write a summary to /tmp/summary.txt",
                  "test -s /tmp/summary.txt"),
        ],
        session_ref="t",
    )
    result = _heuristic_review(plan)
    assert result.approved is True, result.feedback
