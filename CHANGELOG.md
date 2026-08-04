# Changelog

## [Unreleased]

### Added
- `SECURITY.md` with responsible-disclosure guidance and a documented historical-secret allowlist for rotated credentials.
- `justai/exit_codes.py` documents JustAi's process exit codes and maps a run status to one. 0 is reserved for verified completion; 2 stays reserved for `argparse`'s usage-error code.
- `justai/results.py` now owns the canonical result-status vocabulary and the single run verdict that the synthesizer, the learning layer, and the CLI exit code all read.
- `health.readiness()` reports planning readiness and execution readiness separately; `/health` exposes both alongside `all_ok`.
- `escalate_plan` accepts `blocked_indices`, so checkpoint-blocked tasks stay in the plan at their own position instead of being filtered out.

### Changed
- README reframed around the current JustAi control-plane scope and the planned `safe-mini` / `local-resident` split.
- Public documentation trimmed to remove stale internal planning artifacts and obsolete release notes.
- `justai run --local` now fails closed with an explicit unavailable-backend error instead of running planner-authored verification commands, and `check_safe_mini_boundary` reports the protocol stub as not-integrated rather than healthy.
- `justai run` prints an execution-readiness warning during preflight, so a run that will fail closed says so before planning.
- The run summary and the stored run record now count blocked tasks alongside skipped ones.
- The standalone `AgentDispatchPipeline` experiment is quarantined: its `run` raises `NotImplementedError`, and the iterate/escalate phases plus `PipelineResult`, `_run_tests`, `AgentDispatchConfig.test_command`, and `AgentDispatchConfig.work_dir` are removed.

### Fixed
- Local execution mode no longer reports an unperformed mutation as `done`; passing a planner-authored success criterion is no longer treated as task completion.
- Unavailable-backend modes no longer print a fictitious `failed on <model>, escalating to <model>` notice or dispatch a second time; with no backend wired, no model is invoked and nothing is retried.
- README opening description and the packaged project description no longer advertise a productive local / mini-swe-agent execution backend.
- `justai status` no longer exits 0 while the API's `/health` reports `all_ok: false`. Both now read one derivation, and an empty probe set is no longer treated as healthy.
- An ambiguous goal now exits `CLARIFICATION_REQUIRED` instead of 0, in both `justai run` and the legacy `tools/justai_cli.py` entrypoint. Nothing was planned and nothing ran, so 0 told a shell chain the work had happened.
- Checkpoint-blocked tasks no longer renumber the plan. Compacting the task list shifted every later position, so `depends_on` could point at an unrelated task and a dependent could run on a dependency that never completed.
- A `depends_on` entry that cannot name an already-decided task — negative, past the end, its own position, or a later task — now fails that task closed instead of being silently treated as satisfied.
- `synthesize` and `learning.record_run` no longer derive success independently, and no longer call a run with zero results complete. An unrecognised result status now raises rather than falling through to a non-failure bucket; the learning layer refuses to store such a run.
- `AgentDispatchPipeline` no longer runs the launching checkout's test suite and attributes the result to code it generated as strings and never wrote to disk.

## [v0.4.0] - 2026-04-30

### Changed
- Repo identity reframed around the three-repo split: `safe-mini` substrate, JustAi orchestrator, and `local-resident` experiment driver.
- Pipeline narrative reduced to a transparent control-plane: scope, intent, review, checkpoint, execute, and synthesize.

### Added
- Stub runner protocol and canonical substrate types for the future substrate boundary.
- Static analysis tooling for the Python package and tests.
- Documentation contract tests to prevent legacy-term regressions in current docs.

### Removed
- Deprecated runtime integration paths that no longer match the narrowed control-plane role.
- Obsolete dispatch surfaces that are outside the current branch scope.

### Fixed
- Test references to removed services and dispatch paths.
- Demo deployment entrypoint and playback behavior.

### Documentation
- README and architecture docs rewritten around the control-plane thesis and three-repo plan.
- Historical planning material removed from the current public tree.
