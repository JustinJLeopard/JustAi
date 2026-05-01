import { Task, LiveData } from '@/lib/realtime'
import { TaskCard } from '@/components/TaskCard'

interface TaskBoardProps {
  data: LiveData
  onTaskClick?: (task: Task) => void
}

const COLUMNS: { key: Task['status'] | 'in_progress'; label: string; color: string }[] = [
  { key: 'pending',     label: 'Pending',  color: 'var(--text-muted)' },
  { key: 'claimed',     label: 'Claimed',  color: 'var(--text-secondary)' },
  { key: 'in_progress', label: 'Running',  color: 'var(--rose-400)' },
  { key: 'done',        label: 'Done',     color: 'var(--emerald-400)' },
  { key: 'failed',      label: 'Failed',   color: 'var(--red-500)' },
]

interface ColumnProps {
  label: string
  color: string
  tasks: Task[]
  onTaskClick?: (task: Task) => void
}

function KanbanColumn({ label, color, tasks, onTaskClick }: ColumnProps) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--sp-2)',
      minWidth: '220px',
      flex: '1 1 220px',
      background: 'var(--bg-surface)',
      border: '1px solid var(--border-subtle)',
      borderRadius: 'var(--r-lg)',
      padding: 'var(--sp-4)',
    }}>
      {/* Column header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--sp-2)',
        paddingBottom: 'var(--sp-2)',
        borderBottom: `1px solid var(--border-subtle)`,
        marginBottom: 'var(--sp-1)',
      }}>
        <span style={{
          fontSize: 10,
          fontWeight: 500,
          color,
          textTransform: 'uppercase',
          letterSpacing: '1.5px',
        }}>
          {label}
        </span>
        <span style={{
          fontSize: 10,
          padding: '1px 6px',
          borderRadius: 'var(--r-sm)',
          background: 'var(--bg-elevated)',
          color: 'var(--text-muted)',
          border: '1px solid var(--border-subtle)',
          marginLeft: 'auto',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {tasks.length}
        </span>
      </div>

      {/* Task cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)', minHeight: '80px' }}>
        {tasks.length === 0 ? (
          <div style={{
            padding: 'var(--sp-4) var(--sp-3)',
            borderRadius: 'var(--r-md)',
            border: '1px dashed var(--border-subtle)',
            color: 'var(--text-muted)',
            fontSize: 12,
            textAlign: 'center',
            fontWeight: 300,
          }}>
            Empty
          </div>
        ) : (
          tasks.map(task => (
            <TaskCard
              key={task.id.toString()}
              task={task}
              onClick={onTaskClick ? () => onTaskClick(task) : undefined}
            />
          ))
        )}
      </div>
    </div>
  )
}

export function TaskBoard({ data, onTaskClick }: TaskBoardProps) {
  const { tasks } = data

  const byStatus = (status: string) =>
    tasks.filter(t => t.status === status).slice(0, 50)

  const totalActive = tasks.filter(t => t.status === 'in_progress').length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>

      {/* Page header */}
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 200, color: 'var(--text-primary)', letterSpacing: '0.3px', margin: 0 }}>
          Task Board
        </h1>
        <div style={{ marginTop: 5, fontSize: 12, color: 'var(--text-muted)', fontWeight: 300 }}>
          {tasks.length} task{tasks.length !== 1 ? 's' : ''}
          {totalActive > 0 ? ` — ${totalActive} running` : ''}
          {tasks.length === 200 ? ' (limit 200 — use session filter for more)' : ''}
        </div>
      </div>

      {/* Kanban */}
      <div style={{
        display: 'flex',
        gap: 'var(--sp-4)',
        overflowX: 'auto',
        paddingBottom: 'var(--sp-2)',
        alignItems: 'flex-start',
      }}>
        {COLUMNS.map(col => (
          <KanbanColumn
            key={col.key}
            label={col.label}
            color={col.color}
            tasks={byStatus(col.key)}
            onTaskClick={onTaskClick}
          />
        ))}
      </div>
    </div>
  )
}
