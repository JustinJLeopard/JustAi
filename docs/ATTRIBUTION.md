# JustAi Attribution & Licenses

JustAi is built on open-source infrastructure from the Python, frontend, observability, and software-automation ecosystems.

## Core Dependencies

### mini-swe-agent

- **By:** SWE-agent team, Princeton University & Stanford University
- **Repository:** https://github.com/SWE-agent/mini-swe-agent
- **License:** MIT
- **Role in JustAi:** Reference bash-action agent loop. JustAi plans around this execution style; `safe-mini` is the intended local substrate boundary.

### Model Routing Proxy

- **License:** MIT
- **Role in JustAi:** Local model-routing proxy for intent, planning, and review calls.

### Observability Client

- **License:** MIT
- **Role in JustAi:** Optional tracing for cost, latency, and quality telemetry.

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
| pytest | MIT | Test framework |
| ruff | MIT | Linting and formatting |
| mypy | MIT | Type checking |

## Research Foundation

The current JustAi architecture is informed by local-execution substrate research and the control-plane split described in the README.
