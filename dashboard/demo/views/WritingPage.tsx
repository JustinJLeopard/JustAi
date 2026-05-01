import '../styles/writing.css'

export function WritingPage() {
  return (
    <div className="writing-shell">
      <header className="writing-header">
        <a className="writing-brand" href="/">JustAi</a>
        <nav aria-label="Primary">
          <a href="/">Demo</a>
          <a aria-current="page" href="/writing">Writing</a>
          <a href="https://github.com/JustinJLeopard/justai-demo">Source</a>
        </nav>
      </header>

      <main className="writing-main">
        <article className="writing-post">
          <p className="writing-eyebrow">Field note - May 1, 2026</p>
          <h1>Parallel Sessions, Shared Substrate</h1>
          <p className="writing-dek">Last night was the first time the system felt less like a queue of assistants and more like a small engineering floor: separate sessions, different layers, same durable memory, work composing without anyone standing in the middle as a router.</p>
          <p className="writing-byline">By Justin Leopard</p>

          <section>
            <p>The interesting part was not that multiple lab agents were running. That is easy to demo. The interesting part was that they were running at different levels of the stack, at the same time, without a central script telling each one where the others were. One lane was closing the JustAi era. One lane was hardening the public history. One lane was standing up the substrate repo. A separate research session kept watching the edges. Later, another session noticed a small grammar issue on a live deploy and pushed a fix after a different lane had merged the release minutes earlier.</p>
            <p>No ceremony announced that behavior. There was no meeting, no lock service, no carefully staged baton pass. The coordination primitive was much smaller: purpose-slugged writes to an append-only shared bus, hydration patterns before risky action, and a posture-locked orchestrator that treats memory as part of the operating surface rather than a note-taking afterthought.</p>
            <p>That is a different shape from most agentic demos. The usual demo is single-threaded: one instruction, one agent loop, one transcript, one artifact. Useful, but misleading. Real engineering rarely behaves that way. Work lands while other work is in flight. Someone fixes the deploy while someone else is still writing the release note. A safety check changes the release plan. The question is not whether a lab agent can finish a task. The question is whether independent sessions can compose without turning the repo, the deploy, or the operator's attention into shared mutable state.</p>
          </section>

          <section>
            <h2>The Receipts</h2>
            <p>The first lane closed the JustAi pre-public arc: Phase 4 through Phase 6 ratified, the release tagged at <code>v0.4.0</code>, and the architecture split made explicit. JustAi became the orchestration layer. <code>safe-mini</code> became the execution substrate. <code>local-resident</code> remained the experiment driver. That three-repo shape matters because it separates product UX, safety boundary, and research harness instead of letting them blur into one repo that only its author can reason about.</p>
            <p>The second lane made the ownership claim clean. The public history had inherited attribution trailers from assisted development runs. That is fine inside a lab, but it is noise in a principal-owned public artifact. The rewrite stripped 79 attribution trailers across 64 commits using <code>git-filter-repo --message-callback</code>. The important verification was not just "the strings are gone." Tree hashes before and after were byte-identical. The code did not change. The history was made white-label without rewriting the substance of the work.</p>
            <p>The third lane stood up <code>safe-mini</code> as a public substrate repo at <code>v0.2.0</code>. It moved from a 24-file scaffold to a careful port with 51 tests, roughly 95 percent coverage, and green CI on Python 3.11 and 3.12. That is the kind of number that can sound like polish, but here it is more basic: a safety substrate that cannot explain itself under test is not a substrate yet. The public claim has to be inspectable.</p>
            <p>The fourth lane caught the most important fact of the night by refusing to trust a tidy story. Historical credentials were assumed dead. A live probe showed they were still live. That blocked a public flip that would have exposed real keys. This is the line I want preserved from the night: probe before claiming. "Probably rotated" is not a release criterion. The system was useful precisely because a research session was willing to falsify the plan while the release work was otherwise moving forward.</p>
          </section>

          <section>
            <h2>The Coordination Trick</h2>
            <p>The coordination trick was not complex. Each session wrote durable notes with a purpose slug: enough identity to make concurrent writes distinct, enough structure to be searchable later, not so much process that every worker needed to understand the entire organization. There were no key collisions across simultaneous sessions writing the same memory store. That sounds mundane until you compare it with the usual failure mode: a shared scratchpad that becomes either a bottleneck, a conflict zone, or a pile of stale narration.</p>
            <p>Hydration patterns did the other half of the work. Before a risky command, the session asks what it should remember about that class of action. Sometimes the answer is empty and the work proceeds. Sometimes it surfaces a local rule: do not edit harness internals without approval, use upsert because memory delete is soft, run the browser because type checks do not catch UI behavior. The pattern is lightweight, but it moves knowledge from "the operator might remember" into the execution path.</p>
            <p>The result was "do X in support of Y" emerging without explicit coordination. The typo fix is a small example, which is why it is useful. A separate session saw a deployed text issue and corrected it after the landing work had already merged. It did not need to ask which lane owned the page. It had enough durable context to know the active surface, enough restraint to keep the patch tiny, and enough verification discipline to push only after checking the result.</p>
          </section>

          <section>
            <h2>What Changed</h2>
            <p>I do not think last night proves some grand thesis about the future of software work. It proves a narrower, more useful thing: parallel autonomy gets real when the coordination layer is boring. Durable append-only memory. Purpose-slug naming. Hydration before risky operations. A strong boundary between the orchestrator and the substrate. A release posture that values being correct over looking fast.</p>
            <p>The architecture lesson is that composition is mostly a state-management problem. If state lives only in chat history, the human becomes the bus. If state lives in a mutable shared plan, every worker needs a lock protocol. If state is append-only, searchable, and surfaced at the moment of action, independent sessions can make local decisions that still line up with the larger direction.</p>
            <p>There are still rough edges. The public flip is blocked until historical secrets are truly rotated. The three repos need more miles under real workloads. The memory layer needs continued pressure from messy sessions, not just curated milestones. But the shape is now visible. The harness is no longer just a way to run a capable loop. It is becoming an operating substrate for multiple simultaneous engineering conversations that can leave each other useful state, avoid stepping on the same keys, and ship in adjacent lanes.</p>
            <p>That is the part worth writing down. Not "autonomy" as a slogan. Autonomy as a set of boring constraints that let separate sessions become additive instead of theatrical.</p>
          </section>
        </article>
      </main>
    </div>
  )
}
