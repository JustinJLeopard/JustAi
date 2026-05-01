/**
 * JustAi Demo — Mission Control View
 *
 * Full Mission Control dashboard for the interactive demo.
 * Mirrors the real MissionControl.tsx layout and styling but reads
 * all data from SimulationState instead of live control-plane API data.
 */

import { useState } from 'react'
import type { SimulationState, DemoView, DemoTask, ControlPlaneStage, StageStatus } from '../data/types'

// ── Props ───────────────────────────────────────────────────────────────────

export interface DemoMissionControlProps {
  state: SimulationState
  onNavigate: (view: DemoView) => void
  // Triggered by the "+ New Run" button — restarts the sprint from t=0.
  // Wired to useSimulation().controls.replay() in JustAiDemo.
  onNewRun: () => void
}

// ── Time range button (decorative) ──────────────────────────────────────────

function TimeRangeBtn({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '8px 14px',
        borderRadius: 'var(--r-sm)',
        fontSize: 12,
        fontWeight: 400,
        cursor: 'pointer',
        transition: 'all var(--t-fast)',
        border: '1px solid var(--border-default)',
        fontFamily: 'var(--font-sans)',
        letterSpacing: '0.2px',
        background: active ? 'var(--bg-elevated)' : 'var(--bg-surface)',
        color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
        borderColor: active ? 'var(--border-hover)' : 'var(--border-default)',
      }}
    >
      {label}
    </button>
  )
}

// ── Mini Sparkline ──────────────────────────────────────────────────────────

function MiniSparkline({ points, color }: { points: number[]; color: string }) {
  if (points.length === 0) return null
  const max = Math.max(...points, 1)
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 20, marginTop: 6 }}>
      {points.map((v, i) => (
        <div
          key={i}
          style={{
            width: 4,
            borderRadius: 1,
            background: color,
            opacity: 0.5 + (v / max) * 0.5,
            height: `${Math.max(2, (v / max) * 100)}%`,
            transition: 'height 0.3s ease',
          }}
        />
      ))}
    </div>
  )
}

// ── Stat Card ───────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  color,
  subText,
  sparkline,
  sparklineColor,
}: {
  label: string
  value: string
  color: string
  subText: string
  sparkline?: number[]
  sparklineColor?: string
}) {
  return (
    <div
      className="panel"
      style={{ padding: 'var(--sp-4)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}
    >
      <div>
        <div
          style={{
            fontSize: 10,
            fontWeight: 500,
            textTransform: 'uppercase',
            letterSpacing: '1.5px',
            color: 'var(--text-dim)',
            marginBottom: 6,
          }}
        >
          {label}
        </div>
        <div
          style={{
            fontSize: 28,
            fontWeight: 200,
            color,
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1.1,
          }}
        >
          {value}
        </div>
        <div
          style={{
            fontSize: 11,
            fontWeight: 300,
            color: 'var(--text-muted)',
            marginTop: 4,
          }}
        >
          {subText}
        </div>
      </div>
      {sparkline && sparklineColor && (
        <MiniSparkline points={sparkline} color={sparklineColor} />
      )}
    </div>
  )
}

// ── Pipeline Stage Dot ──────────────────────────────────────────────────────

function ControlPlaneStageDot({
  name,
  status,
}: {
  name: string
  status: StageStatus
}) {
  const dotColor =
    status === 'done' ? 'var(--emerald-500)' :
    status === 'active' ? 'var(--amber-500)' :
    'var(--text-dim)'

  const dotShadow =
    status === 'done' ? '0 0 6px var(--emerald-glow)' :
    status === 'active' ? '0 0 6px rgba(245,158,11,0.3)' :
    'none'

  const labelColor =
    status === 'done' ? 'var(--emerald-400)' :
    status === 'active' ? 'var(--amber-500)' :
    'var(--text-dim)'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
      <div
        style={{
          width: 10,
          height: 10,
          borderRadius: '50%',
          background: dotColor,
          boxShadow: dotShadow,
          transition: 'all 0.3s ease',
          animation: status === 'active' ? 'pulse-live 2s ease-in-out infinite' : undefined,
        }}
      />
      <span
        style={{
          fontSize: 10,
          fontWeight: 400,
          color: labelColor,
          textTransform: 'uppercase',
          letterSpacing: '1px',
          transition: 'color 0.3s ease',
        }}
      >
        {name}
      </span>
    </div>
  )
}

// ── Service Row ─────────────────────────────────────────────────────────────

function ServiceRow({ name, detail, ping }: { name: string; detail: string; ping: string }) {
  const dotColor = 'var(--emerald-500)'
  const dotShadow = '0 0 6px var(--emerald-glow)'

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '8px 1fr auto auto',
      gap: 'var(--sp-3)',
      alignItems: 'center',
      padding: '10px 0',
      borderBottom: '1px solid var(--border-subtle)',
      cursor: 'default',
    }}>
      <div style={{
        width: 7, height: 7, borderRadius: '50%',
        background: dotColor, boxShadow: dotShadow,
        flexShrink: 0,
      }} />
      <span style={{ fontSize: 13, fontWeight: 300, color: '#cbd5e1' }}>{name}</span>
      <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{detail}</span>
      <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', textAlign: 'right', minWidth: 44 }}>{ping}</span>
    </div>
  )
}

// ── Main Component ──────────────────────────────────────────────────────────

export function DemoMissionControl({ state, onNavigate, onNewRun }: DemoMissionControlProps) {
  const [timeRange, setTimeRange] = useState<'24h' | '7d' | '30d'>('24h')

  // ── Derived data ────────────────────────────────────────────────────────
  const activeAgents = state.agents.filter(a => a.status === 'active')
  const activeRuns = state.phase !== 'idle' && state.phase !== 'complete' ? 1 : 0
  const activeTasks = state.tasks.filter(t => t.status === 'in_progress' || t.status === 'claimed')

  // Active task: first in-progress task
  const activeTask: DemoTask | null = state.tasks.find(t => t.status === 'in_progress') ?? null
  const isEscalating = activeTask?.escalated === true && activeTask?.status === 'in_progress'

  // Sparkline data for metric cards
  const activeSparkline = [0, 1, 2, 1, 3, 2, activeRuns]
  const doneSparkline = [0, 0, 1, 2, 3, Math.max(0, state.completedCount - 1), state.completedCount].map(v => Math.max(0, v))
  const costSparkline = [0.001, 0.003, 0.002, 0.005, 0.004, 0.008, state.totalCost].map(v => Math.max(0, v))
  const latencySparkline = [1.2, 2.0, 1.5, 2.5, 1.8, 3.0, state.avgLatency].map(v => Math.max(0, v))

  // Control-plane stages array
  const controlPlaneStages: { name: string; key: ControlPlaneStage }[] = [
    { name: 'Intent', key: 'intent' },
    { name: 'Plan', key: 'plan' },
    { name: 'Execute', key: 'execute' },
    { name: 'Review', key: 'review' },
    { name: 'Synthesize', key: 'synthesize' },
  ]

  // Run status label
  const runPhaseLabel =
    state.phase === 'idle' ? 'Idle' :
    state.phase === 'complete' ? 'Complete' :
    state.phase === 'planning' ? 'Planning' :
    state.phase === 'executing' ? 'Executing' :
    state.phase === 'reviewing' ? 'Reviewing' :
    'Active'

  // Progress bar
  const progressPct = activeTask
    ? Math.min(95, Math.max(5, (activeTask.stepsDone / Math.max(activeTask.steps, 1)) * 100))
    : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>

      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 200, color: 'var(--text-primary)', letterSpacing: '0.3px', margin: 0 }}>
            Mission Control
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginTop: 5, fontSize: 12, color: 'var(--text-muted)', fontWeight: 300 }}>
            <div style={{
              width: 5, height: 5, borderRadius: '50%',
              background: 'var(--rose-500)',
              animation: 'pulse-live 2s ease-in-out infinite',
              flexShrink: 0,
            }} />
            <span>
              Live · {activeAgents.length} agent{activeAgents.length !== 1 ? 's' : ''} active
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'center' }}>
          {(['24h', '7d', '30d'] as const).map(r => (
            <TimeRangeBtn key={r} label={r} active={timeRange === r} onClick={() => setTimeRange(r)} />
          ))}
          <button
            onClick={onNewRun}
            aria-label="Start a new run — restart the sprint simulation from the beginning"
            style={{
              padding: '8px 16px',
              borderRadius: 'var(--r-sm)',
              fontSize: 12, fontWeight: 400,
              cursor: 'pointer',
              transition: 'all var(--t-fast)',
              border: '1px solid rgba(244,63,94,0.2)',
              fontFamily: 'var(--font-sans)',
              letterSpacing: '0.2px',
              background: 'rgba(244,63,94,0.1)',
              color: 'var(--rose-400)',
            }}
          >
            + New Run
          </button>
        </div>
      </div>

      {/* ── Metrics Grid (5 columns) ────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 'var(--sp-3)' }}>
        <StatCard
          label="Active Runs"
          value={String(activeRuns)}
          color="var(--rose-400)"
          subText={activeRuns > 0 ? `${activeTasks.length} task${activeTasks.length !== 1 ? 's' : ''} running` : 'idle'}
          sparkline={activeSparkline}
          sparklineColor="var(--rose-500)"
        />
        <StatCard
          label="Completed"
          value={String(state.completedCount)}
          color="var(--emerald-400)"
          subText={state.completedCount > 0 ? `${state.completedCount} total` : 'none yet'}
          sparkline={doneSparkline}
          sparklineColor="var(--emerald-500)"
        />
        <StatCard
          label="Success Rate"
          value={state.completedCount > 0 ? `${state.successRate.toFixed(0)}%` : '--'}
          color="var(--emerald-400)"
          subText={state.completedCount > 0 ? `${state.completedCount} evaluated` : 'no data'}
        />
        <StatCard
          label="Cost (24h)"
          value={`$${state.totalCost.toFixed(2)}`}
          color="var(--gold-300)"
          subText={state.totalCost > 0 ? `avg $${(state.totalCost / Math.max(state.completedCount, 1)).toFixed(3)}/run` : 'no data yet'}
          sparkline={costSparkline}
          sparklineColor="var(--gold-400)"
        />
        <StatCard
          label="Avg Latency"
          value={state.avgLatency > 0 ? `${state.avgLatency.toFixed(1)}s` : '--'}
          color="var(--rose-400)"
          subText={state.avgLatency > 0 ? 'across control plane' : 'no data yet'}
          sparkline={latencySparkline}
          sparklineColor="var(--rose-400)"
        />
      </div>

      {/* ── Active Control Plane Panel ───────────────────────────────────── */}
      <div className="panel panel-pad">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-4)' }}>
          <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)', letterSpacing: '1.5px', textTransform: 'uppercase' }}>
            Active Control Plane
          </span>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 'var(--sp-1)',
            fontSize: 11, fontWeight: 400,
            fontFamily: 'var(--font-mono)',
            padding: '3px 10px', borderRadius: 'var(--r-sm)',
            background: 'var(--rose-glow)',
            color: 'var(--rose-400)',
            letterSpacing: '0.3px',
          }}>
            <div style={{
              width: 5, height: 5, borderRadius: '50%',
              background: 'var(--rose-400)',
              animation: activeRuns > 0 ? 'pulse-live 2s ease-in-out infinite' : undefined,
              opacity: activeRuns > 0 ? 1 : 0.3,
            }} />
            Run #{state.completedCount + activeRuns} · {runPhaseLabel}
          </div>
        </div>

        {/* Control-plane stages (horizontal) */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 0,
          padding: 'var(--sp-5) 0',
          position: 'relative',
        }}>
          {controlPlaneStages.map((stage, i) => (
            <div key={stage.key} style={{ display: 'flex', alignItems: 'center' }}>
              <ControlPlaneStageDot
                name={stage.name}
                status={state.pipeline[stage.key]}
              />
              {i < controlPlaneStages.length - 1 && (
                <div style={{
                  width: 48,
                  height: 1,
                  background:
                    state.pipeline[controlPlaneStages[i + 1].key] !== 'idle'
                      ? 'var(--emerald-500)'
                      : state.pipeline[stage.key] === 'active' || state.pipeline[stage.key] === 'done'
                        ? 'var(--border-default)'
                        : 'var(--border-subtle)',
                  margin: '0 var(--sp-3)',
                  marginBottom: 22,
                  transition: 'background 0.3s ease',
                }} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Active Task Banner ───────────────────────────────────────────── */}
      <div style={{
        padding: 'var(--sp-4)',
        borderRadius: 'var(--r-md)',
        background: isEscalating
          ? 'linear-gradient(135deg, rgba(245,158,11,0.08) 0%, rgba(245,158,11,0.03) 100%)'
          : 'linear-gradient(135deg, rgba(244,63,94,0.08) 0%, rgba(244,63,94,0.03) 100%)',
        border: isEscalating
          ? '1px solid rgba(245,158,11,0.15)'
          : '1px solid rgba(244,63,94,0.1)',
        transition: 'all 0.3s ease',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)', marginBottom: 'var(--sp-3)' }}>
          {activeTask && (
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: isEscalating ? 'var(--amber-500)' : 'var(--rose-500)',
              animation: 'pulse-live 2s ease-in-out infinite',
              flexShrink: 0,
            }} />
          )}
          <div style={{ fontSize: 14, fontWeight: 300, color: 'var(--text-primary)', lineHeight: 1.55 }}>
            {activeTask
              ? activeTask.name
              : 'No active task -- system idle'}
          </div>
        </div>

        {activeTask && (
          <>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-5)' }}>
              {[
                { k: 'Agent', v: activeTask.agent || '--', cls: 'rose' as const },
                { k: 'Model', v: activeTask.model || 'worker-standard', cls: 'mono' as const },
                { k: 'Step', v: `${Math.floor(activeTask.stepsDone)}/${activeTask.steps}`, cls: 'mono' as const },
                { k: 'Cost', v: activeTask.cost > 0 ? `$${activeTask.cost.toFixed(3)}` : '$--', cls: 'gold' as const },
              ].map(({ k, v, cls }) => (
                <span key={k} style={{ fontSize: 11, fontWeight: 300, color: 'var(--text-muted)' }}>
                  {k}{' '}
                  <span style={{
                    fontWeight: 400,
                    color:
                      cls === 'rose' ? 'var(--rose-400)' :
                      cls === 'gold' ? 'var(--gold-300)' :
                      'var(--text-secondary)',
                    fontFamily: cls === 'mono' ? 'var(--font-mono)' : undefined,
                    fontSize: cls === 'mono' ? 10.5 : undefined,
                  }}>
                    {v}
                  </span>
                </span>
              ))}
              {isEscalating && (
                <span style={{
                  fontSize: 10,
                  fontWeight: 500,
                  color: 'var(--amber-500)',
                  textTransform: 'uppercase',
                  letterSpacing: '1px',
                  padding: '2px 8px',
                  borderRadius: 'var(--r-sm)',
                  background: 'rgba(245,158,11,0.12)',
                  border: '1px solid rgba(245,158,11,0.2)',
                }}>
                  Escalated
                </span>
              )}
            </div>

            {/* Progress bar */}
            <div style={{ marginTop: 'var(--sp-3)', height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.04)', overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                borderRadius: 2,
                background: isEscalating
                  ? 'linear-gradient(90deg, var(--amber-500), var(--gold-400))'
                  : 'linear-gradient(90deg, var(--rose-600), var(--rose-400))',
                boxShadow: isEscalating
                  ? '0 0 8px rgba(245,158,11,0.2)'
                  : '0 0 8px rgba(244,63,94,0.2)',
                width: `${progressPct}%`,
                transition: 'width 1s cubic-bezier(0.16,1,0.3,1)',
                position: 'relative',
              }}>
                <div style={{
                  position: 'absolute',
                  right: 0, top: -1, bottom: -1,
                  width: 20,
                  background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.15))',
                  animation: 'shimmer 2s ease-in-out infinite',
                }} />
              </div>
            </div>
          </>
        )}
      </div>

      {/* ── Services + Recent Runs (2 columns) ───────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-3)' }}>

        {/* Services */}
        <div className="panel panel-pad">
          <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)', letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: 'var(--sp-4)' }}>
            Services
          </div>
          <ServiceRow name="Control-plane API" detail="localhost:3000" ping="ok" />
          <ServiceRow name="LiteLLM" detail="localhost:4000" ping="ok" />
          <ServiceRow name="orchestrator-flow MCP" detail="localhost:3100" ping="ok" />
          <ServiceRow name="LangFuse" detail="localhost:3010" ping="ok" />
        </div>

        {/* Recent Runs */}
        <div className="panel panel-pad">
          <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)', letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: 'var(--sp-4)' }}>
            Recent Runs
          </div>

          {/* Table header */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '8px 1fr 72px 56px 56px 56px',
            gap: 'var(--sp-3)',
            paddingBottom: 'var(--sp-2)',
            borderBottom: '1px solid var(--border-default)',
            marginBottom: 'var(--sp-1)',
          }}>
            {['', 'Goal', 'Model', 'Tasks', 'Cost', 'Time'].map((h, i) => (
              <span key={i} style={{
                fontSize: 9, fontWeight: 500,
                color: 'var(--text-dim)',
                textTransform: 'uppercase',
                letterSpacing: '1.5px',
                textAlign: i > 2 ? 'right' : undefined,
              }}>
                {h}
              </span>
            ))}
          </div>

          {/* Single run row: current sprint */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '8px 1fr 72px 56px 56px 56px',
            gap: 'var(--sp-3)',
            alignItems: 'center',
            padding: '9px 0',
            borderBottom: '1px solid rgba(255,255,255,0.02)',
            fontSize: 12,
            cursor: 'pointer',
            transition: 'background var(--t-fast)',
          }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: activeRuns > 0 ? 'var(--rose-400)' : 'var(--emerald-500)',
              animation: activeRuns > 0 ? 'pulse-live 2s ease-in-out infinite' : undefined,
            }} />
            <span style={{ fontWeight: 300, color: '#cbd5e1', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              Sprint 4 Demo Run
            </span>
            <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 10.5 }}>
              worker-standard
            </span>
            <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 10.5, textAlign: 'right' }}>
              {state.tasks.length}
            </span>
            <span style={{ fontWeight: 400, color: 'var(--gold-300)', fontFamily: 'var(--font-mono)', fontSize: 10.5, textAlign: 'right' }}>
              ${state.totalCost.toFixed(2)}
            </span>
            <span style={{ fontWeight: 300, color: 'var(--text-muted)', fontSize: 11, textAlign: 'right' }}>
              {state.elapsed > 0 ? `${state.elapsed.toFixed(0)}s` : '--'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
