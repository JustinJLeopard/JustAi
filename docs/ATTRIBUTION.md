# JustAi Attribution & Licenses

JustAi is built on open-source infrastructure from the Python, observability, and coding-agent ecosystems.

## Core Dependencies

### mini-swe-agent

- **By:** SWE-agent team, Princeton University & Stanford University
- **Repository:** https://github.com/SWE-agent/mini-swe-agent
- **License:** MIT
- **Role in JustAi:** Reference bash-action agent loop. JustAi plans around this execution style; safe-mini is the intended local substrate boundary.

### LiteLLM

- **By:** BerriAI
- **Repository:** https://github.com/BerriAI/litellm
- **License:** MIT
- **Role in JustAi:** Model routing proxy for intent, planning, and review calls.

### LangFuse

- **By:** LangFuse GmbH
- **Website:** https://langfuse.com
- **Repository:** https://github.com/langfuse/langfuse
- **License:** MIT (client SDK)
- **Role in JustAi:** Optional LLM observability for cost, latency, and quality tracing.

### Ruflo / claude-flow / SAFLA

- **By:** Reuven Cohen (rUv)
- **Role in JustAi:** Local memory and surrounding agent-development infrastructure used by the project environment.

## Frontend Dependencies

| Package | License | Role |
| --- | --- | --- |
| React 18.3 | MIT | Dashboard UI framework |
| TypeScript 5.6 | Apache-2.0 | Type safety |
| Vite 6 | MIT | Build tool and dev server |
| TailwindCSS 3.4 | MIT | Utility CSS |
| lucide-react | ISC | Icon library |

## Python Dependencies

| Package | License | Role |
| --- | --- | --- |
| langfuse | MIT | LLM tracing (optional) |
| pytest | MIT | Test framework |
| ruff | MIT | Linting and formatting |
| mypy | MIT | Type checking |

## Research Foundation

The current JustAi architecture is informed by safe-mini/control-plane research and the memory keys listed in the README. Historical sprint evidence is archived under [archive/](archive/).
