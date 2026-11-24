# JustAI product design

Status: design draft for review, 2026-11-24 UTC. This specifies the proposed native workbench, not installed functionality or a replacement for a team's operating rules. [Architecture](ARCHITECTURE.md#native-workbench-design-draft) defines ownership; [Delivery](DELIVERY.md) records milestones and proof. The [README](../README.md) describes the implementation available today.

## Product purpose

Give a continuing human and AI team one place to understand, advance and recover its work. A person opening JustAI should be able to answer: what are we trying to accomplish, who owns the next action, what has actually happened, what needs judgment, and what evidence supports it?

The first-use recommendation is the team's ordinary development work, with portable interfaces from the start. An outside user's installation should supply its own identities, policies, runtimes and Memory service. A public demonstration uses synthetic records. Product behavior does not depend on importing the founding team's private history.

Native Rust is the selected implementation direction. Renderer selection remains an engineering qualification: GPUI Kit leads the candidate set, with nanoui (Zig) and Slint as comparison options. Selecting nanoui would require a deliberate UI-language or Rust/Zig integration decision. Browser and ChatGPT clients have separate target and permission contracts.

## Product boundaries

JustAI owns navigation, interaction design, presentation and application-specific coordination. It consumes maintained execution, capability, work-state and Memory interfaces. Substantial persistent Memory is a required dependency; a transcript viewer or cache does not fulfill it. Memory implementation and accepted-record semantics belong to that product's owner.

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
| Abandon | Stop future dispatch after owner acknowledgement and retain the reason and partial artifacts. | In-flight or uncertain effects remain separately owned until settled. Abandonment neither erases history nor implies rollback. |
| Lose connection | Show dated cached data and preserve drafts. | Staleness, unsent intent and the distinction between local edits and confirmed remote state. |
| Lose an action response | Reconcile with the effect owner before retrying. | Original operation identity and unresolved result; a timeout does not imply no effect. |
| Change or revoke access | Apply current grants before new reads or actions; isolate account state. | Why a capability became unavailable and how authorized recovery works. |

Whether a particular provider supports pause, cancellation, replay or durable resumption is a contract question. The client advertises only the semantics that integration can prove.

## Design questions for human judgment

These are prepared discussion topics, not a request to answer every question now. Recommendations guide reversible design drafts; they do not record human acceptance.

| ID and timing | Question and options | Recommended starting point | What the team prepares |
| --- | --- | --- | --- |
| D1 before M1 closes | First user: A existing team, B independent developer, C small organization? | A, while keeping interfaces portable. Public packaging follows a real daily-use result. | A day-in-the-life storyboard with three recurring jobs and the external user's equivalent. |
| D2 before M2 interaction review | Opening view: A Work and decisions, B Develop workspace, C activity stream? | A, with fast access to active development. | Two walkthroughs of the same task, showing where attention goes and why. |
| D3 during M2 | Identity language: A teammate with session details, B role with session details? How much history is useful? | A with explicit provider, session, environment and source-backed continuity. | Identity detail and a session-replacement demonstration; no fictional personality. |
| D4 before M3 mutating integration | Attention: A notify for real decisions and material failures, B every checkpoint, C selected work subscriptions? | A plus per-work subscriptions. Inherited authorization remains separate from notification preferences. | Routine-action, new-commitment and uncertain-effect scenarios with exact wording. |
| D5 before M3 reconnect qualification | Offline experience: A cached reading and drafts, B also selected queued actions? | A initially; B only for actions with proven expiry, conflict and retry semantics. | Disconnect/reconnect exercise, draft-conflict example and consequences of each queue choice. |
| D6 before M5 public packaging | Public offer: A native open-source workbench, B focused plugin, C hosted service? | A with a useful optional plugin integration; hosted service is a separate commitment. | Clean-install journey, maintenance obligations, data boundaries and support/cost comparison. |

A discussion should end with the chosen option, the reason, its scope, and any condition for revisiting it in this register. Engineering owns protocol, compatibility and implementation choices supported by evidence. Human judgment is needed for product priorities, attention, identity language, external commitments and consequential distribution choices.

## Where ideation fits

Before M1 closes, refine the jobs and storyboard. During M2, use working interactions to compare information density, identity detail and stop/recovery wording. Before M3's write path, walk the actual authority and failure cases. Before M5, design onboarding and the public value proposition with a fresh operator.

For each discussion the team brings concrete alternatives, a recommendation, consequences and a preview or runnable example. Record the outcome in this product document or the owning technical contract. A separate ADR is warranted only when a consequential technical choice needs durable alternatives and rationale beyond these documents.
