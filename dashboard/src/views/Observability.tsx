import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, ComposedChart, Line, CartesianGrid,
  ScatterChart, Scatter, ZAxis, Legend,
} from 'recharts'
import { fetchCostData, fetchLatencyData, fetchQualityData } from '../lib/api-client'
import type { CostData, LatencyData, QualityData } from '../lib/api-client'
import type { View } from '@/components/Sidebar'

interface ObservabilityProps {
  onNavigate?: (view: View) => void
}

// ── Shared colors ────────────────────────────────────────────────────────────
const MODEL_COLORS = [
  '#f43f5e', '#a78bfa', '#38bdf8', '#34d399', '#fbbf24',
  '#fb923c', '#e879f9', '#22d3ee', '#a3e635', '#f472b6',
]

const STAGE_COLORS: Record<string, string> = {
  'intent-gate': '#f43f5e',
  'planner': '#a78bfa',
  'reviewer': '#38bdf8',
  'executor': '#34d399',
  'delegator': '#34d399',
  'synthesizer': '#fbbf24',
}

// ── Section label ────────────────────────────────────────────────────────────
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

// ── Empty state ──────────────────────────────────────────────────────────────
function EmptyPanel({ message }: { message: string }) {
  return (
    <div style={{
      textAlign: 'center',
      padding: 'var(--sp-8) var(--sp-4)',
      color: 'var(--text-muted)',
      fontWeight: 300,
      fontSize: 13,
    }}>
      {message}
    </div>
  )
}

// ── Chart tooltip ────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--bg-popover)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--r-sm)',
      padding: '8px 12px',
      fontSize: 11, fontWeight: 400,
      color: 'var(--text-primary)',
      boxShadow: 'var(--shadow-lg)',
      backdropFilter: 'blur(24px) saturate(1.2)',
      maxWidth: 280,
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 4, fontSize: 10 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey || p.name} style={{ display: 'flex', gap: 8, justifyContent: 'space-between' }}>
          <span style={{ color: p.color || p.fill }}>{p.name}</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>
            {typeof p.value === 'number'
              ? (p.name?.toLowerCase().includes('cost') || p.name?.startsWith('$')
                ? `$${p.value.toFixed(4)}`
                : p.name?.toLowerCase().includes('rate')
                  ? `${(p.value * 100).toFixed(0)}%`
                  : p.value.toFixed(p.value < 10 ? 2 : 0))
              : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Stage bar (horizontal) ───────────────────────────────────────────────────
function StageBar({ stage, value, max, unit, color }: {
  stage: string; value: number; max: number; unit: string; color?: string
}) {
  const pct = max > 0 ? (value / max) * 100 : 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 4 }}>
      <span style={{ fontSize: 10, fontWeight: 300, color: 'var(--text-secondary)', minWidth: 80 }}>{stage}</span>
      <div style={{ flex: 1, height: 4, background: 'var(--bg-elevated)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${pct}%`, borderRadius: 2,
          background: color || STAGE_COLORS[stage] || 'var(--text-muted)',
          transition: 'width 0.3s ease',
        }} />
      </div>
      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', minWidth: 52, textAlign: 'right' }}>
        {unit === '$' ? `$${value.toFixed(4)}` : unit === 'ms' ? `${(value / 1000).toFixed(1)}s` : String(value)}
      </span>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function Observability({ onNavigate }: ObservabilityProps) {
  const [days, setDays] = useState<7 | 30>(7)
  const [costData, setCostData] = useState<CostData | null>(null)
  const [latencyData, setLatencyData] = useState<LatencyData | null>(null)
  const [qualityData, setQualityData] = useState<QualityData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      fetchCostData(days).catch(() => null),
      fetchLatencyData(days).catch(() => null),
      fetchQualityData(days).catch(() => null),
    ]).then(([c, l, q]) => {
      setCostData(c)
      setLatencyData(l)
      setQualityData(q)
      setLoading(false)
    })
  }, [days])

  // Refresh every 60s
  useEffect(() => {
    const id = setInterval(() => {
      Promise.all([
        fetchCostData(days).catch(() => null),
        fetchLatencyData(days).catch(() => null),
        fetchQualityData(days).catch(() => null),
      ]).then(([c, l, q]) => {
        if (c) setCostData(c)
        if (l) setLatencyData(l)
        if (q) setQualityData(q)
      })
    }, 60_000)
    return () => clearInterval(id)
  }, [days])

  const hasCost = costData && costData.daily.length > 0
  const hasLatency = latencyData && latencyData.daily.length > 0
  const hasQuality = qualityData && qualityData.daily.length > 0

  // All unique models for stacked bars
  const models = costData?.models || []

  // Stage entries for waterfalls
  const stageCostEntries = costData?.by_stage
    ? Object.entries(costData.by_stage).sort((a, b) => b[1] - a[1])
    : []
  const stageLatencyEntries = latencyData?.by_stage
    ? Object.entries(latencyData.by_stage).sort((a, b) => b[1] - a[1])
    : []

  // Failure categories
  const failureCats = qualityData?.failure_categories
    ? Object.entries(qualityData.failure_categories).sort((a, b) => b[1] - a[1])
    : []
  const maxFailures = failureCats.length > 0 ? failureCats[0][1] : 0

  const handleBarClick = (_data: any) => {
    if (onNavigate) onNavigate('runs')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 200, color: 'var(--text-primary)', letterSpacing: '0.3px', margin: 0 }}>
            Observability
          </h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 5, fontWeight: 300 }}>
            Cost, latency, and quality metrics from LangFuse traces
          </p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
          {([7, 30] as const).map(d => (
            <button
              key={d}
              onClick={() => setDays(d)}
              style={{
                padding: '8px 14px', borderRadius: 'var(--r-sm)',
                fontSize: 12, fontWeight: 400, cursor: 'pointer',
                transition: 'all var(--t-fast)',
                border: '1px solid var(--border-default)',
                fontFamily: 'var(--font-sans)', letterSpacing: '0.2px',
                background: days === d ? 'var(--bg-elevated)' : 'var(--bg-surface)',
                color: days === d ? 'var(--text-primary)' : 'var(--text-secondary)',
                borderColor: days === d ? 'var(--border-hover)' : 'var(--border-default)',
              }}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="panel panel-pad" style={{ textAlign: 'center', padding: 'var(--sp-10)', color: 'var(--text-muted)', fontWeight: 300, fontSize: 13 }}>
          Loading observability data...
        </div>
      )}

      {!loading && (
        <>
          {/* ── Three main panels (Cost / Latency / Quality) ─────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--sp-4)' }}>

            {/* ═══ COST PANEL ═══ */}
            <div className="panel panel-pad">
              <SectionLabel>Cost</SectionLabel>
              <div style={{
                fontSize: 32, fontWeight: 200, color: 'var(--gold-300)',
                fontVariantNumeric: 'tabular-nums', marginBottom: 'var(--sp-1)',
              }}>
                {hasCost ? `$${costData!.total.toFixed(2)}` : '$0.00'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 300, marginBottom: 'var(--sp-4)' }}>
                {hasCost
                  ? `${days}d total · ${costData!.input_tokens.toLocaleString()} in / ${costData!.output_tokens.toLocaleString()} out tokens`
                  : 'No cost data yet'}
              </div>

              {hasCost ? (
                <>
                  {/* Stacked bar chart by model + running total line */}
                  <ResponsiveContainer width="100%" height={160}>
                    <ComposedChart data={costData!.daily} onClick={handleBarClick} style={{ cursor: 'pointer' }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                      <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--text-dim)' }} tickFormatter={d => d.slice(5)} axisLine={{ stroke: 'var(--border-subtle)' }} tickLine={false} />
                      <YAxis yAxisId="cost" tick={{ fontSize: 9, fill: 'var(--text-dim)' }} tickFormatter={v => `$${v}`} axisLine={false} tickLine={false} width={42} />
                      <YAxis yAxisId="total" orientation="right" tick={{ fontSize: 9, fill: 'var(--text-dim)' }} tickFormatter={v => `$${v}`} axisLine={false} tickLine={false} width={42} hide />
                      <Tooltip content={<ChartTooltip />} />
                      {models.map((model, i) => (
                        <Bar
                          key={model}
                          yAxisId="cost"
                          dataKey={`by_model.${model}`}
                          name={model.split('/').pop() || model}
                          stackId="cost"
                          fill={MODEL_COLORS[i % MODEL_COLORS.length]}
                          fillOpacity={0.7}
                          radius={i === models.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]}
                        />
                      ))}
                      <Line yAxisId="cost" dataKey="running_total" name="Running Total" stroke="var(--gold-400)" dot={false} strokeWidth={1.5} strokeDasharray="4 4" />
                    </ComposedChart>
                  </ResponsiveContainer>

                  {/* Per-stage waterfall */}
                  {stageCostEntries.length > 0 && (
                    <div style={{ marginTop: 'var(--sp-4)' }}>
                      <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '1.5px', marginBottom: 'var(--sp-2)' }}>
                        By Stage
                      </div>
                      {stageCostEntries.map(([stage, cost]) => (
                        <StageBar key={stage} stage={stage} value={cost} max={costData!.total} unit="$" />
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <EmptyPanel message="Run a pipeline to generate cost data" />
              )}
            </div>

            {/* ═══ LATENCY PANEL ═══ */}
            <div className="panel panel-pad">
              <SectionLabel>Latency</SectionLabel>
              <div style={{
                fontSize: 32, fontWeight: 200, color: 'var(--text-primary)',
                fontVariantNumeric: 'tabular-nums', marginBottom: 'var(--sp-1)',
              }}>
                {hasLatency ? `${(latencyData!.avg_ms / 1000).toFixed(1)}s` : '—'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 300, marginBottom: 'var(--sp-4)' }}>
                {hasLatency
                  ? `p50: ${(latencyData!.p50 / 1000).toFixed(1)}s · p90: ${(latencyData!.p90 / 1000).toFixed(1)}s · p99: ${(latencyData!.p99 / 1000).toFixed(1)}s`
                  : 'No latency data yet'}
              </div>

              {hasLatency ? (
                <>
                  <ResponsiveContainer width="100%" height={160}>
                    <ComposedChart data={latencyData!.daily} onClick={handleBarClick} style={{ cursor: 'pointer' }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                      <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--text-dim)' }} tickFormatter={d => d.slice(5)} axisLine={{ stroke: 'var(--border-subtle)' }} tickLine={false} />
                      <YAxis tick={{ fontSize: 9, fill: 'var(--text-dim)' }} tickFormatter={v => `${(v / 1000).toFixed(1)}s`} axisLine={false} tickLine={false} width={42} />
                      <Tooltip content={<ChartTooltip />} />
                      <Bar dataKey="avg_ms" name="Avg (ms)" fill="var(--rose-400)" fillOpacity={0.5} radius={[3, 3, 0, 0]} />
                      <Line dataKey="p50" name="p50" stroke="var(--emerald-400)" dot={false} strokeWidth={1.5} />
                      <Line dataKey="p90" name="p90" stroke="var(--amber-500)" dot={false} strokeWidth={1.5} strokeDasharray="4 4" />
                      <Line dataKey="p99" name="p99" stroke="var(--red-500)" dot={false} strokeWidth={1} strokeDasharray="2 4" />
                    </ComposedChart>
                  </ResponsiveContainer>

                  {/* Bottleneck callout */}
                  {latencyData?.bottleneck && (
                    <div style={{
                      marginTop: 'var(--sp-4)', padding: '10px 14px',
                      background: 'rgba(244,63,94,0.06)', borderRadius: 'var(--r-sm)',
                      border: '1px solid rgba(244,63,94,0.1)',
                      fontSize: 11, fontWeight: 300, color: 'var(--rose-300)',
                    }}>
                      <strong>{latencyData.bottleneck}</strong> is your bottleneck
                      {latencyData.by_stage[latencyData.bottleneck] != null && (
                        <>
                          {' '}— averaging {(latencyData.by_stage[latencyData.bottleneck] / 1000).toFixed(1)}s
                          {latencyData.avg_ms > 0 && (
                            <>, {Math.round((latencyData.by_stage[latencyData.bottleneck] / latencyData.avg_ms) * 100)}% of total</>
                          )}
                        </>
                      )}
                    </div>
                  )}

                  {/* Per-stage breakdown */}
                  {stageLatencyEntries.length > 0 && (
                    <div style={{ marginTop: 'var(--sp-4)' }}>
                      <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '1.5px', marginBottom: 'var(--sp-2)' }}>
                        By Stage
                      </div>
                      {stageLatencyEntries.map(([stage, ms]) => (
                        <StageBar key={stage} stage={stage} value={ms} max={stageLatencyEntries[0][1]} unit="ms" />
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <EmptyPanel message="Run a pipeline to generate latency data" />
              )}
            </div>

            {/* ═══ QUALITY PANEL ═══ */}
            <div className="panel panel-pad">
              <SectionLabel>Quality</SectionLabel>
              <div style={{
                fontSize: 32, fontWeight: 200,
                color: qualityData && qualityData.overall_rate >= 0.8
                  ? 'var(--emerald-400)'
                  : qualityData && qualityData.overall_rate >= 0.5
                    ? 'var(--amber-500)'
                    : 'var(--text-primary)',
                fontVariantNumeric: 'tabular-nums', marginBottom: 'var(--sp-1)',
              }}>
                {hasQuality ? `${(qualityData!.overall_rate * 100).toFixed(0)}%` : '—'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 300, marginBottom: 'var(--sp-4)' }}>
                {hasQuality
                  ? `success rate · ${qualityData!.first_try_total} first-try · ${qualityData!.retry_total} after retry`
                  : 'No quality data yet'}
              </div>

              {hasQuality ? (
                <>
                  {/* Success rate + first-try vs retry stacked area */}
                  <ResponsiveContainer width="100%" height={160}>
                    <AreaChart data={qualityData!.daily} onClick={handleBarClick} style={{ cursor: 'pointer' }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                      <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--text-dim)' }} tickFormatter={d => d.slice(5)} axisLine={{ stroke: 'var(--border-subtle)' }} tickLine={false} />
                      <YAxis tick={{ fontSize: 9, fill: 'var(--text-dim)' }} domain={[0, 'auto']} axisLine={false} tickLine={false} width={30} />
                      <Tooltip content={<ChartTooltip />} />
                      <defs>
                        <linearGradient id="firstTryGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="var(--emerald-400)" stopOpacity={0.4} />
                          <stop offset="100%" stopColor="var(--emerald-400)" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="retryGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="var(--amber-500)" stopOpacity={0.3} />
                          <stop offset="100%" stopColor="var(--amber-500)" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <Area dataKey="first_try" name="First Try" stackId="quality" stroke="var(--emerald-400)" strokeWidth={2} fill="url(#firstTryGrad)" />
                      <Area dataKey="retry" name="After Retry" stackId="quality" stroke="var(--amber-500)" strokeWidth={1.5} fill="url(#retryGrad)" />
                      <Area dataKey="failed" name="Failed" stackId="quality" stroke="var(--red-500)" strokeWidth={1} fill="rgba(239,68,68,0.1)" />
                    </AreaChart>
                  </ResponsiveContainer>

                  {/* AI-generated insight */}
                  {qualityData!.ai_insight && (
                    <div style={{
                      marginTop: 'var(--sp-4)', padding: '10px 14px',
                      background: 'rgba(16,185,129,0.04)', borderRadius: 'var(--r-sm)',
                      border: '1px solid rgba(16,185,129,0.08)',
                      fontSize: 11, fontWeight: 300, color: 'var(--text-secondary)', lineHeight: 1.5,
                    }}>
                      <div style={{ fontSize: 9, fontWeight: 600, color: 'var(--emerald-400)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 4 }}>
                        AI Insight
                      </div>
                      {qualityData!.ai_insight}
                    </div>
                  )}

                  {/* Failure categories */}
                  {failureCats.length > 0 && (
                    <div style={{ marginTop: 'var(--sp-4)' }}>
                      <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '1.5px', marginBottom: 'var(--sp-2)' }}>
                        Failure Categories
                      </div>
                      {failureCats.map(([cat, count]) => (
                        <StageBar key={cat} stage={cat} value={count} max={maxFailures} unit="" color="var(--red-500)" />
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <EmptyPanel message="Run a pipeline to generate quality data" />
              )}
            </div>
          </div>

          {/* ── Cost vs Quality Scatter (full width) ────────────────── */}
          {qualityData && qualityData.cost_quality.length >= 3 && (
            <div className="panel panel-pad">
              <SectionLabel>Cost vs Quality Correlation</SectionLabel>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 300, marginBottom: 'var(--sp-3)' }}>
                Are expensive runs more successful?
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <ScatterChart>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                  <XAxis dataKey="cost" name="Cost" tick={{ fontSize: 9, fill: 'var(--text-dim)' }} tickFormatter={v => `$${v}`} axisLine={{ stroke: 'var(--border-subtle)' }} tickLine={false} />
                  <YAxis dataKey="success" name="Success" tick={{ fontSize: 9, fill: 'var(--text-dim)' }} domain={[-0.1, 1.1]} ticks={[0, 1]} tickFormatter={v => v === 1 ? 'Pass' : v === 0 ? 'Fail' : ''} axisLine={false} tickLine={false} width={36} />
                  <ZAxis range={[40, 40]} />
                  <Tooltip content={<ChartTooltip />} />
                  <Scatter data={qualityData.cost_quality} fill="var(--rose-400)" fillOpacity={0.6} />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  )
}
