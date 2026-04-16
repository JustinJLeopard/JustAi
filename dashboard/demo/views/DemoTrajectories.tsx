/**
 * JustAi Demo — Trajectories View (Stub)
 *
 * Placeholder for the full trajectory viewer.
 * Shows tasks that have trajectory learning enabled and basic step info.
 */

import type { SimulationState } from '../data/types'

export interface DemoTrajectoriesProps {
  state: SimulationState
}

export function DemoTrajectories({ state }: DemoTrajectoriesProps) {
  const trajectoryTasks = state.tasks.filter(t => t.trajectoryLearning || t.status === 'done')

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
        Trajectories
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
        {trajectoryTasks.length} trajectories recorded
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {trajectoryTasks.length === 0 && (
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
            No trajectories yet. Tasks will appear here as they complete.
          </div>
        )}

        {trajectoryTasks.map(task => (
          <div
            key={task.id}
            style={{
              padding: '12px 16px',
              background: 'var(--bg-elevated, rgba(255,255,255,0.03))',
              border: `1px solid ${task.trajectoryLearning ? 'rgba(244,63,94,0.2)' : 'var(--border-subtle, rgba(255,255,255,0.06))'}`,
              borderRadius: 8,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ fontSize: 13, fontWeight: 300, color: 'var(--text-primary)' }}>
                {task.name}
                {task.trajectoryLearning && (
                  <span
                    style={{
                      fontSize: 9,
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: 1,
                      color: 'rgba(244,63,94,0.8)',
                      background: 'rgba(244,63,94,0.1)',
                      padding: '1px 5px',
                      borderRadius: 3,
                      marginLeft: 8,
                    }}
                  >
                    Learning
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, fontWeight: 300, color: 'var(--text-dim)', marginTop: 2 }}>
                {task.agent} / {task.model}
              </div>
            </div>
            <div style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-tertiary)' }}>
              {Math.floor(task.stepsDone)}/{task.steps} steps
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
