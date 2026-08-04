# Changelog

## [Unreleased]

### Added
- `SECURITY.md` with responsible-disclosure guidance and a documented historical-secret allowlist for rotated credentials.
- `justai/exit_codes.py` documents JustAi's process exit codes and maps a run status to one. 0 is reserved for verified completion; 2 stays reserved for `argparse`'s usage-error code.
- `justai/results.py` now owns the canonical result-status vocabulary and the single run verdict that the synthesizer, the learning layer, and the CLI exit code all read.
- `health.readiness()` reports planning readiness and execution readiness separately; `/health` exposes both alongside `all_ok`.
- `escalate_plan` accepts `blocked_indices`, so checkpoint-blocked tasks stay in the plan at their own position instead of being filtered out.
- `justai/run_identity.py` mints and validates a run id: a UUID, and deliberately not derived from the session label, the clock, the process, or the goal, because each of those collides between two runs started together. It is never read from the environment, for the same reason auto mode is not.
- `justai run --run-id ID` resumes a run against the approval gates already on disk. Omitting it mints a fresh identity, which is what an ordinary run does.
- `OrchestrationResult.run_id` reports the identity a run's gates were scoped to, and `POST /api/run` returns `run_id` alongside `session_ref` before the run reaches a gate, so a dashboard operator can name the run that is asking while it is still asking.
- `checkpoint.sweep_gate_dirs()` collects spent run directories — those holding no gate record — once they are older than `JUSTAI_GATE_TOMBSTONE_TTL` (default one hour). Each run sweeps at the end of its checkpoint stage, so the directory count under `gates/` tracks runs that are live or recent rather than every run ever started. A run that is still going, still holds a decision, or holds a file JustAi did not write is never swept.

### Changed
- README reframed around the current JustAi control-plane scope and the planned `safe-mini` / `local-resident` split.
- Public documentation trimmed to remove stale internal planning artifacts and obsolete release notes.
- `justai run --local` now fails closed with an explicit unavailable-backend error instead of running planner-authored verification commands, and `check_safe_mini_boundary` reports the protocol stub as not-integrated rather than healthy.
- `justai run` prints an execution-readiness warning during preflight, so a run that will fail closed says so before planning.
- The run summary and the stored run record now count blocked tasks alongside skipped ones.
- **Public signature change:** `checkpoint.evaluate` takes auto mode as an argument. `auto=None` still reads `JUSTAI_AUTO_MODE`, so a direct call and a shell that exports the variable both keep working; nothing in the package writes it any more. Auto mode belongs to a run, not to the interpreter.
- **Public signature change:** `checkpoint.evaluate(task, gate, auto=None)` takes a required `GateIdentity` — a run id and a plan index — in place of the free-form `task_id` string. A gate is a decision about one task in one run, and a string two runs can agree on is not an identity. `_write_gate`, `_read_gate`, and the new `gate_path` / `gate_dir` / `cleanup_run` / `run_gate_lock` take the same identity.
- **Gate file layout:** approval gates moved from `gates/gate_<session_ref>-plan-<index>.json` to `gates/<run_id>/plan-<index>.json`. Gates in the old layout are not read at all — a file that names no run decides nothing, in either direction. Nothing migrates them; a run interrupted across the upgrade is re-approved under its new identity.
- Gate records are written atomically and carry the run id, plan index, session label, and task title. A record that contradicts its own location — another run's id, another plan index — is read as no decision rather than as an approval.
- `session_ref` is documented and treated throughout as a human label for tracing and memory. It names nothing and scopes nothing.
- `JUSTAI_GATE_POLL_SECONDS` overrides how often a waiting gate re-reads its file. It changes how quickly a decision is noticed, never what is decided.
- The execute stage takes its counts and trace metadata from `results.tally` instead of summing statuses inline. Withheld work fell between the stage's own "done" and "failed" buckets and was reported by neither the trace nor the hook, and a status nothing recognised was counted there as an absence of failure.
- Mission Control renders planning and execution readiness, including an explicit execution-unavailable state while no backend is integrated.
- The standalone `AgentDispatchPipeline` experiment is quarantined: its `run` raises `NotImplementedError`, and the iterate/escalate phases plus `PipelineResult`, `_run_tests`, `AgentDispatchConfig.test_command`, and `AgentDispatchConfig.work_dir` are removed.

### Fixed
- Local execution mode no longer reports an unperformed mutation as `done`; passing a planner-authored success criterion is no longer treated as task completion.
- Unavailable-backend modes no longer print a fictitious `failed on <model>, escalating to <model>` notice or dispatch a second time; with no backend wired, no model is invoked and nothing is retried.
- README opening description and the packaged project description no longer advertise a productive local / mini-swe-agent execution backend.
- `justai status` no longer exits 0 while the API's `/health` reports `all_ok: false`. Both now read one derivation, and an empty probe set is no longer treated as healthy.
- An ambiguous goal now exits `CLARIFICATION_REQUIRED` instead of 0, in both `justai run` and the legacy `tools/justai_cli.py` entrypoint. Nothing was planned and nothing ran, so 0 told a shell chain the work had happened.
- Checkpoint-blocked tasks no longer renumber the plan. Compacting the task list shifted every later position, so `depends_on` could point at an unrelated task and a dependent could run on a dependency that never completed.
- A `depends_on` entry that cannot name an already-decided task — negative, past the end, its own position, or a later task — now fails that task closed instead of being silently treated as satisfied.
- Invalid or out-of-range checkpoint-blocked positions are rejected instead of being dropped and allowing a vetoed task to dispatch.
- `synthesize` and `learning.record_run` no longer derive success independently, and no longer call a run with zero results complete. An unrecognised result status now raises rather than falling through to a non-failure bucket; the learning layer refuses to store such a run.
- Auto mode is scoped to one run. An auto-approved request no longer disables the R1 operator veto for later runs in the same process.
- An approval releases one run. The gate an R2 task waited on was named after `session_ref`, which `justai run` leaves empty unless `--session` is passed and which the dashboard reused per second; two ordinary concurrent runs therefore agreed on a filename and waited on the same file, and one operator approval cleared both — including the run the operator never looked at. The R1 veto collided the same way, in the other direction.
- Gate cleanup can only name one run. It took no argument that could express a wider target, so a finished run no longer deletes a concurrent run's pending approval.
- An approval that arrives before the run records its gate is no longer destroyed by it. The R2 branch marked its gate `pending` with an unconditional write, which overwrote whatever was already on disk — a `--run-id` resume approved before the restart, a dashboard operator using the run id `POST /api/run` returns before the run reaches a gate, or anyone answering the Discord notification inside its ten-second send. The run then waited forever for a decision it had been given and had itself deleted. The marker is now created rather than written, so it only ever appears where nothing has decided yet. A record that cannot speak for this run is still no decision, so an R2 task holding one keeps waiting.
- Gate cleanup no longer removes the lock file while holding it. `flock` excludes the holders of one inode, so unlinking it under the lock ended exclusion rather than the run: a process queued on that file woke holding an inode nothing could reach by name, the next process found the name free and created a second lock, and both then drove the same run's gates at once. Cleanup removes the run's records and keeps the lock; `run_gate_lock` additionally re-takes its lock if the file it acquired is no longer the one at the path, which is what makes an external `/tmp` reaper — or the sweep — safe. `sweep_gate_dirs` renames a directory out of the namespace before deleting anything, so no unlink ever happens under a held lock.
- A finished run no longer leaves a gate directory behind forever. Keeping the lock means the directory outlives the run, and a run interrupted before cleanup already did; `sweep_gate_dirs` bounds both. Interrupted runs that still hold a gate record are the deliberate exception and are kept indefinitely — the record is a pending approval nobody answered, and it is what `--run-id` resumes against.
- Malformed executor results now fail the run nonzero while preserving the error hook, ledger entry, trajectory-record attempt, and trace flush instead of escaping through reporting code.
- Two malformations that are not a bad string field are refused at the same tally boundary: a `duration_seconds` that is not a number, and an executor return value that is not a sequence of results at all. Both used to escape as `TypeError` with nothing flushed and nothing recorded — the first from the synthesizer, which runs past the execute stage's failure boundary, and the second from the failure handler itself while trying to iterate what it had been handed.
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
