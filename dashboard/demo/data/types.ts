/**
 * JustAi Demo — Type Definitions
 *
 * Pure type definitions for the self-contained interactive demo.
 * No runtime code — imports only TypeScript types.
 */

// ── Task & Agent Types ───────────────────────────────────────────────────────

export type DemoTaskStatus = 'pending' | 'claimed' | 'in_progress' | 'done' | 'failed'

export interface DemoTask {
  id: string
  name: string
  agent: string
  model: string
  status: DemoTaskStatus
  cost: number
  steps: number
  stepsDone: number
  escalated: boolean
  escalatedFrom?: string
  trajectoryLearning: boolean
  payload: string
  result: string
}

export interface DemoAgent {
  id: string
  name: string
  model: string
  status: 'idle' | 'active'
  tasksCompleted: number
  currentTaskId: string | null
}

// ── Pipeline Types ───────────────────────────────────────────────────────────

export type PipelineStage = 'intent' | 'plan' | 'execute' | 'review' | 'synthesize'

export type StageStatus = 'idle' | 'active' | 'done'

export interface PipelineState {
  intent: StageStatus
  plan: StageStatus
  execute: StageStatus
  review: StageStatus
  synthesize: StageStatus
}

// ── Memory & Events ──────────────────────────────────────────────────────────

export interface DemoMemoryEntry {
  id: string
  key: string
  value: string
  category: string
  appearsAt: number // seconds into simulation when this memory appears
}

export interface DemoEvent {
  time: number
  type: string
  detail: string
}

// ── Simulation State Machine ─────────────────────────────────────────────────

export type SimPhase = 'idle' | 'planning' | 'executing' | 'reviewing' | 'complete'

export type SpeedMultiplier = 0.5 | 1 | 2

export interface SimulationState {
  phase: SimPhase
  elapsed: number        // seconds elapsed in simulation time
  speed: SpeedMultiplier
  paused: boolean
  tasks: DemoTask[]
  agents: DemoAgent[]
  pipeline: PipelineState
  memories: DemoMemoryEntry[]
  events: DemoEvent[]
  totalCost: number
  avgLatency: number
  successRate: number
  completedCount: number
}

// ── Timeline Actions ─────────────────────────────────────────────────────────

export type TimelineAction =
  | { type: 'start_sprint' }
  | { type: 'set_phase'; phase: SimPhase }
  | { type: 'set_pipeline'; stage: PipelineStage; status: StageStatus }
  | { type: 'claim_task'; taskId: string; agentId: string }
  | { type: 'start_task'; taskId: string }
  | { type: 'complete_task'; taskId: string; cost: number; result: string }
  | { type: 'fail_task'; taskId: string; reason: string }
  | { type: 'escalate_task'; taskId: string; fromAgent: string; toAgent: string; newModel: string }
  | { type: 'add_event'; event: DemoEvent }

export interface TimelineEntry {
  time: number           // seconds into simulation
  actions: TimelineAction[]
}

// ── Chart Data ───────────────────────────────────────────────────────────────

export interface CostDataPoint {
  time: number
  cost: number
  label: string
}

export interface LatencyDataPoint {
  time: number
  latency: number
  label: string
}

// ── Trajectory Replay ────────────────────────────────────────────────────────

export interface TrajectoryCommand {
  taskId: string
  step: number
  command: string
  output: string
  timestamp: number
}

// ── View Navigation ──────────────────────────────────────────────────────────

export type DemoView =
  | 'mission-control'
  | 'task-board'
  | 'pipeline'
  | 'agents'
  | 'memory'
  | 'trajectory'
  | 'metrics'
