/**
 * JustAi Demo — Sprint Timeline Data
 *
 * Full 8-task sprint scenario data for the interactive demo.
 * Pure data — imports types only. No side effects.
 *
 * Scenario: "Build a customer analytics dashboard with real-time metrics,
 * user segmentation, and export capabilities"
 *
 * Timeline: 60 seconds total, with escalation at ~22s and trajectory
 * learning at ~32s to showcase JustAi differentiators.
 */

import type {
  DemoTask,
  DemoAgent,
  DemoMemoryEntry,
  TimelineEntry,
  CostDataPoint,
  LatencyDataPoint,
  TrajectoryCommand,
} from './types'

// ── Sprint Goal ──────────────────────────────────────────────────────────────

export const SPRINT_GOAL =
  'Build a customer analytics dashboard with real-time metrics, user segmentation, and export capabilities'

// ── Initial Tasks (8 total) ──────────────────────────────────────────────────

export const INITIAL_TASKS: DemoTask[] = [
  {
    id: 'task-1',
    name: 'Design database schema for analytics events',
    agent: '',
    model: '',
    status: 'pending',
    cost: 0,
    steps: 12,
    stepsDone: 0,
    escalated: false,
    trajectoryLearning: false,
    payload: 'Create PostgreSQL schema: events, users, segments, metrics tables with proper indexes',
    result: '',
  },
  {
    id: 'task-2',
    name: 'Build real-time metrics ingestion API',
    agent: '',
    model: '',
    status: 'pending',
    cost: 0,
    steps: 18,
    stepsDone: 0,
    escalated: false,
    trajectoryLearning: false,
    payload: 'REST + WebSocket endpoints for event ingestion with batch support and rate limiting',
    result: '',
  },
  {
    id: 'task-3',
    name: 'Implement user segmentation engine',
    agent: '',
    model: '',
    status: 'pending',
    cost: 0,
    steps: 20,
    stepsDone: 0,
    escalated: false,
    trajectoryLearning: false,
    payload: 'Rule-based + ML clustering segmentation with segment builder UI data model',
    result: '',
  },
  {
    id: 'task-4',
    name: 'Create dashboard visualization components',
    agent: '',
    model: '',
    status: 'pending',
    cost: 0,
    steps: 24,
    stepsDone: 0,
    escalated: false,
    trajectoryLearning: false,
    payload: 'React components: line charts, bar charts, heatmaps, KPI cards with Recharts',
    result: '',
  },
  {
    id: 'task-5',
    name: 'Add export functionality (CSV/PDF/API)',
    agent: '',
    model: '',
    status: 'pending',
    cost: 0,
    steps: 16,
    stepsDone: 0,
    escalated: false,
    trajectoryLearning: false,
    payload: 'Export service: CSV streaming, PDF generation via Puppeteer, REST API for programmatic access',
    result: '',
  },
  {
    id: 'task-6',
    name: 'Build authentication and RBAC layer',
    agent: '',
    model: '',
    status: 'pending',
    cost: 0,
    steps: 14,
    stepsDone: 0,
    escalated: false,
    trajectoryLearning: false,
    payload: 'JWT auth with refresh tokens, role-based access control for dashboard views and exports',
    result: '',
  },
  {
    id: 'task-7',
    name: 'Implement real-time WebSocket updates',
    agent: '',
    model: '',
    status: 'pending',
    cost: 0,
    steps: 15,
    stepsDone: 0,
    escalated: false,
    trajectoryLearning: false,
    payload: 'WebSocket server pushing live metric updates to connected dashboard clients',
    result: '',
  },
  {
    id: 'task-8',
    name: 'Integration tests and CI pipeline',
    agent: '',
    model: '',
    status: 'pending',
    cost: 0,
    steps: 22,
    stepsDone: 0,
    escalated: false,
    trajectoryLearning: false,
    payload: 'End-to-end tests: ingestion -> segmentation -> dashboard -> export flow, GitHub Actions CI',
    result: '',
  },
]

// ── Initial Agents (3 total) ─────────────────────────────────────────────────

export const INITIAL_AGENTS: DemoAgent[] = [
  {
    id: 'agent-mini-1',
    name: 'mini-swe-agent-1',
    model: 'gpt-5.4',
    status: 'idle',
    tasksCompleted: 0,
    currentTaskId: null,
  },
  {
    id: 'agent-mini-2',
    name: 'mini-swe-agent-2',
    model: 'gpt-5.4',
    status: 'idle',
    tasksCompleted: 0,
    currentTaskId: null,
  },
  {
    id: 'agent-opus',
    name: 'claude-opus-planner',
    model: 'claude-opus-4-6',
    status: 'idle',
    tasksCompleted: 0,
    currentTaskId: null,
  },
]

// ── Initial Memories (6 entries) ─────────────────────────────────────────────

export const INITIAL_MEMORIES: DemoMemoryEntry[] = [
  {
    id: 'mem-1',
    key: 'project:tech-stack',
    value: 'React 18 + TypeScript + PostgreSQL + Node.js + Recharts',
    category: 'context',
    appearsAt: 0,
  },
  {
    id: 'mem-2',
    key: 'pattern:api-design',
    value: 'REST endpoints follow /api/v1/{resource} convention with JSON:API response format',
    category: 'pattern',
    appearsAt: 0,
  },
  {
    id: 'mem-3',
    key: 'constraint:auth',
    value: 'JWT tokens with 15min access / 7day refresh rotation; RBAC via middleware',
    category: 'constraint',
    appearsAt: 0,
  },
  {
    id: 'mem-4',
    key: 'trajectory:schema-first',
    value: 'Previous sprints show schema-first approach reduces downstream failures by 40%',
    category: 'learning',
    appearsAt: 0,
  },
  {
    id: 'mem-5',
    key: 'model:routing-preference',
    value: 'Use mini-swe-agent (gpt-5.4) for implementation; escalate complex visualization to claude-opus',
    category: 'strategy',
    appearsAt: 0,
  },
  {
    id: 'mem-6',
    key: 'trajectory:escalation-learned',
    value: 'Visualization tasks with >20 steps benefit from claude-opus; gpt-5.4 fails on complex Recharts configs',
    category: 'learning',
    appearsAt: 25,
  },
]

// ── Task Results ─────────────────────────────────────────────────────────────

export const TASK_RESULTS: Record<string, string> = {
  'task-1': 'Schema created: 4 tables (events, users, segments, metrics) with 12 indexes. Migration files generated. ERD diagram exported.',
  'task-2': 'Ingestion API live: POST /api/v1/events (batch), WS /ws/events (stream). Rate limit: 10k events/min. Validated with 50k test events.',
  'task-3': 'Segmentation engine complete: rule-based filters + k-means clustering. 6 pre-built segments. Builder API returns segments in <200ms.',
  'task-4': 'Dashboard components: 5 chart types (line, bar, area, heatmap, KPI cards). Responsive grid layout. Dark/light theme support. Recharts v3.',
  'task-5': 'Export service: CSV streaming (100k rows in 2.3s), PDF via Puppeteer (dashboard snapshot), REST API with pagination. Queue-based for large exports.',
  'task-6': 'Auth layer: JWT with refresh rotation, 4 roles (admin, analyst, viewer, api-key). Middleware applied to all /api routes. Rate limiting per role.',
  'task-7': 'WebSocket server: auto-reconnect, heartbeat, room-based subscriptions per dashboard. Handles 500 concurrent connections. Redis pub/sub backend.',
  'task-8': 'CI pipeline: 47 tests (12 e2e, 35 unit). GitHub Actions workflow with PostgreSQL service container. Coverage: 89%. All tests green.',
}

// ── Full Event Timeline (~40 entries, 60 seconds) ────────────────────────────

export const TIMELINE: TimelineEntry[] = [
  // 0s — Sprint starts, intent classification, planning
  {
    time: 0,
    actions: [
      { type: 'start_sprint' },
      { type: 'set_phase', phase: 'planning' },
      { type: 'set_pipeline', stage: 'intent', status: 'active' },
      { type: 'add_event', event: { time: 0, type: 'sprint', detail: `Sprint started: ${SPRINT_GOAL}` } },
    ],
  },
  {
    time: 1,
    actions: [
      { type: 'set_pipeline', stage: 'intent', status: 'done' },
      { type: 'set_pipeline', stage: 'plan', status: 'active' },
      { type: 'add_event', event: { time: 1, type: 'pipeline', detail: 'Intent classified: BUILD — confidence 0.96' } },
    ],
  },
  {
    time: 2,
    actions: [
      { type: 'set_pipeline', stage: 'plan', status: 'done' },
      { type: 'set_pipeline', stage: 'execute', status: 'active' },
      { type: 'set_phase', phase: 'executing' },
      { type: 'add_event', event: { time: 2, type: 'pipeline', detail: 'Plan decomposed: 8 tasks, 3 agents allocated' } },
    ],
  },

  // 3-8s — Task 1 (schema) by claude-opus
  {
    time: 3,
    actions: [
      { type: 'claim_task', taskId: 'task-1', agentId: 'agent-opus' },
      { type: 'add_event', event: { time: 3, type: 'task', detail: 'Task 1 claimed by claude-opus-planner — schema design' } },
    ],
  },
  {
    time: 3.5,
    actions: [
      { type: 'start_task', taskId: 'task-1' },
    ],
  },
  {
    time: 8,
    actions: [
      { type: 'complete_task', taskId: 'task-1', cost: 0.042, result: TASK_RESULTS['task-1'] },
      { type: 'add_event', event: { time: 8, type: 'task', detail: 'Task 1 complete: schema created — $0.042' } },
    ],
  },

  // 8-16s — Tasks 2+3 parallel by mini-swe-agents
  {
    time: 8.5,
    actions: [
      { type: 'claim_task', taskId: 'task-2', agentId: 'agent-mini-1' },
      { type: 'claim_task', taskId: 'task-3', agentId: 'agent-mini-2' },
      { type: 'add_event', event: { time: 8.5, type: 'task', detail: 'Tasks 2+3 claimed in parallel — mini-swe-agents' } },
    ],
  },
  {
    time: 9,
    actions: [
      { type: 'start_task', taskId: 'task-2' },
      { type: 'start_task', taskId: 'task-3' },
    ],
  },
  {
    time: 14,
    actions: [
      { type: 'complete_task', taskId: 'task-2', cost: 0.018, result: TASK_RESULTS['task-2'] },
      { type: 'add_event', event: { time: 14, type: 'task', detail: 'Task 2 complete: ingestion API live — $0.018' } },
    ],
  },
  {
    time: 16,
    actions: [
      { type: 'complete_task', taskId: 'task-3', cost: 0.021, result: TASK_RESULTS['task-3'] },
      { type: 'add_event', event: { time: 16, type: 'task', detail: 'Task 3 complete: segmentation engine — $0.021' } },
    ],
  },

  // 16-22s — Task 4 starts on mini-swe, fails at 22s
  {
    time: 16.5,
    actions: [
      { type: 'claim_task', taskId: 'task-4', agentId: 'agent-mini-1' },
      { type: 'add_event', event: { time: 16.5, type: 'task', detail: 'Task 4 claimed by mini-swe-agent-1 — dashboard components' } },
    ],
  },
  {
    time: 17,
    actions: [
      { type: 'start_task', taskId: 'task-4' },
    ],
  },
  {
    time: 22,
    actions: [
      { type: 'fail_task', taskId: 'task-4', reason: 'Recharts v3 complex config: heatmap + responsive grid exceeded context window' },
      { type: 'add_event', event: { time: 22, type: 'error', detail: 'Task 4 FAILED on mini-swe-agent-1 — Recharts complexity exceeded model capacity' } },
    ],
  },

  // 22-25s — Escalation
  {
    time: 23,
    actions: [
      { type: 'escalate_task', taskId: 'task-4', fromAgent: 'agent-mini-1', toAgent: 'agent-opus', newModel: 'claude-opus-4-6' },
      { type: 'add_event', event: { time: 23, type: 'escalation', detail: 'Task 4 ESCALATED: mini-swe-agent-1 (gpt-5.4) -> claude-opus (claude-opus-4-6)' } },
    ],
  },
  {
    time: 24,
    actions: [
      { type: 'claim_task', taskId: 'task-4', agentId: 'agent-opus' },
      { type: 'add_event', event: { time: 24, type: 'escalation', detail: 'Task 4 re-claimed by claude-opus-planner — escalation in progress' } },
    ],
  },
  {
    time: 24.5,
    actions: [
      { type: 'start_task', taskId: 'task-4' },
    ],
  },

  // 25-32s — Task 4 redone by claude-opus
  {
    time: 25,
    actions: [
      { type: 'add_event', event: { time: 25, type: 'learning', detail: 'Trajectory learning: recorded escalation pattern for visualization tasks' } },
    ],
  },
  {
    time: 32,
    actions: [
      { type: 'complete_task', taskId: 'task-4', cost: 0.087, result: TASK_RESULTS['task-4'] },
      { type: 'add_event', event: { time: 32, type: 'task', detail: 'Task 4 complete (escalated): dashboard components — $0.087' } },
    ],
  },

  // 32-38s — Task 5 with trajectory learning
  {
    time: 33,
    actions: [
      { type: 'claim_task', taskId: 'task-5', agentId: 'agent-mini-1' },
      { type: 'add_event', event: { time: 33, type: 'learning', detail: 'Trajectory learning applied: enriching Task 5 context with export patterns from prior runs' } },
    ],
  },
  {
    time: 33.5,
    actions: [
      { type: 'start_task', taskId: 'task-5' },
    ],
  },
  {
    time: 38,
    actions: [
      { type: 'complete_task', taskId: 'task-5', cost: 0.015, result: TASK_RESULTS['task-5'] },
      { type: 'add_event', event: { time: 38, type: 'task', detail: 'Task 5 complete: export functionality — $0.015 (trajectory-optimized)' } },
    ],
  },

  // 38-50s — Tasks 6+7 parallel
  {
    time: 38.5,
    actions: [
      { type: 'claim_task', taskId: 'task-6', agentId: 'agent-mini-1' },
      { type: 'claim_task', taskId: 'task-7', agentId: 'agent-mini-2' },
      { type: 'add_event', event: { time: 38.5, type: 'task', detail: 'Tasks 6+7 claimed in parallel — auth + WebSocket' } },
    ],
  },
  {
    time: 39,
    actions: [
      { type: 'start_task', taskId: 'task-6' },
      { type: 'start_task', taskId: 'task-7' },
    ],
  },
  {
    time: 45,
    actions: [
      { type: 'complete_task', taskId: 'task-6', cost: 0.013, result: TASK_RESULTS['task-6'] },
      { type: 'add_event', event: { time: 45, type: 'task', detail: 'Task 6 complete: auth + RBAC — $0.013' } },
    ],
  },
  {
    time: 48,
    actions: [
      { type: 'complete_task', taskId: 'task-7', cost: 0.016, result: TASK_RESULTS['task-7'] },
      { type: 'add_event', event: { time: 48, type: 'task', detail: 'Task 7 complete: WebSocket updates — $0.016' } },
    ],
  },

  // 50-56s — Task 8 (integration tests)
  {
    time: 50,
    actions: [
      { type: 'claim_task', taskId: 'task-8', agentId: 'agent-mini-1' },
      { type: 'add_event', event: { time: 50, type: 'task', detail: 'Task 8 claimed by mini-swe-agent-1 — integration tests' } },
    ],
  },
  {
    time: 50.5,
    actions: [
      { type: 'start_task', taskId: 'task-8' },
    ],
  },
  {
    time: 55,
    actions: [
      { type: 'complete_task', taskId: 'task-8', cost: 0.022, result: TASK_RESULTS['task-8'] },
      { type: 'add_event', event: { time: 55, type: 'task', detail: 'Task 8 complete: CI pipeline — 47 tests, 89% coverage — $0.022' } },
    ],
  },

  // 56-60s — Review + completion
  {
    time: 56,
    actions: [
      { type: 'set_pipeline', stage: 'execute', status: 'done' },
      { type: 'set_pipeline', stage: 'review', status: 'active' },
      { type: 'set_phase', phase: 'reviewing' },
      { type: 'add_event', event: { time: 56, type: 'pipeline', detail: 'All tasks complete — entering review phase' } },
    ],
  },
  {
    time: 58,
    actions: [
      { type: 'set_pipeline', stage: 'review', status: 'done' },
      { type: 'set_pipeline', stage: 'synthesize', status: 'active' },
      { type: 'add_event', event: { time: 58, type: 'pipeline', detail: 'Review passed — synthesizing results' } },
    ],
  },
  {
    time: 59,
    actions: [
      { type: 'set_pipeline', stage: 'synthesize', status: 'done' },
      { type: 'add_event', event: { time: 59, type: 'pipeline', detail: 'Synthesis complete — sprint summary generated' } },
    ],
  },
  {
    time: 60,
    actions: [
      { type: 'set_phase', phase: 'complete' },
      { type: 'add_event', event: { time: 60, type: 'sprint', detail: 'Sprint complete: 8/8 tasks done, 1 escalation, $0.234 total cost, 87.5% first-attempt success' } },
    ],
  },
]

// ── Cost Series (for charts) ─────────────────────────────────────────────────

export const COST_SERIES: CostDataPoint[] = [
  { time: 8,  cost: 0.042, label: 'T1: Schema' },
  { time: 14, cost: 0.060, label: 'T2: Ingestion API' },
  { time: 16, cost: 0.081, label: 'T3: Segmentation' },
  { time: 32, cost: 0.168, label: 'T4: Dashboard (escalated)' },
  { time: 38, cost: 0.183, label: 'T5: Export' },
  { time: 45, cost: 0.196, label: 'T6: Auth' },
  { time: 48, cost: 0.212, label: 'T7: WebSocket' },
  { time: 55, cost: 0.234, label: 'T8: CI Pipeline' },
]

// ── Latency Series (for charts) ──────────────────────────────────────────────

export const LATENCY_SERIES: LatencyDataPoint[] = [
  { time: 8,  latency: 5.0,  label: 'T1: Schema' },
  { time: 14, latency: 5.5,  label: 'T2: Ingestion API' },
  { time: 16, latency: 7.0,  label: 'T3: Segmentation' },
  { time: 32, latency: 15.5, label: 'T4: Dashboard (escalated)' },
  { time: 38, latency: 5.0,  label: 'T5: Export (trajectory)' },
  { time: 45, latency: 6.0,  label: 'T6: Auth' },
  { time: 48, latency: 9.0,  label: 'T7: WebSocket' },
  { time: 55, latency: 5.0,  label: 'T8: CI Pipeline' },
]

// ── Trajectory Commands (mock replay data) ───────────────────────────────────

export const TRAJECTORY_COMMANDS: TrajectoryCommand[] = [
  // Task 4 — failed attempt on mini-swe
  {
    taskId: 'task-4',
    step: 1,
    command: 'cat package.json | jq ".dependencies"',
    output: '{ "react": "^18.3.0", "recharts": "^3.8.1", "lucide-react": "^0.469.0" }',
    timestamp: 17,
  },
  {
    taskId: 'task-4',
    step: 2,
    command: 'mkdir -p src/components/charts && touch src/components/charts/{LineChart,BarChart,Heatmap,KPICard}.tsx',
    output: '',
    timestamp: 18,
  },
  {
    taskId: 'task-4',
    step: 3,
    command: 'write src/components/charts/Heatmap.tsx',
    output: 'ERROR: Context window exceeded — Recharts v3 ResponsiveContainer + custom heatmap requires 48k tokens',
    timestamp: 21,
  },
  // Task 4 — successful attempt on claude-opus
  {
    taskId: 'task-4',
    step: 4,
    command: '[escalated to claude-opus] analyze recharts v3 API surface',
    output: 'Identified: ComposedChart + custom Cell renderer for heatmap. Grid layout via CSS Grid, not Recharts ResponsiveContainer.',
    timestamp: 25,
  },
  {
    taskId: 'task-4',
    step: 5,
    command: 'write src/components/charts/Heatmap.tsx (claude-opus)',
    output: 'Heatmap component: 142 lines, custom color scale, tooltip, responsive via CSS Grid. All TypeScript strict.',
    timestamp: 28,
  },
  {
    taskId: 'task-4',
    step: 6,
    command: 'npm run typecheck && npm test -- --testPathPattern charts',
    output: 'TypeScript: 0 errors. Tests: 8 passed, 0 failed.',
    timestamp: 31,
  },
  // Task 5 — trajectory-enriched
  {
    taskId: 'task-5',
    step: 1,
    command: '[trajectory context] Retrieved: export patterns from sprint-7 (CSV streaming, queue-based PDF)',
    output: 'Enriched context: 3 prior trajectories matched. Applying CSV streaming pattern and Puppeteer PDF snapshot approach.',
    timestamp: 33.5,
  },
  {
    taskId: 'task-5',
    step: 2,
    command: 'write src/services/export.ts (with trajectory patterns)',
    output: 'Export service: streaming CSV (ReadableStream), PDF snapshot (Puppeteer), REST endpoint with pagination. 89 lines.',
    timestamp: 35,
  },
  {
    taskId: 'task-5',
    step: 3,
    command: 'npm test -- --testPathPattern export',
    output: 'Tests: 6 passed, 0 failed. CSV: 100k rows in 2.3s. PDF: dashboard snapshot in 4.1s.',
    timestamp: 37,
  },
]
