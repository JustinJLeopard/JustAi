/**
 * JustAi Demo — Agents View (Stub)
 *
 * Placeholder for the full agents management view.
 * Shows all demo agents with their status, model, and task info.
 */

import type { SimulationState } from '../data/types'

export interface DemoAgentsProps {
  state: SimulationState
}

export function DemoAgents({ state }: DemoAgentsProps) {
  const activeCount = state.agents.filter(a => a.status === 'active').length

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
        Agents
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
        {activeCount} active / {state.agents.length} total
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {state.agents.map(agent => {
          const isActive = agent.status === 'active'
          const currentTask = agent.currentTaskId
            ? state.tasks.find(t => t.id === agent.currentTaskId)
            : null

          return (
            <div
              key={agent.id}
              style={{
                padding: '12px 16px',
                background: 'var(--bg-elevated, rgba(255,255,255,0.03))',
                border: `1px solid ${isActive ? 'rgba(244,63,94,0.2)' : 'var(--border-subtle, rgba(255,255,255,0.06))'}`,
                borderRadius: 8,
                display: 'flex',
                alignItems: 'center',
                gap: 12,
              }}
            >
              {/* Status dot */}
              <span
                style={{
                  display: 'inline-block',
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: isActive ? '#10b981' : 'var(--text-dim)',
                  boxShadow: isActive ? '0 0 6px rgba(16,185,129,0.5)' : 'none',
                  flexShrink: 0,
                }}
              />

              {/* Agent info */}
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 300, color: 'var(--text-primary)' }}>
                  {agent.name}
                </div>
                <div style={{ fontSize: 11, fontWeight: 300, color: 'var(--text-dim)', marginTop: 2 }}>
                  {agent.model}
                  {currentTask && (
                    <span style={{ color: 'var(--text-secondary)', marginLeft: 8 }}>
                      Working on: {currentTask.name}
                    </span>
                  )}
                </div>
              </div>

              {/* Tasks completed */}
              <div
                style={{
                  fontFamily: 'monospace',
                  fontSize: 11,
                  color: 'var(--text-tertiary)',
                  background: 'rgba(255,255,255,0.04)',
                  padding: '2px 8px',
                  borderRadius: 4,
                }}
              >
                {agent.tasksCompleted} done
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
