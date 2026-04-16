/**
 * JustAi Demo — Task Board View
 *
 * Full Kanban-style task board with 5 status columns, task cards with
 * progress bars, escalation/learning badges, and a slide-in detail panel.
 *
 * Mirrors the styling of dashboard/src/views/TaskBoard.tsx and
 * dashboard/src/App.tsx (detail panel).
 */

import { useState } from 'react'
import type { SimulationState, DemoTask, DemoTaskStatus } from '../data/types'

// ── Column config ───────────────────────────────────────────────────────────

interface ColumnDef {
  key: DemoTaskStatus
  label: string
  color: string
}

const COLUMNS: ColumnDef[] = [
  { key: 'pending',     label: 'Pending',  color: 'var(--text-muted)' },
  { key: 'claimed',     label: 'Claimed',  color: 'var(--text-secondary)' },
  { key: 'in_progress', label: 'Running',  color: 'var(--rose-400)' },
  { key: 'done',        label: 'Done',     color: 'var(--emerald-400)' },
  { key: 'failed',      label: 'Failed',   color: 'var(--red-500)' },
]

// ── Status dot colors for cards ─────────────────────────────────────────────

const STATUS_DOT: Record<DemoTaskStatus, { dotColor: string; label: string }> = {
  pending:     { dotColor: 'var(--text-muted)',     label: 'Pending' },
  claimed:     { dotColor: 'var(--text-secondary)', label: 'Claimed' },
  in_progress: { dotColor: 'var(--rose-400)',       label: 'Running' },
  done:        { dotColor: 'var(--emerald-400)',    label: 'Done' },
  failed:      { dotColor: 'var(--red-500)',        label: 'Failed' },
}

// ── Task Card ───────────────────────────────────────────────────────────────

interface DemoTaskCardProps {
  task: DemoTask
  onClick: () => void
}

function DemoTaskCard({ task, onClick }: DemoTaskCardProps) {
  const cfg = STATUS_DOT[task.status]
  const progress = task.steps > 0 ? (task.stepsDone / task.steps) * 100 : 0

  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--bg-elevated)',
        border: task.escalated
          ? '1px solid var(--gold-400, #f59e0b)'
          : '1px solid var(--border-subtle)',
        borderRadius: 'var(--r-md)',
        padding: 'var(--sp-3)',
        cursor: 'pointer',
        transition: 'border-color 150ms ease, transform 150ms ease, box-shadow 150ms ease',
        display: 'flex',
        flexDirection: 'column' as const,
        gap: 'var(--sp-2)',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = 'var(--border-hover)'
        e.currentTarget.style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = task.escalated
          ? 'var(--gold-400, #f59e0b)'
          : 'var(--border-subtle)'
        e.currentTarget.style.transform = 'translateY(0)'
      }}
    >
      {/* Status dot + badges */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
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
            textTransform: 'uppercase' as const,
            letterSpacing: '1px',
          }}>
            {cfg.label}
          </span>
        </div>

        {/* Badges */}
        <div style={{ display: 'flex', gap: 4, marginLeft: 'auto', alignItems: 'center' }}>
          {task.escalated && (
            <span style={{
              fontSize: 9,
              fontWeight: 500,
              padding: '1px 5px',
              borderRadius: 'var(--r-sm)',
              background: 'rgba(245, 158, 11, 0.15)',
              color: 'var(--gold-400, #f59e0b)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              textTransform: 'uppercase' as const,
              letterSpacing: '0.5px',
            }}>
              Escalated
            </span>
          )}
          {task.trajectoryLearning && (
            <span style={{
              fontSize: 9,
              fontWeight: 500,
              padding: '1px 5px',
              borderRadius: 'var(--r-sm)',
              background: 'rgba(168, 85, 247, 0.15)',
              color: '#a855f7',
              border: '1px solid rgba(168, 85, 247, 0.3)',
              textTransform: 'uppercase' as const,
              letterSpacing: '0.5px',
            }}>
              Learning
            </span>
          )}
        </div>
      </div>

      {/* Task name */}
      <div style={{
        fontSize: 13,
        fontWeight: 300,
        color: 'var(--text-secondary)',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical' as const,
        lineHeight: '1.4',
      }}>
        {task.name}
      </div>

      {/* Meta row: agent + model */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--sp-2)',
        fontSize: 11,
        color: 'var(--text-muted)',
        fontFamily: 'var(--font-mono)',
        flexWrap: 'wrap' as const,
      }}>
        {task.agent && <span>{task.agent}</span>}
        {task.model && (
          <span style={{ opacity: 0.7 }}>{task.model}</span>
        )}
        {task.cost > 0 && (
          <span style={{ marginLeft: 'auto', color: 'var(--emerald-400)' }}>
            ${task.cost.toFixed(3)}
          </span>
        )}
      </div>

      {/* Step progress bar */}
      {task.steps > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 3 }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 10,
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
          }}>
            <span>Steps</span>
            <span>{task.stepsDone}/{task.steps}</span>
          </div>
          <div style={{
            height: 3,
            borderRadius: 2,
            background: 'var(--bg-card, rgba(255,255,255,0.04))',
            overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${Math.min(progress, 100)}%`,
              borderRadius: 2,
              background: task.status === 'failed'
                ? 'var(--red-500)'
                : task.status === 'done'
                  ? 'var(--emerald-400)'
                  : 'var(--rose-400)',
              transition: 'width 300ms ease',
            }} />
          </div>
        </div>
      )}

      {/* Result preview (done/failed only) */}
      {(task.status === 'done' || task.status === 'failed') && task.result && (
        <div style={{
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
          color: task.status === 'done' ? 'var(--emerald-400)' : 'var(--red-500)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap' as const,
          paddingTop: 'var(--sp-2)',
          borderTop: '1px solid var(--border-subtle)',
        }}>
          {task.result.slice(0, 100)}
        </div>
      )}
    </div>
  )
}

// ── Kanban Column ───────────────────────────────────────────────────────────

interface KanbanColumnProps {
  label: string
  color: string
  tasks: DemoTask[]
  onTaskClick: (task: DemoTask) => void
}

function KanbanColumn({ label, color, tasks, onTaskClick }: KanbanColumnProps) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column' as const,
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
        borderBottom: '1px solid var(--border-subtle)',
        marginBottom: 'var(--sp-1)',
      }}>
        <span style={{
          fontSize: 10,
          fontWeight: 500,
          color,
          textTransform: 'uppercase' as const,
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
      <div style={{
        display: 'flex',
        flexDirection: 'column' as const,
        gap: 'var(--sp-2)',
        minHeight: '80px',
      }}>
        {tasks.length === 0 ? (
          <div style={{
            padding: 'var(--sp-4) var(--sp-3)',
            borderRadius: 'var(--r-md)',
            border: '1px dashed var(--border-subtle)',
            color: 'var(--text-muted)',
            fontSize: 12,
            textAlign: 'center' as const,
            fontWeight: 300,
          }}>
            Empty
          </div>
        ) : (
          tasks.map(task => (
            <DemoTaskCard
              key={task.id}
              task={task}
              onClick={() => onTaskClick(task)}
            />
          ))
        )}
      </div>
    </div>
  )
}

// ── Detail Panel ────────────────────────────────────────────────────────────

interface DetailPanelProps {
  task: DemoTask
  onClose: () => void
}

function DetailPanel({ task, onClose }: DetailPanelProps) {
  const statusColor = STATUS_DOT[task.status].dotColor

  return (
    <aside
      style={{
        position: 'fixed' as const,
        top: 0,
        right: 0,
        bottom: 0,
        width: 360,
        flexShrink: 0,
        background: 'var(--bg-surface)',
        borderLeft: '1px solid var(--border-subtle)',
        overflow: 'auto',
        padding: 'var(--sp-6)',
        zIndex: 100,
        animation: 'slideInRight 200ms ease-out',
        boxShadow: '-4px 0 24px rgba(0,0,0,0.3)',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 'var(--sp-5)' }}>
        <h2 style={{
          margin: 0,
          fontSize: 15,
          fontWeight: 300,
          color: 'var(--text-primary)',
          letterSpacing: 0.3,
        }}>
          Task Detail
        </h2>
        <button
          onClick={onClose}
          style={{
            marginLeft: 'auto',
            background: 'none',
            border: 'none',
            color: 'var(--text-dim)',
            cursor: 'pointer',
            fontSize: 16,
            padding: '2px 6px',
            lineHeight: 1,
          }}
        >
          {'\u2715'}
        </button>
      </div>

      {/* Fields */}
      <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 'var(--sp-4)' }}>
        {[
          { label: 'ID', value: `#${task.id}` },
          { label: 'Status', value: task.status.replace('_', ' '), color: statusColor },
          { label: 'Agent', value: task.agent || '\u2014' },
          { label: 'Model', value: task.model || '\u2014' },
          { label: 'Steps', value: `${task.stepsDone} / ${task.steps}` },
          { label: 'Cost', value: task.cost > 0 ? `$${task.cost.toFixed(4)}` : '\u2014' },
        ].map(({ label, value, color }) => (
          <div key={label}>
            <div style={{
              fontSize: 10,
              color: 'var(--text-dim)',
              textTransform: 'uppercase' as const,
              letterSpacing: 1.5,
              marginBottom: 4,
              fontWeight: 500,
            }}>
              {label}
            </div>
            <div style={{
              fontSize: 13,
              color: color || 'var(--text-primary)',
              fontWeight: 300,
            }}>
              {value}
            </div>
          </div>
        ))}

        {/* Badges row */}
        {(task.escalated || task.trajectoryLearning) && (
          <div>
            <div style={{
              fontSize: 10,
              color: 'var(--text-dim)',
              textTransform: 'uppercase' as const,
              letterSpacing: 1.5,
              marginBottom: 6,
              fontWeight: 500,
            }}>
              Flags
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {task.escalated && (
                <span style={{
                  fontSize: 10,
                  fontWeight: 500,
                  padding: '2px 8px',
                  borderRadius: 'var(--r-sm)',
                  background: 'rgba(245, 158, 11, 0.15)',
                  color: 'var(--gold-400, #f59e0b)',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                }}>
                  Escalated{task.escalatedFrom ? ` from ${task.escalatedFrom}` : ''}
                </span>
              )}
              {task.trajectoryLearning && (
                <span style={{
                  fontSize: 10,
                  fontWeight: 500,
                  padding: '2px 8px',
                  borderRadius: 'var(--r-sm)',
                  background: 'rgba(168, 85, 247, 0.15)',
                  color: '#a855f7',
                  border: '1px solid rgba(168, 85, 247, 0.3)',
                }}>
                  Trajectory Learning
                </span>
              )}
            </div>
          </div>
        )}

        {/* Payload */}
        <div>
          <div style={{
            fontSize: 10,
            color: 'var(--text-dim)',
            textTransform: 'uppercase' as const,
            letterSpacing: 1.5,
            marginBottom: 6,
            fontWeight: 500,
          }}>
            Payload
          </div>
          <div style={{
            fontSize: 12,
            color: 'var(--text-secondary)',
            background: 'var(--bg-card)',
            borderRadius: 6,
            padding: 10,
            border: '1px solid var(--border-subtle)',
            whiteSpace: 'pre-wrap' as const,
            wordBreak: 'break-word' as const,
            maxHeight: 200,
            overflowY: 'auto' as const,
            fontWeight: 300,
          }}>
            {task.payload || '\u2014'}
          </div>
        </div>

        {/* Result (if done or failed) */}
        {task.result && (
          <div>
            <div style={{
              fontSize: 10,
              color: 'var(--text-dim)',
              textTransform: 'uppercase' as const,
              letterSpacing: 1.5,
              marginBottom: 6,
              fontWeight: 500,
            }}>
              Result
            </div>
            <div style={{
              fontSize: 12,
              color: task.status === 'done' ? 'var(--emerald-500)' : 'var(--rose-500)',
              background: 'var(--bg-card)',
              borderRadius: 6,
              padding: 10,
              border: '1px solid var(--border-subtle)',
              whiteSpace: 'pre-wrap' as const,
              wordBreak: 'break-word' as const,
              maxHeight: 200,
              overflowY: 'auto' as const,
              fontWeight: 300,
            }}>
              {task.result}
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}

// ── Main Export ──────────────────────────────────────────────────────────────

export interface DemoTaskBoardProps {
  state: SimulationState
}

export function DemoTaskBoard({ state }: DemoTaskBoardProps) {
  const [selectedTask, setSelectedTask] = useState<DemoTask | null>(null)

  const byStatus = (status: DemoTaskStatus) =>
    state.tasks.filter(t => t.status === status)

  const totalRunning = state.tasks.filter(t => t.status === 'in_progress').length

  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 'var(--sp-6)' }}>

        {/* Page header */}
        <div>
          <h1 style={{
            fontSize: 22,
            fontWeight: 200,
            color: 'var(--text-primary)',
            letterSpacing: '0.3px',
            margin: 0,
          }}>
            Task Board
          </h1>
          <div style={{
            marginTop: 5,
            fontSize: 12,
            color: 'var(--text-muted)',
            fontWeight: 300,
          }}>
            {state.tasks.length} task{state.tasks.length !== 1 ? 's' : ''}
            {' \u00B7 '}
            {totalRunning} running
          </div>
        </div>

        {/* Kanban board */}
        <div style={{
          display: 'flex',
          gap: 'var(--sp-4)',
          overflowX: 'auto' as const,
          paddingBottom: 'var(--sp-2)',
          alignItems: 'flex-start',
        }}>
          {COLUMNS.map(col => (
            <KanbanColumn
              key={col.key}
              label={col.label}
              color={col.color}
              tasks={byStatus(col.key)}
              onTaskClick={setSelectedTask}
            />
          ))}
        </div>
      </div>

      {/* Task detail slide-in panel */}
      {selectedTask && (
        <>
          {/* Backdrop */}
          <div
            onClick={() => setSelectedTask(null)}
            style={{
              position: 'fixed' as const,
              inset: 0,
              background: 'rgba(0,0,0,0.3)',
              zIndex: 99,
            }}
          />
          <DetailPanel
            task={selectedTask}
            onClose={() => setSelectedTask(null)}
          />
        </>
      )}

      {/* Slide-in animation */}
      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);    opacity: 1; }
        }
      `}</style>
    </>
  )
}
