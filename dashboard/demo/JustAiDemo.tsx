/**
 * JustAi Demo — Top-Level Component
 *
 * Wires together the sidebar, sprint bar, simulation engine, and view routing.
 * This is the root of the self-contained interactive demo — no network calls,
 * no backend dependencies. Everything runs from the simulation state machine.
 *
 * Layout: CSS Grid
 *   - Top row (full width): SprintBar with simulation controls
 *   - Left column: DemoSidebar with nav + badge counts
 *   - Main area: active view component with fadeIn on view change
 */

import { useState, useMemo } from 'react'

import type { DemoView } from './data/types'
import { useSimulation } from './hooks/useSimulation'
import { DemoSidebar } from './components/DemoSidebar'
import { SprintBar } from './components/SprintBar'

import { DemoMissionControl } from './views/DemoMissionControl'
import { DemoTaskBoard } from './views/DemoTaskBoard'
import { DemoRunHistory } from './views/DemoRunHistory'
import { DemoTrajectories } from './views/DemoTrajectories'
import { DemoMemory } from './views/DemoMemory'
import { DemoObservability } from './views/DemoObservability'
import { DemoAgents } from './views/DemoAgents'
import { WritingPage } from './views/WritingPage'

import './styles/demo-theme.css'

// ── Component ───────────────────────────────────────────────────────────────

export default function JustAiDemo() {
  if (window.location.pathname.replace(/\/$/, '') === '/writing') {
    return <WritingPage />
  }

  const { state, controls } = useSimulation()
  const [activeView, setActiveView] = useState<DemoView>('mission-control')

  // ── Badge counts derived from simulation state ──────────────────────────

  const counts = useMemo(() => {
    const activeTasks = state.tasks.filter(
      t => t.status === 'claimed' || t.status === 'in_progress',
    ).length
    const activeAgents = state.agents.filter(a => a.status === 'active').length

    const result: Partial<Record<DemoView, number>> = {}
    if (activeTasks > 0) result['task-board'] = activeTasks
    if (activeAgents > 0) result['agents'] = activeAgents
    return result
  }, [state.tasks, state.agents])

  // ── View routing ────────────────────────────────────────────────────────

  function renderView() {
    switch (activeView) {
      case 'mission-control':
        return <DemoMissionControl state={state} onNavigate={setActiveView} onNewRun={controls.replay} />
      case 'task-board':
        return <DemoTaskBoard state={state} />
      case 'pipeline':
        return <DemoRunHistory state={state} />
      case 'trajectory':
        return <DemoTrajectories state={state} />
      case 'memory':
        return <DemoMemory state={state} />
      case 'metrics':
        return <DemoObservability state={state} />
      case 'agents':
        return <DemoAgents state={state} />
      default:
        return <DemoMissionControl state={state} onNavigate={setActiveView} onNewRun={controls.replay} />
    }
  }

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '232px 1fr',
        gridTemplateRows: '48px 1fr',
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        background: 'var(--bg-primary, var(--bg-void))',
        color: 'var(--text-primary)',
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Top row: SprintBar spans full width */}
      <div style={{ gridColumn: '1 / -1' }}>
        <a
          href="/writing"
          style={{
            position: 'fixed',
            top: 12,
            right: 18,
            zIndex: 20,
            fontSize: 12,
            fontWeight: 500,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--text-secondary)',
            textDecoration: 'none',
            padding: '7px 10px',
            border: '1px solid var(--border-default)',
            borderRadius: 6,
            background: 'rgba(12, 12, 14, 0.86)',
            backdropFilter: 'blur(18px) saturate(1.2)',
          }}
        >
          Writing
        </a>
        <SprintBar
          state={state}
          onPlay={controls.play}
          onPause={controls.pause}
          onSetSpeed={controls.setSpeed}
          onReplay={controls.replay}
        />
      </div>

      {/* Left column: Sidebar */}
      <DemoSidebar
        activeView={activeView}
        onNavigate={setActiveView}
        counts={counts}
      />

      {/* Main area: active view with fadeIn animation on view change */}
      <main
        key={activeView}
        style={{
          overflow: 'auto',
          padding: 24,
          animation: 'demoFadeIn 0.25s ease-out',
        }}
      >
        {renderView()}
      </main>

      {/* fadeIn keyframes */}
      <style>{`
        @keyframes demoFadeIn {
          from { opacity: 0; transform: translateY(6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}
