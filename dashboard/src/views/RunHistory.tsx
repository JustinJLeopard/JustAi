import { useState, useEffect } from 'react'
import type { CSSProperties } from 'react'
import { fetchRuns, fetchRunStatus, triggerRun } from '../lib/api-client'
import type { RunEntry, RunStatus } from '../lib/api-client'

const card: CSSProperties = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: '10px',
  padding: '16px 20px',
}

const label: CSSProperties = {
  fontSize: '11px',
  color: 'var(--text-muted)',
  textTransform: 'uppercase' as const,
  letterSpacing: '0.5px',
}

const mono: CSSProperties = {
  fontFamily: '"IBM Plex Mono", "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
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

      {/* Run Trigger */}
      <div style={{ ...card, display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={label}>New Run</div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            type="text"
            value={goal}
            onChange={e => setGoal(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleRun()}
            placeholder="Enter goal..."
            style={{
              flex: 1,
              background: 'var(--bg-primary)',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              padding: '8px 12px',
              color: 'var(--text-primary)',
              ...mono,
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
              background: 'var(--accent-green)',
              color: 'var(--bg-primary)',
              border: 'none',
              borderRadius: '6px',
              padding: '8px 16px',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading || !goal.trim() ? 0.5 : 1,
            }}
          >
            {loading ? 'Starting...' : 'Run'}
          </button>
        </div>
        {error && (
          <div style={{ fontSize: '12px', color: 'var(--accent-red)' }}>{error}</div>
        )}
      </div>

      {/* Active Run Status */}
      {runStatus && runStatus.status !== 'idle' && (
        <div style={{
          ...card,
          borderColor: runStatus.status === 'running'
            ? 'var(--accent-blue)' : runStatus.status === 'complete'
              ? 'var(--accent-green)' : 'var(--accent-red)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={label}>Active Run</div>
              <div style={{ ...mono, color: 'var(--text-primary)', marginTop: '4px' }}>
                {runStatus.goal}
              </div>
            </div>
            <div style={{
              padding: '4px 12px',
              borderRadius: '12px',
              fontSize: '12px',
              fontWeight: 600,
              background: runStatus.status === 'running'
                ? 'rgba(97, 215, 255, 0.15)' : runStatus.status === 'complete'
                  ? 'rgba(109, 255, 152, 0.15)' : 'rgba(255, 100, 100, 0.15)',
              color: runStatus.status === 'running'
                ? 'var(--accent-blue)' : runStatus.status === 'complete'
                  ? 'var(--accent-green)' : 'var(--accent-red)',
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
      <div style={card}>
        <div style={{ ...label, marginBottom: '12px' }}>Run History</div>
        {runs.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
            No runs recorded yet.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
            {runs.map((run, i) => (
              <div
                key={run.key}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 80px 60px 60px 60px',
                  gap: '12px',
                  padding: '8px 0',
                  borderBottom: i < runs.length - 1 ? '1px solid var(--border)' : 'none',
                  alignItems: 'center',
                }}
              >
                <div style={{
                  ...mono, fontSize: '12px', color: 'var(--text-primary)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                }}>
                  {run.goal || run.key.split('/').pop()}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--accent-blue)' }}>
                  {run.intent || '—'}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textAlign: 'center' as const }}>
                  {run.tasks || '—'}
                </div>
                <div style={{
                  fontSize: '11px', textAlign: 'center' as const,
                  color: run.done === run.tasks ? 'var(--accent-green)' : 'var(--accent-red)',
                }}>
                  {run.done || '0'}/{run.tasks || '?'}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textAlign: 'right' as const }}>
                  {run.duration ? `${run.duration}s` : '—'}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
