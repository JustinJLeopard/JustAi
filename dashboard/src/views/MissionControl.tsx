import { useState, useEffect } from 'react'
import { LiveData, msAgo } from '@/lib/spacetime'
import { fetchHealth, fetchRuns, fetchObservabilitySummary } from '../lib/api-client'
import type { HealthData, RunEntry, ObservabilitySummary } from '../lib/api-client'
import { MetricCard } from '@/components/MetricCard'
import { Pipeline } from '@/components/Pipeline'
import type { PipelineStage } from '@/components/Pipeline'
import { PopoverTitle, PopoverRow, PopoverDivider } from '@/components/Popover'

interface MissionControlProps {
  data: LiveData
  onNavigate?: (view: import('@/components/Sidebar').View) => void
}

// ── Time range button ─────────────────────────────────────────────────────────
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

// ── Service row ───────────────────────────────────────────────────────────────
function ServiceRow({ name, ok, detail, ping }: { name: string; ok: boolean | null; detail: string; ping: string }) {
  const dotColor =
    ok === true  ? 'var(--emerald-500)' :
    ok === false ? 'var(--red-500)' :
    'var(--amber-500)'
  const dotShadow =
    ok === true  ? '0 0 6px var(--emerald-glow)' :
    ok === false ? '0 0 6px rgba(239,68,68,0.2)' :
    '0 0 6px rgba(245,158,11,0.2)'

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

// ── Run row ───────────────────────────────────────────────────────────────────
type RunStatus = 'ok' | 'err' | 'run'

function RunRow({ run, status }: { run: RunEntry; status: RunStatus }) {
  const dotColor = status === 'ok' ? 'var(--emerald-500)' : status === 'err' ? 'var(--red-500)' : 'var(--rose-400)'
  const animation = status === 'run' ? 'pulse-live 2s ease-in-out infinite' : undefined

  return (
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
      <div style={{ width: 6, height: 6, borderRadius: '50%', background: dotColor, animation }} />
      <span style={{ fontWeight: 300, color: '#cbd5e1', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {run.goal ?? '—'}
      </span>
      <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 10.5 }}>
        {run.intent ?? 'gpt-5.4'}
      </span>
      <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 10.5, textAlign: 'right' }}>
        {run.tasks ?? '—'}
      </span>
      <span style={{ fontWeight: 400, color: 'var(--gold-300)', fontFamily: 'var(--font-mono)', fontSize: 10.5, textAlign: 'right' }}>—</span>
      <span style={{ fontWeight: 300, color: 'var(--text-muted)', fontSize: 11, textAlign: 'right' }}>
        {run.duration ?? '—'}
      </span>
    </div>
  )
}

// ── Scope tab ─────────────────────────────────────────────────────────────────
function ScopeTab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '7px 16px',
        borderRadius: 4,
        fontSize: 12, fontWeight: 400,
        color: active ? 'var(--text-primary)' : 'var(--text-muted)',
        cursor: 'pointer',
        transition: 'all var(--t-fast)',
        letterSpacing: '0.2px',
        background: active ? 'var(--bg-elevated)' : 'transparent',
        border: 'none',
        boxShadow: active ? 'var(--shadow-sm)' : 'none',
        fontFamily: 'var(--font-sans)',
      }}
    >
      {label}
    </button>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export function MissionControl({ data, onNavigate }: MissionControlProps) {
  const { tasks, agents, connected, lastUpdated, error } = data
  const [health, setHealth] = useState<HealthData | null>(null)
  const [runs, setRuns] = useState<RunEntry[]>([])
  const [timeRange, setTimeRange] = useState<'24h' | '7d' | '30d'>('24h')
  const [scopeTab, setScopeTab] = useState<'run' | 'sprint'>('run')
  const [secondsAgo, setSecondsAgo] = useState(0)
  const [obsSummary, setObsSummary] = useState<ObservabilitySummary | null>(null)

  // ── Data loading ──────────────────────────────────────────────────────────
  useEffect(() => {
    const load = () => {
      fetchHealth().then(setHealth).catch(() => {})
      fetchRuns(10).then(setRuns).catch(() => {})
    }
    load()
    const id = setInterval(load, 10_000)
    return () => clearInterval(id)
  }, [])

  // ── Observability data (30s poll — slower than SpacetimeDB) ───────────────
  useEffect(() => {
    const loadObs = () => {
      fetchObservabilitySummary().then(setObsSummary).catch(() => {})
    }
    loadObs()
    const id = setInterval(loadObs, 30_000)
    return () => clearInterval(id)
  }, [])

  // ── Live "N seconds ago" counter ──────────────────────────────────────────
  useEffect(() => {
    const tick = setInterval(() => {
      if (lastUpdated) {
        setSecondsAgo(Math.floor((Date.now() - lastUpdated.getTime()) / 1000))
      }
    }, 1000)
    return () => clearInterval(tick)
  }, [lastUpdated])

  // ── Derived data ──────────────────────────────────────────────────────────
  const activeTasks = tasks.filter(t => t.status === 'in_progress' || t.status === 'claimed')
  const doneTasks   = tasks.filter(t => t.status === 'done')
  const failedTasks = tasks.filter(t => t.status === 'failed')
  const onlineAgents = agents.filter(a => a.status === 'online')

  const total = doneTasks.length + failedTasks.length
  const successRate = total > 0 ? Math.round((doneTasks.length / total) * 100) : null

  const litellmSvc  = health?.services.find(s => s.name === 'LiteLLM')
  const stdbSvc     = health?.services.find(s => s.name === 'SpacetimeDB')
  const mcpSvc      = health?.services.find(s => s.name === 'claude-flow MCP')
  const langfuseSvc = health?.services.find(s => s.name === 'LangFuse')

  // ── Pipeline stages ───────────────────────────────────────────────────────
  const pipelineStages: PipelineStage[] = (() => {
    if (activeTasks.length === 0) {
      return [
        { name: 'Intent',     status: 'waiting', detail: 'idle' },
        { name: 'Plan',       status: 'waiting', detail: 'idle' },
        { name: 'Review',     status: 'waiting', detail: 'idle' },
        { name: 'Execute',    status: 'waiting', detail: 'idle' },
        { name: 'Synthesize', status: 'waiting', detail: 'idle' },
      ]
    }
    // Derive stage from task statuses
    const hasRunning = tasks.some(t => t.status === 'in_progress')
    const hasDone    = doneTasks.length > 0
    return [
      { name: 'Intent',     status: hasDone || hasRunning ? 'done'    : 'active',  detail: hasDone ? 'multi-step' : 'parsing' },
      { name: 'Plan',       status: hasDone || hasRunning ? 'done'    : 'waiting', detail: hasDone ? `${tasks.length} tasks` : '—' },
      { name: 'Review',     status: hasRunning             ? 'active'  : hasDone ? 'done' : 'waiting', detail: hasRunning ? 'live' : '—' },
      { name: 'Execute',    status: hasRunning             ? 'active'  : hasDone ? 'done' : 'waiting', detail: hasRunning ? `${activeTasks.length} running` : '—' },
      { name: 'Synthesize', status: hasDone && !hasRunning ? 'active'  : 'waiting', detail: hasDone ? 'compiling' : '—' },
    ]
  })()

  // ── Active task (first in_progress or claimed) ────────────────────────────
  const activeTask = activeTasks[0] ?? null
  const progressPct = activeTask
    ? Math.min(95, Math.max(5, (doneTasks.length / Math.max(tasks.length, 1)) * 100))
    : 0

  // ── Gantt tasks (up to 6 for display) ─────────────────────────────────────
  const ganttTasks = tasks.slice(0, 6)

  // ── Sparkline data (active/done from task counts, cost/latency from observability API)
  const activeSparkline = [0, 1, 2, 1, 3, 2, activeTasks.length]
  const doneSparkline   = [0, 0, 1, 2, 3, doneTasks.length - 1, doneTasks.length].map(v => Math.max(0, v))

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
              Live
              {lastUpdated && ` · Updated ${secondsAgo}s ago`}
              {` · ${onlineAgents.length} agent${onlineAgents.length !== 1 ? 's' : ''} active`}
            </span>
            {error && <span style={{ color: 'var(--red-500)', marginLeft: 4 }}>⚠ {error}</span>}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'center' }}>
          {(['24h', '7d', '30d'] as const).map(r => (
            <TimeRangeBtn key={r} label={r} active={timeRange === r} onClick={() => setTimeRange(r)} />
          ))}
          <button style={{
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
          }}>
            + New Run
          </button>
        </div>
      </div>

      {/* ── Metrics Grid (5 columns) ─────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 'var(--sp-3)' }}>
        <MetricCard
          label="Active Runs"
          value={String(activeTasks.length)}
          color="var(--rose-400)"
          trend={activeTasks.length > 0 ? `${activeTasks.length} running` : 'idle'}
          trendDirection={activeTasks.length > 0 ? 'up' : 'flat'}
          sparklinePoints={activeSparkline}
          sparklineColor="var(--rose-500)"
          popoverContent={
            <>
              <PopoverTitle>Active Runs</PopoverTitle>
              <PopoverRow label="In progress" value={String(tasks.filter(t => t.status === 'in_progress').length)} color="var(--rose-400)" />
              <PopoverRow label="Claimed" value={String(tasks.filter(t => t.status === 'claimed').length)} color="var(--rose-300)" />
              <PopoverDivider />
              <PopoverRow label="Total tasks" value={String(tasks.length)} />
            </>
          }
        />

        <MetricCard
          label="Completed"
          value={String(doneTasks.length)}
          color="var(--emerald-400)"
          trend={doneTasks.length > 0 ? `↑ ${doneTasks.length} total` : 'none yet'}
          trendDirection={doneTasks.length > 0 ? 'up' : 'flat'}
          sparklinePoints={doneSparkline}
          sparklineColor="var(--emerald-500)"
          popoverContent={
            <>
              <PopoverTitle>Completed</PopoverTitle>
              <PopoverRow label="Done" value={String(doneTasks.length)} color="var(--emerald-400)" />
              <PopoverRow label="Failed" value={String(failedTasks.length)} color="var(--red-500)" />
              <PopoverDivider />
              <PopoverRow label="Archived" value={String(tasks.filter(t => t.status === 'archived').length)} />
            </>
          }
        />

        <MetricCard
          label="Success Rate"
          value={successRate !== null ? `${successRate}%` : '—'}
          color="var(--text-primary)"
          trend={total > 0 ? `${total} evaluated` : 'no data'}
          trendDirection={successRate !== null && successRate >= 80 ? 'up' : successRate !== null ? 'down' : 'flat'}
          popoverContent={
            <>
              <PopoverTitle>Success Rate</PopoverTitle>
              <PopoverRow label="Done" value={String(doneTasks.length)} color="var(--emerald-400)" />
              <PopoverRow label="Failed" value={String(failedTasks.length)} color="var(--red-500)" />
              <PopoverDivider />
              <PopoverRow label="Rate" value={successRate !== null ? `${successRate}%` : '—'} />
            </>
          }
        />

        <MetricCard
          label="Cost (24h)"
          value={obsSummary && obsSummary.cost_24h > 0 ? `$${obsSummary.cost_24h.toFixed(2)}` : '$—'}
          color="var(--gold-300)"
          trend={obsSummary && obsSummary.cost_24h > 0
            ? `avg $${(obsSummary.cost_24h / Math.max(obsSummary.cost_trend.length, 1)).toFixed(2)}/run`
            : 'no data yet'}
          trendDirection={obsSummary && obsSummary.cost_24h > 0 ? 'flat' : 'flat'}
          sparklinePoints={obsSummary?.cost_trend?.length ? obsSummary.cost_trend : undefined}
          sparklineColor="var(--gold-400)"
          popoverContent={
            <>
              <PopoverTitle>Cost</PopoverTitle>
              <PopoverRow label="24h total" value={obsSummary ? `$${obsSummary.cost_24h.toFixed(4)}` : '—'} color="var(--gold-300)" />
              <PopoverDivider />
              <PopoverRow label="Input tokens" value={obsSummary ? obsSummary.input_tokens.toLocaleString() : '—'} />
              <PopoverRow label="Output tokens" value={obsSummary ? obsSummary.output_tokens.toLocaleString() : '—'} />
              <PopoverDivider />
              {onNavigate && (
                <div
                  onClick={() => onNavigate('observability')}
                  style={{ fontSize: 10, color: 'var(--rose-400)', cursor: 'pointer', marginTop: 4, fontWeight: 400 }}
                >
                  View details →
                </div>
              )}
            </>
          }
        />

        <MetricCard
          label="Avg Latency"
          value={obsSummary && obsSummary.avg_latency_ms > 0 ? `${(obsSummary.avg_latency_ms / 1000).toFixed(1)}s` : '—'}
          color="var(--text-primary)"
          trend={obsSummary && obsSummary.avg_latency_ms > 0 ? 'across pipeline' : 'no data yet'}
          trendDirection={obsSummary && obsSummary.avg_latency_ms > 0 ? 'flat' : 'flat'}
          sparklinePoints={obsSummary?.latency_trend?.length ? obsSummary.latency_trend : undefined}
          sparklineColor="var(--rose-400)"
          popoverContent={
            <>
              <PopoverTitle>Latency</PopoverTitle>
              <PopoverRow label="p50" value={obsSummary && obsSummary.p50 > 0 ? `${(obsSummary.p50 / 1000).toFixed(1)}s` : '—'} />
              <PopoverRow label="p90" value={obsSummary && obsSummary.p90 > 0 ? `${(obsSummary.p90 / 1000).toFixed(1)}s` : '—'} />
              <PopoverDivider />
              <PopoverRow label="Avg" value={obsSummary && obsSummary.avg_latency_ms > 0 ? `${(obsSummary.avg_latency_ms / 1000).toFixed(1)}s` : '—'} />
              {onNavigate && (
                <div
                  onClick={() => onNavigate('observability')}
                  style={{ fontSize: 10, color: 'var(--rose-400)', cursor: 'pointer', marginTop: 4, fontWeight: 400 }}
                >
                  View details →
                </div>
              )}
            </>
          }
        />
      </div>

      {/* ── Active Pipeline Panel ────────────────────────────────────────── */}
      <div className="panel panel-pad">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-4)' }}>
          <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)', letterSpacing: '1.5px', textTransform: 'uppercase' }}>
            Active Pipeline
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
              animation: activeTasks.length > 0 ? 'pulse-live 2s ease-in-out infinite' : undefined,
              opacity: activeTasks.length > 0 ? 1 : 0.3,
            }} />
            Run #{doneTasks.length + activeTasks.length} · {activeTasks.length > 0 ? 'Live' : 'Idle'}
          </div>
        </div>

        <Pipeline stages={pipelineStages} />

        {/* Task detail bar */}
        <div style={{
          padding: 'var(--sp-4)',
          borderRadius: 'var(--r-md)',
          background: 'rgba(0,0,0,0.3)',
          border: '1px solid rgba(255,255,255,0.025)',
        }}>
          <div style={{ fontSize: 14, fontWeight: 300, color: 'var(--text-primary)', lineHeight: 1.55, marginBottom: 'var(--sp-3)' }}>
            {activeTask
              ? (activeTask.title || activeTask.payload.slice(0, 120))
              : 'No active task — system idle'}
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-5)' }}>
            {[
              { k: 'Agent',      v: activeTask?.claimedBy || '—',         cls: 'rose' },
              { k: 'Model',      v: 'gpt-5.4',                             cls: 'mono' },
              { k: 'Step',       v: activeTask ? String(activeTask.attemptNumber + 1) : '—', cls: 'mono' },
              { k: 'Tokens',     v: '—',                                   cls: 'mono' },
              { k: 'Cost',       v: '$—',                                   cls: 'gold' },
              { k: 'Checkpoint', v: activeTask?.sessionRef || '—',          cls: 'mono' },
            ].map(({ k, v, cls }) => (
              <span key={k} style={{ fontSize: 11, fontWeight: 300, color: 'var(--text-muted)' }}>
                {k}{' '}
                <span style={{
                  fontWeight: 400,
                  color:
                    cls === 'rose' ? 'var(--rose-400)' :
                    cls === 'gold' ? 'var(--gold-300)' :
                    cls === 'green' ? 'var(--emerald-400)' :
                    'var(--text-secondary)',
                  fontFamily: cls === 'mono' ? 'var(--font-mono)' : undefined,
                  fontSize: cls === 'mono' ? 10.5 : undefined,
                }}>
                  {v}
                </span>
              </span>
            ))}
          </div>

          {/* Progress bar */}
          {activeTask && (
            <div style={{ marginTop: 'var(--sp-3)', height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.04)', overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                borderRadius: 2,
                background: 'linear-gradient(90deg, var(--rose-600), var(--rose-400))',
                boxShadow: '0 0 8px rgba(244,63,94,0.2)',
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
          )}
        </div>
      </div>

      {/* ── Services + Recent Runs ────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-3)' }}>

        {/* Services */}
        <div className="panel panel-pad">
          <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)', letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: 'var(--sp-4)' }}>
            Services
          </div>
          <ServiceRow
            name="SpacetimeDB"
            ok={connected ? true : false}
            detail={connected ? 'relay-room-dev' : 'disconnected'}
            ping={connected ? '—' : 'err'}
          />
          <ServiceRow
            name="LiteLLM"
            ok={litellmSvc?.ok ?? null}
            detail={litellmSvc?.detail ?? 'localhost:4000'}
            ping={litellmSvc?.ok ? 'ok' : '—'}
          />
          <ServiceRow
            name="claude-flow MCP"
            ok={mcpSvc?.ok ?? null}
            detail={mcpSvc?.detail ?? 'localhost:3100'}
            ping={mcpSvc?.ok ? 'ok' : '—'}
          />
          <ServiceRow
            name="LangFuse"
            ok={langfuseSvc?.ok ?? null}
            detail={langfuseSvc?.detail ?? 'not configured'}
            ping="—"
          />
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

          {runs.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: 'var(--sp-4) 0' }}>
              No runs recorded yet.
            </div>
          ) : (
            runs.slice(0, 5).map((run, i) => (
              <RunRow
                key={run.key ?? i}
                run={run}
                status={run.failed && Number(run.failed) > 0 ? 'err' : 'ok'}
              />
            ))
          )}
        </div>
      </div>

      {/* ── Pipeline Scope Visualization ─────────────────────────────────── */}
      <div style={{ marginTop: 'var(--sp-3)' }}>
        {/* Scope tabs */}
        <div style={{
          display: 'flex', gap: 2,
          marginBottom: 'var(--sp-5)',
          background: 'rgba(255,255,255,0.015)',
          borderRadius: 'var(--r-sm)',
          padding: 3,
          width: 'fit-content',
        }}>
          <ScopeTab label="This Run" active={scopeTab === 'run'} onClick={() => setScopeTab('run')} />
          <ScopeTab label="Sprint 11" active={scopeTab === 'sprint'} onClick={() => setScopeTab('sprint')} />
        </div>

        <div className="panel panel-pad">
          {/* Gantt header */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '180px 1fr',
            gap: 'var(--sp-4)',
            marginBottom: 'var(--sp-4)',
            paddingBottom: 'var(--sp-3)',
            borderBottom: '1px solid var(--border-subtle)',
          }}>
            <span style={{ fontSize: 10, fontWeight: 500, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '1.5px' }}>Task</span>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              {['0s', '15s', '30s', '45s', '60s'].map(t => (
                <span key={t} style={{ fontSize: 9, fontWeight: 400, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.5px' }}>{t}</span>
              ))}
            </div>
          </div>

          {/* Gantt rows */}
          {ganttTasks.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: 'var(--sp-4) 0' }}>No tasks in this run.</div>
          ) : (
            ganttTasks.map((task, i) => {
              const barStatus =
                task.status === 'done'        ? 'done' :
                task.status === 'in_progress' ? 'running' :
                'queued'

              const barPct =
                task.status === 'done'        ? Math.min(100, 30 + i * 12) :
                task.status === 'in_progress' ? Math.min(85, 15 + i * 10) :
                Math.min(40, i * 8)

              const barBg =
                barStatus === 'done'    ? 'rgba(16,185,129,0.15)'  :
                barStatus === 'running' ? 'rgba(244,63,94,0.12)'   :
                'rgba(255,255,255,0.03)'

              const barBorder =
                barStatus === 'done'    ? '1px solid rgba(16,185,129,0.25)' :
                barStatus === 'running' ? '1px solid rgba(244,63,94,0.2)'   :
                '1px solid rgba(255,255,255,0.04)'

              const barTextColor =
                barStatus === 'done'    ? 'var(--emerald-400)' :
                barStatus === 'running' ? 'var(--rose-400)'    :
                'var(--text-dim)'

              return (
                <div key={task.id.toString()} style={{
                  display: 'grid',
                  gridTemplateColumns: '180px 1fr',
                  gap: 'var(--sp-4)',
                  alignItems: 'center',
                  marginBottom: 'var(--sp-2)',
                  padding: 'var(--sp-2) 0',
                }}>
                  <span style={{ fontSize: 12, fontWeight: 300, color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)', marginRight: 'var(--sp-2)' }}>
                      #{String(i + 1).padStart(2, '0')}
                    </span>
                    {task.title || task.payload.slice(0, 40)}
                  </span>

                  <div style={{
                    height: 28,
                    background: 'rgba(255,255,255,0.015)',
                    borderRadius: 'var(--r-sm)',
                    position: 'relative',
                    overflow: 'hidden',
                  }}>
                    <div style={{
                      position: 'absolute',
                      top: 3, bottom: 3,
                      left: 0,
                      width: `${barPct}%`,
                      borderRadius: 4,
                      background: barBg,
                      border: barBorder,
                      display: 'flex',
                      alignItems: 'center',
                      padding: '0 var(--sp-2)',
                      transition: 'width 1.5s cubic-bezier(0.16,1,0.3,1)',
                    }}>
                      <span style={{ fontSize: 10, fontWeight: 400, fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap', color: barTextColor }}>
                        {task.status}
                      </span>
                    </div>
                  </div>
                </div>
              )
            })
          )}

          {/* ETA footer */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 'var(--sp-4)',
            marginTop: 'var(--sp-5)',
            padding: 'var(--sp-4)',
            borderRadius: 'var(--r-md)',
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
          }}>
            <div>
              <span style={{ fontSize: 22, fontWeight: 200, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>—</span>
              <span style={{ fontSize: 14, color: 'var(--text-muted)', fontWeight: 300, marginLeft: 4 }}>eta</span>
            </div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 300, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
                {activeTasks.length > 0
                  ? `${activeTasks.length} task${activeTasks.length !== 1 ? 's' : ''} running · ETA will show when tasks report progress`
                  : 'No active tasks'}
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                {lastUpdated ? `last sync ${msAgo(BigInt(lastUpdated.getTime()))}` : 'not connected'}
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>
  )
}
