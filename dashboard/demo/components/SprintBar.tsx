/**
 * JustAi Demo — SprintBar
 *
 * Demo-only sprint control bar displayed above the main content area.
 * Shows sprint goal, progress, speed controls, and play/pause/replay.
 *
 * Uses the same Midnight Rose design tokens as the rest of the dashboard.
 */

import type { SimulationState, SpeedMultiplier } from '../data/types'
import { SPRINT_GOAL } from '../data/sprint-timeline'

// ── Constants ───────────────────────────────────────────────────────────────

const TOTAL_TASKS = 8
const SPEED_OPTIONS: SpeedMultiplier[] = [0.5, 1, 2]

// ── Props ───────────────────────────────────────────────────────────────────

export interface SprintBarProps {
  state: SimulationState
  onPlay: () => void
  onPause: () => void
  onSetSpeed: (s: SpeedMultiplier) => void
  onReplay: () => void
}

// ── Component ───────────────────────────────────────────────────────────────

export function SprintBar({ state, onPlay, onPause, onSetSpeed, onReplay }: SprintBarProps) {
  const { completedCount, paused, speed, phase } = state
  const isComplete = phase === 'complete'
  const isIdle = phase === 'idle'
  const isRunning = !paused && !isComplete && !isIdle
  const progress = completedCount / TOTAL_TASKS

  // Accent color shifts to emerald when sprint is complete
  const accentColor = isComplete ? '#10b981' : 'rgba(244,63,94,0.8)'
  const accentBg = isComplete ? 'rgba(16,185,129,0.12)' : 'rgba(244,63,94,0.1)'
  const accentBorder = isComplete ? 'rgba(16,185,129,0.3)' : 'rgba(244,63,94,0.3)'
  const progressBarColor = isComplete ? '#10b981' : '#f43f5e'
  const progressBarGlow = isComplete
    ? '0 0 8px rgba(16,185,129,0.4)'
    : '0 0 8px rgba(244,63,94,0.3)'

  return (
    <div
      className="demo-sprint-bar"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '8px 20px',
        background: 'linear-gradient(90deg, var(--bg-elevated) 0%, var(--bg-surface) 100%)',
        borderBottom: '1px solid var(--border-subtle)',
        minHeight: 44,
        position: 'relative',
      }}
    >
      {/* "Demo" badge */}
      <span
        style={{
          fontSize: 10,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: 1.5,
          color: accentColor,
          background: accentBg,
          border: `1px solid ${accentBorder}`,
          padding: '2px 8px',
          borderRadius: 4,
          flexShrink: 0,
          lineHeight: '16px',
        }}
      >
        Demo
      </span>

      {/* Sprint goal text */}
      <span
        style={{
          fontSize: 12,
          fontWeight: 300,
          color: 'var(--text-secondary)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          flex: 1,
          minWidth: 0,
        }}
        title={SPRINT_GOAL}
      >
        {SPRINT_GOAL}
      </span>

      {/* Progress bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: 120,
            height: 4,
            background: 'rgba(255,255,255,0.06)',
            borderRadius: 2,
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <div
            style={{
              width: `${progress * 100}%`,
              height: '100%',
              background: progressBarColor,
              borderRadius: 2,
              boxShadow: progress > 0 ? progressBarGlow : 'none',
              transition: 'width 0.3s ease-out, background 0.3s ease-out',
            }}
          />
        </div>

        {/* Task count */}
        <span
          style={{
            fontFamily: 'monospace',
            fontSize: 11,
            color: 'var(--text-tertiary)',
            letterSpacing: 0.5,
            flexShrink: 0,
          }}
        >
          {completedCount}/{TOTAL_TASKS}
        </span>
      </div>

      {/* Divider */}
      <div
        style={{
          width: 1,
          height: 20,
          background: 'var(--border-subtle)',
          flexShrink: 0,
        }}
      />

      {/* Speed controls */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          flexShrink: 0,
        }}
      >
        {SPEED_OPTIONS.map((s) => {
          const isActiveSpeed = speed === s
          return (
            <button
              key={s}
              onClick={() => onSetSpeed(s)}
              aria-label={`Set speed to ${s}x`}
              style={{
                fontSize: 11,
                fontFamily: 'monospace',
                fontWeight: isActiveSpeed ? 500 : 300,
                color: isActiveSpeed ? accentColor : 'var(--text-muted)',
                background: isActiveSpeed ? accentBg : 'transparent',
                border: isActiveSpeed ? `1px solid ${accentBorder}` : '1px solid transparent',
                borderRadius: 4,
                padding: '2px 6px',
                cursor: 'pointer',
                lineHeight: '16px',
                transition: 'all 0.15s',
              }}
            >
              {s}x
            </button>
          )
        })}
      </div>

      {/* Play / Pause / Replay button */}
      {isComplete ? (
        <button
          onClick={onReplay}
          aria-label="Replay simulation"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            fontSize: 11,
            fontWeight: 500,
            color: '#10b981',
            background: 'rgba(16,185,129,0.1)',
            border: '1px solid rgba(16,185,129,0.3)',
            borderRadius: 6,
            padding: '4px 10px',
            cursor: 'pointer',
            transition: 'all 0.15s',
            lineHeight: '16px',
          }}
        >
          <span aria-hidden style={{ fontSize: 12 }}>{'\u21BB'}</span>
          Replay
        </button>
      ) : (
        <button
          onClick={isRunning ? onPause : onPlay}
          aria-label={isRunning ? 'Pause simulation' : 'Play simulation'}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 28,
            height: 28,
            fontSize: 14,
            color: accentColor,
            background: accentBg,
            border: `1px solid ${accentBorder}`,
            borderRadius: 6,
            cursor: 'pointer',
            transition: 'all 0.15s',
            flexShrink: 0,
          }}
        >
          {isRunning ? '\u23F8' : '\u25B6'}
        </button>
      )}
    </div>
  )
}
