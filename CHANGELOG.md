# Changelog

## [Unreleased]

### Added
- `SECURITY.md` with responsible-disclosure guidance and a documented historical-secret allowlist for rotated credentials.

### Changed
- README reframed around the current JustAi control-plane scope and the planned `safe-mini` / `local-resident` split.
- Public documentation trimmed to remove stale internal planning artifacts and obsolete release notes.
- `justai run --local` now fails closed with an explicit unavailable-backend error instead of running planner-authored verification commands, and `check_safe_mini_boundary` reports the protocol stub as not-integrated rather than healthy.

### Fixed
- Local execution mode no longer reports an unperformed mutation as `done`; passing a planner-authored success criterion is no longer treated as task completion.

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
