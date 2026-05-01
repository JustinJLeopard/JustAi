# JustAi v2 — Design Specification

**Date:** 2026-04-12
**Status:** Approved for implementation planning
**Builds on:** v1.0.0 (Sprint 11, commit `fb0725a`)

---

## 1. Scope

Three vertical slices, built in order. Each slice ships a working increment.

| Slice | Name | What It Delivers |
|-------|------|-----------------|
| 1 | Glass Aurora Redesign | Design system, grouped nav, light/dark mode, visual overhaul of all views, navigation transitions, hover popovers, keyboard shortcuts |
| 2 | Observability | Full LangFuse instrumentation across all 6 pipeline stages, Observability dashboard view, Mission Control metrics wired to real data |
| 3 | Trajectory Intelligence | AI-powered trajectory analysis, three-mode Trajectory Viewer, cross-linking between views |

Slice 1 comes first so that everything built in Slices 2–3 uses the final visual language from day one. No rework.

---

## 2. Visual Identity: Midnight Rose

### Design Principles

- **Authority through restraint** — no decorative animations, no ambient effects, no color in the background. Data is the visual.
- **Maximum useful density** — as much information as possible without crowding. Every pixel earns its place.
- **Hover for depth** — primary view is scannable at a glance. Hover popovers reveal drill-down data on demand.
- **Semantic color only** — rose for active/live, gold for cost/monetary, emerald for success, red for failure. Never decorative.
- **Enterprise readability** — neutral dark background (#09090b), clean panel separation, high text contrast.

### Design System Tokens

```
Backgrounds
  --bg-void:       #09090b (dark) / #fafafa (light)
  --bg-surface:    rgba(255,255,255, 0.024)
  --bg-elevated:   rgba(255,255,255, 0.038)
  --bg-hover:      rgba(255,255,255, 0.055)
  --bg-popover:    rgba(12,12,14, 0.97)

Borders
  --border-subtle:  rgba(255,255,255, 0.035)
  --border-default: rgba(255,255,255, 0.055)
  --border-hover:   rgba(255,255,255, 0.09)

Accent — Rose (active, live, primary actions)
  --rose-600: #e11d48
  --rose-500: #f43f5e
  --rose-400: #fb7185
  --rose-300: #fda4af

Accent — Gold (cost, monetary data only)
  --gold-400: #facc15
  --gold-300: #fde68a

Accent — Emerald (success, healthy, completed)
  --emerald-500: #10b981
  --emerald-400: #34d399

Accent — Red (failure, errors)
  --red-500: #ef4444

Accent — Amber (warnings, degraded)
  --amber-500: #f59e0b

Text
  --text-primary:   #f1f5f9
  --text-secondary: #94a3b8
  --text-tertiary:  #64748b
  --text-muted:     #475569
  --text-dim:       #334155

Typography
  Sans:  Inter (weights: 200, 300, 400, 500, 600)
  Mono:  JetBrains Mono (weights: 300, 400, 500)
  OpenType features: cv02, cv03, cv04, cv11
  Numeric: font-variant-numeric: tabular-nums (all data values)

Type Scale
  32px  weight-200  Metric display values
  22px  weight-200  Page titles
  14px  weight-300  Body text, task descriptions
  13px  weight-300  Nav items, table rows
  12px  weight-400  Labels, secondary data
  11px  weight-400  Meta values, popovers
  10px  weight-500  Section labels (uppercase, letter-spacing: 1.8px)
  9px   weight-500  Micro labels (uppercase, letter-spacing: 2px)

Spacing (4px base grid)
  --sp-1: 4px   --sp-2: 8px   --sp-3: 12px
  --sp-4: 16px  --sp-5: 20px  --sp-6: 24px
  --sp-8: 32px  --sp-10: 40px

Radii
  --r-sm: 6px   --r-md: 10px  --r-lg: 14px

Shadows (depth hierarchy)
  --shadow-sm:  0 1px 2px rgba(0,0,0,0.3), 0 0 1px rgba(0,0,0,0.2)
  --shadow-md:  0 4px 16px rgba(0,0,0,0.4), 0 0 1px rgba(255,255,255,0.03)
  --shadow-lg:  0 12px 40px rgba(0,0,0,0.5), 0 0 1px rgba(255,255,255,0.04)
  --shadow-xl:  0 24px 64px rgba(0,0,0,0.6), 0 0 1px rgba(255,255,255,0.05)

Transitions
  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1)
  --t-fast:    0.12s ease-out-expo
  --t-default: 0.2s  ease-out-expo
  --t-slow:    0.35s ease-out-expo
```

### Brand Elements

- **Logo mark:** Diamond (◇) rendered in pure CSS — rotated square with inner fill, rose glow
- **Logo text:** "JUSTAI" in Inter weight-300, letter-spacing: 5px
- **Active indicator:** 2px rose bar on left edge of active nav item, with subtle glow
- **Panel style:** `background: var(--bg-surface)`, `border: 1px solid var(--border-subtle)`, `border-radius: var(--r-lg)`

---

## 3. Light / Dark Mode

- Dark mode is the default.
- Toggle location: sidebar footer, next to system status indicator.
- Light mode token overrides:
  - `--bg-void` → `#fafafa`
  - `--bg-surface` → `#ffffff`
  - `--bg-elevated` → `#f8fafc`
  - `--bg-hover` → `#f1f5f9`
  - `--bg-popover` → `rgba(255,255,255, 0.97)`
  - `--border-subtle` → `rgba(0,0,0, 0.06)`
  - `--border-default` → `rgba(0,0,0, 0.1)`
  - `--border-hover` → `rgba(0,0,0, 0.15)`
  - `--text-primary` → `#0f172a`
  - `--text-secondary` → `#475569`
  - `--text-tertiary` → `#64748b`
  - `--text-muted` → `#94a3b8`
  - `--text-dim` → `#cbd5e1`
  - Shadows: reduce opacity by ~50% (lighter environment needs less depth)
  - Accent colors (rose, gold, emerald, red) stay unchanged — they read well on both backgrounds.
- Persisted in `localStorage`.
- On first visit, respects `prefers-color-scheme` media query.
- Implementation: CSS class on `<html>` element (`data-theme="dark"` / `data-theme="light"`), all tokens overridden via `[data-theme="light"]` selector.
- Transition: 0.2s ease on background and color properties. No flash.

---

## 4. Dashboard Layout & Navigation

### Sidebar — Grouped Navigation

```
┌─────────────────────┐
│ ◇ JUSTAI            │
│    v2.0              │
├─────────────────────┤
│ OPERATIONS           │
│  ◉ Mission Control   │
│  ▦ Task Board    [3] │
│  ▸ Run History  [48] │
│                      │
│ INTELLIGENCE         │
│  ◈ Trajectories      │
│  ⬡ Memory      [142]│
│  ◐ Observability     │
│                      │
│ SYSTEM               │
│  ⬢ Agents        [2]│
│                      │
│ ─────────────────    │
│ ● All systems op.    │
│ [◑ dark/light]       │
└─────────────────────┘
```

- Group labels: 10px, weight-500, uppercase, letter-spacing 2.5px, color `--text-dim`
- Nav items: 13px, weight-300. Active item has rose background tint + left bar indicator.
- Counts: monospace badges right-aligned, updating with real data.
- Sidebar width: 232px fixed.
- Sidebar border-right with neutral white gradient (brighter at top, fades to transparent).

### View Transitions

- Sidebar click swaps main content area with crossfade (opacity 0→1, 200ms).
- No full page reloads.
- Breadcrumb trail when drilling down: `Mission Control → Run #48 → Trajectory`. Always one click back.
- Every data reference to another view is a clickable link (rose color on hover).

### Keyboard Shortcuts

- `1`–`7`: Jump to sidebar views in order
- `Esc`: Go back / close popover
- `/`: Focus search (if applicable)

---

## 5. Mission Control (Home View)

The information-dense hub. Everything an operator needs at a glance, with drill-down on hover.

### Top: Metrics Grid (5 columns)

| Card | Primary Value | Trend | Sparkline | Hover Popover |
|------|--------------|-------|-----------|---------------|
| Active Runs | Count (rose) | "across N agents" | 24h activity | Per-agent breakdown, queue depth, avg duration |
| Completed | Count (emerald) | "↑ N today" | 7d trend | Today/yesterday/week counts, avg tasks/run, daily bar chart |
| Success Rate | Percentage | "↑ N% this week" | — | First-try vs after-retry, unrecoverable %, top failure reason |
| Cost (24h) | Dollar amount (gold) | "avg $X/task" | 7d trend | Per-model cost split, token in/out counts, 7d total |
| Avg Latency | Seconds | "↓ Ns from last week" | — | p50/p90/p99 percentiles, slowest pipeline stage |

Each card has:
- SVG sparkline with gradient fill fading to transparent at the bottom
- Hover popover with drill-down data (150ms hover delay, fade+translate animation)
- `font-variant-numeric: tabular-nums` so numbers don't shift during updates

### Middle: Active Pipeline

Horizontal segmented bar showing pipeline stages left-to-right:

```
[ Intent ✓ ][ Plan ✓ ][ Review ✓ ][ ▸ Execute ][ Synthesize ]
```

- Completed stages: emerald tint background, emerald label
- Active stage: rose tint background, rose label, 2px rose bottom border with glow
- Pending stages: dim background, dim label
- Each stage shows timing and key data (e.g., "4 tasks · 2.1s")
- Each stage has a hover popover with: model, tokens, cost, classification/verdict

Below the pipeline: **Task detail bar**
- Current task goal text (14px, weight-300)
- Meta row: Agent, Model, Step N/~35, Tokens, Cost, Checkpoint level
- Live progress bar: 3px height, rose gradient fill, shimmer animation on the leading edge

### Middle: Services + Recent Runs (2-column)

**Services panel:**
- Row per service: status dot (emerald/amber/red), name, detail, latency
- Hover popovers: uptime %, connected agents, request counts, last error
- Services: SpacetimeDB, LiteLLM, claude-flow MCP, LangFuse

**Recent Runs panel:**
- Table with columns: status dot, Goal, Model, Tasks (N/N), Cost, Time
- Column headers: 9px uppercase
- Row hover: slight background elevation + popover with task breakdown, failure reason
- Running rows: pulsing rose dot
- Failed rows: red dot, hover shows root cause
- "View all →" link to Run History

### Bottom: Pipeline Progress (scrollable)

Gantt-style timeline visualization:

**Scope selector tabs:**
- `This Run` | `Sprint N` | `Sprint N–N+1` | `Sprint N–N+2` | `Full Spec`
- Active tab has elevated background + shadow

**Timeline:**
- Left column (180px): task label with monospace task number
- Right: proportional bar track with task bars
- Completed bars: emerald with checkmark and actual duration
- Running bars: rose with shimmer sweep animation, showing step progress
- Queued bars: dim with estimated duration
- **NOW marker**: vertical rose line with "NOW" label, positioned at current time offset

**ETA footer:**
- Large display: "Xm Ys remaining"
- Basis: "Estimated from N similar runs averaging Xm Ys/task"
- Confidence level: high/medium/low (based on variance in historical data)

---

## 6. Observability View

Full LangFuse integration surfaced as a dedicated dashboard view.

### Backend: Pipeline Instrumentation

Every pipeline stage gets `trace_generation()` or `trace_event()` calls with:

| Stage | Trace Data |
|-------|-----------|
| Intent Gate | classification, confidence, model, tokens_in, tokens_out, latency_ms |
| Planner | task_count, decomposition tokens, planning_duration_ms, model |
| Reviewer | verdict (approved/rejected), issues_found, retry_count, tokens |
| Delegator | spacetimedb_post_latency_ms, task_ids, agent_assignment |
| Executor | per_step_tokens, commands_run, exit_codes, wall_time_ms |
| Synthesizer | aggregation_tokens, memory_writes, total_run_cost |

Each trace carries a `run_id` linking to the orchestrator run. LangFuse `usage` dict is populated with actual token counts and costs (currently empty — this is the main backend work).

### Frontend: Three Panels

**Cost Panel**
- Bar chart: cost per run over time (7d / 30d toggle)
- Stacked by model: different color per model within each bar
- Per-stage cost waterfall: how much does planning cost vs execution vs synthesis
- Hover popovers on bars: token counts, per-1K-token rates
- Running total line with daily average
- Drill-down: clicking a bar navigates to that run in Run History

**Latency Panel**
- Stacked bar per run: time in each pipeline stage (color-coded)
- p50/p90/p99 trend lines over time
- Bottleneck callout: "Planner is your bottleneck — averaging 1.9s, 45% of total runtime"
- Per-model latency comparison
- Drill-down: clicking a bar navigates to that run

**Quality Panel**
- Success rate over time: line chart with confidence band
- First-try success vs after-retry breakdown (stacked area)
- Failure categorization pie/bar: ambiguous task, timeout, agent error, model error
- AI-generated insight: e.g., "Your success rate improved 8% after you started including file paths in goal descriptions"
- Correlation scatterplot: cost vs quality (are expensive runs more successful?)
- Drill-down: clicking a data point navigates to that run

### Cross-Linking

- Mission Control metric cards pull from this same LangFuse data
- Observability is the deep-dive behind the top-level numbers
- Every chart data point links to the relevant run
- Cost breakdowns link to Trajectory Viewer audit mode

---

## 7. Trajectory Viewer

Three modes, one viewer. Tab bar at top: `Post-Mortem` | `Learning` | `Audit`.

Trajectory selector: dropdown with search to pick which run/trajectory to examine. Shows run goal, date, status, agent.

### Mode 1: Post-Mortem / Debugging

Primary question: *"What happened at each step, and where did it go wrong?"*

**Left panel — Step timeline (vertical)**
- Numbered list of every agent step
- Each step shows: action type icon (bash, edit, read, think), file touched, exit code
- Failed steps: red indicator, auto-scroll to first failure
- Successful steps collapsed by default, failed/interesting steps expanded

**Right panel — Step detail**
- Agent reasoning text (what the model was thinking)
- Exact command run (monospace, syntax highlighted)
- Full stdout/stderr output
- File diffs: unified diff format with syntax highlighting (green/red lines)
- Token count and cost for this step

**Top — AI analysis**
- "What went wrong" summary: root cause identification, which step diverged from the plan, what the agent should have done differently
- Generated by passing the trajectory + failure context through Claude

### Mode 2: Learning / Optimization

Primary question: *"How do I write better goals and get better results?"*

**Pattern analysis panel**
- Aggregated view across runs: which goal phrasings lead to first-try success
- Average task complexity vs success rate scatter
- Common failure patterns (ranked by frequency)

**AI suggestions panel**
- Specific, actionable recommendations derived from the user's run history
- Examples: "Goals mentioning 'refactor' without specifying scope fail 40% more often", "Tasks with explicit verification criteria complete 2x faster"

**Run comparison**
- Side-by-side view: select a successful vs failed run for similar goals
- Diff highlighting: what was different about the goal, the plan, the execution

**Efficiency metrics**
- Tokens per step distribution
- Cost efficiency over time (improving or worsening?)
- Steps-to-completion trend

### Mode 3: Audit / Compliance

Primary question: *"Prove exactly what the agent did."*

**Chronological event log**
- Every action with precise ISO-8601 timestamps
- No summarization, no collapsing — full record
- Action type, target, input, output for each event

**File change manifest**
- Every file created, modified, or deleted
- Before/after diffs for modifications
- File permissions and sizes

**Chain of evidence**
- Which prompt led to which action
- Full token accounting: input tokens, output tokens, cost per action
- Model and version used for each decision

**Export**
- Download as JSON (machine-readable) or PDF (human-readable)
- Includes all metadata, timestamps, and diffs

**Immutable view**
- Read-only presentation — no interactive elements that could obscure the record
- Clear visual distinction from the interactive modes (e.g., subtle background difference)

### Data Sources

- Primary: `.traj.json` files produced by mini-swe-agent on completion
- Supplementary: LangFuse traces for token/cost/latency data
- AI analysis: Claude API calls for post-mortem summaries and learning suggestions

---

## 8. Hover Popovers (Global Pattern)

Popovers appear throughout every view — a consistent interaction pattern.

**Trigger:** Hover with 150ms delay (prevents flicker on mouse-through)

**Appearance:**
```css
background: var(--bg-popover);       /* rgba(12,12,14, 0.97) */
backdrop-filter: blur(24px) saturate(1.2);
border: 1px solid var(--border-default);
border-radius: var(--r-md);          /* 10px */
box-shadow: var(--shadow-xl);
```

**Animation:** Fade in + translateY(4px → 0), using `--t-default` (0.2s ease-out-expo)

**Dismissal:** Mouse-out with 100ms grace period (prevents accidental close when moving to popover)

**Content:** Always additional context useful for understanding but not essential for scanning. Structured as label/value rows with optional mini-charts (bar charts, sparklines).

**Applied to:** Metric cards, pipeline stages, service rows, run table rows, chart data points, task cards, agent cards.

---

## 9. E2E Pipeline (Backend Hardening)

### SpacetimeDB-First Architecture

The relay path is the real execution path. `justai run "goal"` posts tasks to SpacetimeDB, mini-swe-agent claims them from the relay board.

**`--local` mode remains dry-run only:** Runs the pipeline through Intent → Plan → Review but does not post to SpacetimeDB or invoke mini-swe-agent. Used for testing goal decomposition and plan quality without execution costs.

### Instrumentation Integration

The orchestrator pipeline (`orchestrator.py`) is the integration point for LangFuse tracing. Each stage call wraps in `trace_generation()` / `trace_event()` with the data specified in Section 6. The `run_id` is generated at orchestrator entry and threaded through all stages.

### Existing Architecture (Preserved)

No changes to:
- Intent Gate classification logic
- Planner decomposition logic
- Reviewer quality gate logic
- Delegator SpacetimeDB posting logic
- Checkpoint R0–R3 gate logic
- Synthesizer aggregation logic

The only backend changes are: (1) adding LangFuse trace wrappers, (2) populating the `usage` dict with actual token/cost data, (3) API endpoints to serve observability data to the dashboard.

---

## 10. API Endpoints (New/Modified)

The dashboard needs data. These endpoints extend `justai/api.py`:

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/api/observability/cost` | GET | Cost per run over time, by model, by stage |
| `/api/observability/latency` | GET | Latency per run over time, by stage, percentiles |
| `/api/observability/quality` | GET | Success rates, failure categories, trends |
| `/api/observability/insights` | GET | AI-generated suggestions (cached, refreshed hourly) |
| `/api/trajectory/:run_id` | GET | Parsed .traj.json for a specific run |
| `/api/trajectory/:run_id/analysis` | GET | AI post-mortem analysis (cached per trajectory) |
| `/api/trajectory/patterns` | GET | Aggregated pattern data across runs |
| `/api/runs` | GET | (Existing) Enhanced with LangFuse cost/token data |

Data sources: LangFuse API for observability metrics, filesystem for .traj.json files, Claude API for AI analysis (results cached).

---

## 11. Existing Views (Redesigned in Slice 1)

These views exist in v1 and get the Midnight Rose visual treatment:

**Task Board** — Kanban columns (Pending / Claimed / Running / Done / Failed). Task cards get the new panel styling, hover popovers with full task detail, rose accent on running tasks, gold cost display.

**Run History** — Currently exists but not wired into App.tsx routing. Wire it in, apply Midnight Rose styling, add LangFuse cost/token columns once Slice 2 lands.

**Memory Browser** — Connects to claude-flow MCP. Apply Midnight Rose panel styling, improve search UX with the new popover pattern for memory entry previews.

**Agent Registry** — New view under System group. Registered agents with capability tags, heartbeat history, task history per agent, success rate. Data from SpacetimeDB agent table.

---

## 12. Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend framework | React 18 + TypeScript | Existing |
| Build | Vite 6 | Existing |
| Styling | CSS custom properties + Tailwind (utility-first adoption) | Migrate from inline styles |
| Charts | Recharts or Nivo | Evaluate during Slice 2; need bar, line, stacked, scatter |
| Icons | Lucide React | Already installed, adopt consistently |
| Data fetching | Polling via SpacetimeDB HTTP API (3s) | Existing; no WebSocket changes in v2 |
| Tracing | LangFuse Python SDK | Existing (partially wired) |
| AI analysis | Claude API via LiteLLM | For trajectory summaries and suggestions |
| State management | React state + context | No Redux needed at this scale |

---

## 13. Testing Requirements

Per the project's non-negotiable testing rules:

- Every new Python module gets a test file
- Every new function gets happy path + edge case tests
- All tests run offline — mock LangFuse, SpacetimeDB, Claude API calls
- Dashboard components: test that they render, that hover interactions work, that data flows correctly
- `python3 -m pytest tests/` passes before any slice commit
- Target: no untested code paths in files touched during the slice

---

## 14. Out of Scope for v2

- Theme customization beyond light/dark
- Mobile responsive layout (desktop-first operator tool)
- WebSocket real-time subscriptions (polling-first, upgrade in v3)
- Discord integration (separate initiative)
- Agent payment ledger (v3)
- Multi-user / authentication
