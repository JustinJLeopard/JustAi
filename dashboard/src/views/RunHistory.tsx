import { useState, useEffect } from 'react'
import type { CSSProperties } from 'react'
import { fetchRuns, fetchRunStatus, triggerRun } from '../lib/api-client'
import type { RunEntry, RunStatus } from '../lib/api-client'

const panel: CSSProperties = {
  background: 'var(--bg-surface)',
  border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--r-md)',
  padding: '16px 20px',
}

const colHeader: CSSProperties = {
  fontSize: '9px',
  color: 'var(--text-tertiary)',
  textTransform: 'uppercase' as const,
  letterSpacing: '0.8px',
  fontWeight: 600,
}

const monoStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: '13px',
}

export function RunHistory() {
  const [runs, setRuns] = useState<RunEntry[]>([])
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null)
  const [goal, setGoal] = useState('')
  const [autoMode, setAutoMode] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [r, s] = await Promise.all([fetchRuns(15), fetchRunStatus()])
        setRuns(r)
        setRunStatus(s)
        setError(null)
      } catch (e) {
        setError('API server unavailable. Start with: python3 -m justai.api')
      }
    }
    load()
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [])

  const handleRun = async () => {
    if (!goal.trim()) return
    setLoading(true)
    try {
      const result = await triggerRun(goal, autoMode)
      if (result.error) {
        setError(result.error)
      } else {
        setGoal('')
        setError(null)
      }
    } catch (e) {
      setError('Failed to trigger run')
    }
    setLoading(false)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

      {/* Page Header */}
      <div>
        <div style={{ fontSize: '22px', fontWeight: 200, color: 'var(--text-primary)', letterSpacing: '-0.3px' }}>
          Run History
        </div>
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          {runs.length} run{runs.length !== 1 ? 's' : ''} recorded
        </div>
      </div>

      {/* Run Trigger */}
      <div style={{ ...panel, display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={colHeader}>New Run</div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            type="text"
            value={goal}
            onChange={e => setGoal(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleRun()}
            placeholder="Enter goal..."
            style={{
              flex: 1,
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--r-sm)',
              padding: '8px 12px',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)',
              fontSize: '13px',
              outline: 'none',
            }}
          />
          <label style={{
            display: 'flex', alignItems: 'center', gap: '4px',
            fontSize: '12px', color: 'var(--text-secondary)',
          }}>
            <input
              type="checkbox"
              checked={autoMode}
              onChange={e => setAutoMode(e.target.checked)}
            />
            Auto
          </label>
          <button
            onClick={handleRun}
            disabled={loading || !goal.trim()}
            style={{
              background: 'rgba(244,63,94,0.1)',
              color: 'var(--rose-400)',
              border: '1px solid rgba(244,63,94,0.2)',
              borderRadius: 'var(--r-sm)',
              padding: '8px 16px',
              fontWeight: 600,
              fontSize: '13px',
              cursor: loading || !goal.trim() ? 'not-allowed' : 'pointer',
              opacity: loading || !goal.trim() ? 0.5 : 1,
              transition: 'opacity var(--t-fast)',
            }}
          >
            {loading ? 'Starting...' : 'Run'}
          </button>
        </div>
        {error && (
          <div style={{ fontSize: '12px', color: 'var(--red-500)' }}>{error}</div>
        )}
      </div>

      {/* Active Run Status */}
      {runStatus && runStatus.status !== 'idle' && (
        <div style={{
          ...panel,
          borderColor: runStatus.status === 'running'
            ? 'rgba(244,63,94,0.3)' : runStatus.status === 'complete'
              ? 'rgba(52,211,153,0.3)' : 'rgba(239,68,68,0.3)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={colHeader}>Active Run</div>
              <div style={{ ...monoStyle, color: 'var(--text-primary)', marginTop: '4px', fontWeight: 300 }}>
                {runStatus.goal}
              </div>
            </div>
            <div style={{
              padding: '4px 12px',
              borderRadius: '12px',
              fontSize: '12px',
              fontWeight: 600,
              background: runStatus.status === 'running'
                ? 'var(--rose-glow)' : runStatus.status === 'complete'
                  ? 'var(--emerald-glow)' : 'rgba(239,68,68,0.12)',
              color: runStatus.status === 'running'
                ? 'var(--rose-400)' : runStatus.status === 'complete'
                  ? 'var(--emerald-400)' : 'var(--red-500)',
            }}>
              {runStatus.status}
            </div>
          </div>
          {runStatus.task_count !== undefined && (
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '8px' }}>
              {runStatus.task_count} tasks | {runStatus.duration?.toFixed(0)}s
            </div>
          )}
        </div>
      )}

      {/* Run History Table */}
      <div style={panel}>
        {/* Table Header */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 80px 60px 60px 60px',
          gap: '12px',
          padding: '0 0 8px',
          borderBottom: '1px solid var(--border-subtle)',
          marginBottom: '4px',
        }}>
          <div style={colHeader}>Goal</div>
          <div style={colHeader}>Intent</div>
          <div style={{ ...colHeader, textAlign: 'center' as const }}>Tasks</div>
          <div style={{ ...colHeader, textAlign: 'center' as const }}>Done</div>
          <div style={{ ...colHeader, textAlign: 'right' as const }}>Duration</div>
        </div>

        {runs.length === 0 ? (
          <div style={{ color: 'var(--text-tertiary)', fontSize: '13px', padding: '12px 0' }}>
            No runs recorded yet.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
            {runs.map((run, i) => {
              const isSuccess = run.done === run.tasks
              const statusColor = isSuccess ? 'var(--emerald-400)' : 'var(--red-500)'
              return (
                <div
                  key={run.key}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 80px 60px 60px 60px',
                    gap: '12px',
                    padding: '8px 0',
                    borderBottom: i < runs.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                    alignItems: 'center',
                  }}
                >
                  {/* Goal with status dot */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
                    <div style={{
                      width: '5px', height: '5px', borderRadius: '50%',
                      flexShrink: 0,
                      background: statusColor,
                    }} />
                    <div style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '13px',
                      fontWeight: 300,
                      color: 'var(--text-primary)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                    }}>
                      {run.goal || run.key.split('/').pop()}
                    </div>
                  </div>

                  {/* Intent */}
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                    {run.intent || '—'}
                  </div>

                  {/* Task count */}
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textAlign: 'center' as const, fontFamily: 'var(--font-mono)' }}>
                    {run.tasks || '—'}
                  </div>

                  {/* Done/total */}
                  <div style={{
                    fontSize: '11px', textAlign: 'center' as const,
                    color: statusColor,
                    fontFamily: 'var(--font-mono)',
                  }}>
                    {run.done || '0'}/{run.tasks || '?'}
                  </div>

                  {/* Duration */}
                  <div style={{
                    fontSize: '11px', color: 'var(--gold-300)',
                    textAlign: 'right' as const,
                    fontFamily: 'var(--font-mono)',
                  }}>
                    {run.duration ? `${run.duration}s` : '—'}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
