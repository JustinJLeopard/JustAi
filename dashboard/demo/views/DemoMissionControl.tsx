/**
 * JustAi Demo — Mission Control View (Stub)
 *
 * Placeholder for the full Mission Control dashboard.
 * Shows system overview with pipeline status, active agents, and task summary.
 */

import type { SimulationState, DemoView } from '../data/types'

export interface DemoMissionControlProps {
  state: SimulationState
  onNavigate?: (view: DemoView) => void
}

export function DemoMissionControl({ state, onNavigate }: DemoMissionControlProps) {
  const activeTasks = state.tasks.filter(
    t => t.status === 'claimed' || t.status === 'in_progress',
  ).length
  const completedTasks = state.tasks.filter(t => t.status === 'done').length
  const activeAgents = state.agents.filter(a => a.status === 'active').length

  return (
    <div>
      <h1
        style={{
          fontSize: 22,
          fontWeight: 200,
          letterSpacing: 1,
          color: 'var(--text-primary)',
          marginBottom: 8,
        }}
      >
        Mission Control
      </h1>

      <p
        style={{
          fontSize: 13,
          fontWeight: 300,
          color: 'var(--text-secondary)',
          marginBottom: 24,
        }}
      >
        Phase: <strong style={{ fontWeight: 500 }}>{state.phase}</strong>
        {' \u00B7 '}
        Elapsed: {state.elapsed.toFixed(1)}s
      </p>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <StatCard label="Active Tasks" value={activeTasks} />
        <StatCard label="Completed" value={completedTasks} />
        <StatCard label="Active Agents" value={activeAgents} />
        <StatCard label="Total Cost" value={`$${state.totalCost.toFixed(3)}`} />
        <StatCard label="Success Rate" value={`${state.successRate.toFixed(0)}%`} />
      </div>

      {onNavigate && (
        <p
          style={{
            fontSize: 11,
            color: 'var(--text-dim)',
            marginTop: 32,
            fontWeight: 300,
          }}
        >
          Use the sidebar to navigate between views.
        </p>
      )}
    </div>
  )
}

// ── Tiny stat card ──────────────────────────────────────────────────────────

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div
      style={{
        padding: '12px 16px',
        background: 'var(--bg-elevated, rgba(255,255,255,0.03))',
        border: '1px solid var(--border-subtle, rgba(255,255,255,0.06))',
        borderRadius: 8,
        minWidth: 120,
      }}
    >
      <div
        style={{
          fontSize: 10,
          fontWeight: 500,
          textTransform: 'uppercase',
          letterSpacing: 1.5,
          color: 'var(--text-dim)',
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 20,
          fontWeight: 200,
          color: 'var(--text-primary)',
          fontFamily: 'monospace',
        }}
      >
        {value}
      </div>
    </div>
  )
}
