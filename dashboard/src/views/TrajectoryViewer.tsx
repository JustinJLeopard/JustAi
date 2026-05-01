import { useState, useEffect, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, CartesianGrid,
} from 'recharts'
import {
  TrajFile, Trajectory, TrajStep,
  listTrajectories, loadTrajectory, parseSteps,
} from '@/lib/trajectories'
import {
  fetchTrajectoryAnalysis, fetchTrajectoryPatterns, fetchTrajectoryAudit,
} from '@/lib/api-client'
import type { TrajAnalysis, PatternReport, AuditData } from '@/lib/api-client'
import type { View } from '@/components/Sidebar'

type Mode = 'post-mortem' | 'learning' | 'audit'

interface TrajectoryViewerProps {
  onNavigate?: (view: View) => void
  initialFile?: string
}

// ── Tab button ───────────────────────────────────────────────────────────────
function ModeTab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '8px 18px',
        borderRadius: 4,
        fontSize: 12, fontWeight: active ? 500 : 400,
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

// ── Section label ────────────────────────────────────────────────────────────
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

// ── Code block ───────────────────────────────────────────────────────────────
function CodeBlock({ text, maxHeight, style: extra }: { text: string; maxHeight?: string; style?: React.CSSProperties }) {
  return (
    <pre style={{
      margin: 0, padding: '10px 12px', borderRadius: 'var(--r-sm)',
      background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)',
      fontFamily: 'var(--font-mono)',
      fontSize: 12, lineHeight: 1.5, color: 'var(--text-secondary)',
      whiteSpace: 'pre-wrap', wordBreak: 'break-word',
      maxHeight: maxHeight ?? '400px', overflow: 'auto',
      ...extra,
    }}>
      {text}
    </pre>
  )
}

// ── Meta tag ─────────────────────────────────────────────────────────────────
function MetaTag({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase' as const, letterSpacing: '0.8px', fontWeight: 600 }}>
        {label}
      </span>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500, color: color ?? 'var(--text-primary)' }}>
        {value}
      </span>
    </div>
  )
}

// ── Chart tooltip ────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--bg-popover)', border: '1px solid var(--border-default)',
      borderRadius: 'var(--r-sm)', padding: '8px 12px', fontSize: 11,
      color: 'var(--text-primary)', boxShadow: 'var(--shadow-lg)',
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 4, fontSize: 10 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} style={{ display: 'flex', gap: 8, justifyContent: 'space-between' }}>
          <span style={{ color: p.color }}>{p.name}</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>
            {typeof p.value === 'number' ? (p.name.includes('cost') ? `$${p.value.toFixed(4)}` : p.value.toFixed(1)) : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Action type icon/color ───────────────────────────────────────────────────
const ACTION_ICONS: Record<string, { icon: string; color: string }> = {
  bash:  { icon: '▸', color: 'var(--rose-400)' },
  edit:  { icon: '✎', color: 'var(--amber-500)' },
  read:  { icon: '◎', color: 'var(--emerald-400)' },
  think: { icon: '◇', color: 'var(--text-muted)' },
  write: { icon: '✎', color: 'var(--amber-500)' },
}

function extractTask(content: string): string {
  const match = content.match(/TASK:\s*(.*?)(?:\n\n|$)/s)
  if (match) return match[1].trim()
  return content.slice(0, 500)
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function TrajectoryViewer({ onNavigate, initialFile }: TrajectoryViewerProps) {
  const [mode, setMode] = useState<Mode>('post-mortem')
  const [files, setFiles] = useState<TrajFile[]>([])
  const [selected, setSelected] = useState<string | null>(initialFile ?? null)
  const [traj, setTraj] = useState<Trajectory | null>(null)
  const [steps, setSteps] = useState<TrajStep[]>([])
  const [expandedStep, setExpandedStep] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // AI analysis state
  const [analysis, setAnalysis] = useState<TrajAnalysis | null>(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)

  // Learning mode state
  const [patterns, setPatterns] = useState<PatternReport | null>(null)
  const [patternsLoading, setPatternsLoading] = useState(false)

  // Audit mode state
  const [auditData, setAuditData] = useState<AuditData | null>(null)
  const [auditLoading, setAuditLoading] = useState(false)

  // Load file list on mount
  useEffect(() => {
    listTrajectories()
      .then(setFiles)
      .catch(e => setError(e.message))
  }, [])

  // Load trajectory when selected
  useEffect(() => {
    if (!selected) { setTraj(null); setSteps([]); setAnalysis(null); setAuditData(null); return }
    setLoading(true)
    setError(null)
    loadTrajectory(selected)
      .then(t => {
        setTraj(t)
        setSteps(parseSteps(t))
        setExpandedStep(null)
        setAnalysis(null)
        setAuditData(null)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [selected])

  // Auto-load analysis when Post-Mortem mode + trajectory selected
  useEffect(() => {
    if (mode === 'post-mortem' && selected && traj && !analysis && !analysisLoading) {
      setAnalysisLoading(true)
      fetchTrajectoryAnalysis(selected)
        .then(setAnalysis)
        .catch(() => {})
        .finally(() => setAnalysisLoading(false))
    }
  }, [mode, selected, traj])

  // Auto-load patterns when Learning mode entered
  useEffect(() => {
    if (mode === 'learning' && !patterns && !patternsLoading) {
      setPatternsLoading(true)
      fetchTrajectoryPatterns()
        .then(setPatterns)
        .catch(() => {})
        .finally(() => setPatternsLoading(false))
    }
  }, [mode])

  // Auto-load audit when Audit mode + trajectory selected
  useEffect(() => {
    if (mode === 'audit' && selected && !auditData && !auditLoading) {
      setAuditLoading(true)
      fetchTrajectoryAudit(selected)
        .then(setAuditData)
        .catch(() => {})
        .finally(() => setAuditLoading(false))
    }
  }, [mode, selected])

  const autoScrollToFailure = useCallback(() => {
    if (steps.length > 0) {
      const firstFail = steps.find(s => s.returncode !== null && s.returncode !== 0)
      if (firstFail) {
        setExpandedStep(firstFail.index)
      }
    }
  }, [steps])

  // Auto-expand first failure
  useEffect(() => {
    if (mode === 'post-mortem') autoScrollToFailure()
  }, [steps, mode, autoScrollToFailure])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: 'calc(100vh - 120px)' }}>

      {/* ── Header + Mode Tabs ────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 200, color: 'var(--text-primary)', letterSpacing: '-0.3px' }}>
            Trajectories
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            {files.length} file{files.length !== 1 ? 's' : ''}
            {selected && traj ? ` — ${steps.length} steps` : ''}
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

      {/* ── Main Layout ───────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', gap: 16, overflow: 'hidden' }}>

        {/* File List Sidebar (all modes except Learning) */}
        {mode !== 'learning' && (
          <div style={{
            width: 260, flexShrink: 0,
            background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--r-md)', overflow: 'auto',
          }}>
            <div style={{
              padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)',
              fontSize: 9, fontWeight: 600, color: 'var(--text-tertiary)',
              textTransform: 'uppercase' as const, letterSpacing: '0.8px',
            }}>
              Trajectories ({files.length})
            </div>
            {files.length === 0 && !error && (
              <div style={{ padding: '20px 16px', color: 'var(--text-tertiary)', fontSize: 12 }}>
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
                  onMouseEnter={e => { if (!active) (e.currentTarget).style.background = 'var(--bg-hover)' }}
                  onMouseLeave={e => { if (!active) (e.currentTarget).style.background = 'transparent' }}
                >
                  <div style={{
                    fontSize: 12, fontWeight: active ? 500 : 400,
                    color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                  }}>
                    {label}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>
                    {date.toLocaleDateString()} {date.toLocaleTimeString()} — {(f.size / 1024).toFixed(0)}KB
                  </div>
                </button>
              )
            })}
          </div>
        )}

        {/* ── Content Area ─────────────────────────────────────────── */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {error && (
            <div style={{
              padding: '12px 16px', borderRadius: 'var(--r-sm)',
              background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
              color: 'var(--red-500)', fontSize: 13, marginBottom: 16,
            }}>
              {error}
            </div>
          )}

          {mode === 'post-mortem' && <PostMortemMode
            selected={selected} traj={traj} steps={steps} loading={loading}
            expandedStep={expandedStep} setExpandedStep={setExpandedStep}
            analysis={analysis} analysisLoading={analysisLoading}
          />}

          {mode === 'learning' && <LearningMode
            patterns={patterns} loading={patternsLoading}
          />}

          {mode === 'audit' && <AuditMode
            selected={selected} traj={traj} steps={steps} loading={loading}
            auditData={auditData} auditLoading={auditLoading}
          />}
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MODE 1: POST-MORTEM
// ═══════════════════════════════════════════════════════════════════════════════

function PostMortemMode({
  selected, traj, steps, loading, expandedStep, setExpandedStep, analysis, analysisLoading,
}: {
  selected: string | null
  traj: Trajectory | null
  steps: TrajStep[]
  loading: boolean
  expandedStep: number | null
  setExpandedStep: (n: number | null) => void
  analysis: TrajAnalysis | null
  analysisLoading: boolean
}) {
  if (!selected) {
    return <EmptyState message="Select a trajectory to analyze" />
  }
  if (loading) {
    return <LoadingState message="Loading trajectory..." />
  }
  if (!traj) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* AI Analysis Panel */}
      <div className="panel panel-pad">
        <SectionLabel>AI Analysis</SectionLabel>
        {analysisLoading ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, fontWeight: 300, padding: '8px 0' }}>
            Analyzing trajectory...
          </div>
        ) : analysis ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ fontSize: 13, fontWeight: 300, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {analysis.summary}
            </div>
            {analysis.root_cause && (
              <div style={{
                padding: '10px 14px', borderRadius: 'var(--r-sm)',
                background: analysis.status === 'failure' ? 'rgba(239,68,68,0.06)' : 'rgba(16,185,129,0.06)',
                border: `1px solid ${analysis.status === 'failure' ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)'}`,
              }}>
                <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-dim)', marginBottom: 4 }}>
                  {analysis.status === 'failure' ? 'Root Cause' : 'Key Insight'}
                </div>
                <div style={{ fontSize: 12, fontWeight: 300, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {analysis.root_cause}
                </div>
              </div>
            )}
            {analysis.recommendation && (
              <div style={{
                padding: '10px 14px', borderRadius: 'var(--r-sm)',
                background: 'rgba(244,63,94,0.04)', border: '1px solid rgba(244,63,94,0.08)',
              }}>
                <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-dim)', marginBottom: 4 }}>
                  Recommendation
                </div>
                <div style={{ fontSize: 12, fontWeight: 300, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {analysis.recommendation}
                </div>
              </div>
            )}
            {analysis.cached && (
              <div style={{ fontSize: 10, color: 'var(--text-dim)', fontStyle: 'italic' }}>cached result</div>
            )}
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, fontWeight: 300 }}>
            Analysis unavailable — API server may be offline
          </div>
        )}
      </div>

      {/* Run Metadata */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--r-md)', padding: '14px 20px',
        display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap',
      }}>
        <MetaTag label="Model" value={traj.info.config?.model?.model_name ?? '?'} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase' as const, letterSpacing: '0.8px', fontWeight: 600 }}>Steps</span>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500,
            color: 'var(--rose-400)', background: 'var(--rose-glow)',
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
        <MetaTag label="Cost" value={`$${(traj.info.model_stats?.instance_cost ?? 0).toFixed(4)}`} color="var(--gold-300)" />
        <MetaTag label="Version" value={traj.info.mini_version ?? '?'} />
      </div>

      {/* Task */}
      {traj.messages.find(m => m.role === 'user') && (
        <div className="panel" style={{ padding: '14px 20px' }}>
          <SectionLabel>Task</SectionLabel>
          <div style={{
            fontSize: 13, color: 'var(--text-secondary)', fontWeight: 300,
            whiteSpace: 'pre-wrap', lineHeight: 1.5, maxHeight: 120, overflow: 'auto',
          }}>
            {extractTask(traj.messages.find(m => m.role === 'user')?.content ?? '')}
          </div>
        </div>
      )}

      {/* Steps */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {steps.map(step => {
          const expanded = expandedStep === step.index
          const isFailed = step.returncode !== null && step.returncode !== 0
          const ai = ACTION_ICONS[step.toolName?.toLowerCase()] || ACTION_ICONS[step.returncode === null ? 'think' : 'bash']
          const actionInfo = ai || { icon: '▸', color: 'var(--text-muted)' }

          return (
            <div
              key={step.index}
              style={{
                border: `1px solid ${isFailed ? 'rgba(239,68,68,0.2)' : 'var(--border-subtle)'}`,
                borderRadius: 'var(--r-md)', overflow: 'hidden',
                transition: 'border-color var(--t-fast)',
                ...(expanded ? { borderColor: isFailed ? 'rgba(239,68,68,0.3)' : 'var(--border-default)' } : {}),
              }}
            >
              <button
                onClick={() => setExpandedStep(expanded ? null : step.index)}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 16px', background: 'none', border: 'none',
                  cursor: 'pointer', textAlign: 'left',
                }}
                onMouseEnter={e => { (e.currentTarget).style.background = 'var(--bg-hover)' }}
                onMouseLeave={e => { (e.currentTarget).style.background = 'none' }}
              >
                <span style={{
                  fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                  color: isFailed ? 'var(--red-500)' : 'var(--rose-400)', minWidth: 28,
                }}>
                  #{step.index + 1}
                </span>
                <span style={{ fontSize: 12, color: actionInfo.color }}>{actionInfo.icon}</span>
                <span style={{
                  fontSize: 10, fontWeight: 600,
                  padding: '2px 6px', borderRadius: 'var(--r-sm)',
                  background: isFailed ? 'rgba(239,68,68,0.1)' : 'var(--rose-glow)',
                  color: isFailed ? 'var(--red-500)' : 'var(--rose-300)',
                }}>
                  {step.toolName || 'reasoning'}
                </span>
                <span style={{
                  fontSize: 12, color: 'var(--text-secondary)',
                  flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                }}>
                  {step.command || step.reasoning.slice(0, 80)}
                </span>
                {step.returncode !== null && (
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 600,
                    color: step.returncode === 0 ? 'var(--emerald-400)' : 'var(--red-500)',
                  }}>
                    rc={step.returncode}
                  </span>
                )}
                <span style={{
                  fontSize: 14, color: 'var(--text-tertiary)',
                  transform: expanded ? 'rotate(180deg)' : 'none',
                  transition: 'transform var(--t-fast)',
                }}>
                  ▾
                </span>
              </button>

              {expanded && (
                <div style={{
                  padding: '0 16px 16px',
                  display: 'flex', flexDirection: 'column', gap: 10,
                  borderTop: '1px solid var(--border-subtle)',
                }}>
                  {step.reasoning && (
                    <div style={{ marginTop: 10 }}>
                      <SectionLabel>Reasoning</SectionLabel>
                      <div style={{
                        fontSize: 13, color: 'var(--text-secondary)', fontWeight: 300,
                        lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                        maxHeight: 150, overflow: 'auto', padding: '8px 0',
                      }}>
                        {step.reasoning}
                      </div>
                    </div>
                  )}
                  {step.command && (
                    <div>
                      <SectionLabel>Command</SectionLabel>
                      <CodeBlock text={step.command} style={{ color: 'var(--rose-300)', fontWeight: 500 }} />
                    </div>
                  )}
                  {step.result && (
                    <div>
                      <SectionLabel>
                        Output
                        {step.returncode !== null && (
                          <span style={{
                            marginLeft: 8, fontSize: 10, fontFamily: 'var(--font-mono)',
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
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MODE 2: LEARNING
// ═══════════════════════════════════════════════════════════════════════════════

function LearningMode({ patterns, loading }: { patterns: PatternReport | null; loading: boolean }) {
  if (loading) {
    return <LoadingState message="Analyzing patterns across trajectories..." />
  }
  if (!patterns || patterns.total_trajectories === 0) {
    return <EmptyState message="No trajectory data available. Run a control-plane sprint to generate data." />
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>

      {/* Summary metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--sp-3)' }}>
        <MiniMetric label="Trajectories" value={String(patterns.total_trajectories)} />
        <MiniMetric label="Avg Steps" value={patterns.avg_steps.toFixed(0)} />
        <MiniMetric label="Avg Cost" value={`$${patterns.avg_cost.toFixed(4)}`} color="var(--gold-300)" />
        <MiniMetric
          label="Success Rate"
          value={`${(patterns.success_rate * 100).toFixed(0)}%`}
          color={patterns.success_rate >= 0.8 ? 'var(--emerald-400)' : patterns.success_rate >= 0.5 ? 'var(--amber-500)' : 'var(--red-500)'}
        />
      </div>

      {/* Two-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-4)' }}>

        {/* AI Suggestions */}
        <div className="panel panel-pad">
          <SectionLabel>AI Suggestions</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {patterns.suggestions.map((s, i) => (
              <div key={i} style={{
                padding: '10px 14px', borderRadius: 'var(--r-sm)',
                background: 'rgba(244,63,94,0.04)', border: '1px solid rgba(244,63,94,0.08)',
                fontSize: 12, fontWeight: 300, color: 'var(--text-secondary)', lineHeight: 1.5,
              }}>
                {s}
              </div>
            ))}
          </div>
        </div>

        {/* Common Failures */}
        <div className="panel panel-pad">
          <SectionLabel>Common Failure Patterns</SectionLabel>
          {patterns.common_failures.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 300, padding: '8px 0' }}>
              No failures recorded
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {patterns.common_failures.map((f, i) => (
                <div key={i} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '6px 0', borderBottom: '1px solid var(--border-subtle)',
                }}>
                  <span style={{
                    fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '80%',
                  }}>
                    {f.pattern}
                  </span>
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--red-500)', fontWeight: 600 }}>
                    ×{f.count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Efficiency Trend */}
      {patterns.efficiency_trend.length > 1 && (
        <div className="panel panel-pad">
          <SectionLabel>Efficiency Trend</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--sp-4)' }}>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 8, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '1.5px' }}>
                Steps per Run
              </div>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={patterns.efficiency_trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--text-dim)' }} tickFormatter={d => d.slice(5)} axisLine={{ stroke: 'var(--border-subtle)' }} tickLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: 'var(--text-dim)' }} axisLine={false} tickLine={false} width={30} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="avg_steps" name="Avg Steps" fill="var(--rose-400)" fillOpacity={0.6} radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 8, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '1.5px' }}>
                Cost per Run
              </div>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={patterns.efficiency_trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--text-dim)' }} tickFormatter={d => d.slice(5)} axisLine={{ stroke: 'var(--border-subtle)' }} tickLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: 'var(--text-dim)' }} tickFormatter={v => `$${v}`} axisLine={false} tickLine={false} width={36} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="avg_cost" name="Avg Cost" fill="var(--gold-400)" fillOpacity={0.6} radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 8, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '1.5px' }}>
                Success Rate
              </div>
              <ResponsiveContainer width="100%" height={140}>
                <AreaChart data={patterns.efficiency_trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--text-dim)' }} tickFormatter={d => d.slice(5)} axisLine={{ stroke: 'var(--border-subtle)' }} tickLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: 'var(--text-dim)' }} domain={[0, 1]} tickFormatter={v => `${(v * 100).toFixed(0)}%`} axisLine={false} tickLine={false} width={36} />
                  <Tooltip content={<ChartTooltip />} />
                  <defs>
                    <linearGradient id="successGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--emerald-400)" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="var(--emerald-400)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area dataKey="success_rate" name="Success Rate" stroke="var(--emerald-400)" strokeWidth={2} fill="url(#successGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MODE 3: AUDIT
// ═══════════════════════════════════════════════════════════════════════════════

function AuditMode({
  selected, traj, steps, loading, auditData, auditLoading,
}: {
  selected: string | null
  traj: Trajectory | null
  steps: TrajStep[]
  loading: boolean
  auditData: AuditData | null
  auditLoading: boolean
}) {
  if (!selected) {
    return <EmptyState message="Select a trajectory to audit" />
  }
  if (loading || auditLoading) {
    return <LoadingState message="Loading audit data..." />
  }
  if (!traj || !auditData) return null

  const handleExportJSON = () => {
    const blob = new Blob([JSON.stringify(auditData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selected.replace('.traj.json', '')}-audit.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 12,
      background: 'rgba(255,255,255,0.008)',
      borderRadius: 'var(--r-lg)',
      padding: 'var(--sp-1)',
    }}>

      {/* Audit Header */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--r-md)', padding: '14px 20px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
          <MetaTag label="Model" value={auditData.model} />
          <MetaTag label="Steps" value={String(auditData.step_count)} />
          <MetaTag label="API Calls" value={String(auditData.api_calls)} />
          <MetaTag label="Cost" value={`$${auditData.total_cost.toFixed(4)}`} color="var(--gold-300)" />
          <MetaTag
            label="Exit Status"
            value={auditData.exit_status}
            color={auditData.exit_status === 'Submitted' ? 'var(--emerald-400)' : 'var(--amber-500)'}
          />
          <MetaTag label="Version" value={auditData.version} />
        </div>
        <button
          onClick={handleExportJSON}
          style={{
            padding: '7px 14px', borderRadius: 'var(--r-sm)',
            fontSize: 11, fontWeight: 400, cursor: 'pointer',
            border: '1px solid var(--border-default)',
            background: 'var(--bg-surface)', color: 'var(--text-secondary)',
            fontFamily: 'var(--font-sans)', letterSpacing: '0.2px',
            transition: 'all var(--t-fast)',
          }}
        >
          Export JSON
        </button>
      </div>

      {/* File Change Manifest */}
      {auditData.files_changed.length > 0 && (
        <div className="panel" style={{ padding: '14px 20px' }}>
          <SectionLabel>File Change Manifest</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 80px 80px',
              padding: '6px 0', borderBottom: '1px solid var(--border-subtle)',
              fontSize: 9, fontWeight: 600, color: 'var(--text-dim)',
              textTransform: 'uppercase', letterSpacing: '0.8px',
            }}>
              <span>File</span>
              <span style={{ textAlign: 'right' }}>First Touch</span>
              <span style={{ textAlign: 'right' }}>Modifications</span>
            </div>
            {auditData.files_changed.map((f, i) => (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '1fr 80px 80px',
                padding: '8px 0', borderBottom: '1px solid rgba(255,255,255,0.02)',
                fontSize: 12, color: 'var(--text-secondary)', fontWeight: 300,
              }}>
                <span style={{ fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {f.file}
                </span>
                <span style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                  Step {f.first_touch_step + 1}
                </span>
                <span style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--amber-500)' }}>
                  {f.modifications}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Chain of Evidence — Token Accounting */}
      <div className="panel" style={{ padding: '14px 20px' }}>
        <SectionLabel>Chain of Evidence</SectionLabel>
        <div style={{ display: 'flex', gap: 'var(--sp-4)', marginBottom: 'var(--sp-3)', flexWrap: 'wrap' }}>
          <MetaTag label="Model" value={auditData.model} />
          <MetaTag label="Total Cost" value={`$${auditData.total_cost.toFixed(4)}`} color="var(--gold-300)" />
          <MetaTag label="API Calls" value={String(auditData.api_calls)} />
          <MetaTag label="Total Steps" value={String(auditData.step_count)} />
        </div>
      </div>

      {/* Chronological Event Log */}
      <div className="panel" style={{ padding: '14px 20px' }}>
        <SectionLabel>Chronological Event Log</SectionLabel>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          <div style={{
            display: 'grid', gridTemplateColumns: '50px 60px 1fr 60px 60px 50px',
            padding: '6px 0', borderBottom: '1px solid var(--border-subtle)',
            fontSize: 9, fontWeight: 600, color: 'var(--text-dim)',
            textTransform: 'uppercase', letterSpacing: '0.8px',
          }}>
            <span>Step</span>
            <span>Type</span>
            <span>Command</span>
            <span style={{ textAlign: 'right' }}>Target</span>
            <span style={{ textAlign: 'right' }}>Chars</span>
            <span style={{ textAlign: 'right' }}>Exit</span>
          </div>
          {auditData.events.map((evt, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '50px 60px 1fr 60px 60px 50px',
              padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.02)',
              fontSize: 11, color: 'var(--text-secondary)', fontWeight: 300,
              fontFamily: 'var(--font-mono)',
            }}>
              <span style={{ color: 'var(--rose-400)', fontWeight: 600 }}>#{evt.step + 1}</span>
              <span style={{ color: 'var(--text-muted)' }}>{evt.action_type}</span>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {evt.command.slice(0, 80) || '—'}
              </span>
              <span style={{ textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--text-muted)' }}>
                {evt.target ? evt.target.split('/').pop() : '—'}
              </span>
              <span style={{ textAlign: 'right', color: 'var(--text-dim)', fontSize: 10 }}>
                {((evt.reasoning_length || 0) + (evt.result_length || 0)).toLocaleString()}
              </span>
              <span style={{
                textAlign: 'right', fontWeight: 600,
                color: evt.returncode === null ? 'var(--text-dim)' : evt.returncode === 0 ? 'var(--emerald-400)' : 'var(--red-500)',
              }}>
                {evt.returncode !== null ? evt.returncode : '—'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Shared utility components ────────────────────────────────────────────────

function MiniMetric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="panel" style={{ padding: '12px 16px' }}>
      <div style={{ fontSize: 10, fontWeight: 500, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1.8px', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 200, color: color ?? 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </div>
    </div>
  )
}

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

function LoadingState({ message }: { message: string }) {
  return (
    <div style={{ color: 'var(--text-tertiary)', fontSize: 13, padding: 20 }}>
      {message}
    </div>
  )
}
