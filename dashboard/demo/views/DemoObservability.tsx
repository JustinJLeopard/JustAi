/**
 * JustAi Demo — Observability View (Stub)
 *
 * Placeholder for the full metrics/observability dashboard.
 * Shows key metrics: cost, latency, success rate, and task throughput.
 */

import type { SimulationState } from '../data/types'

export interface DemoObservabilityProps {
  state: SimulationState
}

export function DemoObservability({ state }: DemoObservabilityProps) {
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
        Observability
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

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 24 }}>
        <MetricCard label="Total Cost" value={`$${state.totalCost.toFixed(3)}`} />
        <MetricCard label="Avg Latency" value={`${state.avgLatency.toFixed(1)}ms`} />
        <MetricCard label="Success Rate" value={`${state.successRate.toFixed(1)}%`} />
        <MetricCard label="Completed" value={`${state.completedCount}/${state.tasks.length}`} />
      </div>

      {/* Speed indicator */}
      <div
        style={{
          padding: '12px 16px',
          background: 'var(--bg-elevated, rgba(255,255,255,0.03))',
          border: '1px solid var(--border-subtle, rgba(255,255,255,0.06))',
          borderRadius: 8,
        }}
      >
        <div
          style={{
            fontSize: 10,
            fontWeight: 500,
            textTransform: 'uppercase',
            letterSpacing: 1.5,
            color: 'var(--text-dim)',
            marginBottom: 8,
          }}
        >
          Simulation
        </div>
        <div style={{ fontSize: 12, fontWeight: 300, color: 'var(--text-secondary)' }}>
          Speed: {state.speed}x
          {' \u00B7 '}
          {state.paused ? 'Paused' : 'Running'}
          {' \u00B7 '}
          Events logged: {state.events.length}
        </div>
      </div>
    </div>
  )
}

// ── Metric card ─────────────────────────────────────────────────────────────

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        padding: '12px 16px',
        background: 'var(--bg-elevated, rgba(255,255,255,0.03))',
        border: '1px solid var(--border-subtle, rgba(255,255,255,0.06))',
        borderRadius: 8,
        minWidth: 130,
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
