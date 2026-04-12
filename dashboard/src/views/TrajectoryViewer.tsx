import { useState, useEffect } from 'react'
import {
  TrajFile, Trajectory, TrajStep,
  listTrajectories, loadTrajectory, parseSteps,
} from '@/lib/trajectories'

export function TrajectoryViewer() {
  const [files, setFiles] = useState<TrajFile[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [traj, setTraj] = useState<Trajectory | null>(null)
  const [steps, setSteps] = useState<TrajStep[]>([])
  const [expandedStep, setExpandedStep] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load file list on mount
  useEffect(() => {
    listTrajectories()
      .then(setFiles)
      .catch(e => setError(e.message))
  }, [])

  // Load trajectory when selected
  useEffect(() => {
    if (!selected) { setTraj(null); setSteps([]); return }
    setLoading(true)
    setError(null)
    loadTrajectory(selected)
      .then(t => {
        setTraj(t)
        setSteps(parseSteps(t))
        setExpandedStep(null)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [selected])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: 'calc(100vh - 120px)' }}>

      {/* Page Header */}
      <div>
        <div style={{ fontSize: '22px', fontWeight: 200, color: 'var(--text-primary)', letterSpacing: '-0.3px' }}>
          Trajectories
        </div>
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          {files.length} file{files.length !== 1 ? 's' : ''}
          {selected && traj ? ` — ${steps.length} steps` : ''}
        </div>
      </div>

      {/* Main Layout */}
      <div style={{ flex: 1, display: 'flex', gap: '16px', overflow: 'hidden' }}>

        {/* File List Sidebar */}
        <div style={{
          width: '260px', flexShrink: 0,
          background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-md)', overflow: 'auto',
        }}>
          <div style={{
            padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)',
            fontSize: '9px', fontWeight: 600, color: 'var(--text-tertiary)',
            textTransform: 'uppercase' as const, letterSpacing: '0.8px',
          }}>
            Trajectories ({files.length})
          </div>
          {files.length === 0 && !error && (
            <div style={{ padding: '20px 16px', color: 'var(--text-tertiary)', fontSize: '12px' }}>
              No trajectory files found.
            </div>
          )}
          {files.map(f => {
            const active = selected === f.name
            const label = f.name.replace('.traj.json', '').replace('relay_dispatch/', '')
            const date = new Date(f.mtime)
            return (
              <button
                key={f.name}
                onClick={() => setSelected(f.name)}
                style={{
                  width: '100%', display: 'block', textAlign: 'left',
                  padding: '10px 16px',
                  background: active ? 'var(--bg-elevated)' : 'transparent',
                  borderLeft: active ? '2px solid var(--rose-500)' : '2px solid transparent',
                  border: 'none', borderBottom: '1px solid var(--border-subtle)',
                  cursor: 'pointer', transition: 'background var(--t-fast)',
                }}
                onMouseEnter={e => { if (!active) (e.currentTarget as HTMLButtonElement).style.background = 'var(--bg-hover)' }}
                onMouseLeave={e => { if (!active) (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
              >
                <div style={{
                  fontSize: '12px', fontWeight: active ? 500 : 400,
                  color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                }}>
                  {label}
                </div>
                <div style={{ fontSize: '10px', color: 'var(--text-tertiary)', marginTop: '2px' }}>
                  {date.toLocaleDateString()} {date.toLocaleTimeString()} — {(f.size / 1024).toFixed(0)}KB
                </div>
              </button>
            )
          })}
        </div>

        {/* Main Content */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {error && (
            <div style={{
              padding: '12px 16px', borderRadius: 'var(--r-sm)',
              background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
              color: 'var(--red-500)', fontSize: '13px', marginBottom: '16px',
            }}>
              {error}
            </div>
          )}

          {!selected && !error && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              height: '100%', color: 'var(--text-tertiary)', fontSize: '14px',
            }}>
              Select a trajectory to view
            </div>
          )}

          {loading && (
            <div style={{ color: 'var(--text-tertiary)', fontSize: '13px', padding: '20px' }}>
              Loading trajectory...
            </div>
          )}

          {traj && !loading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

              {/* Run Metadata */}
              <div style={{
                background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--r-md)', padding: '14px 20px',
                display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap',
              }}>
                <MetaTag label="Model" value={traj.info.config?.model?.model_name ?? '?'} />
                {/* Step count badge */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ fontSize: '9px', color: 'var(--text-tertiary)', textTransform: 'uppercase' as const, letterSpacing: '0.8px', fontWeight: 600 }}>Steps</span>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 500,
                    color: 'var(--rose-400)',
                    background: 'var(--rose-glow)',
                    padding: '0px 6px', borderRadius: 'var(--r-sm)',
                  }}>
                    {steps.length}
                  </span>
                </div>
                <MetaTag label="API Calls" value={String(traj.info.model_stats?.api_calls ?? 0)} />
                <MetaTag
                  label="Status"
                  value={traj.info.exit_status}
                  color={traj.info.exit_status === 'Submitted' ? 'var(--emerald-400)' : 'var(--amber-500)'}
                />
                <MetaTag label="Mode" value={traj.info.config?.agent?.mode ?? '?'} />
                <MetaTag label="Version" value={traj.info.mini_version ?? '?'} />
              </div>

              {/* Task (from user message) */}
              {traj.messages.find(m => m.role === 'user') && (
                <div style={{
                  background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--r-md)', padding: '14px 20px',
                }}>
                  <div style={{
                    fontSize: '9px', fontWeight: 600, color: 'var(--text-tertiary)',
                    textTransform: 'uppercase' as const, letterSpacing: '0.8px', marginBottom: '8px',
                  }}>
                    Task
                  </div>
                  <div style={{
                    fontSize: '13px', color: 'var(--text-secondary)',
                    fontWeight: 300,
                    whiteSpace: 'pre-wrap', lineHeight: 1.5,
                    maxHeight: '120px', overflow: 'auto',
                  }}>
                    {extractTask(traj.messages.find(m => m.role === 'user')?.content ?? '')}
                  </div>
                </div>
              )}

              {/* Steps */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {steps.map(step => {
                  const expanded = expandedStep === step.index
                  return (
                    <div
                      key={step.index}
                      style={{
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--r-md)', overflow: 'hidden',
                        transition: 'border-color var(--t-fast)',
                        ...(expanded ? { borderColor: 'var(--border-default)' } : {}),
                      }}
                    >
                      {/* Step Header */}
                      <button
                        onClick={() => setExpandedStep(expanded ? null : step.index)}
                        style={{
                          width: '100%', display: 'flex', alignItems: 'center', gap: '10px',
                          padding: '10px 16px', background: 'none', border: 'none',
                          cursor: 'pointer', textAlign: 'left',
                        }}
                        onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--bg-hover)' }}
                        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'none' }}
                      >
                        <span style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '10px', fontWeight: 700,
                          color: 'var(--rose-400)', minWidth: '28px',
                        }}>
                          #{step.index + 1}
                        </span>
                        <span style={{
                          fontSize: '10px', fontWeight: 600,
                          padding: '2px 6px', borderRadius: 'var(--r-sm)',
                          background: 'var(--rose-glow)', color: 'var(--rose-300)',
                        }}>
                          {step.toolName || 'reasoning'}
                        </span>
                        <span style={{
                          fontSize: '12px', color: 'var(--text-secondary)',
                          flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                        }}>
                          {step.command || step.reasoning.slice(0, 80)}
                        </span>
                        {step.returncode !== null && (
                          <span style={{
                            fontFamily: 'var(--font-mono)',
                            fontSize: '10px', fontWeight: 600,
                            color: step.returncode === 0 ? 'var(--emerald-400)' : 'var(--red-500)',
                          }}>
                            rc={step.returncode}
                          </span>
                        )}
                        <span style={{
                          fontSize: '14px', color: 'var(--text-tertiary)',
                          transform: expanded ? 'rotate(180deg)' : 'none',
                          transition: 'transform var(--t-fast)',
                        }}>
                          ▾
                        </span>
                      </button>

                      {/* Step Detail */}
                      {expanded && (
                        <div style={{
                          padding: '0 16px 16px',
                          display: 'flex', flexDirection: 'column', gap: '10px',
                          borderTop: '1px solid var(--border-subtle)',
                        }}>
                          {/* Reasoning */}
                          {step.reasoning && (
                            <div style={{ marginTop: '10px' }}>
                              <SectionLabel>Reasoning</SectionLabel>
                              <div style={{
                                fontSize: '13px', color: 'var(--text-secondary)',
                                fontWeight: 300, lineHeight: 1.6,
                                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                                maxHeight: '150px', overflow: 'auto',
                                padding: '8px 0',
                              }}>
                                {step.reasoning}
                              </div>
                            </div>
                          )}

                          {/* Command */}
                          {step.command && (
                            <div>
                              <SectionLabel>Command</SectionLabel>
                              <CodeBlock
                                text={step.command}
                                style={{ color: 'var(--rose-300)', fontWeight: 500 }}
                              />
                            </div>
                          )}

                          {/* Result */}
                          {step.result && (
                            <div>
                              <SectionLabel>
                                Output
                                {step.returncode !== null && (
                                  <span style={{
                                    marginLeft: '8px', fontSize: '10px',
                                    fontFamily: 'var(--font-mono)',
                                    color: step.returncode === 0 ? 'var(--emerald-400)' : 'var(--red-500)',
                                  }}>
                                    exit {step.returncode}
                                  </span>
                                )}
                              </SectionLabel>
                              <CodeBlock text={step.result} maxHeight="300px" />
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function MetaTag({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
      <span style={{ fontSize: '9px', color: 'var(--text-tertiary)', textTransform: 'uppercase' as const, letterSpacing: '0.8px', fontWeight: 600 }}>
        {label}
      </span>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 500, color: color ?? 'var(--text-primary)' }}>
        {value}
      </span>
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontSize: '9px', fontWeight: 600, color: 'var(--text-tertiary)',
      textTransform: 'uppercase' as const, letterSpacing: '0.8px', marginBottom: '4px',
    }}>
      {children}
    </div>
  )
}

function CodeBlock({ text, maxHeight, style }: { text: string; maxHeight?: string; style?: React.CSSProperties }) {
  return (
    <pre style={{
      margin: 0, padding: '10px 12px', borderRadius: 'var(--r-sm)',
      background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)',
      fontFamily: 'var(--font-mono)',
      fontSize: '12px', lineHeight: 1.5, color: 'var(--text-secondary)',
      whiteSpace: 'pre-wrap', wordBreak: 'break-word',
      maxHeight: maxHeight ?? '400px', overflow: 'auto',
      ...style,
    }}>
      {text}
    </pre>
  )
}

function extractTask(content: string): string {
  // Extract just the TASK: line from the user message
  const match = content.match(/TASK:\s*(.*?)(?:\n\n|$)/s)
  if (match) return match[1].trim()
  return content.slice(0, 500)
}
