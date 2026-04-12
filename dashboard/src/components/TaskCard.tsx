import { Task, taskDuration, msAgo } from '@/lib/spacetime'

interface TaskCardProps {
  task: Task
  onClick?: () => void
}

const STATUS_CONFIG: Record<string, { dotColor: string; label: string }> = {
  pending:     { dotColor: 'var(--text-muted)',    label: 'Pending' },
  claimed:     { dotColor: 'var(--text-secondary)', label: 'Claimed' },
  in_progress: { dotColor: 'var(--rose-400)',       label: 'Running' },
  done:        { dotColor: 'var(--emerald-400)',    label: 'Done' },
  failed:      { dotColor: 'var(--red-500)',        label: 'Failed' },
  archived:    { dotColor: 'var(--text-muted)',     label: 'Archived' },
}

const RISK_COLOR: Record<string, string> = {
  R0: 'var(--emerald-400)',
  R1: 'var(--text-secondary)',
  R2: 'var(--gold-400)',
  R3: 'var(--red-500)',
}

export function TaskCard({ task, onClick }: TaskCardProps) {
  const cfg = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.pending
  const duration = taskDuration(task)
  const age = msAgo(task.createdAt)

  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--r-md)',
        padding: 'var(--sp-3)',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'border-color var(--t-fast)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--sp-2)',
      }}
      onMouseEnter={e => {
        if (onClick) {
          e.currentTarget.style.borderColor = 'var(--border-hover)'
        }
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'var(--border-subtle)'
      }}
    >
      {/* Status badge + ID */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
        {/* Colored dot + status label */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: cfg.dotColor,
            flexShrink: 0,
          }} />
          <span style={{
            fontSize: 10,
            fontWeight: 500,
            color: cfg.dotColor,
            textTransform: 'uppercase',
            letterSpacing: '1px',
          }}>
            {cfg.label}
          </span>
        </div>
        <span style={{
          fontSize: 11,
          color: 'var(--text-muted)',
          marginLeft: 'auto',
          fontFamily: 'var(--font-mono)',
        }}>
          #{task.id.toString()}
        </span>
      </div>

      {/* Task description */}
      <div style={{
        fontSize: 13,
        fontWeight: 300,
        color: 'var(--text-secondary)',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        lineHeight: '1.4',
      }}>
        {task.title || task.payload.slice(0, 80)}
      </div>

      {/* Meta row */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--sp-2)',
        fontSize: 11,
        color: 'var(--text-muted)',
        fontFamily: 'var(--font-mono)',
        flexWrap: 'wrap',
      }}>
        {task.toAgent && (
          <span>→ {task.toAgent}</span>
        )}
        {task.retryCount > 0 && (
          <span style={{ color: 'var(--gold-400)' }}>
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
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
          color: task.status === 'done' ? 'var(--emerald-400)' : 'var(--red-500)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          paddingTop: 'var(--sp-2)',
          borderTop: '1px solid var(--border-subtle)',
        }}>
          {task.result.slice(0, 100)}
        </div>
      )}
    </div>
  )
}
