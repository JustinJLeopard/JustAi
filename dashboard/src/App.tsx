import { useState, useEffect, useCallback } from 'react'
import { SpacetimePoller, LiveData, Task } from '@/lib/spacetime'
import { Sidebar } from '@/components/Sidebar'
import type { View } from '@/components/Sidebar'
import { useKeyboard } from '@/hooks/useKeyboard'
import { MissionControl } from '@/views/MissionControl'
import { TaskBoard } from '@/views/TaskBoard'
import { TrajectoryViewer } from '@/views/TrajectoryViewer'
import { MemoryBrowser } from '@/views/MemoryBrowser'
import { RunHistory } from '@/views/RunHistory'
import AgentRegistry from '@/views/AgentRegistry'

const EMPTY_DATA: LiveData = {
  tasks: [], agents: [], events: [],
  connected: false, lastUpdated: null, error: null,
}

function PlaceholderView({ name, description }: { name: string; description: string }) {
  return (
    <div>
      <div style={{ marginBottom: 'var(--sp-6)' }}>
        <h1 style={{ fontSize: 22, fontWeight: 200, color: 'var(--text-primary)', letterSpacing: 0.3 }}>{name}</h1>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 5, fontWeight: 300 }}>{description}</p>
      </div>
      <div
        className="panel panel-pad"
        style={{
          textAlign: 'center',
          padding: 'var(--sp-10)',
          color: 'var(--text-muted)',
          fontWeight: 300,
          fontSize: 14,
        }}
      >
        {description}
      </div>
    </div>
  )
}

export default function App() {
  const [view, setView] = useState<View>('mission-control')
  const [data, setData] = useState<LiveData>(EMPTY_DATA)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)

  const handleData = useCallback((incoming: LiveData) => {
    setData(incoming)
  }, [])

  useEffect(() => {
    const poller = new SpacetimePoller(handleData)
    poller.start(3000)
    return () => poller.stop()
  }, [handleData])

  const handleNavigate = useCallback((v: View) => {
    setView(v)
    if (v !== 'task-board') setSelectedTask(null)
  }, [])

  const handleBack = useCallback(() => {
    setSelectedTask(null)
  }, [])

  useKeyboard(handleNavigate, selectedTask ? handleBack : undefined)

  // Compute sidebar counts from live data
  const activeTasks = data.tasks.filter(t => t.status === 'running' || t.status === 'claimed').length
  const counts: Partial<Record<View, number>> = {
    'task-board': activeTasks > 0 ? activeTasks : undefined,
    'runs': data.events.length > 0 ? data.events.length : undefined,
    'agents': data.agents.length > 0 ? data.agents.length : undefined,
  } as Partial<Record<View, number>>

  // Remove undefined entries
  Object.keys(counts).forEach(k => {
    if (counts[k as View] === undefined) delete counts[k as View]
  })

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '232px 1fr',
        height: '100vh',
        overflow: 'hidden',
        background: 'var(--bg-primary)',
      }}
    >
      <Sidebar activeView={view} onNavigate={handleNavigate} counts={counts} />

      <div style={{ display: 'flex', overflow: 'hidden' }}>
        {/* Main content */}
        <main
          style={{
            flex: 1,
            overflow: 'auto',
            padding: '28px 32px',
          }}
        >
          <div key={view} style={{ animation: 'fadeIn 0.2s cubic-bezier(0.16,1,0.3,1)' }}>
            {view === 'mission-control' && <MissionControl data={data} />}
            {view === 'task-board' && <TaskBoard data={data} onTaskClick={setSelectedTask} />}
            {view === 'runs' && <RunHistory />}
            {view === 'trajectories' && <TrajectoryViewer />}
            {view === 'memory' && <MemoryBrowser />}
            {view === 'observability' && <PlaceholderView name="Observability" description="Coming in Slice 2" />}
            {view === 'agents' && <AgentRegistry data={data} />}
          </div>
        </main>

        {/* Task detail panel (only for task-board view) */}
        {selectedTask && view === 'task-board' && (
          <aside
            style={{
              width: 360,
              flexShrink: 0,
              background: 'var(--bg-surface)',
              borderLeft: '1px solid var(--border-subtle)',
              overflow: 'auto',
              padding: 'var(--sp-6)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 'var(--sp-5)' }}>
              <h2 style={{ margin: 0, fontSize: 15, fontWeight: 300, color: 'var(--text-primary)', letterSpacing: 0.3 }}>
                Task Detail
              </h2>
              <button
                onClick={() => setSelectedTask(null)}
                style={{
                  marginLeft: 'auto',
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-dim)',
                  cursor: 'pointer',
                  fontSize: 16,
                  padding: '2px 6px',
                  lineHeight: 1,
                }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>
              {[
                { label: 'ID', value: `#${selectedTask.id}` },
                { label: 'Status', value: selectedTask.status },
                { label: 'From', value: selectedTask.fromAgent || '—' },
                { label: 'To', value: selectedTask.toAgent || '—' },
                { label: 'Session', value: selectedTask.sessionRef || '—' },
                { label: 'Retries', value: String(selectedTask.retryCount) },
              ].map(({ label, value }) => (
                <div key={label}>
                  <div
                    style={{
                      fontSize: 10,
                      color: 'var(--text-dim)',
                      textTransform: 'uppercase',
                      letterSpacing: 1.5,
                      marginBottom: 4,
                      fontWeight: 500,
                    }}
                  >
                    {label}
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 300 }}>{value}</div>
                </div>
              ))}

              <div>
                <div
                  style={{
                    fontSize: 10,
                    color: 'var(--text-dim)',
                    textTransform: 'uppercase',
                    letterSpacing: 1.5,
                    marginBottom: 6,
                    fontWeight: 500,
                  }}
                >
                  Payload
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: 'var(--text-secondary)',
                    background: 'var(--bg-card)',
                    borderRadius: 6,
                    padding: 10,
                    border: '1px solid var(--border-subtle)',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    maxHeight: 200,
                    overflowY: 'auto',
                    fontWeight: 300,
                  }}
                >
                  {selectedTask.payload}
                </div>
              </div>

              {selectedTask.result && (
                <div>
                  <div
                    style={{
                      fontSize: 10,
                      color: 'var(--text-dim)',
                      textTransform: 'uppercase',
                      letterSpacing: 1.5,
                      marginBottom: 6,
                      fontWeight: 500,
                    }}
                  >
                    Result
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: selectedTask.status === 'done' ? 'var(--emerald-500)' : 'var(--rose-500)',
                      background: 'var(--bg-card)',
                      borderRadius: 6,
                      padding: 10,
                      border: '1px solid var(--border-subtle)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      maxHeight: 200,
                      overflowY: 'auto',
                      fontWeight: 300,
                    }}
                  >
                    {selectedTask.result}
                  </div>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>

      {/* Fade-in keyframe */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}
