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


def test_flags_quoted_fabricated_input_precondition():
    plan = Plan(
        goal="Convert /data/report.csv to /backup/report.json",
        tasks=[
            _task("Create source", 'touch "/data/report.csv"', "test -f /data/report.csv"),
            _task("Convert it", "python convert.py /data/report.csv > /backup/report.json",
                  "test -s /backup/report.json", depends_on=[0]),
        ],
        session_ref="t",
    )
    result = _heuristic_review(plan)
    assert result.approved is False
    assert any("fabricate" in f.lower() or "manufactur" in f.lower() for f in result.feedback), result.feedback


def test_allows_creation_when_goal_introduces_the_path_as_output():
    # Consumer verb present (so the check runs) AND the path is introduced as an
    # output by "generate <path>", so creating it is correct, not fabricated.
    plan = Plan(
        goal="Generate /data/report.csv, then compress /data/report.csv",
        tasks=[
            _task("Create file", "touch /data/report.csv and add header",
                  "test -f /data/report.csv"),
        ],
        session_ref="t",
    )
    result = _heuristic_review(plan)
    assert result.approved is True, result.feedback


def test_allows_output_path_created_by_task():
    # "convert IN to OUT" — OUT is a destination; a task writing it must not flag.
    plan = Plan(
        goal="Convert /data/in.csv to /data/out.json",
        tasks=[
            _task("Convert", "jq . /data/in.csv > /data/out.json", "test -s /data/out.json"),
        ],
        session_ref="t",
    )
    result = _heuristic_review(plan)
    assert result.approved is True, result.feedback


def test_does_not_flag_prefix_path_collision():
    # touching report.csv.lock must not match the goal input report.csv.
    plan = Plan(
        goal="Summarize /data/report.csv",
        tasks=[
            _task("Lock", "touch /data/report.csv.lock", "test -f /data/report.csv.lock"),
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
