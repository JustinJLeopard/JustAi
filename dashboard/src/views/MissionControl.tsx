import { useState, useEffect } from 'react'
import { LiveData } from '@/lib/spacetime'
import { fetchHealth } from '../lib/api-client'
import type { HealthData } from '../lib/api-client'
import { AgentCard } from '@/components/AgentCard'
import { TaskCard } from '@/components/TaskCard'

interface MissionControlProps {
  data: LiveData
}

function HealthDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <div style={{
        width: '8px', height: '8px', borderRadius: '50%',
        background: ok ? 'var(--accent-green)' : 'var(--accent-red)',
        boxShadow: ok ? '0 0 6px var(--accent-green)' : 'none',
      }} />
      <span style={{ fontSize: '12px', color: ok ? 'var(--text-secondary)' : 'var(--accent-red)' }}>
        {label}
      </span>
    </div>
  )
}

export function MissionControl({ data }: MissionControlProps) {
  const { tasks, agents, connected, lastUpdated, error } = data
  const [health, setHealth] = useState<HealthData | null>(null)

  useEffect(() => {
    const load = () => fetchHealth().then(setHealth).catch(() => {})
    load()
    const id = setInterval(load, 10000)
    return () => clearInterval(id)
  }, [])

  const litellmOk = health?.services.find(s => s.name === 'LiteLLM')?.ok ?? false
  const mcpOk = health?.services.find(s => s.name === 'claude-flow MCP')?.ok ?? false

  const activeTasks = tasks.filter(t =>
    t.status === 'in_progress' || t.status === 'claimed'
  )
  const onlineAgents = agents.filter(a => a.status === 'online')
  const doneTasks = tasks.filter(t => t.status === 'done')
  const failedTasks = tasks.filter(t => t.status === 'failed')

  // Map currentTaskId to task title for agent cards
  const taskTitleById = new Map(tasks.map(t => [t.id, t.title || t.payload.slice(0, 60)]))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* System Health Bar */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: '10px',
        padding: '14px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: '24px',
        flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '1px', textTransform: 'uppercase' }}>
          System
        </span>
        <HealthDot ok={connected} label="SpacetimeDB" />
        <HealthDot ok={litellmOk} label="LiteLLM" />
        <HealthDot ok={mcpOk} label="Memory" />
        <HealthDot ok={onlineAgents.length > 0} label={`${onlineAgents.length} agent${onlineAgents.length !== 1 ? 's' : ''} online`} />
        {error && (
          <span style={{ fontSize: '12px', color: 'var(--accent-red)', marginLeft: 'auto' }}>
            ⚠ {error}
          </span>
        )}
        {lastUpdated && !error && (
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: 'auto' }}>
            updated {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Stats Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
        {[
          { label: 'Active', value: activeTasks.length, color: 'var(--accent-purple)' },
          { label: 'Done', value: doneTasks.length, color: 'var(--accent-green)' },
          { label: 'Failed', value: failedTasks.length, color: 'var(--accent-red)' },
          { label: 'Total', value: tasks.length, color: 'var(--text-secondary)' },
        ].map(stat => (
          <div key={stat.label} style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: '10px',
            padding: '16px',
            textAlign: 'center',
          }}>
            <div style={{ fontSize: '28px', fontWeight: 700, color: stat.color, lineHeight: 1 }}>
              {stat.value}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              {stat.label}
            </div>
          </div>
        ))}
      </div>

      {/* Agent Grid */}
      <section>
        <h2 style={{ margin: '0 0 12px', fontSize: '13px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>
          Agents
        </h2>
        {agents.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '13px', padding: '20px 0' }}>
            No agents registered.
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: '12px',
          }}>
            {agents.map(agent => (
              <AgentCard
                key={agent.name}
                agent={agent}
                taskTitle={
                  agent.currentTaskId > 0n
                    ? taskTitleById.get(agent.currentTaskId)
                    : undefined
                }
              />
            ))}
          </div>
        )}
      </section>

      {/* Active Task Pipeline */}
      <section>
        <h2 style={{ margin: '0 0 12px', fontSize: '13px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>
          Active Pipeline
        </h2>
        {activeTasks.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '13px', padding: '20px 0' }}>
            No tasks currently running.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {activeTasks.map(task => (
              <TaskCard key={task.id.toString()} task={task} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
