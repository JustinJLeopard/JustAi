import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, ComposedChart, Line, CartesianGrid, Cell,
} from 'recharts'
import { fetchCostData, fetchLatencyData, fetchQualityData } from '../lib/api-client'
import type { CostData, LatencyData, QualityData } from '../lib/api-client'
import type { View } from '@/components/Sidebar'

interface ObservabilityProps {
  onNavigate?: (view: View) => void
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

// ── Stage color map ──────────────────────────────────────────────────────────
const STAGE_COLORS: Record<string, string> = {
  'intent-gate': '#f43f5e',
  'planner': '#a78bfa',
  'reviewer': '#38bdf8',
  'executor': '#34d399',
  'delegator': '#34d399',
  'synthesizer': '#fbbf24',
}

// ── Recharts custom tooltip ──────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--bg-popover)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--r-sm)',
      padding: '8px 12px',
      fontSize: 11,
      fontWeight: 400,
      color: 'var(--text-primary)',
      boxShadow: 'var(--shadow-lg)',
      backdropFilter: 'blur(24px) saturate(1.2)',
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 4, fontSize: 10 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} style={{ display: 'flex', gap: 8, justifyContent: 'space-between' }}>
          <span style={{ color: p.color }}>{p.name}</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>
            {typeof p.value === 'number' ? p.value.toFixed(p.name.includes('$') || p.name.includes('cost') ? 4 : 0) : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Failure category bar ─────────────────────────────────────────────────────
function FailureBar({ category, count, max }: { category: string; count: number; max: number }) {
  const pct = max > 0 ? (count / max) * 100 : 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 6 }}>
      <span style={{ fontSize: 11, fontWeight: 300, color: 'var(--text-secondary)', minWidth: 100 }}>{category}</span>
      <div style={{ flex: 1, height: 6, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: 'var(--red-500)', borderRadius: 3, transition: 'width 0.3s ease' }} />
      </div>
      <span style={{ fontSize: 10, fontWeight: 400, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', minWidth: 20, textAlign: 'right' }}>{count}</span>
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────
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

  // ── Stage breakdown for cost waterfall ────────────────────────────────────
  const stageCostEntries = costData?.by_stage
    ? Object.entries(costData.by_stage).sort((a, b) => b[1] - a[1])
    : []

  // ── Stage latency breakdown ───────────────────────────────────────────────
  const stageLatencyEntries = latencyData?.by_stage
    ? Object.entries(latencyData.by_stage).sort((a, b) => b[1] - a[1])
    : []

  // ── Failure categories ────────────────────────────────────────────────────
  const failureCats = qualityData?.failure_categories
    ? Object.entries(qualityData.failure_categories).sort((a, b) => b[1] - a[1])
    : []
  const maxFailures = failureCats.length > 0 ? failureCats[0][1] : 0

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
                padding: '8px 14px',
                borderRadius: 'var(--r-sm)',
                fontSize: 12, fontWeight: 400,
                cursor: 'pointer',
                transition: 'all var(--t-fast)',
                border: '1px solid var(--border-default)',
                fontFamily: 'var(--font-sans)',
                letterSpacing: '0.2px',
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
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--sp-4)' }}>

          {/* ── Cost Panel ────────────────────────────────────────────── */}
          <div className="panel panel-pad">
            <SectionLabel>Cost</SectionLabel>
            <div style={{
              fontSize: 32, fontWeight: 200, color: 'var(--gold-300)',
              fontVariantNumeric: 'tabular-nums', marginBottom: 'var(--sp-3)',
            }}>
              {hasCost ? `$${costData!.total.toFixed(2)}` : '$0.00'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 300, marginBottom: 'var(--sp-4)' }}>
              {hasCost ? `${days}d total across ${costData!.daily.length} days` : 'No cost data yet'}
            </div>

            {hasCost ? (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={costData!.daily}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 9, fill: 'var(--text-dim)' }}
                    tickFormatter={d => d.slice(5)}
                    axisLine={{ stroke: 'var(--border-subtle)' }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 9, fill: 'var(--text-dim)' }}
                    tickFormatter={v => `$${v}`}
                    axisLine={false}
                    tickLine={false}
                    width={42}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="total" name="Cost" radius={[3, 3, 0, 0]}>
                    {costData!.daily.map((_, i) => (
                      <Cell key={i} fill="var(--gold-400)" fillOpacity={0.7} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyPanel message="Run a pipeline to generate cost data" />
            )}

            {/* Stage cost waterfall */}
            {stageCostEntries.length > 0 && (
              <div style={{ marginTop: 'var(--sp-4)' }}>
                <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '1.5px', marginBottom: 'var(--sp-2)' }}>
                  By Stage
                </div>
                {stageCostEntries.map(([stage, cost]) => {
                  const pct = costData!.total > 0 ? (cost / costData!.total) * 100 : 0
                  return (
                    <div key={stage} style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 4 }}>
                      <span style={{ fontSize: 10, fontWeight: 300, color: 'var(--text-secondary)', minWidth: 80 }}>{stage}</span>
                      <div style={{ flex: 1, height: 4, background: 'var(--bg-elevated)', borderRadius: 2, overflow: 'hidden' }}>
                        <div style={{
                          height: '100%', width: `${pct}%`, borderRadius: 2,
                          background: STAGE_COLORS[stage] || 'var(--text-muted)',
                          transition: 'width 0.3s ease',
                        }} />
                      </div>
                      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--gold-300)', minWidth: 48, textAlign: 'right' }}>
                        ${cost.toFixed(4)}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* ── Latency Panel ─────────────────────────────────────────── */}
          <div className="panel panel-pad">
            <SectionLabel>Latency</SectionLabel>
            <div style={{
              fontSize: 32, fontWeight: 200, color: 'var(--text-primary)',
              fontVariantNumeric: 'tabular-nums', marginBottom: 'var(--sp-3)',
            }}>
              {hasLatency ? `${(latencyData!.avg_ms / 1000).toFixed(1)}s` : '—'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 300, marginBottom: 'var(--sp-4)' }}>
              {hasLatency
                ? `p50: ${(latencyData!.p50 / 1000).toFixed(1)}s · p90: ${(latencyData!.p90 / 1000).toFixed(1)}s · p99: ${(latencyData!.p99 / 1000).toFixed(1)}s`
                : 'No latency data yet'}
            </div>

            {hasLatency ? (
              <ResponsiveContainer width="100%" height={160}>
                <ComposedChart data={latencyData!.daily}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 9, fill: 'var(--text-dim)' }}
                    tickFormatter={d => d.slice(5)}
                    axisLine={{ stroke: 'var(--border-subtle)' }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 9, fill: 'var(--text-dim)' }}
                    tickFormatter={v => `${(v / 1000).toFixed(1)}s`}
                    axisLine={false}
                    tickLine={false}
                    width={42}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="avg_ms" name="Avg (ms)" fill="var(--rose-400)" fillOpacity={0.5} radius={[3, 3, 0, 0]} />
                  <Line dataKey="p50" name="p50" stroke="var(--emerald-400)" dot={false} strokeWidth={1.5} />
                  <Line dataKey="p90" name="p90" stroke="var(--amber-500)" dot={false} strokeWidth={1.5} strokeDasharray="4 4" />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <EmptyPanel message="Run a pipeline to generate latency data" />
            )}

            {/* Bottleneck callout */}
            {latencyData?.bottleneck && (
              <div style={{
                marginTop: 'var(--sp-4)',
                padding: '10px 14px',
                background: 'rgba(244,63,94,0.06)',
                borderRadius: 'var(--r-sm)',
                border: '1px solid rgba(244,63,94,0.1)',
                fontSize: 11, fontWeight: 300, color: 'var(--rose-300)',
              }}>
                <strong>{latencyData.bottleneck}</strong> is your bottleneck
                {latencyData.by_stage[latencyData.bottleneck]
                  ? ` — averaging ${(latencyData.by_stage[latencyData.bottleneck] / 1000).toFixed(1)}s`
                  : ''}
              </div>
            )}

            {/* Per-stage latency */}
            {stageLatencyEntries.length > 0 && (
              <div style={{ marginTop: 'var(--sp-4)' }}>
                <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '1.5px', marginBottom: 'var(--sp-2)' }}>
                  By Stage
                </div>
                {stageLatencyEntries.map(([stage, ms]) => {
                  const maxMs = stageLatencyEntries[0][1]
                  const pct = maxMs > 0 ? (ms / maxMs) * 100 : 0
                  return (
                    <div key={stage} style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 4 }}>
                      <span style={{ fontSize: 10, fontWeight: 300, color: 'var(--text-secondary)', minWidth: 80 }}>{stage}</span>
                      <div style={{ flex: 1, height: 4, background: 'var(--bg-elevated)', borderRadius: 2, overflow: 'hidden' }}>
                        <div style={{
                          height: '100%', width: `${pct}%`, borderRadius: 2,
                          background: STAGE_COLORS[stage] || 'var(--text-muted)',
                          transition: 'width 0.3s ease',
                        }} />
                      </div>
                      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', minWidth: 40, textAlign: 'right' }}>
                        {(ms / 1000).toFixed(1)}s
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* ── Quality Panel ─────────────────────────────────────────── */}
          <div className="panel panel-pad">
            <SectionLabel>Quality</SectionLabel>
            <div style={{
              fontSize: 32, fontWeight: 200,
              color: qualityData && qualityData.overall_rate >= 0.8
                ? 'var(--emerald-400)'
                : qualityData && qualityData.overall_rate >= 0.5
                  ? 'var(--amber-500)'
                  : 'var(--text-primary)',
              fontVariantNumeric: 'tabular-nums', marginBottom: 'var(--sp-3)',
            }}>
              {hasQuality ? `${(qualityData!.overall_rate * 100).toFixed(0)}%` : '—'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 300, marginBottom: 'var(--sp-4)' }}>
              {hasQuality
                ? `success rate over ${days}d`
                : 'No quality data yet'}
            </div>

            {hasQuality ? (
              <ResponsiveContainer width="100%" height={160}>
                <AreaChart data={qualityData!.daily}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 9, fill: 'var(--text-dim)' }}
                    tickFormatter={d => d.slice(5)}
                    axisLine={{ stroke: 'var(--border-subtle)' }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 9, fill: 'var(--text-dim)' }}
                    tickFormatter={v => `${(v * 100).toFixed(0)}%`}
                    domain={[0, 1]}
                    axisLine={false}
                    tickLine={false}
                    width={36}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <defs>
                    <linearGradient id="qualityGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--emerald-400)" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="var(--emerald-400)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area
                    dataKey="rate"
                    name="Success Rate"
                    stroke="var(--emerald-400)"
                    strokeWidth={2}
                    fill="url(#qualityGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <EmptyPanel message="Run a pipeline to generate quality data" />
            )}

            {/* Failure categories */}
            {failureCats.length > 0 && (
              <div style={{ marginTop: 'var(--sp-4)' }}>
                <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '1.5px', marginBottom: 'var(--sp-2)' }}>
                  Failure Categories
                </div>
                {failureCats.map(([cat, count]) => (
                  <FailureBar key={cat} category={cat} count={count} max={maxFailures} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
