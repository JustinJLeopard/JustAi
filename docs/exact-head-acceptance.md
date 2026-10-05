# Exact-head acceptance

After independent review has accepted the exact current head and required CI has
passed, an authorized maintainer publishes that decision with:

```sh
gh workflow run exact-head-acceptance.yml --ref main \
  -f pr_number=NUMBER -f head_sha=FULL_40_CHARACTER_HEAD_SHA
```

Run this in the repository checkout, or add `--repo OWNER/REPO`. Verify the
workflow finishes successfully and the `Exact-head acceptance` check appears on
that exact SHA. A new commit needs a new independent review and acceptance.
Dispatch is an attestation that review has happened; it does not perform review.

The publisher only accepts an open, non-draft, same-repository PR targeting
`main`, with the supplied SHA matching its current head. Both the dispatcher and
rerun actor must be `JustinJLeopard`; dispatch must use `main`. No PR code is
checked out or executed. Publication grants only checks-write and PR-read.

Merge this publisher before adding `Exact-head acceptance` to repository rules.
The workflow alone does not enforce a merge gate. Activation is a separate
ruleset change after proving a missing acceptance blocks, an exact acceptance
passes, and a new head loses acceptance. Keep all other required checks intact.

Binding a required check to the GitHub Actions app identifies the app, not this
specific workflow. Another workflow with checks-write can publish the same
check name. This publisher and an app-bound ruleset are not a universal defense
against a malicious writer changing workflows; consumers that need that threat
model must also validate trusted workflow-run provenance.
