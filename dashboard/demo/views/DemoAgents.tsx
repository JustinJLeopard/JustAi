/**
 * JustAi Demo — Agents View
 *
 * Displays all demo agents in a responsive 3-column grid with status dots,
 * model info, tasks completed count, and current task name when active.
 */

import type { SimulationState, DemoAgent, DemoTask } from '../data/types'

// ── Props ───────────────────────────────────────────────────────────────────

export interface DemoAgentsProps {
  state: SimulationState
}

// ── Agent Card ──────────────────────────────────────────────────────────────

function AgentCard({
  agent,
  currentTask,
}: {
  agent: DemoAgent
  currentTask: DemoTask | null
}) {
  const isActive = agent.status === 'active'

  return (
    <div
      className="panel"
      style={{
        padding: 'var(--sp-5)',
        borderColor: isActive ? 'rgba(244,63,94,0.15)' : undefined,
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--sp-3)',
      }}
    >
      {/* Top row: status dot + name */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--sp-2)',
        }}
      >
        {/* Status dot */}
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: isActive ? 'var(--emerald-500)' : 'var(--text-dim)',
            boxShadow: isActive ? '0 0 6px var(--emerald-glow)' : 'none',
            animation: isActive ? 'pulse-live 2s ease-in-out infinite' : undefined,
            flexShrink: 0,
          }}
        />

        {/* Agent name */}
        <span
          style={{
            fontSize: 14,
            fontWeight: 400,
            color: 'var(--text-primary)',
            flex: 1,
          }}
        >
          {agent.name}
        </span>
      </div>

      {/* Model */}
      <div
        style={{
          fontSize: 11,
          fontWeight: 400,
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
        }}
      >
        {agent.model}
      </div>

      {/* Current task (if active) */}
      {isActive && currentTask && (
        <div
          style={{
            fontSize: 11,
            fontWeight: 300,
            color: 'var(--rose-400)',
            padding: '6px 10px',
            borderRadius: 'var(--r-sm)',
            background: 'var(--rose-glow)',
            border: '1px solid rgba(244,63,94,0.1)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {currentTask.name}
        </div>
      )}

      {/* Tasks completed count */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginTop: 'auto',
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontWeight: 500,
            textTransform: 'uppercase',
            letterSpacing: '1px',
            color: 'var(--text-dim)',
          }}
        >
          Tasks Completed
        </span>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            fontWeight: 500,
            color: agent.tasksCompleted > 0 ? 'var(--emerald-400)' : 'var(--text-dim)',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {agent.tasksCompleted}
        </span>
      </div>
    </div>
  )
}

// ── Main Component ──────────────────────────────────────────────────────────

export function DemoAgents({ state }: DemoAgentsProps) {
  const activeCount = state.agents.filter(a => a.status === 'active').length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>

      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div>
        <h1
          style={{
            fontSize: 22,
            fontWeight: 200,
            color: 'var(--text-primary)',
            letterSpacing: '0.3px',
            margin: 0,
          }}
        >
          Agents
        </h1>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--sp-2)',
            fontSize: 13,
            color: 'var(--text-secondary)',
            marginTop: 2,
            fontWeight: 300,
          }}
        >
          {activeCount > 0 && (
            <div
              style={{
                width: 5,
                height: 5,
                borderRadius: '50%',
                background: 'var(--emerald-500)',
                animation: 'pulse-live 2s ease-in-out infinite',
                flexShrink: 0,
              }}
            />
          )}
          <span>
            {state.agents.length} agent{state.agents.length !== 1 ? 's' : ''}
            {activeCount > 0 ? ` \u00B7 ${activeCount} active` : ''}
          </span>
        </div>
      </div>

      {/* ── Agent Grid (3-column responsive) ────────────────────────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 'var(--sp-3)',
        }}
      >
        {state.agents.length === 0 ? (
          <div
            className="panel panel-pad"
            style={{
              gridColumn: '1 / -1',
              textAlign: 'center',
              padding: 'var(--sp-10)',
              color: 'var(--text-muted)',
              fontWeight: 300,
              fontSize: 13,
            }}
          >
            No agents registered
          </div>
        ) : (
          state.agents.map(agent => {
            const currentTask = agent.currentTaskId
              ? state.tasks.find(t => t.id === agent.currentTaskId) ?? null
              : null

            return (
              <AgentCard
                key={agent.id}
                agent={agent}
                currentTask={currentTask}
              />
            )
          })
        )}
      </div>
    </div>
  )
}
