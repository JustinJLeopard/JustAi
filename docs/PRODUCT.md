# JustAI product design

Status: design draft for review, reconciled 2026-11-27 UTC. This specifies the proposed native workbench, not installed functionality or a replacement for a team's operating rules. [Architecture](ARCHITECTURE.md#native-workbench-design-draft) defines ownership; [Delivery](DELIVERY.md) records milestones and proof. The [README](../README.md) describes the implementation available today.

## Product purpose

Give a continuing human and AI team one place to understand, advance and recover its work. A person opening JustAI should be able to answer: what are we trying to accomplish, what changed while I was away, why does it matter, who owns the next action, am I needed, and what evidence supports it? The product turns those answers into useful navigation, review and action through the responsible owners.

The initial product direction is to improve the existing native team's ordinary work, with portable interfaces from the start. The accepted investment rule is a finite useful-work comparison, then an evidence-based choice to reuse, build or retire the optional JustAI addition. This rule evaluates the workbench's value; substantial Memory remains a required foundation under its existing project. An outside user's installation should supply its own identities, policies, runtimes and Memory service. A public demonstration uses synthetic records. Product behavior does not depend on importing the founding team's private history.

Native Rust is the selected implementation direction. Renderer selection remains an engineering qualification: GPUI Kit leads the candidate set, with nanoui (Zig) and Slint as comparison options. Selecting nanoui would require a deliberate UI-language or Rust/Zig integration decision. Browser and ChatGPT clients have separate target and permission contracts.

## Product boundaries

JustAI owns navigation, interaction design, presentation and composition of supported operations through owner contracts. It consumes maintained execution, capability, work-state and Memory interfaces. Git and the owning repository systems retain source/revision evidence; existing runtime and work owners retain live work; Memory retains accepted records. Substantial persistent Memory is a required dependency; a transcript viewer or cache does not fulfill it.

Local drafts, view state and dated source-linked snapshots support the experience. Their status and freshness remain explicit. Closing or removing JustAI must leave accepted work recoverable through its existing owners. New product workflows remain in scope; any genuinely new durable authority needs an explicit ownership and integration decision under [Architecture](ARCHITECTURE.md#client-checkpoints-and-new-workflow-ownership).

Continuing teammate identity, the current session, model, machine and authorization are distinct. The UI presents verified attribution and uncertainty. It does not infer subjective experience, manufacture a biography, or treat a display name or identifier as a permission.

## Five connected views

| View | Question it answers | Essential interaction |
| --- | --- | --- |
| Work | What outcome is moving, waiting or finished? | Open the next action, evidence, owner and unresolved effects; continue, pause or abandon supported work. |
| Develop | What changed, and does it work? | Inspect source, diff, checks and artifacts in the actual development environment. |
| Team | Who is responsible, through which current surface? | Inspect continuing identity, session, model, environment and effective capability separately. |
| Memory | What is known, why, and can it be corrected? | Follow source references; distinguish accepted records from proposed learning and correction drafts. |
| System | Which dependencies are usable here? | Inspect supported capability, version, connection state and recovery action. |

The views share work and source references. They do not each create a separate task record or Memory copy. The existing private five-view concept remains an internal interaction reference; prepare a shareable synthetic design fixture for public review in M2. The concept's example implementation language does not choose the production renderer.

## Product requirements

All rows describe target behavior. Completion evidence is maintained in Delivery, not duplicated here.

| ID | Required behavior | Observable outcome |
| --- | --- | --- |
| P1 | Preserve work across session changes. | A fresh session retrieves the existing goal, accepted decisions, source-backed context and pending actions without the user reconstructing them. |
| P2 | Make status attributable. | Every consequential status links to its owning source and distinguishes observed, stale, unavailable and unresolved information. |
| P3 | Support a complete development outcome. | A goal leads to inspected changes, meaningful checks and a usable delivered artifact through a supported executor. |
| P4 | Preserve lifecycle meaning. | Pause, resume, close, abandonment and effect reconciliation behave as specified below. |
| P5 | Use Memory with provenance. | Retrieval opens the supporting record; a correction or learning proposal reaches the owner, and acceptance appears only after owner readback. |
| P6 | Preserve identity and authorization boundaries. | Replacing a session or switching an account does not transfer another principal's access, memories or pending commands. |
| P7 | Support native daily use. | Streaming text, code, selection, keyboard navigation, IME, accessibility and scaling work on declared target machines. |
| P8 | Expose integration failure honestly. | A disconnected, incompatible or missing dependency remains visible; unsupported actions cannot appear successful. |
| P9 | Make ownership and reuse explicit. | Each integration names its owner; derived views identify their origin; a reusable addition has one maintained implementation. |
| P10 | Support a portable public profile. | A new operator can install, configure, use and remove the supported public product without the founding team's private infrastructure. |

## One complete journey including interruption

The reference task is a real repository change: recover a prior decision from Memory, inspect and modify source through an existing native executor, review evidence, deliver the change, and propose useful learning. It visits all five views because each has a job in that outcome.

| Event | Required behavior | What must remain visible |
| --- | --- | --- |
| Successful delivery | Verify the intended artifact and recipient/use condition before displaying completion. | Change, checks, source references and owner-confirmed outcome. |
| Pause | Request a supported checkpoint; show acknowledgement separately from the request. | Drafts, changes, pending effects and the owner of anything still running. |
| Resume in a fresh session | Reconcile current source state, then continue the same work identity. | Prior decisions, new session attribution and any changed authorization. |
| Close the window | End the client session without implicitly ending independently owned work. | Reopening restores the owner's current state. |
| Abandon | Immediately withhold new JustAI-originated dispatch for the abandoned goal. Request the owner's stop of future continuation and show abandonment as requested until acknowledged. Retain the reason and partial artifacts. | In-flight or uncertain effects remain separately owned until settled. Abandonment neither erases history nor implies rollback. |
| Lose connection | Show dated cached data and preserve drafts. | Staleness, unsent intent and the distinction between local edits and confirmed remote state. |
| Lose an action response | Reconcile with the effect owner before retrying. | Original operation identity and unresolved result; a timeout does not imply no effect. |
| Change or revoke access | Apply current grants before new reads or actions; isolate account state. | Why a capability became unavailable and how authorized recovery works. |

Whether a particular provider supports pause, cancellation, replay or durable resumption is a contract question. The client advertises only the semantics that integration can prove.

## First complete job for the design trial

**Working scenario:** return to an unfinished repository change, recover why it exists, carry it through review and delivery, and preserve a useful lesson for a later task. The initial audience and investment rule are established. M1 selects the representative task and its accountable owner. Immediately before M3, revalidate that task's current eligibility, source and authorization, or select equivalent authorized work exercising the same journey. M2 uses a clearly labeled synthetic instance.

The story serves three recurring jobs:

| Job | What the person needs | Equivalent for an outside operator |
| --- | --- | --- |
| Return to work | Understand what changed, which result is usable and whether a decision needs attention. | Recover a project after time away without access to the founding team's private context. |
| Advance a change | Follow the actual source, executor, checks and delivery through one outcome. | Use the operator's own repository, runtime and permissions. |
| Carry learning forward | Correct a prior belief or procedure, see its disposition and observe useful later use. | Use the operator's supported Memory service and its own acceptance rules. |

### Walkthrough

| Step | Experience | Required evidence and ownership |
| --- | --- | --- |
| 1. Reorient in Work | Show the continuing outcome, what changed since the last observation, the next accountable action and any genuine decision. No-decision-needed is a valid state. | Source-backed work state with observation time; explicit stale, unavailable or unresolved fields. The client does not infer progress from a busy indicator. |
| 2. Recover the decision in Memory | Open the decision that explains the change, its supporting source and any superseding revision. Retrieve only the context this task needs. | The Memory owner's authorized result and source revision. A saved record, retrieval and demonstrated use remain distinct. |
| 3. Continue with the right teammate | Resume through the current owner and supported runtime, preserving the work identity. Show the continuing identity separately from this session, model, environment and effective access. | Current ownership and authorization, with the accepted next action. A new session does not silently inherit another principal's grants. |
| 4. Work in Develop | Open the actual repository revision, relevant changes, checks and artifacts. Ordinary engineering continues without asking the person to relay messages. | Repository/worktree identity and execution-owner acknowledgement. A UI draft is not a submitted or executed operation. |
| 5. Recover a boundary | Close and reopen the client, then separately exercise a fresh execution session. Restore the current outcome and reconcile any command whose response was lost before retrying that operation or dispatching work that depends on its outcome. Unrelated authorized work remains eligible. | Closing the window leaves independently owned work running. Session replacement recovers obligations and unresolved effects through their owners; it is not proved by restoring the UI alone. |
| 6. Inspect the result | Present the intended change, meaningful tests, review disposition and any remaining integration condition. | Exact source and test/review evidence. Written, committed, pushed, merged, installed and consumer-verified are separate claims. |
| 7. Deliver | Show the actual recipient or consumer outcome, with an owned next action where acceptance is pending. | An artifact link alone does not prove uptake. Use recipient-authored or actual-consumer evidence appropriate to the delivery. |
| 8. Learn and revise | Submit a useful learning or correction proposal to Memory; display its accepted, rejected or pending disposition. On a later task, show retrieval and application, including revision when contrary evidence appears. | Memory retains the accepted-record writer. JustAI can preserve a draft and display the owner's decision; it cannot award itself acceptance or claim learning merely because text was stored. |

Pause, abandonment, access changes and disconnects remain required branches of this journey, with the meanings in the lifecycle table above. The trial must retain useful partial artifacts and the identity of unsettled effects.

### Opening the same job in two ways

| Starting view | First interaction | Consequence to test |
| --- | --- | --- |
| Work first, recommended working default | Read the outcome and meaningful change, then open its active Develop workspace. | Makes returning after absence and deciding whether attention is needed straightforward; adds one navigation step when the operator already knows exactly which file to edit. |
| Develop first | Restore the previous workspace, with an outcome/status panel linked to Work. | Suits sustained editing; must make changed ownership, stale evidence and pending decisions visible without requiring a hunt through tabs. |

Compare these with the same task and source evidence. Keep the assisted native/chat workflow as the baseline; do not make it artificially harder or rerun model jobs merely to populate a second screen. Measure orientation effort, correctness, interruptions, artifact-finding effort and recurring curation. A later natural task checks whether the benefit survives without a special mapping rebuilt for that example.

Work first guides the reversible trial. Final opening behavior, information density and how much identity detail belongs on the main screen remain interaction choices for review, not additional infrastructure prerequisites.

## Design questions for human judgment

D1 records the established initial scope. The remaining rows are prepared discussion topics, not a request to answer every question now. Recommendations guide reversible design drafts; they do not record human acceptance.

| ID and timing | Question and options | Recommended starting point | What the team prepares |
| --- | --- | --- | --- |
| D1 established initial scope | Improve the existing native team's work; use a finite proof to decide reuse, build or retirement of the optional addition. | Carry this accepted direction forward. The wider public audience remains a D6 question. | The first complete job and three recurring jobs above; qualify them through M1–M4 without reopening the requirement for full Memory. |
| D2 before M2 interaction review | Opening view: A Work and decisions, B Develop workspace, C activity stream? | A, with fast access to active development. | Two walkthroughs of the same task, showing where attention goes and why. |
| D3 during M2 | Identity language: A teammate with session details, B role with session details? How much history is useful? | A with explicit provider, session, environment and source-backed continuity. | Identity detail and a session-replacement demonstration; no fictional personality. |
| D4 before M3 mutating integration | Attention: A notify for real decisions and material failures, B every checkpoint, C selected work subscriptions? | A plus per-work subscriptions. Inherited authorization remains separate from notification preferences. | Routine-action, new-commitment and uncertain-effect scenarios with exact wording. |
| D5 before M3 reconnect qualification | Offline experience: A cached reading and drafts, B also selected queued actions? | A initially; B only for actions with proven expiry, conflict and retry semantics. | Disconnect/reconnect exercise, draft-conflict example and consequences of each queue choice. |
| D6 before M5 public packaging | Public offer: A native open-source workbench, B focused plugin, C hosted service? | A with a useful optional plugin integration; hosted service is a separate commitment. | Clean-install journey, maintenance obligations, data boundaries and support/cost comparison. |

A discussion should end with the chosen option, the reason, its scope, and any condition for revisiting it in this register. Engineering owns protocol, compatibility and implementation choices supported by evidence. Human judgment is needed for product priorities, attention, identity language, external commitments and consequential distribution choices.

## Where ideation fits

Before M1 closes, qualify the storyboard against actual supported contracts and select a representative task and accountable owner. Revalidate the live task instance immediately before M3. During M2, use working interactions to compare information density, identity detail and stop/recovery wording. Before M3's write path, walk the actual authority and failure cases. Before M5, design onboarding and the public value proposition with a fresh operator.

For each discussion the team brings concrete alternatives, a recommendation, consequences and a preview or runnable example. Record the outcome in this product document or the owning technical contract. A separate ADR is warranted only when a consequential technical choice needs durable alternatives and rationale beyond these documents.
