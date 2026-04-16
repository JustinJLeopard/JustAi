/**
 * JustAi Demo — Memory View (Stub)
 *
 * Placeholder for the full memory browser.
 * Shows memory entries that have appeared so far in the simulation.
 */

import type { SimulationState } from '../data/types'

export interface DemoMemoryProps {
  state: SimulationState
}

export function DemoMemory({ state }: DemoMemoryProps) {
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
        Memory
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
        {' \u00B7 '}
        {state.memories.length} entries visible
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {state.memories.length === 0 && (
          <div
            style={{
              fontSize: 12,
              color: 'var(--text-dim)',
              fontStyle: 'italic',
              padding: 16,
              background: 'var(--bg-elevated, rgba(255,255,255,0.03))',
              border: '1px solid var(--border-subtle, rgba(255,255,255,0.06))',
              borderRadius: 8,
            }}
          >
            No memory entries yet. Memories appear as the simulation progresses.
          </div>
        )}

        {state.memories.map(mem => (
          <div
            key={mem.id}
            style={{
              padding: '10px 14px',
              background: 'var(--bg-elevated, rgba(255,255,255,0.03))',
              border: '1px solid var(--border-subtle, rgba(255,255,255,0.06))',
              borderRadius: 8,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 400,
                  color: 'var(--text-primary)',
                  fontFamily: 'monospace',
                }}
              >
                {mem.key}
              </span>
              <span
                style={{
                  fontSize: 9,
                  fontWeight: 500,
                  textTransform: 'uppercase',
                  letterSpacing: 1,
                  color: 'var(--text-dim)',
                  background: 'rgba(255,255,255,0.04)',
                  padding: '1px 6px',
                  borderRadius: 3,
                }}
              >
                {mem.category}
              </span>
            </div>
            <div style={{ fontSize: 12, fontWeight: 300, color: 'var(--text-secondary)' }}>
              {mem.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
