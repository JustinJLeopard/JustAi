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
    <div style={{ display: 'flex', gap: '16px', height: 'calc(100vh - 120px)' }}>

      {/* File List */}
      <div style={{
        width: '260px', flexShrink: 0,
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: '10px', overflow: 'auto',
      }}>
        <div style={{
          padding: '12px 16px', borderBottom: '1px solid var(--border)',
          fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)',
          textTransform: 'uppercase', letterSpacing: '1px',
        }}>
          Trajectories ({files.length})
        </div>
        {files.length === 0 && !error && (
          <div style={{ padding: '20px 16px', color: 'var(--text-muted)', fontSize: '12px' }}>
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
                background: active ? 'var(--bg-primary)' : 'transparent',
                borderLeft: active ? '2px solid var(--accent-purple)' : '2px solid transparent',
                border: 'none', borderBottom: '1px solid var(--border)',
                cursor: 'pointer', transition: 'background 0.1s',
              }}
            >
              <div style={{
                fontSize: '12px', fontWeight: active ? 600 : 400,
                color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {label}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
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
            padding: '12px 16px', borderRadius: '8px',
            background: 'rgba(239,68,68,0.1)', border: '1px solid var(--accent-red)',
            color: 'var(--accent-red)', fontSize: '13px', marginBottom: '16px',
          }}>
            {error}
          </div>
        )}

        {!selected && !error && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '100%', color: 'var(--text-muted)', fontSize: '14px',
          }}>
            Select a trajectory to view
          </div>
        )}

        {loading && (
          <div style={{ color: 'var(--text-muted)', fontSize: '13px', padding: '20px' }}>
            Loading trajectory...
          </div>
        )}

        {traj && !loading && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

            {/* Run Metadata */}
            <div style={{
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              borderRadius: '10px', padding: '14px 20px',
              display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap',
            }}>
              <MetaTag label="Model" value={traj.info.config?.model?.model_name ?? '?'} />
              <MetaTag label="Steps" value={String(steps.length)} />
              <MetaTag label="API Calls" value={String(traj.info.model_stats?.api_calls ?? 0)} />
              <MetaTag
                label="Status"
                value={traj.info.exit_status}
                color={traj.info.exit_status === 'Submitted' ? 'var(--accent-green)' : 'var(--accent-yellow)'}
              />
              <MetaTag label="Mode" value={traj.info.config?.agent?.mode ?? '?'} />
              <MetaTag label="Version" value={traj.info.mini_version ?? '?'} />
            </div>

            {/* Task (from user message) */}
            {traj.messages.find(m => m.role === 'user') && (
              <div style={{
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: '10px', padding: '14px 20px',
              }}>
                <div style={{
                  fontSize: '10px', fontWeight: 600, color: 'var(--text-muted)',
                  textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px',
                }}>
                  Task
                </div>
                <div style={{
                  fontSize: '13px', color: 'var(--text-secondary)',
                  whiteSpace: 'pre-wrap', lineHeight: 1.5,
                  maxHeight: '120px', overflow: 'auto',
                }}>
                  {extractTask(traj.messages.find(m => m.role === 'user')?.content ?? '')}
                </div>
              </div>
            )}

            {/* Steps */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {steps.map(step => {
                const expanded = expandedStep === step.index
                return (
                  <div
                    key={step.index}
                    style={{
                      background: 'var(--bg-card)', border: '1px solid var(--border)',
                      borderRadius: '10px', overflow: 'hidden',
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
                    >
                      <span style={{
                        fontSize: '10px', fontWeight: 700,
                        color: 'var(--accent-purple)', minWidth: '28px',
                      }}>
                        #{step.index + 1}
                      </span>
                      <span style={{
                        fontSize: '10px', fontWeight: 600,
                        padding: '2px 6px', borderRadius: '3px',
                        background: 'rgba(139,92,246,0.12)', color: 'var(--accent-purple)',
                      }}>
                        {step.toolName || 'reasoning'}
                      </span>
                      <span style={{
                        fontSize: '12px', color: 'var(--text-secondary)',
                        flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {step.command || step.reasoning.slice(0, 80)}
                      </span>
                      {step.returncode !== null && (
                        <span style={{
                          fontSize: '10px', fontWeight: 600,
                          color: step.returncode === 0 ? 'var(--accent-green)' : 'var(--accent-red)',
                        }}>
                          rc={step.returncode}
                        </span>
                      )}
                      <span style={{
                        fontSize: '14px', color: 'var(--text-muted)',
                        transform: expanded ? 'rotate(180deg)' : 'none',
                        transition: 'transform 0.15s',
                      }}>
                        ▾
                      </span>
                    </button>

                    {/* Step Detail */}
                    {expanded && (
                      <div style={{
                        padding: '0 16px 16px',
                        display: 'flex', flexDirection: 'column', gap: '10px',
                      }}>
                        {/* Reasoning */}
                        {step.reasoning && (
                          <div>
                            <SectionLabel>Reasoning</SectionLabel>
                            <CodeBlock text={step.reasoning} maxHeight="150px" />
                          </div>
                        )}

                        {/* Command */}
                        {step.command && (
                          <div>
                            <SectionLabel>Command</SectionLabel>
                            <CodeBlock
                              text={step.command}
                              style={{ color: 'var(--accent-blue)', fontWeight: 500 }}
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
                                  color: step.returncode === 0 ? 'var(--accent-green)' : 'var(--accent-red)',
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
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function MetaTag({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
      <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        {label}
      </span>
      <span style={{ fontSize: '13px', fontWeight: 500, color: color ?? 'var(--text-primary)' }}>
        {value}
      </span>
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontSize: '10px', fontWeight: 600, color: 'var(--text-muted)',
      textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: '4px',
    }}>
      {children}
    </div>
  )
}

function CodeBlock({ text, maxHeight, style }: { text: string; maxHeight?: string; style?: React.CSSProperties }) {
  return (
    <pre style={{
      margin: 0, padding: '10px 12px', borderRadius: '6px',
      background: 'var(--bg-primary)', border: '1px solid var(--border)',
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
