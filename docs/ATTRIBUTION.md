# JustAi — Attribution & Licenses

JustAi is built on open-source infrastructure from world-class teams.
This document credits every major dependency and its role in the system.

---

## Core Dependencies

### mini-swe-agent
- **By:** SWE-agent team, Princeton University & Stanford University
- **Repository:** https://github.com/SWE-agent/mini-swe-agent
- **License:** MIT
- **Role in JustAi:** The execution engine. mini-swe-agent claims tasks from SpacetimeDB and executes them via bash. 74% SWE-bench Verified — the highest-performing open-source coding agent.
- **Version used:** 2.2.8

### Ruflo / claude-flow
- **By:** Reuven Cohen (rUv)
- **Repository:** https://github.com/ruvnet/ruflo
- **License:** MIT
- **Role in JustAi:** Agent orchestration infrastructure. claude-flow provides the MCP server (264 tools), memory backend (sql.js + HNSW vector search), swarm coordination, and agent lifecycle management. JustAi uses claude-flow v3.5.78 via HTTP transport on port 3100.
- **Version used:** 3.5.78

### SpacetimeDB
- **By:** Clockwork Labs
- **Website:** https://spacetimedb.com
- **License:** BSL (Business Source License)
- **Role in JustAi:** Real-time task backbone. All task posting, claiming, status tracking, and agent heartbeats go through SpacetimeDB. The relay-room module defines the schema (Task, Agent, Message, Event tables). 1000x faster than traditional databases for our workload.

### LiteLLM
- **By:** BerriAI
- **Repository:** https://github.com/BerriAI/litellm
- **License:** MIT
- **Role in JustAi:** Model routing proxy. All LLM calls from the orchestrator pipeline (intent gate, planner, reviewer) go through LiteLLM at port 4000. Handles model selection, API key management, fallback chains, and rate limiting.

### LangFuse
- **By:** LangFuse GmbH
- **Website:** https://langfuse.com
- **Repository:** https://github.com/langfuse/langfuse
- **License:** MIT (client SDK)
- **Role in JustAi:** LLM observability. When configured, traces every orchestrator pipeline stage with cost, latency, and token usage. Opt-in via environment variables.

### SAFLA
- **By:** Reuven Cohen (rUv)
- **Role in JustAi:** Memory and safety validation MCP interface. Runs alongside claude-flow as a complementary memory/safety layer.

### agentic-flow
- **By:** Reuven Cohen (rUv)
- **Role in JustAi:** Federation hub for cross-generation agent memory persistence. Enables agents from different sessions to share context.

---

## Frontend Dependencies

| Package | License | Role |
|---------|---------|------|
| React 18.3 | MIT | Dashboard UI framework |
| TypeScript 5.6 | Apache-2.0 | Type safety |
| Vite 6 | MIT | Build tool + dev server |
| TailwindCSS 3.4 | MIT | Utility CSS |
| lucide-react | ISC | Icon library |
| spacetimedb-sdk 2.1 | BSL | SpacetimeDB TypeScript client |

## Python Dependencies

| Package | License | Role |
|---------|---------|------|
| langfuse | MIT | LLM tracing (optional) |
| pytest | MIT | Test framework |

---

## Research Foundation

JustAi's orchestrator design is informed by empirical data from 10 sprints
of development with mini-swe-agent. Key findings documented in
[docs/EVIDENCE.md](EVIDENCE.md):

- Task decomposition quality is the #1 driver of agent success (80% → 100%)
- mini-swe-agent completes tasks in ~35 messages on average
- Single-concern, unambiguous tasks achieve 100% first-try success
- Model switching was not needed when task scoping was correct

These findings come from the SWE-agent research at Princeton & Stanford,
validated through our own sprint execution data.

---

## License

JustAi itself is proprietary. The open-source dependencies listed above
retain their respective licenses. See each project's repository for details.
