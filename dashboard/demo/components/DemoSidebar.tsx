/**
 * JustAi Demo — DemoSidebar
 *
 * Pixel-identical replica of the real JustAi dashboard sidebar
 * (dashboard/src/components/Sidebar.tsx), adapted for the self-contained
 * demo. Uses DemoView instead of View, adds badge counts from props,
 * and shows "Demo Mode" in the footer instead of transport status.
 *
 * All inline style values are copied verbatim from the real sidebar.
 */

import { useState, useEffect, useCallback } from 'react'

import type { DemoView } from '../data/types'

// ── Nav structure (mirrors real sidebar exactly) ────────────────────────────

interface NavItem {
  view: DemoView
  label: string
  icon: string
}

interface NavGroup {
  label: string
  items: NavItem[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Operations',
    items: [
      { view: 'mission-control', label: 'Mission Control', icon: '\u25C9' },
      { view: 'task-board', label: 'Task Board', icon: '\u25A6' },
      { view: 'pipeline', label: 'Run History', icon: '\u25B8' },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { view: 'trajectory', label: 'Trajectories', icon: '\u25C8' },
      { view: 'memory', label: 'Memory', icon: '\u2B21' },
      { view: 'metrics', label: 'Observability', icon: '\u25D0' },
    ],
  },
  {
    label: 'System',
    items: [
      { view: 'agents', label: 'Agents', icon: '\u2B22' },
    ],
  },
]

// ── Theme toggle (self-contained, matches real ThemeToggle) ─────────────────

type Theme = 'dark' | 'light'

function useDemoTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === 'undefined') return 'dark'
    const stored = localStorage.getItem('justai-theme')
    if (stored === 'dark' || stored === 'light') return stored
    if (window.matchMedia('(prefers-color-scheme: light)').matches) return 'light'
    return 'dark'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('justai-theme', theme)
  }, [theme])

  const toggle = useCallback(() => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'))
  }, [])

  return { theme, toggle } as const
}

// ── Props ───────────────────────────────────────────────────────────────────

export interface DemoSidebarProps {
  activeView: DemoView
  onNavigate: (view: DemoView) => void
  counts?: Partial<Record<DemoView, number>>
}

// ── Component ───────────────────────────────────────────────────────────────

export function DemoSidebar({ activeView, onNavigate, counts }: DemoSidebarProps) {
  const { theme, toggle } = useDemoTheme()

  return (
    <aside
      style={{
        width: 232,
        minWidth: 232,
        maxWidth: 232,
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Neutral gradient overlay -- white at top, fading to transparent */}
      <div
        aria-hidden
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 120,
          background: 'linear-gradient(to bottom, rgba(255,255,255,0.03) 0%, transparent 100%)',
          pointerEvents: 'none',
          zIndex: 0,
        }}
      />

      {/* Logo area */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '24px 20px 20px',
          position: 'relative',
          zIndex: 1,
        }}
      >
        {/* Diamond mark -- CSS-only rotated square */}
        <div
          aria-hidden
          style={{
            width: 18,
            height: 18,
            transform: 'rotate(45deg)',
            background: 'rgba(244,63,94,0.12)',
            border: '1px solid rgba(244,63,94,0.35)',
            borderRadius: 3,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 8px rgba(244,63,94,0.2)',
            flexShrink: 0,
          }}
        >
          <div
            style={{
              width: 7,
              height: 7,
              background: 'rgba(244,63,94,0.8)',
              borderRadius: 1,
              boxShadow: '0 0 6px rgba(244,63,94,0.6)',
            }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <span
            style={{
              fontSize: 15,
              fontWeight: 300,
              letterSpacing: 5,
              color: 'var(--text-primary)',
              lineHeight: 1,
            }}
          >
            JUSTAI
          </span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 400,
              letterSpacing: 1.5,
              color: 'var(--text-dim)',
              lineHeight: 1,
            }}
          >
            v2.0
          </span>
        </div>
      </div>

      {/* Nav groups */}
      <nav
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '4px 0',
          position: 'relative',
          zIndex: 1,
        }}
      >
        {NAV_GROUPS.map((group) => (
          <div key={group.label} style={{ marginBottom: 20 }}>
            {/* Group label */}
            <div
              style={{
                fontSize: 10,
                fontWeight: 500,
                textTransform: 'uppercase',
                letterSpacing: 2.5,
                color: 'var(--text-dim)',
                padding: '0 20px 6px',
              }}
            >
              {group.label}
            </div>

            {/* Nav items */}
            {group.items.map((item) => {
              const isActive = item.view === activeView
              const count = counts?.[item.view]

              return (
                <button
                  key={item.view}
                  data-active={isActive ? 'true' : 'false'}
                  onClick={() => onNavigate(item.view)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    width: '100%',
                    padding: '7px 20px',
                    background: isActive ? 'rgba(244,63,94,0.05)' : 'transparent',
                    border: 'none',
                    borderLeft: isActive
                      ? '2px solid rgba(244,63,94,0.7)'
                      : '2px solid transparent',
                    borderRight: 'none',
                    borderTop: isActive ? '1px solid rgba(244,63,94,0.07)' : '1px solid transparent',
                    borderBottom: isActive ? '1px solid rgba(244,63,94,0.07)' : '1px solid transparent',
                    cursor: 'pointer',
                    fontSize: 13,
                    fontWeight: 300,
                    color: isActive ? '#fce7f3' : 'var(--text-tertiary)',
                    textAlign: 'left',
                    boxShadow: isActive ? '2px 0 8px rgba(244,63,94,0.12) inset' : 'none',
                    transition: 'background 0.15s, color 0.15s, border-color 0.15s',
                  }}
                >
                  {/* Icon */}
                  <span
                    aria-hidden
                    style={{
                      fontSize: 11,
                      opacity: isActive ? 1 : 0.5,
                      color: isActive ? 'rgba(244,63,94,0.8)' : 'inherit',
                      textShadow: isActive ? '0 0 6px rgba(244,63,94,0.5)' : 'none',
                      flexShrink: 0,
                    }}
                  >
                    {item.icon}
                  </span>

                  {/* Label */}
                  <span style={{ flex: 1 }}>{item.label}</span>

                  {/* Count badge */}
                  {count !== undefined && (
                    <span
                      style={{
                        fontFamily: 'monospace',
                        fontSize: 11,
                        color: isActive ? 'rgba(244,63,94,0.8)' : 'var(--text-dim)',
                        background: isActive
                          ? 'rgba(244,63,94,0.1)'
                          : 'rgba(255,255,255,0.04)',
                        padding: '1px 5px',
                        borderRadius: 4,
                        lineHeight: '16px',
                      }}
                    >
                      {count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div
        style={{
          padding: '12px 20px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          position: 'relative',
          zIndex: 1,
        }}
      >
        {/* Breathing emerald status dot */}
        <span
          aria-hidden
          style={{
            display: 'inline-block',
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: '#10b981',
            boxShadow: '0 0 4px rgba(16,185,129,0.6)',
            animation: 'breathe 2.8s ease-in-out infinite',
            flexShrink: 0,
          }}
        />

        <span
          style={{
            flex: 1,
            fontSize: 11,
            fontWeight: 300,
            color: 'var(--text-dim)',
            letterSpacing: 0.3,
          }}
        >
          Demo Mode
        </span>

        {/* Theme toggle */}
        <button
          onClick={toggle}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--text-muted)',
            fontSize: 14,
            padding: 4,
            borderRadius: 'var(--r-sm)',
            transition: 'color var(--t-fast)',
          }}
        >
          {theme === 'dark' ? '\u2600' : '\u263E'}
        </button>
      </div>

      {/* Breathing keyframes -- injected as a style tag */}
      <style>{`
        @keyframes breathe {
          0%, 100% { opacity: 1; box-shadow: 0 0 4px rgba(16,185,129,0.6); }
          50% { opacity: 0.5; box-shadow: 0 0 8px rgba(16,185,129,0.3); }
        }
      `}</style>
    </aside>
  )
}
