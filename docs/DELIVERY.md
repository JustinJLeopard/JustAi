# JustAI delivery and acceptance

Status: proposed sequence, reconciled 2026-11-27 UTC. No implementation schedule or background worker is created by this document. [Product](PRODUCT.md) owns requirements and design questions; [Architecture](ARCHITECTURE.md#native-workbench-design-draft) owns the proposed component boundaries. Existing implementation checks remain in [Testing](TESTING.md).

## Milestones

A milestone closes when its outcome is demonstrated. Documentation, implementation, integration, verification and adoption remain separate states.

| Milestone | Outcome and completion evidence | Dependencies and decisions | Current state |
| --- | --- | --- | --- |
| M1 Product and contracts | Qualify the first complete job and lifecycle; map every integration to an owner, supported revision, contract and precisely owned gap. | Accepted team-first direction; product/architecture review and current provider/Memory contracts. | D1 carried forward; storyboard and contract-readiness matrix drafted. Actual binding and representative task/owner selection remain open. |
| M2 Native experience | Run the complete five-view task in a native client. Compare difficult text, input and recovery interactions; select renderer from evidence on declared targets. Synthetic data is clearly labeled. | M1 journey; D2 and D3. Can proceed alongside dependency delivery. | Not implemented. HTML interaction concept only. |
| M3 Real integrated outcome | Use actual authorized Memory retrieval and native execution, deliver a checked repository change, survive interruption, and observe the Memory owner's decision on proposed learning. | M1 contracts; full required Memory acceptance and supported executor delivery under their existing owners; D4 and D5. | Not integrated. Existing services are inputs, not proof of this milestone. |
| M4 Ordinary team use | Complete multiple distinct ordinary tasks across fresh sessions; operators can recover failures without reconstructing context or inventing status. Demonstrate upgrade, rollback and supported restore. | M3, representative adoption window and agreed usability budgets. | Not started. |
| M5 Portable public product | A fresh operator installs and completes the supported workflow with synthetic/public data and their own dependencies. Ship accurate docs, license notices, support/data policies, versioned artifacts and removal procedure. | M4 evidence; D6; public support and distribution decisions. | Design preparation only. |
| M6 External submission | Prepare the selected OpenAI package or program application, execute its required review cases, and make the exact submission reviewable by its publisher. | M5 for a product submission; route eligibility, publisher identity and explicit external-submission decision. | Opportunity researched; no application, upload or submission. |

M2's native client and synthetic interaction trial can proceed alongside Memory delivery without taking its workers off their accepted work. Full Memory completion under the existing feature-to-proof plan and evidence-based exception rule remains the prerequisite for Continuity runtime implementation, live adoption and the integrated M3 claim. A fixture or older bounded service does not meet that prerequisite. Browser, plugin and new-provider adapters can advance in parallel once their contracts are clear; each has its own support and acceptance scope.

## Proof that matters

Use the existing test results, release/PR records and owning service evidence. Keep one consolidated milestone outcome with links to those records; do not create a receipt for every substep.

| Proof | Requirement | Evidence needed |
| --- | --- | --- |
| A1 Fresh continuation | P1, P2 | Close a session, start a fresh one, recover the same work and sources, and perform the correct next useful action. |
| A2 Real delivery | P3 | Exact source revision, meaningful check result, resulting artifact and demonstrated consumer use or its explicitly outstanding condition. |
| A3 Lifecycle recovery | P4, P8 | Pause acknowledgement, fresh-session resume, window close/reopen, abandonment with retained reason, and reconciliation of a lost response. |
| A4 Memory use and correction | P5 | Source-backed retrieval, correction proposal, owner's acceptance/rejection readback, and later retrieval reflecting the accepted disposition. |
| A5 Identity isolation | P6 | Session replacement, account switch and revoked permission preserve attribution without carrying access or data across principals. |
| A6 Native usability | P7 | Variable-height streaming history, code/Markdown, selection/copy, keyboard and screen-reader use, mixed-script IME, scaling and representative VM/GPU behavior. |
| A7 Source evolution | P9 | Change an upstream contract or policy source; detect stale consumption, review compatibility, update the consumer and its displayed revision. Trace one reusable addition into its maintained home. |
| A8 Public portability | P10 | Clean installation, configuration, successful task, recovery and removal without access to the founding team's private files or network. |

For A6 record total shipped/install size, cold/warm readiness, idle/active/peak memory, CPU/GPU and input/render behavior on the same representative workload. Set acceptable budgets after measurement and user-experience review; no fabricated performance threshold or comparison across unequal demos. A compiled binary alone does not establish this proof.

For A3 and A5, exercise failure injection around command acknowledgement, reconnect, stale grants and duplicate delivery. Safety must come from the owning operation's contract, not a UI label or optimistic local state.

## First-job trial and decision

Use [Product's first complete job](PRODUCT.md#first-complete-job-for-the-design-trial) and [Architecture's contract-readiness matrix](ARCHITECTURE.md#first-job-contract-readiness) as the shared scenario. These steps produce different evidence:

1. **M1 contract review:** preserve the accepted product direction; reconcile the exact native and Memory interfaces; select the representative repository task and its accountable owner.
2. **M2 interaction trial:** run the five-view scenario with labeled synthetic records, including unavailable/stale data, a session transition and an uncertain action. Compare Work-first and Develop-first views on the same evidence. A renderer result establishes only its tested scope.
3. **M3 integrated trial:** after dependency acceptance, revalidate the live task's eligibility, source and authorization, or select equivalent authorized work with the same journey; then exercise the actual path through delivery and Memory disposition. Check an interruption and a lost response without repeating an unsettled external effect.
4. **M4 natural follow-through:** use a different ordinary task to assess reuse of learning, correction under contrary evidence and recovery without rebuilding a special demonstration. Observe benefit and maintenance cost against the ordinary assisted native/chat baseline.

The finite-proof rule applies to optional JustAI product additions. Continue a useful capability, repair a concrete defect, adopt a better existing route or retire the addition according to the observed outcome. It does not reopen the need for substantial Memory, erase accepted obligations or authorize discarding unfinished work.

The consolidated result should identify the source revisions, task and baseline, observed user effort, incorrect or unresolved status, interruptions, delivery/uptake, learning disposition and recurring curation cost. Set quantitative usability budgets from the representative trial instead of inventing a pass threshold before measurement. Keep acceptance evidence with its owning source and link it once.

## Progress reporting and later scheduling

Track each capability as **specified → implemented → integrated → verified → adopted**, with an evidence link and an accountable maintainer. Use blocked, deferred or abandoned as explicit dispositions; preserve the reason and any unsettled effects. A percentage is useful only when its denominator is defined, so these stages do not imply an invented completion percentage.

Before assigning dates, use M1's open contracts and M2's renderer trial to estimate work and dependency lead times. Then choose a cadence with the actual contributors: review availability, provisioned compute/provider limits, dependency readiness and maintenance capacity. Report outcome, proof, next action and decision needed at checkpoints. Do not create another scheduler or assume that a document runs work.

A possible discussion rhythm is two or three focused design/review sessions per week, matching availability. It is a planning option, not an active schedule or a promise of unattended work.

## Public boundary

Public releases contain portable code, supported contracts, deliberate product defaults and synthetic examples. Operator-specific rosters, operating directions, credentials, private Memory, machine addresses and deployment profiles stay in their established private homes.

A public artifact is an explicitly selected projection with an origin and revision. It is not a wholesale copy of an internal workspace. Review the exact package and its transitive assets/dependencies before publication. A private implementation is not made public merely because JustAI can call it; any distributable interface must have a publishing owner and rights.

## OpenAI opportunities

Checked against official sources on 2026-11-24; recheck when preparing a real application.

| Route | Fit and condition | Preparation |
| --- | --- | --- |
| [Developer showcase](https://developers.openai.com/community) | Share a useful public project/demo. This is distinct from directory approval or model access. | Accurate product story, working demo and evidence of the result. |
| [Plugin directory](https://developers.openai.com/plugins/deploy/submission) | A package of skills and/or MCP capabilities for supported ChatGPT/Codex surfaces. Remote MCP submission uses a public HTTPS service and verified publishing identity. | Useful bounded workflow, package, authentication/data handling, review evidence and publisher details. |
| [Desktop-only local MCP](https://developers.openai.com/plugins/deploy/desktop-only) | Compatible with a native Rust server, but local MCP submissions currently require approved-partner organization allowlisting. | Clean desktop installation and local workflow proof; establish eligibility before submission. |
| [Sign in with ChatGPT for OSS/local apps](https://developers.openai.com/siwc/token-sharing-open-source) | An optional native integration for eligible plan usage. It does not expose ChatGPT conversations or account context. Paid or remotely hosted variants have a separate interest route. | Qualify account isolation, stable host identity, consent, credential storage and [preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations). |
| [Codex for Open Source](https://developers.openai.com/community/codex-for-oss) | Maintainers may apply for credits, Pro/Codex support and conditional security access. Eligibility and acceptance are not established for this project. | Evidence of useful public maintenance, ecosystem value and the proposed use of support. |

The native executable, a remote plugin service and a sign-in provider adapter are different deliverables. Directory publication does not itself grant model access, partner status, credits or a commercial agreement.

For the chosen plugin route, prepare current positive/negative cases, expected tools and results, a walkthrough, and an appropriate synthetic reviewer account if required. The [submission guide](https://developers.openai.com/plugins/deploy/submission) owns the exact current checklist. Account verification, terms/attestations, external applications, publication and any new spending need the publisher's actual decision.

## Stop or change direction

If a renderer cannot meet the representative workload, retain the product requirements and try the next candidate; document the failing case. If an external program is unavailable, continue the native product and retain the evidence. If a public/hosted option creates an unacceptable maintenance or privacy commitment, defer that distribution mode explicitly.

If a milestone is abandoned, preserve usable source, accepted decisions and unsettled effects, name their owners, and close only the work actually stopped. Failed experiments inform the next decision; they do not silently lower required product behavior.
