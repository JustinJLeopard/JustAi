/**
 * JustAi Demo — Trajectories View
 *
 * Full Trajectory Viewer for the interactive demo.
 * Three mode tabs: Post-Mortem (default), Learning, Audit.
 * Two-panel layout: file list (left) + content (right).
 *
 * Styled to match dashboard/src/views/TrajectoryViewer.tsx.
 */

import { useState, useMemo } from 'react'
import type { SimulationState, DemoTask } from '../data/types'
import { TRAJECTORY_COMMANDS } from '../data/sprint-timeline'

// ── Types ───────────────────────────────────────────────────────────────────────

type Mode = 'post-mortem' | 'learning' | 'audit'

export interface DemoTrajectoriesProps {
  state: SimulationState
}

// ── Mock data generators ────────────────────────────────────────────────────────

function taskToFileName(task: DemoTask): string {
  return task.name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/_+$/, '')
}

function mockFileSize(task: DemoTask): number {
  return task.steps * 2.4 + 8.1 // KB
}

function mockTimestamp(task: DemoTask, baseElapsed: number): Date {
  const idx = parseInt(task.id.replace('task-', ''), 10) || 1
  const d = new Date()
  d.setMinutes(d.getMinutes() - Math.max(0, 60 - baseElapsed) + idx * 2)
  return d
}

function mockAnalysis(task: DemoTask): string {
  const analyses: Record<string, string> = {
    'task-1': 'Schema design task completed efficiently by claude-opus-planner. The agent created 4 PostgreSQL tables with 12 indexes following a schema-first approach, reducing downstream integration failures. No escalation needed.',
    'task-2': 'Ingestion API implemented by mini-swe-agent-1 with both REST and WebSocket endpoints. Batch support and rate limiting at 10k events/min were implemented correctly. Validated against 50k test events with zero data loss.',
    'task-3': 'Segmentation engine completed with both rule-based filters and k-means clustering. Six pre-built segments defined. Builder API response time under 200ms meets the performance requirement.',
    'task-4': 'This task required escalation from gpt-5.4 to claude-opus-4-6 after the initial agent exceeded its context window on Recharts v3 heatmap configuration. The escalated agent identified a CSS Grid approach instead of ResponsiveContainer, successfully completing all 5 chart types.',
    'task-5': 'Export functionality leveraged trajectory learning from prior sprint runs. The agent was enriched with CSV streaming and Puppeteer PDF snapshot patterns, completing the task in fewer steps and lower cost than baseline.',
    'task-6': 'Authentication layer implemented with JWT refresh token rotation and 4-role RBAC. Middleware applied to all API routes with per-role rate limiting. Standard implementation with no issues.',
    'task-7': 'WebSocket server implemented with auto-reconnect, heartbeat, and room-based subscriptions. Redis pub/sub backend handles 500 concurrent connections. Clean implementation.',
    'task-8': 'CI pipeline with 47 tests (12 e2e, 35 unit) created using GitHub Actions with PostgreSQL service container. Coverage at 89% exceeds the 80% target.',
  }
  return analyses[task.id] || `Task "${task.name}" completed successfully in ${task.steps} steps.`
}

const GENERIC_COMMANDS = [
  { step: 1, tool: 'bash', command: 'ls -la src/', result: 'rc=0' },
  { step: 2, tool: 'bash', command: 'cat requirements.txt', result: 'rc=0' },
  { step: 3, tool: 'write', command: 'write src/module.ts', result: 'rc=0' },
  { step: 4, tool: 'bash', command: 'npm test -- --testPathPattern module', result: 'rc=0' },
]

// ── Shared sub-components (matching TrajectoryViewer.tsx patterns) ───────────

function ModeTab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '8px 18px',
        borderRadius: 4,
        fontSize: 12,
        fontWeight: active ? 500 : 400,
        color: active ? 'var(--text-primary)' : 'var(--text-muted)',
        cursor: 'pointer',
        transition: 'all var(--t-fast)',
        background: active ? 'var(--bg-elevated)' : 'transparent',
        border: 'none',
        boxShadow: active ? 'var(--shadow-sm)' : 'none',
        fontFamily: 'var(--font-sans)',
        letterSpacing: '0.2px',
      }}
    >
      {label}
    </button>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontSize: 9, fontWeight: 600, color: 'var(--text-tertiary)',
      textTransform: 'uppercase' as const, letterSpacing: '0.8px', marginBottom: 4,
    }}>
      {children}
    </div>
  )
}

function MetaTag({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{
        fontSize: 9, color: 'var(--text-tertiary)',
        textTransform: 'uppercase' as const, letterSpacing: '0.8px', fontWeight: 600,
      }}>
        {label}
      </span>
      <span style={{
        fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500,
        color: color ?? 'var(--text-primary)',
      }}>
        {value}
      </span>
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═════════════════════════════════════════════════════════════════════════════════

export function DemoTrajectories({ state }: DemoTrajectoriesProps) {
  const [mode, setMode] = useState<Mode>('post-mortem')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // Only show tasks that have reached 'done' status
  const doneTasks = useMemo(
    () => state.tasks.filter(t => t.status === 'done'),
    [state.tasks],
  )

  const totalSteps = useMemo(
    () => doneTasks.reduce((sum, t) => sum + t.steps, 0),
    [doneTasks],
  )

  const selectedTask = useMemo(
    () => doneTasks.find(t => t.id === selectedId) ?? null,
    [doneTasks, selectedId],
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: 'calc(100vh - 120px)' }}>

      {/* ── Header + Mode Tabs ──────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 200, color: 'var(--text-primary)', letterSpacing: '-0.3px' }}>
            Trajectories
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            {doneTasks.length} file{doneTasks.length !== 1 ? 's' : ''}
            {' \u2014 '}
            {totalSteps} steps
          </div>
        </div>

        <div style={{
          display: 'flex', gap: 2,
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 6, padding: 3,
        }}>
          <ModeTab label="Post-Mortem" active={mode === 'post-mortem'} onClick={() => setMode('post-mortem')} />
          <ModeTab label="Learning" active={mode === 'learning'} onClick={() => setMode('learning')} />
          <ModeTab label="Audit" active={mode === 'audit'} onClick={() => setMode('audit')} />
        </div>
      </div>

      {/* ── Main Layout ─────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', gap: 16, overflow: 'hidden' }}>

        {/* ── Left Panel — File List ────────────────────────────────────── */}
        <div style={{
          width: 350, flexShrink: 0,
          background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-md)', overflow: 'auto',
        }}>
          <div style={{
            padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)',
            fontSize: 9, fontWeight: 600, color: 'var(--text-tertiary)',
            textTransform: 'uppercase' as const, letterSpacing: '0.8px',
          }}>
            Trajectories ({doneTasks.length})
          </div>

          {doneTasks.length === 0 && (
            <div style={{ padding: '20px 16px', color: 'var(--text-tertiary)', fontSize: 12 }}>
              No completed tasks yet. Tasks appear here as they finish.
            </div>
          )}

          {doneTasks.map(task => {
            const active = selectedId === task.id
            const fileName = taskToFileName(task)
            const ts = mockTimestamp(task, state.elapsed)
            const size = mockFileSize(task)

            return (
              <button
                key={task.id}
                onClick={() => setSelectedId(task.id)}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                  textAlign: 'left',
                  padding: '10px 16px',
                  background: active ? 'var(--bg-elevated)' : 'transparent',
                  borderLeft: active ? '2px solid var(--rose-500)' : '2px solid transparent',
                  border: 'none', borderBottom: '1px solid var(--border-subtle)',
                  cursor: 'pointer', transition: 'background var(--t-fast)',
                }}
                onMouseEnter={e => { if (!active) (e.currentTarget).style.background = 'var(--bg-hover)' }}
                onMouseLeave={e => { if (!active) (e.currentTarget).style.background = 'transparent' }}
              >
                {/* Green checkmark */}
                <span style={{
                  fontSize: 14, color: 'var(--emerald-400)', flexShrink: 0,
                }}>
                  &#10003;
                </span>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 12, fontWeight: active ? 500 : 400,
                    color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                    fontFamily: 'var(--font-mono)',
                  }}>
                    {fileName}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>
                    {ts.toLocaleDateString()} {ts.toLocaleTimeString()}
                    {' \u2014 '}
                    {size.toFixed(0)}KB
                  </div>
                </div>
              </button>
            )
          })}
        </div>

        {/* ── Right Panel — Content Area ────────────────────────────────── */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {mode === 'post-mortem' && (
            <PostMortemPanel task={selectedTask} elapsed={state.elapsed} />
          )}
          {mode === 'learning' && (
            <LearningPanel task={selectedTask} />
          )}
          {mode === 'audit' && (
            <AuditPanel task={selectedTask} />
          )}
        </div>
      </div>
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════════
// MODE 1: POST-MORTEM
// ═════════════════════════════════════════════════════════════════════════════════

function PostMortemPanel({ task, elapsed }: { task: DemoTask | null; elapsed: number }) {
  if (!task) {
    return <EmptyState message="Select a trajectory to analyze" />
  }

  // Get commands for this task from TRAJECTORY_COMMANDS, or fall back to generics
  const taskCommands = TRAJECTORY_COMMANDS.filter(c => c.taskId === task.id)
  const hasRealCommands = taskCommands.length > 0

  const statusColor = task.status === 'done'
    ? 'var(--emerald-400)'
    : task.status === 'failed'
      ? 'var(--red-500)'
      : 'var(--amber-500)'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* AI Analysis Panel */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--r-md)', padding: '14px 20px',
      }}>
        <SectionLabel>AI Analysis</SectionLabel>
        <div style={{ fontSize: 13, fontWeight: 300, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          {mockAnalysis(task)}
        </div>
      </div>

      {/* Metadata Row */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--r-md)', padding: '14px 20px',
        display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap',
      }}>
        <MetaTag label="Model" value={task.model || 'gpt-5.4'} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{
            fontSize: 9, color: 'var(--text-tertiary)',
            textTransform: 'uppercase' as const, letterSpacing: '0.8px', fontWeight: 600,
          }}>Steps</span>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500,
            color: 'var(--rose-400)', background: 'var(--rose-glow)',
            padding: '0px 6px', borderRadius: 'var(--r-sm)',
          }}>
            {task.steps}
          </span>
        </div>
        <MetaTag label="API Calls" value={String(task.steps)} />
        <MetaTag label="Status" value={task.status} color={statusColor} />
        <MetaTag label="Cost" value={`$${task.cost.toFixed(4)}`} color="var(--gold-300)" />
        <MetaTag label="Version" value="2.2.8" />
      </div>

      {/* Task Description */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--r-md)', padding: '14px 20px',
      }}>
        <SectionLabel>Task</SectionLabel>
        <div style={{
          fontSize: 13, color: 'var(--text-secondary)', fontWeight: 300,
          whiteSpace: 'pre-wrap', lineHeight: 1.5, maxHeight: 120, overflow: 'auto',
        }}>
          {task.payload}
        </div>
      </div>

      {/* Command Replay */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <SectionLabel>Command Replay</SectionLabel>
        {(hasRealCommands ? taskCommands : GENERIC_COMMANDS).map((cmd, i) => {
          const stepNum = hasRealCommands ? (cmd as typeof taskCommands[number]).step : (cmd as typeof GENERIC_COMMANDS[number]).step
          const command = hasRealCommands ? (cmd as typeof taskCommands[number]).command : (cmd as typeof GENERIC_COMMANDS[number]).command
          const result = hasRealCommands ? (cmd as typeof taskCommands[number]).output : (cmd as typeof GENERIC_COMMANDS[number]).result
          const tool = hasRealCommands ? 'bash' : (cmd as typeof GENERIC_COMMANDS[number]).tool

          return (
            <div
              key={i}
              style={{
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--r-md)',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 16px', background: 'none',
                }}
              >
                {/* Step number */}
                <span style={{
                  fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                  color: 'var(--rose-400)', minWidth: 28,
                }}>
                  #{stepNum}
                </span>

                {/* Tool badge */}
                <span style={{
                  fontSize: 10, fontWeight: 600,
                  padding: '2px 6px', borderRadius: 'var(--r-sm)',
                  background: 'var(--rose-glow)',
                  color: 'var(--rose-300)',
                }}>
                  {tool}
                </span>

                {/* Command text */}
                <span style={{
                  fontSize: 12, color: 'var(--text-secondary)',
                  flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                  fontFamily: 'var(--font-mono)',
                }}>
                  {command}
                </span>

                {/* Result indicator */}
                <span style={{
                  fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 600,
                  color: 'var(--emerald-400)',
                }}>
                  rc=0
                </span>
              </div>

              {/* Output (if present) */}
              {result && result !== 'rc=0' && (
                <div style={{
                  padding: '8px 16px 10px',
                  borderTop: '1px solid var(--border-subtle)',
                }}>
                  <pre style={{
                    margin: 0, padding: '8px 10px', borderRadius: 'var(--r-sm)',
                    background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11, lineHeight: 1.5, color: 'var(--text-secondary)',
                    whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                    maxHeight: '120px', overflow: 'auto',
                  }}>
                    {result}
                  </pre>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════════
// MODE 2: LEARNING
// ═════════════════════════════════════════════════════════════════════════════════

function LearningPanel({ task }: { task: DemoTask | null }) {
  if (!task) {
    return <EmptyState message="Select a trajectory to view learning data" />
  }

  if (task.trajectoryLearning) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Matched Pattern Box */}
        <div style={{
          background: 'var(--bg-surface)',
          border: '1px solid rgba(168, 85, 247, 0.25)',
          borderLeft: '3px solid rgba(168, 85, 247, 0.7)',
          borderRadius: 'var(--r-md)', padding: '18px 22px',
        }}>
          <SectionLabel>Matched Pattern</SectionLabel>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 8 }}>
            {/* Pattern Name */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{
                fontSize: 14, fontWeight: 400, color: 'var(--text-primary)',
              }}>
                Export Service — CSV Streaming + PDF Snapshot
              </span>
              <span style={{
                fontSize: 10, fontWeight: 600, padding: '2px 8px',
                borderRadius: 'var(--r-sm)',
                background: 'rgba(168, 85, 247, 0.12)',
                color: 'rgba(168, 85, 247, 0.9)',
              }}>
                92% confidence
              </span>
            </div>

            {/* Details grid */}
            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 1fr',
              gap: 10, marginTop: 4,
            }}>
              <div>
                <div style={{
                  fontSize: 9, fontWeight: 600, color: 'var(--text-dim)',
                  textTransform: 'uppercase' as const, letterSpacing: '0.8px', marginBottom: 4,
                }}>
                  Source
                </div>
                <div style={{
                  fontSize: 12, fontWeight: 300, color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-mono)',
                }}>
                  Sprint 7
                </div>
              </div>
              <div>
                <div style={{
                  fontSize: 9, fontWeight: 600, color: 'var(--text-dim)',
                  textTransform: 'uppercase' as const, letterSpacing: '0.8px', marginBottom: 4,
                }}>
                  Pattern Name
                </div>
                <div style={{
                  fontSize: 12, fontWeight: 300, color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-mono)',
                }}>
                  export-service-streaming
                </div>
              </div>
            </div>

            {/* Description */}
            <div style={{ marginTop: 4 }}>
              <div style={{
                fontSize: 9, fontWeight: 600, color: 'var(--text-dim)',
                textTransform: 'uppercase' as const, letterSpacing: '0.8px', marginBottom: 4,
              }}>
                Description
              </div>
              <div style={{
                fontSize: 12, fontWeight: 300, color: 'var(--text-secondary)', lineHeight: 1.6,
              }}>
                Prior trajectory from Sprint 7 demonstrated that CSV exports exceeding 50k rows
                benefit from ReadableStream-based streaming instead of buffered responses.
                PDF generation via Puppeteer dashboard snapshots was 3x faster than DOM-to-PDF
                conversion. These patterns were applied to enrich the task context before execution,
                reducing steps from an estimated 22 to 16 and cost from $0.31 to $0.19.
              </div>
            </div>
          </div>
        </div>

        {/* Enrichment summary */}
        <div style={{
          background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-md)', padding: '14px 20px',
        }}>
          <SectionLabel>Context Enrichment Applied</SectionLabel>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginTop: 8 }}>
            <MetaTag label="Trajectories Matched" value="3" />
            <MetaTag label="Steps Saved" value="6" color="var(--emerald-400)" />
            <MetaTag label="Cost Saved" value="$0.12" color="var(--gold-300)" />
            <MetaTag label="Pattern Confidence" value="92%" color="rgba(168, 85, 247, 0.9)" />
          </div>
        </div>
      </div>
    )
  }

  // Non-learning task
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      height: '100%', gap: 8,
    }}>
      <div style={{ color: 'var(--text-tertiary)', fontSize: 14 }}>
        No learning patterns applied to this task
      </div>
      <div style={{ color: 'var(--text-dim)', fontSize: 12, fontWeight: 300 }}>
        Tasks with trajectory learning enabled show matched patterns and context enrichment data here.
      </div>
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════════
// MODE 3: AUDIT
// ═════════════════════════════════════════════════════════════════════════════════

function AuditPanel({ task }: { task: DemoTask | null }) {
  if (!task) {
    return <EmptyState message="Select a trajectory to audit" />
  }

  const tokenCount = task.steps * 1200
  const executionTime = (task.steps * 0.8 + 2.5).toFixed(1)

  const auditRows: { label: string; value: string; color: string }[] = [
    { label: 'Model Used', value: task.model || 'gpt-5.4', color: 'var(--text-primary)' },
    { label: 'Token Count', value: tokenCount.toLocaleString(), color: 'var(--text-primary)' },
    { label: 'Total Cost', value: `$${task.cost.toFixed(4)}`, color: 'var(--gold-300)' },
    { label: 'Execution Time', value: `${executionTime}s`, color: 'var(--text-primary)' },
    { label: 'Safety Check', value: 'Passed', color: 'var(--emerald-400)' },
    { label: 'Scope Compliance', value: 'Within bounds', color: 'var(--emerald-400)' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* Audit header metadata */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--r-md)', padding: '14px 20px',
        display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap',
      }}>
        <MetaTag label="Model" value={task.model || 'gpt-5.4'} />
        <MetaTag label="Steps" value={String(task.steps)} />
        <MetaTag label="API Calls" value={String(task.steps)} />
        <MetaTag label="Cost" value={`$${task.cost.toFixed(4)}`} color="var(--gold-300)" />
        <MetaTag
          label="Status"
          value={task.status}
          color={task.status === 'done' ? 'var(--emerald-400)' : 'var(--amber-500)'}
        />
        <MetaTag label="Version" value="2.2.8" />
      </div>

      {/* Audit Table */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--r-md)', padding: '14px 20px',
      }}>
        <SectionLabel>Audit Details</SectionLabel>

        {/* Header row */}
        <div style={{
          display: 'grid', gridTemplateColumns: '200px 1fr',
          padding: '8px 0', borderBottom: '1px solid var(--border-subtle)',
          fontSize: 9, fontWeight: 600, color: 'var(--text-dim)',
          textTransform: 'uppercase' as const, letterSpacing: '0.8px',
        }}>
          <span>Property</span>
          <span>Value</span>
        </div>

        {/* Data rows */}
        {auditRows.map((row, i) => (
          <div key={i} style={{
            display: 'grid', gridTemplateColumns: '200px 1fr',
            padding: '10px 0',
            borderBottom: i < auditRows.length - 1 ? '1px solid rgba(255,255,255,0.02)' : 'none',
            fontSize: 12, fontWeight: 300,
          }}>
            <span style={{ color: 'var(--text-muted)' }}>{row.label}</span>
            <span style={{
              fontFamily: 'var(--font-mono)', color: row.color, fontWeight: 500,
            }}>
              {row.value}
              {/* Add badge for safety/compliance rows */}
              {(row.label === 'Safety Check' || row.label === 'Scope Compliance') && (
                <span style={{
                  marginLeft: 8,
                  fontSize: 9, fontWeight: 600,
                  padding: '1px 6px', borderRadius: 'var(--r-sm)',
                  background: 'rgba(16, 185, 129, 0.1)',
                  color: 'var(--emerald-400)',
                }}>
                  OK
                </span>
              )}
            </span>
          </div>
        ))}
      </div>

      {/* Escalation note if applicable */}
      {task.escalated && (
        <div style={{
          background: 'rgba(244, 63, 94, 0.04)',
          border: '1px solid rgba(244, 63, 94, 0.12)',
          borderRadius: 'var(--r-md)', padding: '14px 20px',
        }}>
          <SectionLabel>Escalation Record</SectionLabel>
          <div style={{
            fontSize: 12, fontWeight: 300, color: 'var(--text-secondary)', lineHeight: 1.6, marginTop: 4,
          }}>
            This task was escalated from {task.escalatedFrom || 'gpt-5.4'} to {task.model} after
            the initial agent failed. The escalation is recorded in the trajectory for future
            learning pattern matching.
          </div>
        </div>
      )}
    </div>
  )
}

// ── Shared Utility ──────────────────────────────────────────────────────────────

function EmptyState({ message }: { message: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100%', color: 'var(--text-tertiary)', fontSize: 14,
    }}>
      {message}
    </div>
  )
}
