/**
 * JustAi Demo — Run History View
 *
 * Shows the current sprint run card with status, progress, cost, and elapsed
 * time, plus a reverse-chronological event log with colored type badges.
 */

import type { SimulationState, DemoEvent } from '../data/types'

// ── Props ───────────────────────────────────────────────────────────────────

export interface DemoRunHistoryProps {
  state: SimulationState
}

// ── Event type -> badge color mapping ───────────────────────────────────────

const eventTypeColors: Record<string, { bg: string; fg: string }> = {
  task:       { bg: 'rgba(59,130,246,0.12)',  fg: '#60a5fa'  },  // blue
  error:      { bg: 'rgba(239,68,68,0.12)',   fg: '#f87171'  },  // red
  escalation: { bg: 'rgba(245,158,11,0.12)',  fg: '#fbbf24'  },  // amber
  learning:   { bg: 'rgba(139,92,246,0.12)',  fg: '#a78bfa'  },  // purple
  pipeline:   { bg: 'rgba(100,116,139,0.12)', fg: '#94a3b8'  },  // gray
  sprint:     { bg: 'rgba(16,185,129,0.12)',  fg: '#34d399'  },  // emerald
}

function getEventColor(type: string) {
  return eventTypeColors[type] ?? eventTypeColors.pipeline
}

// ── Event row ───────────────────────────────────────────────────────────────

function EventRow({ event }: { event: DemoEvent }) {
  const colors = getEventColor(event.type)
  const eventLabel = event.type === 'pipeline' ? 'stage' : event.type
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 'var(--sp-3)',
        padding: '8px 0',
        borderBottom: '1px solid var(--border-subtle)',
        animation: 'fadeIn 0.3s ease',
      }}
    >
      {/* Timestamp */}
      <span
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          fontWeight: 400,
          color: 'var(--text-dim)',
          minWidth: 44,
          flexShrink: 0,
          textAlign: 'right',
        }}
      >
        {event.time.toFixed(0)}s
      </span>

      {/* Type badge */}
      <span
        style={{
          fontSize: 9,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.8px',
          padding: '2px 8px',
          borderRadius: 'var(--r-sm)',
          background: colors.bg,
          color: colors.fg,
          whiteSpace: 'nowrap',
          flexShrink: 0,
        }}
      >
        {eventLabel}
      </span>

      {/* Detail */}
      <span
        style={{
          fontSize: 12,
          fontWeight: 300,
          color: 'var(--text-secondary)',
          lineHeight: 1.5,
        }}
      >
        {event.detail}
      </span>
    </div>
  )
}

// ── Main Component ──────────────────────────────────────────────────────────

export function DemoRunHistory({ state }: DemoRunHistoryProps) {
  const isRunning = state.phase !== 'idle' && state.phase !== 'complete'
  const isDone = state.phase === 'complete'
  const progressPct = (state.completedCount / 8) * 100

  // Format elapsed time
  const minutes = Math.floor(state.elapsed / 60)
  const seconds = Math.floor(state.elapsed % 60)
  const elapsedStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`

  // Reverse events for newest-first display
  const reversedEvents = [...state.events].reverse()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>

      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div>
        <h1
          style={{
            fontSize: 22,
            fontWeight: 200,
            color: 'var(--text-primary)',
            letterSpacing: '0.3px',
            margin: 0,
          }}
        >
          Run History
        </h1>
        <div
          style={{
            fontSize: 13,
            color: 'var(--text-secondary)',
            marginTop: 2,
            fontWeight: 300,
          }}
        >
          {isRunning ? '1 run active' : isDone ? '1 run completed' : 'No runs yet'}
        </div>
      </div>

      {/* ── Run Entry Card ──────────────────────────────────────────────── */}
      <div
        className="panel"
        style={{
          padding: 'var(--sp-5)',
          borderColor: isRunning
            ? 'rgba(244,63,94,0.2)'
            : isDone
              ? 'rgba(16,185,129,0.2)'
              : undefined,
        }}
      >
        {/* Header row: sprint name + status badge */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 'var(--sp-4)',
          }}
        >
          <div>
            <div
              style={{
                fontSize: 9,
                fontWeight: 500,
                textTransform: 'uppercase',
                letterSpacing: '1.5px',
                color: 'var(--text-dim)',
                marginBottom: 4,
              }}
            >
              Sprint Run
            </div>
            <div
              style={{
                fontSize: 15,
                fontWeight: 300,
                color: 'var(--text-primary)',
              }}
            >
              Customer Analytics Dashboard
            </div>
          </div>

          {/* Status badge */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--sp-1)',
              padding: '4px 12px',
              borderRadius: 12,
              fontSize: 12,
              fontWeight: 600,
              background: isRunning
                ? 'var(--rose-glow)'
                : isDone
                  ? 'var(--emerald-glow)'
                  : 'rgba(100,116,139,0.1)',
              color: isRunning
                ? 'var(--rose-400)'
                : isDone
                  ? 'var(--emerald-400)'
                  : 'var(--text-dim)',
            }}
          >
            {isRunning && (
              <div
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: '50%',
                  background: 'var(--rose-400)',
                  animation: 'pulse-live 2s ease-in-out infinite',
                }}
              />
            )}
            {isRunning ? 'Running' : isDone ? 'Done' : 'Idle'}
          </div>
        </div>

        {/* Progress bar */}
        <div
          style={{
            height: 4,
            borderRadius: 2,
            background: 'rgba(255,255,255,0.04)',
            overflow: 'hidden',
            marginBottom: 'var(--sp-4)',
          }}
        >
          <div
            style={{
              height: '100%',
              borderRadius: 2,
              background: isDone
                ? 'linear-gradient(90deg, var(--emerald-500), var(--emerald-400))'
                : 'linear-gradient(90deg, var(--rose-600), var(--rose-400))',
              boxShadow: isDone
                ? '0 0 8px rgba(16,185,129,0.2)'
                : '0 0 8px rgba(244,63,94,0.2)',
              width: `${Math.min(100, progressPct)}%`,
              transition: 'width 1s cubic-bezier(0.16,1,0.3,1)',
              position: 'relative',
            }}
          >
            {isRunning && (
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  top: -1,
                  bottom: -1,
                  width: 20,
                  background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.15))',
                  animation: 'shimmer 2s ease-in-out infinite',
                }}
              />
            )}
          </div>
        </div>

        {/* Stats row */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 'var(--sp-5)',
            fontSize: 12,
          }}
        >
          <span style={{ fontWeight: 300, color: 'var(--text-muted)' }}>
            Model{' '}
            <span
              style={{
                fontWeight: 400,
                color: 'var(--text-secondary)',
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
              }}
            >
              gpt-5.4 + claude-opus-4-6
            </span>
          </span>

          <span style={{ fontWeight: 300, color: 'var(--text-muted)' }}>
            Tasks{' '}
            <span
              style={{
                fontWeight: 400,
                color: state.completedCount === 8 ? 'var(--emerald-400)' : 'var(--text-secondary)',
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
              }}
            >
              {state.completedCount}/8
            </span>
          </span>

          <span style={{ fontWeight: 300, color: 'var(--text-muted)' }}>
            Cost{' '}
            <span
              style={{
                fontWeight: 400,
                color: 'var(--gold-300)',
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
              }}
            >
              ${state.totalCost.toFixed(2)}
            </span>
          </span>

          <span style={{ fontWeight: 300, color: 'var(--text-muted)' }}>
            Elapsed{' '}
            <span
              style={{
                fontWeight: 400,
                color: 'var(--text-secondary)',
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
              }}
            >
              {elapsedStr}
            </span>
          </span>
        </div>
      </div>

      {/* ── Event Log ───────────────────────────────────────────────────── */}
      <div>
        <div
          style={{
            fontSize: 11,
            fontWeight: 500,
            color: 'var(--text-secondary)',
            letterSpacing: '1.5px',
            textTransform: 'uppercase',
            marginBottom: 'var(--sp-3)',
          }}
        >
          Event Log ({state.events.length})
        </div>

        <div
          className="panel"
          style={{
            padding: 'var(--sp-4)',
            maxHeight: 420,
            overflowY: 'auto',
          }}
        >
          {reversedEvents.length === 0 ? (
            <div
              style={{
                fontSize: 13,
                fontWeight: 300,
                color: 'var(--text-dim)',
                fontStyle: 'italic',
                padding: 'var(--sp-4)',
                textAlign: 'center',
              }}
            >
              Waiting for sprint to start...
            </div>
          ) : (
            reversedEvents.map((evt, i) => (
              <EventRow key={`${evt.time}-${i}`} event={evt} />
            ))
          )}
        </div>
      </div>
    </div>
  )
}
