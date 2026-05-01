# JustAi Demo-Readiness Design Spec

> Date: 2026-04-16
> Status: Approved
> Author: Justin Leopard + Claude

## Overview

Make JustAi demo-ready for a dual audience: hiring managers evaluating technical depth and potential clients evaluating what Delegate & Orchestrate can build for them. The deliverable is an interactive dashboard demo hosted at `delegateandorchestrate.com/demo/justai`, backed by a polished showcase repo at `JustinJLeopard/justai-demo`.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Audience | Hiring managers + D&O clients | Portfolio that doubles as business showcase |
| Open-source strategy | Showcase-only | No code published. README + screenshots + live demo link. Protects IP while proving technical depth. |
| Demo format | Interactive dashboard replica | Self-contained React component with mock data and a choreographed sprint simulation |
| Hosting | `delegateandorchestrate.com/demo/justai` | Single domain, single brand, single funnel. No traffic fragmentation. |
| Development branch | `demo-build` on private JustAi repo | Demo components live next to the real dashboard for easy style/code reference |
| Handoff to D&O site | Extract `dashboard/demo/` → hand to Aegis | Aegis adds a React Router route at `/demo/justai` on the Zo-hosted D&O site |

## Sprint Story

The demo simulates a full sprint where JustAi orchestrates building a customer analytics dashboard.

**Goal:** "Build a customer analytics dashboard with real-time metrics, user segmentation, and export capabilities"

**8 Tasks:**

| # | Task | Agent | Notable Behavior |
|---|------|-------|-------------------|
| 1 | Design API schema & data models | claude-opus | Planning — goal decomposition |
| 2 | Build metrics ingestion pipeline | mini-swe-agent | Fast delegation to workhorse |
| 3 | Create REST endpoints (CRUD + aggregation) | mini-swe-agent | Parallel execution with task 2 |
| 4 | Implement user segmentation engine | mini-swe-agent → claude-opus | **Escalation** — mini fails on complex query logic, auto-routes to stronger model |
| 5 | Build React dashboard components | mini-swe-agent | **Trajectory learning** — pulls context from past successful charting run |
| 6 | Add real-time WebSocket updates | mini-swe-agent | Standard delegation |
| 7 | CSV/PDF export with background jobs | mini-swe-agent | Standard delegation |
| 8 | Integration tests + CI setup | mini-swe-agent | Final review cycle, sprint completes |

**Key moments:**
- Task 4 escalation: card turns amber, shows "Escalating...", re-assigns to claude-opus
- Task 5 trajectory learning: indicator shows system pulling context from prior run
- Sprint completion: all cards in Done, final stats ($2.14 cost, 12.4s avg latency, 100% quality)

## Demo Shell Architecture

### Layout

The demo is a pixel-identical replica of the real JustAi dashboard (7 views, sidebar navigation, dark/light theme) with one addition: a Sprint Control Bar at the top.

**Sprint Control Bar (demo-only):**
- "Demo" badge
- Sprint goal text
- Progress bar with task count (e.g., "3/8")
- Speed control: 0.5x / 1x / 2x
- Play/Pause button

**Everything below the bar** is a faithful recreation of the real dashboard using the same CSS variables, layout patterns, and visual language. Dark/light theme toggle is included in the sidebar footer (same as real dashboard) — demo defaults to dark mode for maximum visual impact.

### View-by-View Behavior

**Mission Control:**
- Stats cards: Active Runs, Completed, Success Rate, Cost (24h), Avg Latency
- Active Pipeline: stages light up as sprint progresses (Intent → Plan → Execute → Review → Synthesize)
- Active task banner with pulsing indicator, agent/model/step/cost metadata
- Services panel: all green (SpacetimeDB, LiteLLM, claude-flow MCP, LangFuse)
- Recent Runs table
- During escalation: banner flashes amber, shows "Escalating to claude-opus"

**Task Board:**
- 5-column Kanban: Pending → Claimed → In Progress → Done → Failed
- Cards animate between columns as simulation progresses
- Task 4: moves to In Progress, turns amber, re-appears with "Escalated" badge
- Click any card → detail panel slides in (same as real dashboard)

**Run History:**
- One run entry: "Sprint: Analytics Dashboard" with status indicator
- Progress bar fills during simulation
- Task completion events appear as timestamped log entries

**Trajectories:**
- List of 8 trajectory files (one per task)
- Three modes: Post-Mortem, Learning, Audit (tabs at top-right)
- Task 4 post-mortem: shows escalation reasoning with step-by-step command replay
- Task 5 learning mode: shows matched pattern from prior run
- Completed tasks get green checkmarks

**Memory:**
- Pre-populated with ~6 entries: architecture decisions, model preferences, past patterns
- After escalation: new entry appears — "Segmentation queries require claude-opus for complex join logic"
- Demonstrates system learning in real-time

**Observability:**
- Cost chart: steps up with each task completion
- Latency distribution: fills in as tasks complete
- Quality scores: appear after review cycles
- Final state: $2.14 total, 12.4s avg latency, 100% quality

**Agents:**
- 3 agents: mini-swe-agent (x2 instances), claude-opus (x1)
- Status indicators: active/idle
- Task counts increment during simulation
- During escalation: claude-opus transitions from idle to active

### Simulation Engine

A deterministic state machine driven by a timer:

```
States: idle → planning → executing(1..8) → reviewing → complete
```

- `useSimulation()` React hook manages timer, current state, and exposes data to all views
- All task data and transitions defined in `sprint-timeline.ts`
- Speed control multiplies base delays (0.5x / 1x / 2x)
- Pause/resume supported
- Visitors can navigate between views freely — simulation runs in background

**Timeline at 1x speed (~60 seconds):**

| Time | Event |
|------|-------|
| 0s | Sprint starts. Intent: "full-stack app". Plan: 8 tasks. |
| 3s | Task 1 claimed by claude-opus |
| 8s | Task 1 done. Tasks 2+3 claimed (parallel) |
| 16s | Tasks 2+3 done. Task 4 claimed by mini-swe-agent |
| 22s | Task 4 fails — escalation triggered |
| 25s | Task 4 re-assigned to claude-opus |
| 32s | Task 4 done. Task 5 claimed — trajectory learning indicator |
| 38s | Task 5 done. Task 6 claimed |
| 44s | Task 6 done. Task 7 claimed |
| 50s | Task 7 done. Task 8 claimed |
| 56s | Task 8 done. Review cycle |
| 60s | Sprint complete. Final stats. |

**Post-completion:** When the simulation finishes, the Sprint Control Bar shows a "Replay" button. The dashboard stays at the final state (all tasks Done, full stats visible) so visitors can explore freely. Clicking Replay resets to initial state and runs again.

## File Structure

### Demo components (in JustAi repo, `demo-build` branch)

```
dashboard/demo/
├── JustAiDemo.tsx              # Top-level: sidebar + view router + sprint bar
├── hooks/
│   └── useSimulation.ts        # State machine, timer, speed control, mock data
├── views/
│   ├── DemoMissionControl.tsx
│   ├── DemoTaskBoard.tsx
│   ├── DemoRunHistory.tsx
│   ├── DemoTrajectories.tsx
│   ├── DemoMemory.tsx
│   ├── DemoObservability.tsx
│   └── DemoAgents.tsx
├── components/
│   ├── DemoSidebar.tsx
│   ├── SprintBar.tsx           # Play/Pause, speed, progress (demo-only)
│   └── shared/                 # Cards, charts, badges reused across views
├── data/
│   └── sprint-timeline.ts      # 8-task scenario, all mock data, timing config
└── styles/
    └── demo-theme.css          # CSS variables matching real dashboard
```

### Demo repo (justai-demo, public)

```
justai-demo/
├── README.md                   # Polished showcase document
├── docs/
│   └── architecture.md         # System architecture deep-dive
└── screenshots/
    ├── mission-control.png
    ├── task-board.png
    ├── trajectory-postmortem.png
    ├── trajectory-learning.png
    ├── observability.png
    ├── memory-browser.png
    └── agents.png
```

### Demo repo README structure

1. Hero — one-line pitch + link to live demo
2. What is JustAi — 3-sentence explanation
3. Architecture diagram — Mermaid: Goal → Intent Gate → Planner → Delegator → mini-swe-agent → Reviewer → Learning Layer
4. Key Features — bullet list with inline screenshots:
   - Multi-model orchestration (Mission Control)
   - Smart escalation (Task Board)
   - Trajectory intelligence (Trajectory Viewer)
   - Cost observability (Observability)
   - Persistent memory (Memory Browser)
5. Tech Stack — Python orchestrator, React dashboard, SpacetimeDB, LangFuse, claude-flow
6. Live Demo — prominent CTA to `delegateandorchestrate.com/demo/justai`
7. Built by — delegateandorchestrate.com + LinkedIn

## D&O Site Integration

**D&O site stack:** Vite + Bun + TypeScript React + Tailwind CSS 4, shadcn/ui, Lucide icons. Hosted on Zo Computer.

**Integration steps (Aegis):**
1. Pull demo component files from `dashboard/demo/`
2. Install Recharts dependency (`bun add recharts`)
3. Add route in React Router: `/demo/justai` → `<JustAiDemo />`
4. Build and deploy

**Dependencies beyond D&O baseline:** Recharts (for charts). Everything else (React, Tailwind) already in stack.

## Deliverables Summary

| # | Deliverable | Location | Owner |
|---|-------------|----------|-------|
| 1 | Interactive demo component | `dashboard/demo/` on `demo-build` branch | Claude (build) |
| 2 | Fresh dashboard screenshots | `screenshots/` on `demo-build` branch | Claude (capture) |
| 3 | Revised justai-demo README | Pushed to `JustinJLeopard/justai-demo` | Claude (write) + Justin (push) |
| 4 | D&O site integration | `/demo/justai` route on D&O site | Aegis (deploy) |
