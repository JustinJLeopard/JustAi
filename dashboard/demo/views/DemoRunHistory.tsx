/**
 * JustAi Demo — Run History View (Stub)
 *
 * Placeholder for the full pipeline/run history view.
 * Shows pipeline stage statuses and event log.
 */

import type { SimulationState } from '../data/types'

export interface DemoRunHistoryProps {
  state: SimulationState
}

export function DemoRunHistory({ state }: DemoRunHistoryProps) {
  const stages = ['intent', 'plan', 'execute', 'review', 'synthesize'] as const

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
        Run History
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

      {/* Pipeline stages */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
        {stages.map(stage => {
          const status = state.pipeline[stage]
          const color =
            status === 'active'
              ? 'rgba(244,63,94,0.8)'
              : status === 'done'
                ? '#10b981'
                : 'var(--text-dim)'

          return (
            <div
              key={stage}
              style={{
                padding: '8px 14px',
                background: 'var(--bg-elevated, rgba(255,255,255,0.03))',
                border: `1px solid ${status === 'active' ? 'rgba(244,63,94,0.3)' : 'var(--border-subtle, rgba(255,255,255,0.06))'}`,
                borderRadius: 6,
                textAlign: 'center',
              }}
            >
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 500,
                  textTransform: 'uppercase',
                  letterSpacing: 1,
                  color,
                }}
              >
                {stage}
              </div>
              <div style={{ fontSize: 11, fontWeight: 300, color, marginTop: 2 }}>
                {status}
              </div>
            </div>
          )
        })}
      </div>

      {/* Event log */}
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
        Events ({state.events.length})
      </div>
      <div
        style={{
          maxHeight: 300,
          overflowY: 'auto',
          background: 'var(--bg-elevated, rgba(255,255,255,0.03))',
          border: '1px solid var(--border-subtle, rgba(255,255,255,0.06))',
          borderRadius: 8,
          padding: 12,
        }}
      >
        {state.events.length === 0 && (
          <div style={{ fontSize: 12, color: 'var(--text-dim)', fontStyle: 'italic' }}>
            No events yet. Press play to start the simulation.
          </div>
        )}
        {state.events.map((evt, i) => (
          <div
            key={i}
            style={{
              fontSize: 12,
              fontWeight: 300,
              color: 'var(--text-secondary)',
              padding: '3px 0',
              borderBottom: '1px solid var(--border-subtle, rgba(255,255,255,0.04))',
              fontFamily: 'monospace',
            }}
          >
            <span style={{ color: 'var(--text-dim)', marginRight: 8 }}>
              {evt.time.toFixed(1)}s
            </span>
            <span style={{ color: 'rgba(244,63,94,0.7)', marginRight: 8 }}>
              [{evt.type}]
            </span>
            {evt.detail}
          </div>
        ))}
      </div>
    </div>
  )
}
