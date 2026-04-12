import { useState, useEffect, useCallback } from 'react'
import { SpacetimePoller, LiveData, Task } from '@/lib/spacetime'
import { MissionControl } from '@/views/MissionControl'
import { TaskBoard } from '@/views/TaskBoard'
import { TrajectoryViewer } from '@/views/TrajectoryViewer'
import { MemoryBrowser } from '@/views/MemoryBrowser'
import { RunHistory } from '@/views/RunHistory'

type View = 'mission-control' | 'task-board' | 'runs' | 'trajectories' | 'memory'

const NAV_ITEMS: { id: View; label: string; icon: string }[] = [
  { id: 'mission-control', label: 'Mission Control', icon: '⬡' },
  { id: 'task-board',      label: 'Task Board',      icon: '⊞' },
  { id: 'runs',            label: 'Runs',             icon: '▶' },
  { id: 'trajectories',    label: 'Trajectories',    icon: '⇥' },
  { id: 'memory',          label: 'Memory',           icon: '⧫' },
]

const EMPTY_DATA: LiveData = {
  tasks: [], agents: [], events: [],
  connected: false, lastUpdated: null, error: null,
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

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      overflow: 'hidden',
      background: 'var(--bg-primary)',
    }}>
      {/* Sidebar */}
      <nav style={{
        width: '200px',
        flexShrink: 0,
        background: 'var(--bg-secondary)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        padding: '20px 0',
      }}>
        {/* Logo */}
        <div style={{ padding: '0 20px 24px' }}>
          <div style={{ fontSize: '18px', fontWeight: 800, letterSpacing: '-0.5px' }}>
            <span style={{ color: 'var(--accent-blue)' }}>Just</span>
            <span style={{ color: 'var(--text-primary)' }}>Ai</span>
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px', letterSpacing: '1px', textTransform: 'uppercase' }}>
            Orchestrator
          </div>
        </div>

        {/* Nav items */}
        <div style={{ flex: 1 }}>
          {NAV_ITEMS.map(item => {
            const active = view === item.id
            return (
              <button
                key={item.id}
                onClick={() => setView(item.id)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '10px 20px',
                  background: active ? 'var(--bg-card)' : 'transparent',
                  border: 'none',
                  borderLeft: active ? '2px solid var(--accent-blue)' : '2px solid transparent',
                  color: active ? 'var(--text-primary)' : 'var(--text-muted)',
                  fontSize: '13px',
                  fontWeight: active ? 600 : 400,
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.1s',
                }}
              >
                <span style={{ fontSize: '16px', opacity: 0.8 }}>{item.icon}</span>
                {item.label}
              </button>
            )
          })}
        </div>

        {/* Connection status */}
        <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{
              width: '6px', height: '6px', borderRadius: '50%',
              background: data.connected ? 'var(--accent-green)' : 'var(--accent-red)',
              boxShadow: data.connected ? '0 0 5px var(--accent-green)' : 'none',
            }} />
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              {data.connected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main style={{
        flex: 1,
        overflow: 'auto',
        padding: '28px 32px',
      }}>
        {/* Page header */}
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{
            margin: 0,
            fontSize: '20px',
            fontWeight: 700,
            color: 'var(--text-primary)',
          }}>
            {NAV_ITEMS.find(n => n.id === view)?.label}
          </h1>
        </div>

        {/* View */}
        {view === 'mission-control' && (
          <MissionControl data={data} />
        )}
        {view === 'task-board' && (
          <TaskBoard data={data} onTaskClick={setSelectedTask} />
        )}
        {view === 'trajectories' && (
          <TrajectoryViewer />
        )}
        {view === 'memory' && (
          <MemoryBrowser />
        )}
      </main>

      {/* Task detail panel (only for task-board view) */}
      {selectedTask && view === 'task-board' && (
        <aside style={{
          width: '360px',
          flexShrink: 0,
          background: 'var(--bg-secondary)',
          borderLeft: '1px solid var(--border)',
          overflow: 'auto',
          padding: '24px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px' }}>
            <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 600 }}>Task Detail</h2>
            <button
              onClick={() => setSelectedTask(null)}
              style={{
                marginLeft: 'auto', background: 'none', border: 'none',
                color: 'var(--text-muted)', cursor: 'pointer', fontSize: '18px', padding: '2px 6px',
              }}
            >
              ✕
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {[
              { label: 'ID', value: `#${selectedTask.id}` },
              { label: 'Status', value: selectedTask.status },
              { label: 'From', value: selectedTask.fromAgent || '—' },
              { label: 'To', value: selectedTask.toAgent || '—' },
              { label: 'Session', value: selectedTask.sessionRef || '—' },
              { label: 'Retries', value: String(selectedTask.retryCount) },
            ].map(({ label, value }) => (
              <div key={label}>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: '4px' }}>
                  {label}
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{value}</div>
              </div>
            ))}

            <div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: '6px' }}>
                Payload
              </div>
              <div style={{
                fontSize: '12px', color: 'var(--text-secondary)',
                background: 'var(--bg-card)', borderRadius: '6px',
                padding: '10px', border: '1px solid var(--border)',
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                maxHeight: '200px', overflowY: 'auto',
              }}>
                {selectedTask.payload}
              </div>
            </div>

            {selectedTask.result && (
              <div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: '6px' }}>
                  Result
                </div>
                <div style={{
                  fontSize: '12px',
                  color: selectedTask.status === 'done' ? 'var(--accent-green)' : 'var(--accent-red)',
                  background: 'var(--bg-card)', borderRadius: '6px',
                  padding: '10px', border: '1px solid var(--border)',
                  whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  maxHeight: '200px', overflowY: 'auto',
                }}>
                  {selectedTask.result}
                </div>
              </div>
            )}
          </div>
        </aside>
      )}
    </div>
  )
}
