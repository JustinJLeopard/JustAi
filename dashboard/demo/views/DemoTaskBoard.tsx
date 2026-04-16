/**
 * JustAi Demo — Task Board View (Stub)
 *
 * Placeholder for the full Kanban-style task board.
 * Shows tasks grouped by status with basic details.
 */

import type { SimulationState } from '../data/types'

export interface DemoTaskBoardProps {
  state: SimulationState
}

export function DemoTaskBoard({ state }: DemoTaskBoardProps) {
  const byStatus = {
    pending: state.tasks.filter(t => t.status === 'pending'),
    claimed: state.tasks.filter(t => t.status === 'claimed'),
    in_progress: state.tasks.filter(t => t.status === 'in_progress'),
    done: state.tasks.filter(t => t.status === 'done'),
    failed: state.tasks.filter(t => t.status === 'failed'),
  }

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
        Task Board
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
        {state.tasks.length} tasks total
      </p>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {(Object.entries(byStatus) as [string, typeof state.tasks][]).map(([status, tasks]) => (
          <div
            key={status}
            style={{
              flex: '1 1 160px',
              minWidth: 160,
              padding: 12,
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
              {status.replace('_', ' ')} ({tasks.length})
            </div>

            {tasks.map(task => (
              <div
                key={task.id}
                style={{
                  fontSize: 12,
                  fontWeight: 300,
                  color: 'var(--text-secondary)',
                  padding: '4px 0',
                  borderBottom: '1px solid var(--border-subtle, rgba(255,255,255,0.04))',
                }}
              >
                {task.name}
                {task.escalated && (
                  <span style={{ color: 'rgba(244,63,94,0.8)', marginLeft: 6, fontSize: 10 }}>
                    ESC
                  </span>
                )}
              </div>
            ))}

            {tasks.length === 0 && (
              <div style={{ fontSize: 11, color: 'var(--text-dim)', fontStyle: 'italic' }}>
                None
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
