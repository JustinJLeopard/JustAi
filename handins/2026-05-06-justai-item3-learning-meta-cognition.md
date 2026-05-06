# JustAi Item 3 - Learning Meta-Cognition

Branch: `justai-learning-meta-cognition-2026-05-06`

## Schema Additions

`record_run()` remains backward-compatible with `record_run(goal, results, duration)`.
The new fields are additive keyword-only metadata:

- `failure_class`: normalized category from `timeout`, `tool_error`,
  `wrong_action`, `inferred_action`, or `verification_fail`. Explicit caller
  values win; otherwise `RunResult.results` and legacy result statuses are
  inspected.
- `execution_evidence`: list of durable action/result pairs extracted from
  safe-mini-shaped `RunResult.actions` and `RunResult.results`. Each entry
  carries `action_id`, `result_id`, `evidence_ref`, `status`, and step label.
- `strategy_used`: selected catalog strategy plus explicit `accepted` or
  `ignored` outcome.
- `did_next_plan_change`: loop-awareness boolean. It can be supplied directly
  or computed from prior/current `chosen_focus` and `next_experiment`.
- `correlation_id`: optional correlation hook for future verdict mirroring.

`TrajectoryStore` now persists and returns these fields so `enrich_context()`
can surface failure distribution, evidence links, strategy outcomes, and
next-plan-change signals in future planner context.

## Verification

- `python3 -m pytest tests/test_learning.py -q` -> 12 passed
- `python3 -m pytest tests/test_trajectory.py -q` -> 6 passed
- `python3 -m pytest -q` -> 368 passed, 6 known baseline failures, 14 subtests passed
