# RFC — safe-mini Scope After JustAi Action/Result Pairing

**Date:** 2026-05-06  
**Status:** DRAFT / SPEC ONLY  
**Author:** Codex  
**Repos inspected:** `JustAi@demo-build`, `safe-mini@origin/main`  
**Primary refs:** `JustAi` commit `0ba9052`; `safe-mini` tag `v0.2.0` / commit `b3d3a41`

## Purpose

Define the sensible next scope for `safe-mini` now that `JustAi` has a
post-merge runner-protocol stub with explicit `ActionRecord` / `ResultRecord`
pairing.

This RFC is intentionally spec-only. It proposes no code changes in this
handin.

## Inputs Read

- `JustAi/handins/2026-05-06-bubbleup-runner-protocol-and-learning.md`
- `JustAi/justai/runner_protocol.py`
- `JustAi/tests/test_runner_protocol.py`
- Local clone: `/home/justinleopard/projects/safe-mini`
- `safe-mini` remote state after `git fetch origin --prune`

## Current Public State

`safe-mini` is public at `https://github.com/JustinJLeopard/safe-mini`.

Observed public refs:

- `origin/main` -> `b3d3a41 Merge pull request #1 from JustinJLeopard/refactor/port-from-reference`
- tag `v0.2.0` -> `b3d3a41`
- prior scaffold commit `1073aed scaffold: safe-mini v0.1.0`
- initial commit `2ff4011`

Local caveat:

- The local checkout is still on `refactor/port-from-reference` at `096b13a`.
- That branch was deleted on origin after merge.
- Its tree is the feature payload merged by `b3d3a41`; this RFC treats
  `origin/main` / `v0.2.0` as the public source of truth.

Version/docs caveat:

- `origin/main` is tagged `v0.2.0`, but `pyproject.toml` still says
  `version = "0.1.0"`.
- `safe_mini/__init__.py` still says `__version__ = "0.1.0"`.
- `README.md` still describes the package as initial `v0.1.0` scaffolding and
  says the concrete `SafeMiniRunner` is the next port pass, even though
  `SafeMiniRunner` now exists in `safe_mini/runner.py`.

## What safe-mini Is

`safe-mini` is the substrate-level runtime for mini-swe-agent-style coding
agents that emit one bash action at a time under explicit budgets and safety
policy.

Its intended boundary is generic and consumer-neutral:

- It does not know about JustAi tasks, sessions, dashboards, Discord, memory, or
  learning aggregation.
- It owns the local execution loop, worktree isolation, executor safety,
  observation shaping, transcript/evidence capture, and failure taxonomy.
- `JustAi` should consume it as an `AgentRunner` implementation, while keeping
  orchestration-level concepts in JustAi.

## What safe-mini Does Today

### Public API / Entry Points

Exported from `safe_mini/__init__.py`:

- `SafeMiniRunner`
- `AgentRunner`
- `Budget`
- `Chunk`
- `RunResult`
- `Observation`
- `FailureClass`
- `ObservationPolicy`
- `ExecutorPolicy`
- `ExecutorPolicies`
- `ActionFormat`
- `ParsedAction`
- `ActionParseError`
- `parse_action`
- `classify_failure`

Core modules:

- `safe_mini/protocol.py` defines the `AgentRunner` protocol.
- `safe_mini/types.py` defines canonical substrate dataclasses and enums.
- `safe_mini/runner.py` implements `SafeMiniRunner`.
- `safe_mini/action_parser.py` parses fenced `bash-action` blocks and JSON bash
  actions.
- `safe_mini/policies/executor.py` implements `open`, `safe`, and `allowlist`
  execution policies.
- `safe_mini/observation/policies.py` implements `full`, `tail`, `headtail`,
  `structured`, and `structured+raw-tail` observation shaping.
- `safe_mini/worktree.py` provisions fresh copied worktrees with scoped HOME.
- `safe_mini/classifier.py` maps failed run results to the 7-class taxonomy.

### Current Type Shape

`safe-mini` `RunResult` is currently transcript-centric:

- `label`
- `success`
- `leaked_secret`
- `blocked_commands`
- `steps`
- `elapsed_sec`
- `final_tests_pass`
- `transcript: list[dict]`
- `failure_class`
- `action_protocol_violations`
- `observation_chars_used`
- `observation_budget_exhausted`
- `reward_hacking_detected`
- `worktree_path`

It does not yet define typed `ActionRecord` or `ResultRecord`.

### Runner Behavior

`SafeMiniRunner.run()` currently:

- provisions a fresh worktree from `repo_path`
- starts a transcript with a task prompt
- asks the model for one action at a time through `ActionModel.next(transcript)`
- parses either fenced bash-action or JSON bash action
- runs the parsed command through the selected executor policy
- shapes command output through the selected observation policy
- records assistant/user transcript entries for each action/result turn
- tracks leaked fake secret output, blocked commands, action protocol
  violations, observation budget usage, reward-hacking heuristic, and final test
  result
- classifies failed runs with the 7-class taxonomy
- optionally keeps or cleans up the worktree

### Test Surface

Current public tests cover:

- Protocol structural conformance: `tests/test_protocol_contract.py`
- Type shape and taxonomy locks: `tests/test_types_contract.py`
- Action parser behavior: `tests/test_action_parser.py`
- Executor policy behavior: `tests/test_executor_policies.py`
- Observation shaping: `tests/test_observation_policies.py`
- Failure classification: `tests/test_classifier.py`
- Worktree provisioning: `tests/test_worktree.py`
- Runner integration using a scripted model and fixture repo:
  `tests/test_runner_integration.py`

Important integration assertions already present:

- success path completes
- budget exhaustion is detected
- safety violation is detected
- action protocol violation is detected
- context starvation is detected
- reward hacking is detected
- open executor can leak the fake safety-test secret

## JustAi Integration Point

`JustAi/justai/runner_protocol.py` is still a stub, but it now contains the
shape that safe-mini should probably absorb:

- `ActionRecord(action_id, action_type, args, issued_at)`
- `ResultRecord(result_id, action_id, status, evidence_ref, finished_at)`
- `RunResult.actions: list[ActionRecord]`
- `RunResult.results: list[ResultRecord]`

JustAi tests now lock the desired invariant:

- every action has a matching result by `action_id`
- timeout is an explicit result status, not an absent result

The JustAi file explicitly says the canonical home for these types is the
`safe-mini` repo and warns not to add JustAi-specific fields to the substrate
types.

## Proposed Scope Expansion

### Scope 1 — Adopt Typed Action/Result Evidence

Add generic typed evidence records to `safe_mini/types.py`:

```python
@dataclass
class ActionRecord:
    action_id: UUID
    action_type: str
    args: dict
    issued_at: datetime


@dataclass
class ResultRecord:
    result_id: UUID
    action_id: UUID
    status: Literal["ok", "fail", "timeout"]
    evidence_ref: str | None
    finished_at: datetime
```

Extend `RunResult` with:

```python
actions: list[ActionRecord] = field(default_factory=list)
results: list[ResultRecord] = field(default_factory=list)
```

This should be additive for `safe-mini` consumers.

### Scope 2 — Populate Records in SafeMiniRunner

For every parsed bash action:

- create an `ActionRecord` before executor dispatch
- set `action_type = "bash"`
- set `args = {"command": parsed.command, "format": parsed.format.value}`
- create exactly one `ResultRecord` after executor return
- map statuses:
  - `ok` when return code is `0` and command is not blocked/timed out
  - `fail` when return code is nonzero or command is blocked
  - `timeout` when the observation has `timed_out = True`
- set `evidence_ref` to a stable pointer into the transcript/artifact

Minimum viable `evidence_ref` format:

- `transcript:<turn_index>`

Better follow-up format:

- `artifact:<path>#turn=<turn_index>`

The minimum is enough to prove durable correlation before full incident
artifact naming is finalized.

### Scope 3 — Preserve Transcript Back-Compat

Do not replace `transcript` immediately.

`transcript` remains useful for:

- replay/debugging
- prompt context reconstruction
- failure classifier input
- fixture tests

The new typed records should become the stable machine contract, while
`transcript` remains the human/audit artifact.

### Scope 4 — Lock the Correlation Invariant in safe-mini Tests

Add safe-mini tests equivalent to the JustAi stub tests:

- default `RunResult.actions == []`
- default `RunResult.results == []`
- `ActionRecord.create(...)` creates UUID + UTC timestamp
- `ResultRecord.create(...)` links to an action UUID
- every action emitted by `SafeMiniRunner` has exactly one matching result
- blocked commands produce `status == "fail"` with evidence
- timed-out commands produce `status == "timeout"` with evidence
- action protocol violations before command execution do not create a fake
  action; instead the protocol violation remains on the run-level failure path

### Scope 5 — Align JustAi Import Path After safe-mini Ships

After safe-mini releases the typed records:

- Replace JustAi's stub with re-exports from `safe_mini`.
- Add a git URL pin first, then PyPI pin later.
- Keep JustAi's orchestration-only tests around consumer expectations, not
  duplicate substrate implementation details.

## Non-Goals

Do not add these to `safe-mini`:

- JustAi `Task`
- `session_ref`
- dashboard fields
- Discord/event bus fields
- learning-store fields
- planner strategy metadata
- user-facing orchestration status

Those belong in JustAi or local-resident.

Do not make the first action/result pass depend on:

- a database
- cross-run memory
- a full artifact indexer
- PyPI publication

The right first move is an additive typed evidence contract plus runner
population and tests.

## Recommended Sequencing

1. Fix safe-mini release metadata/docs drift:
   - bump `pyproject.toml` / `__version__` to match the next tag
   - update README current-state text to acknowledge `SafeMiniRunner`
2. Add `ActionRecord` / `ResultRecord` to `safe_mini/types.py`.
3. Export them from `safe_mini/__init__.py`.
4. Extend `RunResult` with `actions` and `results`.
5. Populate records in `SafeMiniRunner.run()`.
6. Add type-contract and runner-integration tests for one-result-per-action.
7. Tag a new safe-mini release.
8. Update JustAi to import from safe-mini instead of maintaining the stub.

## Open Questions for Justin

1. Should `safe-mini` keep the current `Chunk(id, description, success_criteria,
   budget)` shape, or converge toward JustAi's stub shape
   `Chunk(goal, success_criteria, budget)` before JustAi imports it?
2. Should `AgentRunner.run()` keep the current safe-mini signature
   `run(chunk, budget, observation_policy, executor_policy)`, or should budget
   only live on `chunk`?
3. Is `ResultRecord.status` limited to `ok | fail | timeout`, or should
   `blocked` be its own status instead of `fail` plus failure classification?
4. What should the durable `evidence_ref` format be for v0.3.0:
   transcript index, artifact path, JSONL event id, or a URI-like scheme?
5. Should action protocol violations before command execution get their own
   typed record, or remain run-level failures with no action record?
6. Should `safe-mini` expose a helper that validates
   `set(result.action_id) == set(action.action_id)`, or should this stay as a
   test-only invariant?
7. Should `safe-mini` write transcript artifacts to disk now, or wait until the
   action/result evidence contract is merged?
8. Should JustAi pin `safe-mini` by tag only after the metadata/docs drift is
   fixed, or is a commit pin acceptable for the first integration pass?

## Recommendation

Proceed with a narrow `safe-mini` v0.3.0 scope:

- metadata/docs cleanup
- typed `ActionRecord` / `ResultRecord`
- additive `RunResult.actions/results`
- runner population of those records
- invariant tests

Do not broaden into JustAi orchestration semantics. The ActionRecord /
ResultRecord pairing is substrate-generic and belongs in `safe-mini`, but the
learning and planning interpretation of those records belongs above the
substrate.

Confidence: 0.88. The repo state and JustAi stub are directly inspected; the
main uncertainty is Justin's preferred compatibility direction for `Chunk` and
`AgentRunner.run()` signatures.
