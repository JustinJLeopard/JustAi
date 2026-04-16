/**
 * JustAi Demo — Simulation Engine
 *
 * React hook that drives a deterministic state machine for the interactive demo.
 * Processes TIMELINE events on a 100ms interval, supports play/pause/speed/reset,
 * and computes derived metrics (cost, latency, success rate).
 *
 * The simulation is fully self-contained — no network calls, no side effects
 * beyond React state. All data comes from sprint-timeline.ts.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import type {
  DemoTask,
  DemoAgent,
  DemoEvent,
  DemoMemoryEntry,
  PipelineState,
  SimPhase,
  SimulationState,
  SpeedMultiplier,
  TimelineAction,
} from '../data/types'

import {
  INITIAL_TASKS,
  INITIAL_AGENTS,
  INITIAL_MEMORIES,
  TIMELINE,
  LATENCY_SERIES,
} from '../data/sprint-timeline'

// ── Constants ────────────────────────────────────────────────────────────────

const TICK_INTERVAL_MS = 100 // 100ms real-time tick
const SECONDS_PER_TICK = 0.1 // base: each tick = 0.1 simulated seconds

// ── Helper: deep-clone arrays of plain objects ───────────────────────────────

function cloneTasks(tasks: DemoTask[]): DemoTask[] {
  return tasks.map(t => ({ ...t }))
}

function cloneAgents(agents: DemoAgent[]): DemoAgent[] {
  return agents.map(a => ({ ...a }))
}

// ── Initial pipeline state ───────────────────────────────────────────────────

function initialPipeline(): PipelineState {
  return {
    intent: 'idle',
    plan: 'idle',
    execute: 'idle',
    review: 'idle',
    synthesize: 'idle',
  }
}

// ── Initial simulation state ─────────────────────────────────────────────────

function initialState(): SimulationState {
  return {
    phase: 'idle',
    elapsed: 0,
    speed: 1,
    paused: true,
    tasks: cloneTasks(INITIAL_TASKS),
    agents: cloneAgents(INITIAL_AGENTS),
    pipeline: initialPipeline(),
    memories: [],
    events: [],
    totalCost: 0,
    avgLatency: 0,
    successRate: 0,
    completedCount: 0,
  }
}

// ── Compute derived metrics ──────────────────────────────────────────────────

function computeDerivedMetrics(tasks: DemoTask[]): {
  totalCost: number
  avgLatency: number
  successRate: number
  completedCount: number
} {
  const completed = tasks.filter(t => t.status === 'done')
  const completedCount = completed.length
  const totalCost = completed.reduce((sum, t) => sum + t.cost, 0)

  // Average latency from LATENCY_SERIES for completed tasks
  const completedIds = new Set(completed.map(t => t.id))
  const matchedLatencies = LATENCY_SERIES.filter((_, i) => {
    const taskId = `task-${i + 1}`
    return completedIds.has(taskId)
  })
  const avgLatency =
    matchedLatencies.length > 0
      ? matchedLatencies.reduce((sum, l) => sum + l.latency, 0) / matchedLatencies.length
      : 0

  // Success rate: completed tasks / total attempted (escalated-but-done = success)
  const attempted = tasks.filter(t => t.status === 'done' || t.status === 'failed')
  const succeeded = attempted.filter(t => t.status === 'done')
  const successRate =
    attempted.length > 0
      ? (succeeded.length / attempted.length) * 100
      : 0

  return { totalCost, avgLatency, successRate, completedCount }
}

// ── Filter memories by elapsed time ──────────────────────────────────────────

function filterMemories(elapsed: number): DemoMemoryEntry[] {
  return INITIAL_MEMORIES.filter(m => m.appearsAt <= elapsed)
}

// ── Apply a single timeline action to state ──────────────────────────────────

function applyAction(
  state: SimulationState,
  action: TimelineAction,
): SimulationState {
  switch (action.type) {
    case 'start_sprint':
      return { ...state, phase: 'planning', paused: false }

    case 'set_phase':
      return { ...state, phase: action.phase }

    case 'set_pipeline':
      return {
        ...state,
        pipeline: { ...state.pipeline, [action.stage]: action.status },
      }

    case 'claim_task': {
      const tasks = state.tasks.map(t =>
        t.id === action.taskId
          ? {
              ...t,
              status: 'claimed' as const,
              agent: state.agents.find(a => a.id === action.agentId)?.name ?? action.agentId,
              model: state.agents.find(a => a.id === action.agentId)?.model ?? '',
              stepsDone: 0,
            }
          : t,
      )
      const agents = state.agents.map(a =>
        a.id === action.agentId
          ? { ...a, status: 'active' as const, currentTaskId: action.taskId }
          : a,
      )
      return { ...state, tasks, agents }
    }

    case 'start_task': {
      const tasks = state.tasks.map(t =>
        t.id === action.taskId ? { ...t, status: 'in_progress' as const } : t,
      )
      return { ...state, tasks }
    }

    case 'complete_task': {
      const tasks = state.tasks.map(t =>
        t.id === action.taskId
          ? { ...t, status: 'done' as const, cost: action.cost, result: action.result, stepsDone: t.steps }
          : t,
      )
      // Free the agent
      const completedTask = state.tasks.find(t => t.id === action.taskId)
      const agents = state.agents.map(a =>
        a.currentTaskId === action.taskId
          ? {
              ...a,
              status: 'idle' as const,
              currentTaskId: null,
              tasksCompleted: a.tasksCompleted + 1,
            }
          : a,
      )
      // Mark trajectory learning if task 5
      const finalTasks = tasks.map(t =>
        t.id === action.taskId && action.taskId === 'task-5'
          ? { ...t, trajectoryLearning: true }
          : t,
      )
      void completedTask // used for reference only
      const metrics = computeDerivedMetrics(finalTasks)
      return { ...state, tasks: finalTasks, agents, ...metrics }
    }

    case 'fail_task': {
      const tasks = state.tasks.map(t =>
        t.id === action.taskId ? { ...t, status: 'failed' as const, result: action.reason } : t,
      )
      // Free the agent
      const agents = state.agents.map(a =>
        a.currentTaskId === action.taskId
          ? { ...a, status: 'idle' as const, currentTaskId: null }
          : a,
      )
      return { ...state, tasks, agents }
    }

    case 'escalate_task': {
      const tasks = state.tasks.map(t =>
        t.id === action.taskId
          ? {
              ...t,
              status: 'pending' as const,
              escalated: true,
              escalatedFrom: action.fromAgent,
              agent: '',
              model: '',
              stepsDone: 0,
            }
          : t,
      )
      // Free the old agent
      const agents = state.agents.map(a =>
        a.id === action.fromAgent
          ? { ...a, status: 'idle' as const, currentTaskId: null }
          : a,
      )
      return { ...state, tasks, agents }
    }

    case 'add_event':
      return { ...state, events: [...state.events, action.event] }

    default:
      return state
  }
}

// ── Step progress animation ──────────────────────────────────────────────────
// For in-progress tasks, smoothly increment stepsDone toward steps total.

function animateStepProgress(tasks: DemoTask[], speed: SpeedMultiplier): DemoTask[] {
  return tasks.map(t => {
    if (t.status !== 'in_progress' || t.stepsDone >= t.steps) return t
    // Increment by a fraction proportional to speed
    const increment = (speed * 0.15)
    const newStepsDone = Math.min(t.stepsDone + increment, t.steps - 1)
    return { ...t, stepsDone: newStepsDone }
  })
}

// ── Hook Interface ───────────────────────────────────────────────────────────

export interface SimulationControls {
  play: () => void
  pause: () => void
  togglePlayPause: () => void
  setSpeed: (speed: SpeedMultiplier) => void
  reset: () => void
  replay: () => void
}

export interface UseSimulationReturn {
  state: SimulationState
  controls: SimulationControls
}

// ── The Hook ─────────────────────────────────────────────────────────────────

export function useSimulation(): UseSimulationReturn {
  const [state, setState] = useState<SimulationState>(initialState)

  // Track which timeline entries have been processed (by index)
  const processedRef = useRef<Set<number>>(new Set())
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Tick function ────────────────────────────────────────────────────────

  const tick = useCallback(() => {
    setState(prev => {
      if (prev.paused || prev.phase === 'idle' || prev.phase === 'complete') {
        return prev
      }

      // Advance elapsed time
      const elapsed = prev.elapsed + SECONDS_PER_TICK * prev.speed
      let next: SimulationState = { ...prev, elapsed }

      // Process timeline entries whose time has been reached
      TIMELINE.forEach((entry, index) => {
        if (processedRef.current.has(index)) return
        if (elapsed >= entry.time) {
          processedRef.current.add(index)
          for (const action of entry.actions) {
            next = applyAction(next, action)
          }
        }
      })

      // Animate step progress for in-progress tasks
      next = { ...next, tasks: animateStepProgress(next.tasks, next.speed) }

      // Update visible memories based on elapsed time
      next = { ...next, memories: filterMemories(elapsed) }

      // Recompute derived metrics (step progress may not change costs,
      // but keeps state consistent)
      const metrics = computeDerivedMetrics(next.tasks)
      next = { ...next, ...metrics }

      return next
    })
  }, [])

  // ── Interval management ──────────────────────────────────────────────────

  useEffect(() => {
    intervalRef.current = setInterval(tick, TICK_INTERVAL_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [tick])

  // ── Controls ─────────────────────────────────────────────────────────────

  const play = useCallback(() => {
    setState(prev => {
      if (prev.phase === 'idle') {
        // First play: start the sprint
        processedRef.current = new Set()
        return { ...prev, paused: false, phase: 'planning' }
      }
      return { ...prev, paused: false }
    })
  }, [])

  const pause = useCallback(() => {
    setState(prev => ({ ...prev, paused: true }))
  }, [])

  const togglePlayPause = useCallback(() => {
    setState(prev => {
      if (prev.phase === 'idle') {
        processedRef.current = new Set()
        return { ...prev, paused: false, phase: 'planning' }
      }
      if (prev.phase === 'complete') {
        return prev // Don't unpause when complete
      }
      return { ...prev, paused: !prev.paused }
    })
  }, [])

  const setSpeed = useCallback((speed: SpeedMultiplier) => {
    setState(prev => ({ ...prev, speed }))
  }, [])

  const reset = useCallback(() => {
    processedRef.current = new Set()
    setState(initialState())
  }, [])

  const replay = useCallback(() => {
    processedRef.current = new Set()
    const fresh = initialState()
    setState({ ...fresh, paused: false, phase: 'planning' })
  }, [])

  return {
    state,
    controls: { play, pause, togglePlayPause, setSpeed, reset, replay },
  }
}
