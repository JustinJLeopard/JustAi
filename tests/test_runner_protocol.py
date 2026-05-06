import pytest

from justai.runner_protocol import (
    ActionRecord,
    AgentRunner,
    Budget,
    Chunk,
    ExecutorPolicy,
    FailureClass,
    ObservationPolicy,
    ResultRecord,
    RunResult,
)
from justai.scope_planner import AgentType, RiskLevel, Task


def test_failure_class_has_expected_members_and_values():
    assert {member.name: member.value for member in FailureClass} == {
        "SAFETY_VIOLATION": "safety-violation",
        "ACTION_PROTOCOL_VIOLATION": "action-protocol-violation",
        "EXHAUSTED_IDEAS": "exhausted-ideas",
        "BUDGET_EXHAUSTED": "budget-exhausted",
        "CONTEXT_STARVATION": "context-starvation",
        "REWARD_HACKING": "reward-hacking",
        "EMBODIMENT_FAILURE": "embodiment-failure",
    }


def test_observation_policy_has_expected_members_and_values():
    assert {member.name: member.value for member in ObservationPolicy} == {
        "FULL": "full",
        "TAIL": "tail",
        "HEAD_TAIL": "head-tail",
        "STRUCTURED": "structured",
        "STRUCTURED_RAW_TAIL": "structured+raw-tail",
    }


def test_executor_policy_has_expected_members_and_values():
    assert {member.name: member.value for member in ExecutorPolicy} == {
        "OPEN": "open",
        "SAFE": "safe",
        "ALLOWLIST": "allowlist",
    }


def test_budget_requires_move_and_observation_budgets():
    budget = Budget(move_budget=12, observation_budget=4096)

    assert budget.move_budget == 12
    assert budget.observation_budget == 4096
    with pytest.raises(TypeError):
        Budget(12)


def test_chunk_instantiates_with_goal_success_criteria_and_budget():
    budget = Budget(move_budget=8, observation_budget=2048)
    chunk = Chunk(
        goal="Add runner protocol tests",
        success_criteria="python -m pytest tests/test_runner_protocol.py",
        budget=budget,
    )

    assert chunk.goal == "Add runner protocol tests"
    assert chunk.success_criteria == "python -m pytest tests/test_runner_protocol.py"
    assert chunk.budget == budget


def test_run_result_defaults_optional_fields():
    chunk = Chunk(
        goal="Verify protocol import",
        success_criteria="python -c 'import justai.runner_protocol'",
        budget=Budget(move_budget=2, observation_budget=1000),
    )
    result = RunResult(
        chunk=chunk,
        success=True,
        steps_used=1,
        final_diff="",
        transcript_path="/tmp/run.txt",
    )

    assert result.chunk == chunk
    assert result.success is True
    assert result.steps_used == 1
    assert result.failure_class is None
    assert result.cost_usd == 0.0
    assert result.tokens_used == 0
    assert result.latency_seconds == 0.0
    assert result.actions == []
    assert result.results == []


def test_run_result_carries_action_and_result_records():
    chunk = Chunk(
        goal="Verify action evidence",
        success_criteria="python -m pytest tests/test_runner_protocol.py",
        budget=Budget(move_budget=2, observation_budget=1000),
    )
    action = ActionRecord.create("bash", {"command": "pytest"})
    result_record = ResultRecord.create(
        action.action_id,
        "ok",
        evidence_ref="/tmp/action-1.json",
    )

    result = RunResult(
        chunk=chunk,
        success=True,
        steps_used=1,
        final_diff="",
        transcript_path="/tmp/run.txt",
        actions=[action],
        results=[result_record],
    )

    assert result.actions == [action]
    assert result.results == [result_record]
    assert result.results[0].action_id == result.actions[0].action_id
    assert result.results[0].status == "ok"
    assert result.results[0].evidence_ref == "/tmp/action-1.json"


def test_every_action_lands_matching_result_or_timeout_result():
    chunk = Chunk(
        goal="Verify every action has explicit evidence closure",
        success_criteria="python -m pytest tests/test_runner_protocol.py",
        budget=Budget(move_budget=3, observation_budget=1000),
    )
    completed = ActionRecord.create("bash", {"command": "pytest"})
    timed_out = ActionRecord.create("bash", {"command": "sleep 999"})
    result = RunResult(
        chunk=chunk,
        success=False,
        steps_used=2,
        final_diff="",
        transcript_path="/tmp/run.txt",
        actions=[completed, timed_out],
        results=[
            ResultRecord.create(completed.action_id, "ok", evidence_ref="/tmp/completed.json"),
            ResultRecord.create(timed_out.action_id, "timeout", evidence_ref="/tmp/timeout.json"),
        ],
    )

    result_by_action_id = {record.action_id: record for record in result.results}

    assert set(result_by_action_id) == {action.action_id for action in result.actions}
    assert result_by_action_id[completed.action_id].status == "ok"
    assert result_by_action_id[timed_out.action_id].status == "timeout"


def test_agent_runner_protocol_runtime_checkable_by_duck_typing():
    class FakeRunner:
        def run(
            self,
            chunk: Chunk,
            observation_policy: ObservationPolicy = ObservationPolicy.STRUCTURED_RAW_TAIL,
            executor_policy: ExecutorPolicy = ExecutorPolicy.SAFE,
        ) -> RunResult:
            return RunResult(
                chunk=chunk,
                success=True,
                steps_used=1,
                final_diff="",
                transcript_path="/tmp/fake-runner.txt",
            )

        def classify_failure(self, result: RunResult) -> FailureClass:
            return result.failure_class or FailureClass.EXHAUSTED_IDEAS

    class MissingClassifier:
        def run(
            self,
            chunk: Chunk,
            observation_policy: ObservationPolicy = ObservationPolicy.STRUCTURED_RAW_TAIL,
            executor_policy: ExecutorPolicy = ExecutorPolicy.SAFE,
        ) -> RunResult:
            return RunResult(
                chunk=chunk,
                success=True,
                steps_used=1,
                final_diff="",
                transcript_path="/tmp/missing-classifier.txt",
            )

    assert isinstance(FakeRunner(), AgentRunner)
    assert not isinstance(MissingClassifier(), AgentRunner)


def test_chunk_rejects_justai_task_as_goal_shape():
    task = Task(
        title="Do orchestration work",
        description="This is a JustAi orchestration-level task.",
        agent=AgentType.MINI,
        risk=RiskLevel.R1,
        success_criteria="pytest",
        depends_on=[],
        session_ref="phase-4",
    )

    with pytest.raises(TypeError, match="Chunk.goal must be a string"):
        Chunk(
            goal=task,
            success_criteria=task.success_criteria,
            budget=Budget(move_budget=4, observation_budget=1024),
        )
