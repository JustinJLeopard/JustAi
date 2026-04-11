import { Task, taskDuration, msAgo } from '@/lib/spacetime'

interface TaskCardProps {
  task: Task
  onClick?: () => void
}

const STATUS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  pending:     { color: 'var(--text-muted)',    bg: 'rgba(85,85,112,0.15)',  label: 'Pending' },
  claimed:     { color: 'var(--accent-blue)',   bg: 'rgba(77,124,254,0.12)', label: 'Claimed' },
  in_progress: { color: 'var(--accent-purple)', bg: 'rgba(139,92,246,0.12)', label: 'Running' },
  done:        { color: 'var(--accent-green)',  bg: 'rgba(34,197,94,0.12)',  label: 'Done' },
  failed:      { color: 'var(--accent-red)',    bg: 'rgba(239,68,68,0.12)',  label: 'Failed' },
  archived:    { color: 'var(--text-muted)',    bg: 'rgba(85,85,112,0.10)',  label: 'Archived' },
}

const RISK_COLOR: Record<string, string> = {
  R0: 'var(--accent-green)',
  R1: 'var(--accent-blue)',
  R2: 'var(--accent-yellow)',
  R3: 'var(--accent-red)',
}

export function TaskCard({ task, onClick }: TaskCardProps) {
  const cfg = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.pending
  const duration = taskDuration(task)
  const age = msAgo(task.createdAt)

  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--bg-card)',
        border: `1px solid var(--border)`,
        borderRadius: '8px',
        padding: '12px',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.15s',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
      }}
      onMouseEnter={e => {
        if (onClick) {
          e.currentTarget.style.borderColor = 'var(--border-bright)'
          e.currentTarget.style.transform = 'translateY(-1px)'
        }
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'var(--border)'
        e.currentTarget.style.transform = 'none'
      }}
    >
      {/* Status badge + ID */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{
          fontSize: '10px', fontWeight: 600,
          padding: '2px 7px', borderRadius: '4px',
          color: cfg.color, background: cfg.bg,
          letterSpacing: '0.5px', textTransform: 'uppercase',
        }}>
          {cfg.label}
        </span>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: 'auto' }}>
          #{task.id.toString()}
        </span>
      </div>

      {/* Title */}
      <div style={{
        fontSize: '13px', fontWeight: 500,
        color: 'var(--text-primary)',
        overflow: 'hidden', textOverflow: 'ellipsis',
        display: '-webkit-box', WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        lineHeight: '1.4',
      }}>
        {task.title || task.payload.slice(0, 80)}
      </div>

      {/* Meta row */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        fontSize: '11px', color: 'var(--text-muted)',
        flexWrap: 'wrap',
      }}>
        {task.toAgent && (
          <span>→ {task.toAgent}</span>
        )}
        {task.retryCount > 0 && (
          <span style={{ color: 'var(--accent-yellow)' }}>
            ↻ {task.retryCount}
          </span>
        )}
        {duration !== '—' && (
          <span>⏱ {duration}</span>
        )}
        <span style={{ marginLeft: 'auto' }}>{age}</span>
      </div>

      {/* Result preview (done/failed only) */}
      {(task.status === 'done' || task.status === 'failed') && task.result && (
        <div style={{
          fontSize: '11px',
          color: task.status === 'done' ? 'var(--accent-green)' : 'var(--accent-red)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          paddingTop: '4px', borderTop: '1px solid var(--border)',
        }}>
          {task.result.slice(0, 100)}
        </div>
      )}
    </div>
  )
}
