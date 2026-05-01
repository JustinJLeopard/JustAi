/**
 * JustAi Demo — Memory View
 *
 * Displays memory entries from the simulation with category badges,
 * a decorative search bar, and fade-in animations for entries that
 * appear during the simulation run.
 */

import type { SimulationState, DemoMemoryEntry } from '../data/types'

// ── Props ───────────────────────────────────────────────────────────────────

export interface DemoMemoryProps {
  state: SimulationState
}

// ── Category -> badge color mapping ─────────────────────────────────────────

const categoryColors: Record<string, { bg: string; fg: string }> = {
  architecture:   { bg: 'rgba(59,130,246,0.12)',  fg: '#60a5fa'  },  // blue
  routing:        { bg: 'rgba(139,92,246,0.12)',   fg: '#a78bfa'  },  // purple
  testing:        { bg: 'rgba(16,185,129,0.12)',   fg: '#34d399'  },  // green
  learning:       { bg: 'rgba(245,158,11,0.12)',   fg: '#fbbf24'  },  // amber
  infrastructure: { bg: 'rgba(100,116,139,0.12)',  fg: '#94a3b8'  },  // gray
}

function getCategoryColor(category: string) {
  return categoryColors[category] ?? categoryColors.infrastructure
}

// ── Memory Entry Card ───────────────────────────────────────────────────────

function MemoryEntryCard({
  entry,
  isNew,
}: {
  entry: DemoMemoryEntry
  isNew: boolean
}) {
  const colors = getCategoryColor(entry.category)

  return (
    <div
      className="panel"
      style={{
        padding: 'var(--sp-4)',
        animation: isNew ? 'fadeIn 0.6s ease' : undefined,
        borderColor: isNew ? 'rgba(16,185,129,0.15)' : undefined,
      }}
    >
      {/* Top row: key + badges */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--sp-2)',
          marginBottom: 'var(--sp-2)',
        }}
      >
        {/* Key */}
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            fontWeight: 400,
            color: 'var(--text-primary)',
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {entry.key}
        </span>

        {/* "New" badge for entries that appeared during simulation */}
        {isNew && (
          <span
            style={{
              fontSize: 9,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.8px',
              padding: '2px 6px',
              borderRadius: 'var(--r-sm)',
              background: 'var(--emerald-glow)',
              color: 'var(--emerald-400)',
              flexShrink: 0,
            }}
          >
            New
          </span>
        )}

        {/* Category badge */}
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
            flexShrink: 0,
          }}
        >
          {entry.category}
        </span>
      </div>

      {/* Value */}
      <div
        style={{
          fontSize: 12,
          fontWeight: 300,
          color: 'var(--text-secondary)',
          lineHeight: 1.55,
        }}
      >
        {entry.value}
      </div>
    </div>
  )
}

// ── Main Component ──────────────────────────────────────────────────────────

export function DemoMemory({ state }: DemoMemoryProps) {
  const visibleCount = state.memories.length

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
          Memory
        </h1>
        <div
          style={{
            fontSize: 13,
            color: 'var(--text-secondary)',
            marginTop: 2,
            fontWeight: 300,
          }}
        >
          {visibleCount} entr{visibleCount === 1 ? 'y' : 'ies'} stored
        </div>
      </div>

      {/* ── Search Bar (visual-only) ────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          gap: 'var(--sp-2)',
        }}
      >
        <input
          type="text"
          placeholder="Search memories..."
          readOnly
          style={{
            flex: 1,
            padding: '8px 14px',
            fontSize: 13,
            fontFamily: 'var(--font-sans)',
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--r-sm)',
            color: 'var(--text-primary)',
            outline: 'none',
            cursor: 'default',
            opacity: 0.6,
          }}
        />
        <div
          style={{
            padding: '8px 20px',
            fontSize: 13,
            fontWeight: 500,
            background: 'rgba(244,63,94,0.1)',
            color: 'var(--rose-400)',
            border: '1px solid rgba(244,63,94,0.2)',
            borderRadius: 'var(--r-sm)',
            opacity: 0.5,
            cursor: 'default',
          }}
        >
          Search
        </div>
      </div>

      {/* ── Memory Entries List ──────────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--sp-2)',
          maxHeight: 480,
          overflowY: 'auto',
        }}
      >
        {visibleCount === 0 ? (
          <div
            className="panel"
            style={{
              padding: 'var(--sp-10)',
              textAlign: 'center',
              color: 'var(--text-dim)',
              fontSize: 13,
              fontWeight: 300,
              fontStyle: 'italic',
            }}
          >
            No memory entries yet. Memories appear as the simulation progresses.
          </div>
        ) : (
          state.memories.map(entry => (
            <MemoryEntryCard
              key={entry.id}
              entry={entry}
              isNew={entry.appearsAt > 0}
            />
          ))
        )}
      </div>
    </div>
  )
}
