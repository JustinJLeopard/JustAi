# Product CI runner policy

Python CI and Dashboard CI use the standard GitHub-hosted `ubuntu-26.04`
x64 runner explicitly. Python remains a 3.12/3.13 matrix; the dashboard takes
Node 24.x from `dashboard/package.json`. Both workflows test the exact PR head.
Action SHAs, read-only token permissions, fork-safe triggers and credential
non-persistence remain unchanged. No larger or custom paid runner is selected.

GitHub announced the `ubuntu-latest` migration from 24.04 to 26.04 for
October 19 through November 19, 2026:
[official migration announcement](https://github.blog/changelog/2026-09-17-ubuntu-26-generally-available-and-latest-migration/).
The explicit label avoids an implicit platform change. Qualification requires
successful Python 3.12 and 3.13 lint/tests and dashboard install/build/tests on
the PR's exact head, with the hosted job's runner image recorded. Local workflow
contract tests alone do not establish hosted image compatibility.

If those jobs expose a 26.04 incompatibility, preserve the failed run and
identify the failing dependency or platform assumption before changing policy.
For a temporary fallback, change **both** product workflow `runs-on` labels to
`ubuntu-24.04` and the expected label in
`tests/test_ci_workflows.py::test_product_ci_uses_explicit_qualified_runner`.
Keep the language versions, checkout refs, action pins and all security settings.
Run the focused workflow tests, review that delta, and qualify both Python jobs
and the dashboard again on the fallback. Never silently continue after a failed
qualification or use `ubuntu-latest` as a fallback. A normal revert of this change
restores the previous source, including its moving-label behavior; prefer the
explicit 24.04 fallback when recovering a platform incompatibility.

This policy does not change repository rulesets. The existing required
`Exact-head acceptance` attestation remains separate; it does not by itself
inspect Python or dashboard results. The integrator must inspect the actual
product CI results before acceptance. Direct required product-check enforcement
remains tracked separately in issues #58 and #60 and requires a separately
selected settings operation after check contexts are verified.
