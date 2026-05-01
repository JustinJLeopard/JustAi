/**
 * JustAi Demo — Observability View
 *
 * Cost, latency, and quality metrics from simulated LangFuse traces.
 * Uses Recharts for chart rendering, matching the real Observability view
 * styling and patterns.
 */

import { useState, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { COST_SERIES, LATENCY_SERIES } from '../data/sprint-timeline'
import type { SimulationState } from '../data/types'

// ── Props ───────────────────────────────────────────────────────────────────

export interface DemoObservabilityProps {
  state: SimulationState
}

// ── Model-to-color mapping ──────────────────────────────────────────────────

const MODEL_COLORS: Record<string, string> = {
  'orchestrator-large': '#f43f5e',  // rose
  'worker-standard': '#38bdf8',          // sky
}

// Task -> model mapping derived from the sprint timeline
const TASK_MODEL: Record<string, string> = {
  'T1': 'orchestrator-large',
  'T2': 'worker-standard',
  'T3': 'worker-standard',
  'T4': 'orchestrator-large',  // escalated
  'T5': 'worker-standard',
  'T6': 'worker-standard',
  'T7': 'worker-standard',
  'T8': 'worker-standard',
}

// ── Section label ───────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: string }) {
  return (
    <div style={{
      fontSize: 10, fontWeight: 500,
      color: 'var(--text-muted)',
      textTransform: 'uppercase',
      letterSpacing: '1.8px',
      marginBottom: 'var(--sp-3)',
    }}>
      {children}
    </div>
  )
}

// ── Chart tooltip ───────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--bg-popover, #1e1e2e)',
      border: '1px solid var(--border-default, rgba(255,255,255,0.08))',
      borderRadius: 'var(--r-sm, 6px)',
      padding: '8px 12px',
      fontSize: 11, fontWeight: 400,
      color: 'var(--text-primary, #e2e8f0)',
      boxShadow: 'var(--shadow-lg, 0 8px 32px rgba(0,0,0,0.4))',
      backdropFilter: 'blur(24px) saturate(1.2)',
      maxWidth: 280,
    }}>
      <div style={{ color: 'var(--text-muted, #64748b)', marginBottom: 4, fontSize: 10 }}>
        {label}
      </div>
      {payload.map((p: any) => (
        <div key={p.dataKey || p.name} style={{
          display: 'flex', gap: 8, justifyContent: 'space-between',
        }}>
          <span style={{ color: p.color || p.fill }}>{p.name}</span>
          <span style={{
            fontFamily: 'var(--font-mono, monospace)',
            fontVariantNumeric: 'tabular-nums',
          }}>
            {typeof p.value === 'number'
              ? p.name?.toLowerCase().includes('cost')
                ? `$${p.value.toFixed(3)}`
                : `${p.value.toFixed(1)}s`
              : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function DemoObservability({ state }: DemoObservabilityProps) {
  const [days, setDays] = useState<7 | 30>(7)

  // ── Derive visible data from elapsed time ───────────────────────────────

  const visibleCost = useMemo(
    () => COST_SERIES.filter(d => d.time <= state.elapsed),
    [state.elapsed],
  )

  const visibleLatency = useMemo(
    () => LATENCY_SERIES.filter(d => d.time <= state.elapsed),
    [state.elapsed],
  )

  // Derive per-task cost (COST_SERIES is cumulative)
  const costChartData = useMemo(() => {
    return visibleCost.map((point, i) => {
      const prevCost = i > 0 ? visibleCost[i - 1].cost : 0
      const taskCost = +(point.cost - prevCost).toFixed(3)
      const taskKey = point.label.split(':')[0].trim()  // "T1", "T2", etc.
      const model = TASK_MODEL[taskKey] || 'worker-standard'
      return {
        label: point.label,
        cost: taskCost,
        model,
        fill: MODEL_COLORS[model] || '#38bdf8',
      }
    })
  }, [visibleCost])

  // Latency chart data
  const latencyChartData = useMemo(() => {
    return visibleLatency.map(point => ({
      label: point.label,
      latency: point.latency,
    }))
  }, [visibleLatency])

  // ── Computed metrics ────────────────────────────────────────────────────

  const totalCost = visibleCost.length > 0
    ? visibleCost[visibleCost.length - 1].cost
    : 0

  const completedCount = visibleCost.length

  const avgLatency = visibleLatency.length > 0
    ? visibleLatency.reduce((sum, d) => sum + d.latency, 0) / visibleLatency.length
    : 0

  const sortedLatencies = useMemo(() => {
    const vals = visibleLatency.map(d => d.latency).sort((a, b) => a - b)
    return vals
  }, [visibleLatency])

  const p50 = sortedLatencies.length > 0
    ? sortedLatencies[Math.floor(sortedLatencies.length * 0.5)]
    : 0
  const p90 = sortedLatencies.length > 0
    ? sortedLatencies[Math.floor(sortedLatencies.length * 0.9)]
    : 0
  const p99 = sortedLatencies.length > 0
    ? sortedLatencies[Math.min(sortedLatencies.length - 1, Math.floor(sortedLatencies.length * 0.99))]
    : 0

  // Quality: all completed tasks pass review in this demo (100% success)
  const totalTasks = state.tasks.length
  const passedCount = state.tasks.filter(t => t.status === 'done').length
  const successRate = totalTasks > 0 && passedCount > 0
    ? (passedCount / totalTasks) * 100
    : completedCount > 0 ? 100 : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6, 24px)' }}>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{
            fontSize: 22, fontWeight: 200,
            color: 'var(--text-primary)',
            letterSpacing: '0.3px', margin: 0,
          }}>
            Observability
          </h1>
          <p style={{
            fontSize: 12, color: 'var(--text-muted)',
            marginTop: 5, fontWeight: 300,
          }}>
            Cost, latency, and quality metrics from LangFuse traces
          </p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--sp-2, 8px)' }}>
          {([7, 30] as const).map(d => (
            <button
              key={d}
              onClick={() => setDays(d)}
              style={{
                padding: '8px 14px', borderRadius: 'var(--r-sm, 6px)',
                fontSize: 12, fontWeight: 400, cursor: 'pointer',
                transition: 'all var(--t-fast, 0.15s)',
                border: '1px solid var(--border-default, rgba(255,255,255,0.08))',
                fontFamily: 'var(--font-sans, inherit)', letterSpacing: '0.2px',
                background: days === d
                  ? 'var(--bg-elevated, rgba(255,255,255,0.06))'
                  : 'var(--bg-surface, rgba(255,255,255,0.02))',
                color: days === d
                  ? 'var(--text-primary, #e2e8f0)'
                  : 'var(--text-secondary, #94a3b8)',
                borderColor: days === d
                  ? 'var(--border-hover, rgba(255,255,255,0.15))'
                  : 'var(--border-default, rgba(255,255,255,0.08))',
              }}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* ── Three main panels (Cost / Latency / Quality) ─────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 1fr',
        gap: 'var(--sp-4, 16px)',
      }}>

        {/* ═══ COST PANEL ═══ */}
        <div className="panel panel-pad">
          <SectionLabel>Cost</SectionLabel>
          <div style={{
            fontSize: 32, fontWeight: 200,
            color: 'var(--gold-400, #f59e0b)',
            fontVariantNumeric: 'tabular-nums',
            marginBottom: 'var(--sp-1, 4px)',
          }}>
            ${totalCost.toFixed(2)}
          </div>
          <div style={{
            fontSize: 11, color: 'var(--text-muted)',
            fontWeight: 300, marginBottom: 'var(--sp-4, 16px)',
          }}>
            {completedCount} task{completedCount !== 1 ? 's' : ''} completed
          </div>

          {costChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={costChartData}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.06)"
                />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 9, fill: '#475569' }}
                  tickFormatter={(v: string) => v.split(':')[0].trim()}
                  axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 9, fill: '#475569' }}
                  tickFormatter={(v: number) => `$${v}`}
                  axisLine={false}
                  tickLine={false}
                  width={42}
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar
                  dataKey="cost"
                  name="Cost"
                  radius={[3, 3, 0, 0]}
                  fillOpacity={0.75}
                  shape={(props: any) => {
                    const { x, y, width, height, payload } = props
                    return (
                      <rect
                        x={x}
                        y={y}
                        width={width}
                        height={height}
                        rx={3}
                        ry={3}
                        fill={payload.fill}
                        fillOpacity={0.75}
                      />
                    )
                  }}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{
              textAlign: 'center', padding: '32px 16px',
              color: 'var(--text-muted)', fontWeight: 300, fontSize: 13,
            }}>
              Waiting for tasks to complete...
            </div>
          )}

          {/* Model legend */}
          {costChartData.length > 0 && (
            <div style={{
              display: 'flex', gap: 16, marginTop: 'var(--sp-3, 12px)',
              fontSize: 10, color: 'var(--text-muted)',
            }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{
                  width: 8, height: 8, borderRadius: 2,
                  background: MODEL_COLORS['orchestrator-large'],
                  display: 'inline-block',
                }} />
                orchestrator
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{
                  width: 8, height: 8, borderRadius: 2,
                  background: MODEL_COLORS['worker-standard'],
                  display: 'inline-block',
                }} />
                worker-standard
              </span>
            </div>
          )}
        </div>

        {/* ═══ LATENCY PANEL ═══ */}
        <div className="panel panel-pad">
          <SectionLabel>Latency</SectionLabel>
          <div style={{
            fontSize: 32, fontWeight: 200,
            color: 'var(--text-primary)',
            fontVariantNumeric: 'tabular-nums',
            marginBottom: 'var(--sp-1, 4px)',
          }}>
            {visibleLatency.length > 0 ? `${avgLatency.toFixed(1)}s` : '\u2014'}
          </div>
          <div style={{
            fontSize: 11, color: 'var(--text-muted)',
            fontWeight: 300, marginBottom: 'var(--sp-4, 16px)',
          }}>
            {visibleLatency.length > 0
              ? `p50: ${p50.toFixed(1)}s \u00B7 p90: ${p90.toFixed(1)}s \u00B7 p99: ${p99.toFixed(1)}s`
              : 'No latency data yet'}
          </div>

          {latencyChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={latencyChartData}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.06)"
                />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 9, fill: '#475569' }}
                  tickFormatter={(v: string) => v.split(':')[0].trim()}
                  axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 9, fill: '#475569' }}
                  tickFormatter={(v: number) => `${v.toFixed(1)}s`}
                  axisLine={false}
                  tickLine={false}
                  width={42}
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar
                  dataKey="latency"
                  name="Latency"
                  fill="#f43f5e"
                  fillOpacity={0.6}
                  radius={[3, 3, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{
              textAlign: 'center', padding: '32px 16px',
              color: 'var(--text-muted)', fontWeight: 300, fontSize: 13,
            }}>
              Waiting for tasks to complete...
            </div>
          )}
        </div>

        {/* ═══ QUALITY PANEL ═══ */}
        <div className="panel panel-pad">
          <SectionLabel>Quality</SectionLabel>
          <div style={{
            fontSize: 32, fontWeight: 200,
            color: completedCount > 0 && successRate >= 80
              ? 'var(--emerald-400, #34d399)'
              : completedCount > 0 && successRate >= 50
                ? 'var(--amber-500, #f59e0b)'
                : 'var(--text-primary)',
            fontVariantNumeric: 'tabular-nums',
            marginBottom: 'var(--sp-1, 4px)',
          }}>
            {completedCount > 0 ? `${successRate.toFixed(0)}%` : '\u2014'}
          </div>
          <div style={{
            fontSize: 11, color: 'var(--text-muted)',
            fontWeight: 300, marginBottom: 'var(--sp-4, 16px)',
          }}>
            {completedCount > 0
              ? `${passedCount}/${totalTasks} tasks passed review`
              : 'No quality data yet'}
          </div>

          {/* Success rate visual bar */}
          {completedCount > 0 ? (
            <div>
              {/* Overall bar */}
              <div style={{
                height: 32, borderRadius: 6, overflow: 'hidden',
                background: 'var(--bg-elevated, rgba(255,255,255,0.03))',
                position: 'relative',
              }}>
                <div style={{
                  height: '100%',
                  width: `${successRate}%`,
                  borderRadius: 6,
                  background: successRate >= 80
                    ? 'linear-gradient(90deg, rgba(52,211,153,0.3), rgba(52,211,153,0.6))'
                    : successRate >= 50
                      ? 'linear-gradient(90deg, rgba(245,158,11,0.3), rgba(245,158,11,0.6))'
                      : 'linear-gradient(90deg, rgba(239,68,68,0.3), rgba(239,68,68,0.6))',
                  transition: 'width 0.5s ease',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }} />
                <div style={{
                  position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 400,
                  color: 'var(--text-primary, #e2e8f0)',
                  letterSpacing: '0.5px',
                }}>
                  {passedCount} passed / {totalTasks - passedCount} remaining
                </div>
              </div>

              {/* Per-task status dots */}
              <div style={{
                display: 'flex', gap: 6, marginTop: 'var(--sp-3, 12px)',
                justifyContent: 'center',
              }}>
                {state.tasks.map(task => (
                  <div
                    key={task.id}
                    title={`${task.name}: ${task.status}`}
                    style={{
                      width: 12, height: 12, borderRadius: '50%',
                      background: task.status === 'done'
                        ? 'var(--emerald-400, #34d399)'
                        : task.status === 'failed'
                          ? 'var(--red-500, #ef4444)'
                          : task.status === 'in_progress'
                            ? 'var(--amber-500, #f59e0b)'
                            : 'var(--bg-elevated, rgba(255,255,255,0.06))',
                      border: '1px solid rgba(255,255,255,0.1)',
                      transition: 'background 0.3s ease',
                    }}
                  />
                ))}
              </div>
              <div style={{
                display: 'flex', gap: 12, marginTop: 8,
                justifyContent: 'center',
                fontSize: 9, color: 'var(--text-dim, #64748b)',
              }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: '#34d399', display: 'inline-block',
                  }} />
                  done
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: '#f59e0b', display: 'inline-block',
                  }} />
                  running
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: 'rgba(255,255,255,0.06)', display: 'inline-block',
                    border: '1px solid rgba(255,255,255,0.1)',
                  }} />
                  pending
                </span>
              </div>
            </div>
          ) : (
            <div style={{
              textAlign: 'center', padding: '32px 16px',
              color: 'var(--text-muted)', fontWeight: 300, fontSize: 13,
            }}>
              Waiting for tasks to complete...
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
