import { Task, LiveData } from '@/lib/spacetime'
import { TaskCard } from '@/components/TaskCard'

interface TaskBoardProps {
  data: LiveData
  onTaskClick?: (task: Task) => void
}

const COLUMNS: { key: Task['status'] | 'in_progress'; label: string; color: string }[] = [
  { key: 'pending',     label: 'Pending',  color: 'var(--text-muted)' },
  { key: 'claimed',     label: 'Claimed',  color: 'var(--accent-blue)' },
  { key: 'in_progress', label: 'Running',  color: 'var(--accent-purple)' },
  { key: 'done',        label: 'Done',     color: 'var(--accent-green)' },
  { key: 'failed',      label: 'Failed',   color: 'var(--accent-red)' },
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
      gap: '8px',
      minWidth: '220px',
      flex: '1 1 220px',
    }}>
      {/* Column header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 4px',
        borderBottom: `2px solid ${color}`,
        marginBottom: '4px',
      }}>
        <span style={{ fontSize: '12px', fontWeight: 600, color, textTransform: 'uppercase', letterSpacing: '0.8px' }}>
          {label}
        </span>
        <span style={{
          fontSize: '11px',
          padding: '1px 6px',
          borderRadius: '10px',
          background: 'var(--bg-secondary)',
          color: 'var(--text-muted)',
          border: '1px solid var(--border)',
        }}>
          {tasks.length}
        </span>
      </div>

      {/* Task cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minHeight: '80px' }}>
        {tasks.length === 0 ? (
          <div style={{
            padding: '16px 12px',
            borderRadius: '8px',
            border: '1px dashed var(--border)',
            color: 'var(--text-muted)',
            fontSize: '12px',
            textAlign: 'center',
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Session filter hint */}
      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
        Showing {tasks.length} task{tasks.length !== 1 ? 's' : ''}
        {tasks.length === 200 ? ' (limit 200 — use session filter for more)' : ''}
      </div>

      {/* Kanban */}
      <div style={{
        display: 'flex',
        gap: '16px',
        overflowX: 'auto',
        paddingBottom: '8px',
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
