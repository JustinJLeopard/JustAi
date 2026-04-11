import { Agent, msAgo, isStale } from '@/lib/spacetime'

interface AgentCardProps {
  agent: Agent
  taskTitle?: string
}

const STATUS_COLOR: Record<string, string> = {
  online: 'var(--accent-green)',
  offline: 'var(--text-muted)',
  stale: 'var(--accent-yellow)',
}

const HANDLER_ICON: Record<string, string> = {
  'discord-bot': '🤖',
  'daemon': '⚙️',
  'cli': '💻',
}

export function AgentCard({ agent, taskTitle }: AgentCardProps) {
  const stale = isStale(agent.lastHeartbeat)
  const effectiveStatus = stale && agent.status === 'online' ? 'stale' : agent.status
  const color = STATUS_COLOR[effectiveStatus] ?? STATUS_COLOR.offline
  const icon = HANDLER_ICON[agent.handlerType] ?? '🔲'
  const caps = agent.capabilities.split(',').map(c => c.trim()).filter(Boolean)

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: `1px solid var(--border)`,
      borderRadius: '10px',
      padding: '14px 16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      transition: 'border-color 0.15s',
      cursor: 'default',
    }}
    onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-bright)')}
    onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '16px' }}>{icon}</span>
        <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '13px' }}>
          {agent.name}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '5px' }}>
          <div style={{
            width: '7px', height: '7px', borderRadius: '50%',
            background: color,
            boxShadow: effectiveStatus === 'online' ? `0 0 6px ${color}` : 'none',
          }} />
          <span style={{ fontSize: '11px', color, textTransform: 'capitalize' }}>
            {effectiveStatus}
          </span>
        </div>
      </div>

      {/* Current task */}
      <div style={{
        fontSize: '12px',
        color: taskTitle ? 'var(--text-secondary)' : 'var(--text-muted)',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {taskTitle ?? (agent.status === 'online' ? 'Idle' : '—')}
      </div>

      {/* Capabilities */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
        {caps.map(cap => (
          <span key={cap} style={{
            fontSize: '10px',
            padding: '2px 6px',
            borderRadius: '4px',
            background: 'var(--bg-secondary)',
            color: 'var(--text-muted)',
            border: '1px solid var(--border)',
          }}>
            {cap}
          </span>
        ))}
      </div>

      {/* Heartbeat */}
      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
        ♥ {agent.lastHeartbeat > 0n ? msAgo(agent.lastHeartbeat) : 'never'}
      </div>
    </div>
  )
}
