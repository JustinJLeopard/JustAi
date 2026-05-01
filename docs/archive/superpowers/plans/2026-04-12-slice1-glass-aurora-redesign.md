# Slice 1: Glass Aurora Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the v1 dashboard visuals with the Midnight Rose design system — grouped sidebar navigation, light/dark mode, hover popovers, keyboard shortcuts, and enterprise-grade CSS across all views.

**Architecture:** The design system lives in a single CSS file (`theme.css`) using CSS custom properties. A `useTheme` hook manages dark/light mode via a `data-theme` attribute on `<html>`. All views are restyled to use design tokens instead of inline styles. A shared `Popover` component provides the hover drill-down pattern used everywhere.

**Tech Stack:** React 18, TypeScript, CSS custom properties, Vite 6, Vitest + @testing-library/react (new)

**Reference:** Design spec at `docs/superpowers/specs/2026-04-12-justai-v2-design.md`
**Reference mockup:** `.superpowers/brainstorm/25878-1775975034/content/enterprise-dashboard.html`

---

## File Structure

### Create
```
dashboard/src/styles/theme.css          — Design system tokens + global styles (replaces index.css)
dashboard/src/styles/views.css          — View-specific styles
dashboard/src/components/Popover.tsx    — Hover popover component
dashboard/src/components/Sidebar.tsx    — Grouped navigation sidebar
dashboard/src/components/ThemeToggle.tsx — Dark/light mode toggle
dashboard/src/components/MetricCard.tsx — Metric card with sparkline + popover
dashboard/src/components/Pipeline.tsx   — Pipeline stage bar component
dashboard/src/hooks/useTheme.ts         — Theme state hook (localStorage + prefers-color-scheme)
dashboard/src/hooks/useKeyboard.ts      — Keyboard shortcut handler
dashboard/src/views/AgentRegistry.tsx   — New view: registered agents
dashboard/src/__tests__/Popover.test.tsx
dashboard/src/__tests__/Sidebar.test.tsx
dashboard/src/__tests__/ThemeToggle.test.tsx
dashboard/src/__tests__/App.test.tsx
```

### Modify
```
dashboard/index.html                     — Font links (add JetBrains Mono, weight range)
dashboard/package.json                   — Add vitest, @testing-library/react, jsdom
dashboard/src/main.tsx                   — Import theme.css instead of index.css
dashboard/src/App.tsx                    — New layout with Sidebar, view transitions, keyboard hooks
dashboard/src/views/MissionControl.tsx   — Full redesign with MetricCards, Pipeline, popovers
dashboard/src/views/TaskBoard.tsx        — Restyle with design tokens
dashboard/src/views/RunHistory.tsx       — Wire into routing + restyle
dashboard/src/views/MemoryBrowser.tsx    — Restyle with design tokens
dashboard/src/views/TrajectoryViewer.tsx — Restyle with design tokens (visual only, not 3-mode)
```

### Delete
```
dashboard/src/index.css                  — Replaced by theme.css
```

---

### Task 1: Design System CSS

**Files:**
- Create: `dashboard/src/styles/theme.css`
- Delete: `dashboard/src/index.css`
- Modify: `dashboard/src/main.tsx`

- [ ] **Step 1: Create theme.css with all design tokens**

```css
/* dashboard/src/styles/theme.css */

/* ═══════════════════════════════════════════════════════════════
   JUSTAI DESIGN SYSTEM — Midnight Rose
   ═══════════════════════════════════════════════════════════════ */

:root,
[data-theme="dark"] {
  /* Backgrounds */
  --bg-void:       #09090b;
  --bg-surface:    rgba(255,255,255, 0.024);
  --bg-elevated:   rgba(255,255,255, 0.038);
  --bg-hover:      rgba(255,255,255, 0.055);
  --bg-popover:    rgba(12,12,14, 0.97);

  /* Borders */
  --border-subtle:  rgba(255,255,255, 0.035);
  --border-default: rgba(255,255,255, 0.055);
  --border-hover:   rgba(255,255,255, 0.09);

  /* Rose — active, live, primary actions */
  --rose-600: #e11d48;
  --rose-500: #f43f5e;
  --rose-400: #fb7185;
  --rose-300: #fda4af;
  --rose-glow: rgba(244,63,94, 0.12);

  /* Gold — cost, monetary data */
  --gold-400: #facc15;
  --gold-300: #fde68a;
  --gold-glow: rgba(253,224,171, 0.08);

  /* Emerald — success, healthy */
  --emerald-500: #10b981;
  --emerald-400: #34d399;
  --emerald-glow: rgba(16,185,129, 0.12);

  /* Status */
  --red-500: #ef4444;
  --amber-500: #f59e0b;

  /* Text */
  --text-primary:   #f1f5f9;
  --text-secondary: #94a3b8;
  --text-tertiary:  #64748b;
  --text-muted:     #475569;
  --text-dim:       #334155;

  /* Typography */
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;

  /* Spacing — 4px base */
  --sp-1: 4px;  --sp-2: 8px;  --sp-3: 12px;
  --sp-4: 16px; --sp-5: 20px; --sp-6: 24px;
  --sp-8: 32px; --sp-10: 40px;

  /* Radii */
  --r-sm: 6px;  --r-md: 10px; --r-lg: 14px;

  /* Shadows */
  --shadow-sm:  0 1px 2px rgba(0,0,0,0.3), 0 0 1px rgba(0,0,0,0.2);
  --shadow-md:  0 4px 16px rgba(0,0,0,0.4), 0 0 1px rgba(255,255,255,0.03);
  --shadow-lg:  0 12px 40px rgba(0,0,0,0.5), 0 0 1px rgba(255,255,255,0.04);
  --shadow-xl:  0 24px 64px rgba(0,0,0,0.6), 0 0 1px rgba(255,255,255,0.05);

  /* Transitions */
  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
  --t-fast:    0.12s cubic-bezier(0.16, 1, 0.3, 1);
  --t-default: 0.2s  cubic-bezier(0.16, 1, 0.3, 1);
  --t-slow:    0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

/* ─── Light Mode ─── */
[data-theme="light"] {
  --bg-void:       #fafafa;
  --bg-surface:    #ffffff;
  --bg-elevated:   #f8fafc;
  --bg-hover:      #f1f5f9;
  --bg-popover:    rgba(255,255,255, 0.97);

  --border-subtle:  rgba(0,0,0, 0.06);
  --border-default: rgba(0,0,0, 0.1);
  --border-hover:   rgba(0,0,0, 0.15);

  --text-primary:   #0f172a;
  --text-secondary: #475569;
  --text-tertiary:  #64748b;
  --text-muted:     #94a3b8;
  --text-dim:       #cbd5e1;

  --shadow-sm:  0 1px 2px rgba(0,0,0,0.05), 0 0 1px rgba(0,0,0,0.08);
  --shadow-md:  0 4px 16px rgba(0,0,0,0.08), 0 0 1px rgba(0,0,0,0.05);
  --shadow-lg:  0 12px 40px rgba(0,0,0,0.1), 0 0 1px rgba(0,0,0,0.06);
  --shadow-xl:  0 24px 64px rgba(0,0,0,0.12), 0 0 1px rgba(0,0,0,0.06);
}

/* ─── Base Reset & Globals ─── */
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

html {
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
  font-feature-settings: 'cv02', 'cv03', 'cv04', 'cv11';
}

body {
  font-family: var(--font-sans);
  color: var(--text-primary);
  background: var(--bg-void);
  overflow: hidden;
  height: 100vh;
  transition: background var(--t-default), color var(--t-default);
}

/* ─── Scrollbar ─── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.06); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.1); }
[data-theme="light"] ::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.08); }
[data-theme="light"] ::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.15); }

/* ─── Utility Classes ─── */
.mono { font-family: var(--font-mono); }
.tabular { font-variant-numeric: tabular-nums; }
.text-rose { color: var(--rose-400); }
.text-gold { color: var(--gold-300); }
.text-emerald { color: var(--emerald-400); }
.text-red { color: var(--red-500); }

/* ─── Panel ─── */
.panel {
  border-radius: var(--r-lg);
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  transition: border-color var(--t-default);
}

.panel:hover { border-color: var(--border-default); }
.panel-pad { padding: var(--sp-5); }

/* ─── Animations ─── */
@keyframes breathe {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

@keyframes pulse-live {
  0%, 100% { opacity: 1; box-shadow: 0 0 4px rgba(244,63,94,0.3); }
  50% { opacity: 0.4; box-shadow: 0 0 8px rgba(244,63,94,0.5); }
}

@keyframes shimmer {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.8; }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
```

- [ ] **Step 2: Update main.tsx to import theme.css**

Replace line 1 of `dashboard/src/main.tsx`:
```typescript
// Change: import './index.css'
// To:
import './styles/theme.css'
```

- [ ] **Step 3: Delete old index.css**

Run: `rm dashboard/src/index.css`

- [ ] **Step 4: Verify the app still renders**

Run: `cd dashboard && npm run dev`
Open http://localhost:3001 — page should load with the new dark background (#09090b). Existing views will look broken (old CSS vars gone) — that's expected.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/styles/theme.css dashboard/src/main.tsx
git rm dashboard/src/index.css
git commit -m "feat(dashboard): add Midnight Rose design system, replace index.css"
```

---

### Task 2: Update index.html and Fonts

**Files:**
- Modify: `dashboard/index.html`

- [ ] **Step 1: Update font links and title**

Replace the contents of `dashboard/index.html`:

```html
<!DOCTYPE html>
<html lang="en" data-theme="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>JustAi — Orchestrator</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@100;200;300;400;500;600&family=JetBrains+Mono:wght@300;400;500&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Key changes: `data-theme="dark"` on `<html>`, added JetBrains Mono, Inter weight range extended to 100-600, updated title.

- [ ] **Step 2: Commit**

```bash
git add dashboard/index.html
git commit -m "feat(dashboard): update fonts and theme attribute"
```

---

### Task 3: Add Frontend Testing Infrastructure

**Files:**
- Modify: `dashboard/package.json`
- Create: `dashboard/src/__tests__/setup.ts`

- [ ] **Step 1: Install test dependencies**

```bash
cd /home/justinleopard/projects/JustAi/dashboard
npm install --save-dev vitest @testing-library/react @testing-library/jest-dom jsdom
```

- [ ] **Step 2: Create test setup file**

```typescript
// dashboard/src/__tests__/setup.ts
import '@testing-library/jest-dom'
```

- [ ] **Step 3: Add vitest config to vite.config.ts**

Add to the existing `defineConfig` in `dashboard/vite.config.ts`, inside the config object (after the `plugins` array):

```typescript
test: {
  globals: true,
  environment: 'jsdom',
  setupFiles: './src/__tests__/setup.ts',
},
```

- [ ] **Step 4: Add test script to package.json**

Add to the `"scripts"` section of `dashboard/package.json`:

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 5: Verify test runner works**

Create a trivial test to verify setup:

```typescript
// dashboard/src/__tests__/smoke.test.tsx
import { describe, it, expect } from 'vitest'

describe('test setup', () => {
  it('runs', () => {
    expect(1 + 1).toBe(2)
  })
})
```

Run: `cd dashboard && npm test`
Expected: 1 test passed.

- [ ] **Step 6: Commit**

```bash
git add dashboard/package.json dashboard/package-lock.json dashboard/vite.config.ts dashboard/src/__tests__/setup.ts dashboard/src/__tests__/smoke.test.tsx
git commit -m "feat(dashboard): add vitest testing infrastructure"
```

---

### Task 4: useTheme Hook + ThemeToggle Component

**Files:**
- Create: `dashboard/src/hooks/useTheme.ts`
- Create: `dashboard/src/components/ThemeToggle.tsx`
- Create: `dashboard/src/__tests__/ThemeToggle.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
// dashboard/src/__tests__/ThemeToggle.test.tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ThemeToggle } from '../components/ThemeToggle'

beforeEach(() => {
  document.documentElement.removeAttribute('data-theme')
  localStorage.clear()
})

describe('ThemeToggle', () => {
  it('renders a button', () => {
    render(<ThemeToggle />)
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('toggles data-theme on html element', () => {
    document.documentElement.setAttribute('data-theme', 'dark')
    render(<ThemeToggle />)
    fireEvent.click(screen.getByRole('button'))
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('persists theme to localStorage', () => {
    document.documentElement.setAttribute('data-theme', 'dark')
    render(<ThemeToggle />)
    fireEvent.click(screen.getByRole('button'))
    expect(localStorage.getItem('justai-theme')).toBe('light')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard && npx vitest run src/__tests__/ThemeToggle.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement useTheme hook**

```typescript
// dashboard/src/hooks/useTheme.ts
import { useState, useEffect, useCallback } from 'react'

type Theme = 'dark' | 'light'

const STORAGE_KEY = 'justai-theme'

function getInitialTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  if (window.matchMedia('(prefers-color-scheme: light)').matches) return 'light'
  return 'dark'
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  const toggle = useCallback(() => {
    setThemeState(prev => prev === 'dark' ? 'light' : 'dark')
  }, [])

  return { theme, toggle } as const
}
```

- [ ] **Step 4: Implement ThemeToggle component**

```tsx
// dashboard/src/components/ThemeToggle.tsx
import { useTheme } from '../hooks/useTheme'

export function ThemeToggle() {
  const { theme, toggle } = useTheme()

  return (
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
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd dashboard && npx vitest run src/__tests__/ThemeToggle.test.tsx`
Expected: 3 tests passed

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/hooks/useTheme.ts dashboard/src/components/ThemeToggle.tsx dashboard/src/__tests__/ThemeToggle.test.tsx
git commit -m "feat(dashboard): add dark/light theme toggle with localStorage persistence"
```

---

### Task 5: Popover Component

**Files:**
- Create: `dashboard/src/components/Popover.tsx`
- Create: `dashboard/src/__tests__/Popover.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// dashboard/src/__tests__/Popover.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Popover } from '../components/Popover'

describe('Popover', () => {
  it('renders children', () => {
    render(
      <Popover content={<span>Details</span>}>
        <button>Hover me</button>
      </Popover>
    )
    expect(screen.getByText('Hover me')).toBeInTheDocument()
  })

  it('shows popover content on mouse enter', async () => {
    render(
      <Popover content={<span>Details</span>}>
        <button>Hover me</button>
      </Popover>
    )
    fireEvent.mouseEnter(screen.getByText('Hover me'))
    // Content exists in DOM but may be opacity 0 until delay
    expect(screen.getByText('Details')).toBeInTheDocument()
  })

  it('positions popover below by default', () => {
    render(
      <Popover content={<span>Details</span>} position="bottom">
        <button>Hover me</button>
      </Popover>
    )
    expect(screen.getByText('Hover me')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard && npx vitest run src/__tests__/Popover.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement Popover component**

```tsx
// dashboard/src/components/Popover.tsx
import { useState, useRef, useCallback, type ReactNode, type CSSProperties } from 'react'

interface PopoverProps {
  children: ReactNode
  content: ReactNode
  position?: 'top' | 'bottom'
  delay?: number
}

const baseStyle: CSSProperties = {
  position: 'absolute',
  zIndex: 50,
  minWidth: 200,
  background: 'var(--bg-popover)',
  backdropFilter: 'blur(24px) saturate(1.2)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--r-md)',
  padding: 'var(--sp-4)',
  boxShadow: 'var(--shadow-xl)',
  pointerEvents: 'auto' as const,
  transition: 'opacity var(--t-default), transform var(--t-default)',
}

export function Popover({ children, content, position = 'bottom', delay = 150 }: PopoverProps) {
  const [visible, setVisible] = useState(false)
  const enterTimer = useRef<ReturnType<typeof setTimeout>>()
  const leaveTimer = useRef<ReturnType<typeof setTimeout>>()

  const show = useCallback(() => {
    clearTimeout(leaveTimer.current)
    enterTimer.current = setTimeout(() => setVisible(true), delay)
  }, [delay])

  const hide = useCallback(() => {
    clearTimeout(enterTimer.current)
    leaveTimer.current = setTimeout(() => setVisible(false), 100)
  }, [])

  const posStyle: CSSProperties = position === 'top'
    ? { bottom: 'calc(100% + 8px)', left: '50%', transform: `translateX(-50%) translateY(${visible ? 0 : 4}px)` }
    : { top: 'calc(100% + 8px)', left: '50%', transform: `translateX(-50%) translateY(${visible ? 0 : -4}px)` }

  return (
    <div
      style={{ position: 'relative', display: 'inline-block' }}
      onMouseEnter={show}
      onMouseLeave={hide}
    >
      {children}
      <div style={{ ...baseStyle, ...posStyle, opacity: visible ? 1 : 0, pointerEvents: visible ? 'auto' : 'none' }}>
        {content}
      </div>
    </div>
  )
}

/* Popover content helpers */
export function PopoverRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', fontSize: 12 }}>
      <span style={{ color: 'var(--text-tertiary)', fontWeight: 300 }}>{label}</span>
      <span style={{ color: color ?? 'var(--text-secondary)', fontWeight: 400, fontFamily: 'var(--font-mono)', fontSize: 11 }}>{value}</span>
    </div>
  )
}

export function PopoverDivider() {
  return <div style={{ height: 1, background: 'var(--border-subtle)', margin: 'var(--sp-2) 0' }} />
}

export function PopoverTitle({ children }: { children: ReactNode }) {
  return (
    <div style={{
      fontSize: 10, fontWeight: 500, color: 'var(--text-muted)',
      textTransform: 'uppercase' as const, letterSpacing: '1.5px',
      marginBottom: 'var(--sp-3)', paddingBottom: 'var(--sp-2)',
      borderBottom: '1px solid var(--border-subtle)',
    }}>
      {children}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd dashboard && npx vitest run src/__tests__/Popover.test.tsx`
Expected: 3 tests passed

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/components/Popover.tsx dashboard/src/__tests__/Popover.test.tsx
git commit -m "feat(dashboard): add Popover component with hover delay and positioning"
```

---

### Task 6: Sidebar Component

**Files:**
- Create: `dashboard/src/components/Sidebar.tsx`
- Create: `dashboard/src/__tests__/Sidebar.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// dashboard/src/__tests__/Sidebar.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Sidebar, type View } from '../components/Sidebar'

describe('Sidebar', () => {
  const onNavigate = (v: View) => {}

  it('renders all navigation groups', () => {
    render(<Sidebar activeView="mission-control" onNavigate={onNavigate} />)
    expect(screen.getByText('Operations')).toBeInTheDocument()
    expect(screen.getByText('Intelligence')).toBeInTheDocument()
    expect(screen.getByText('System')).toBeInTheDocument()
  })

  it('renders all 7 nav items', () => {
    render(<Sidebar activeView="mission-control" onNavigate={onNavigate} />)
    expect(screen.getByText('Mission Control')).toBeInTheDocument()
    expect(screen.getByText('Task Board')).toBeInTheDocument()
    expect(screen.getByText('Run History')).toBeInTheDocument()
    expect(screen.getByText('Trajectories')).toBeInTheDocument()
    expect(screen.getByText('Memory')).toBeInTheDocument()
    expect(screen.getByText('Observability')).toBeInTheDocument()
    expect(screen.getByText('Agents')).toBeInTheDocument()
  })

  it('highlights active view', () => {
    const { container } = render(<Sidebar activeView="task-board" onNavigate={onNavigate} />)
    const activeItem = container.querySelector('[data-active="true"]')
    expect(activeItem).toHaveTextContent('Task Board')
  })

  it('calls onNavigate when item clicked', () => {
    let navigated: View | undefined
    render(<Sidebar activeView="mission-control" onNavigate={(v) => { navigated = v }} />)
    fireEvent.click(screen.getByText('Task Board'))
    expect(navigated).toBe('task-board')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard && npx vitest run src/__tests__/Sidebar.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement Sidebar component**

```tsx
// dashboard/src/components/Sidebar.tsx
import { type CSSProperties } from 'react'
import { ThemeToggle } from './ThemeToggle'

export type View =
  | 'mission-control'
  | 'task-board'
  | 'runs'
  | 'trajectories'
  | 'memory'
  | 'observability'
  | 'agents'

interface NavItem {
  id: View
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
      { id: 'mission-control', label: 'Mission Control', icon: '◉' },
      { id: 'task-board',      label: 'Task Board',      icon: '▦' },
      { id: 'runs',            label: 'Run History',      icon: '▸' },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { id: 'trajectories',   label: 'Trajectories',    icon: '◈' },
      { id: 'memory',          label: 'Memory',           icon: '⬡' },
      { id: 'observability',   label: 'Observability',    icon: '◐' },
    ],
  },
  {
    label: 'System',
    items: [
      { id: 'agents',          label: 'Agents',           icon: '⬢' },
    ],
  },
]

interface SidebarProps {
  activeView: View
  onNavigate: (view: View) => void
  counts?: Partial<Record<View, number>>
}

const sidebarStyle: CSSProperties = {
  width: 232,
  flexShrink: 0,
  background: 'var(--bg-surface)',
  borderRight: '1px solid var(--border-subtle)',
  display: 'flex',
  flexDirection: 'column',
  position: 'relative',
}

const edgeGradient: CSSProperties = {
  position: 'absolute',
  top: 0, right: -1,
  width: 1, height: '100%',
  background: 'linear-gradient(180deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.03) 40%, transparent 100%)',
  pointerEvents: 'none',
}

export function Sidebar({ activeView, onNavigate, counts = {} }: SidebarProps) {
  return (
    <nav style={sidebarStyle}>
      <div style={edgeGradient} />

      {/* Logo */}
      <div style={{ padding: '24px 20px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <LogoDiamond />
          <div>
            <div style={{ fontSize: 15, fontWeight: 300, letterSpacing: 5, color: 'var(--text-primary)' }}>JUSTAI</div>
            <div style={{ fontSize: 9, fontWeight: 400, letterSpacing: 2, color: 'var(--text-muted)', marginTop: 2 }}>v2.0</div>
          </div>
        </div>
      </div>

      {/* Nav Groups */}
      {NAV_GROUPS.map(group => (
        <div key={group.label} style={{ padding: '20px 12px 4px' }}>
          <div style={{
            fontSize: 10, fontWeight: 500, color: 'var(--text-dim)',
            letterSpacing: 2.5, textTransform: 'uppercase', padding: '0 12px', marginBottom: 6,
          }}>
            {group.label}
          </div>
          {group.items.map(item => {
            const isActive = item.id === activeView
            return (
              <div
                key={item.id}
                data-active={isActive}
                onClick={() => onNavigate(item.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '9px 12px', borderRadius: 'var(--r-sm)',
                  fontSize: 13, fontWeight: 300, cursor: 'pointer',
                  color: isActive ? '#fce7f3' : 'var(--text-tertiary)',
                  background: isActive ? 'rgba(244,63,94,0.05)' : 'transparent',
                  border: isActive ? '1px solid rgba(244,63,94,0.07)' : '1px solid transparent',
                  position: 'relative',
                  transition: 'all var(--t-fast)',
                  marginBottom: 1,
                }}
              >
                {isActive && (
                  <div style={{
                    position: 'absolute', left: 0, top: '20%', bottom: '20%', width: 2,
                    background: 'var(--rose-500)', borderRadius: '0 2px 2px 0',
                    boxShadow: '0 0 8px rgba(244,63,94,0.3)',
                  }} />
                )}
                <span style={{ width: 18, textAlign: 'center', fontSize: 12, opacity: isActive ? 0.9 : 0.5 }}>
                  {item.icon}
                </span>
                {item.label}
                {counts[item.id] != null && (
                  <span style={{
                    marginLeft: 'auto', fontSize: 10, fontWeight: 500,
                    fontFamily: 'var(--font-mono)',
                    color: isActive ? 'var(--rose-400)' : 'var(--text-dim)',
                    background: isActive ? 'rgba(244,63,94,0.08)' : 'rgba(255,255,255,0.03)',
                    padding: '2px 6px', borderRadius: 4, minWidth: 20, textAlign: 'center',
                  }}>
                    {counts[item.id]}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      ))}

      {/* Footer */}
      <div style={{ marginTop: 'auto', padding: '16px 20px', borderTop: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: 'var(--emerald-500)', boxShadow: '0 0 8px var(--emerald-glow)',
            animation: 'breathe 4s ease-in-out infinite',
          }} />
          <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 300 }}>All systems operational</span>
        </div>
        <ThemeToggle />
      </div>
    </nav>
  )
}

function LogoDiamond() {
  return (
    <div style={{ width: 30, height: 30, position: 'relative', flexShrink: 0 }}>
      <div style={{
        position: 'absolute', width: 20, height: 20, top: '50%', left: '50%',
        transform: 'translate(-50%, -50%) rotate(45deg)',
        border: '1.5px solid rgba(244,63,94,0.45)', borderRadius: 3,
      }} />
      <div style={{
        position: 'absolute', width: 7, height: 7, top: '50%', left: '50%',
        transform: 'translate(-50%, -50%) rotate(45deg)',
        background: 'var(--rose-500)', borderRadius: 1.5,
        boxShadow: '0 0 14px rgba(244,63,94,0.4), 0 0 28px rgba(244,63,94,0.15)',
      }} />
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd dashboard && npx vitest run src/__tests__/Sidebar.test.tsx`
Expected: 4 tests passed

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/components/Sidebar.tsx dashboard/src/__tests__/Sidebar.test.tsx
git commit -m "feat(dashboard): add grouped Sidebar with Midnight Rose styling"
```

---

### Task 7: Restructure App.tsx

**Files:**
- Modify: `dashboard/src/App.tsx`
- Create: `dashboard/src/hooks/useKeyboard.ts`
- Create: `dashboard/src/__tests__/App.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// dashboard/src/__tests__/App.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import App from '../App'

describe('App', () => {
  it('renders the sidebar with grouped navigation', () => {
    render(<App />)
    expect(screen.getByText('Operations')).toBeInTheDocument()
    expect(screen.getByText('Intelligence')).toBeInTheDocument()
    expect(screen.getByText('System')).toBeInTheDocument()
  })

  it('renders Mission Control by default', () => {
    render(<App />)
    expect(screen.getByText('Mission Control')).toBeInTheDocument()
  })

  it('switches views when sidebar item clicked', () => {
    render(<App />)
    fireEvent.click(screen.getByText('Task Board'))
    // TaskBoard view should be visible (check for a kanban-specific element)
    expect(screen.getByText('Pending')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Implement useKeyboard hook**

```typescript
// dashboard/src/hooks/useKeyboard.ts
import { useEffect } from 'react'
import type { View } from '../components/Sidebar'

const VIEW_KEYS: Record<string, View> = {
  '1': 'mission-control',
  '2': 'task-board',
  '3': 'runs',
  '4': 'trajectories',
  '5': 'memory',
  '6': 'observability',
  '7': 'agents',
}

export function useKeyboard(onNavigate: (view: View) => void, onBack?: () => void) {
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      // Ignore when typing in inputs
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      const view = VIEW_KEYS[e.key]
      if (view) {
        e.preventDefault()
        onNavigate(view)
        return
      }

      if (e.key === 'Escape' && onBack) {
        e.preventDefault()
        onBack()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onNavigate, onBack])
}
```

- [ ] **Step 3: Rewrite App.tsx with new layout**

Rewrite `dashboard/src/App.tsx`. The existing file is ~221 lines. Replace entirely:

```tsx
// dashboard/src/App.tsx
import { useState, useEffect, useCallback } from 'react'
import { Sidebar, type View } from './components/Sidebar'
import { useKeyboard } from './hooks/useKeyboard'
import { SpacetimePoller } from './lib/spacetime'
import MissionControl from './views/MissionControl'
import TaskBoard from './views/TaskBoard'
import RunHistory from './views/RunHistory'
import TrajectoryViewer from './views/TrajectoryViewer'
import MemoryBrowser from './views/MemoryBrowser'
import AgentRegistry from './views/AgentRegistry'

export default function App() {
  const [view, setView] = useState<View>('mission-control')
  const [data, setData] = useState<any>({ tasks: [], agents: [], events: [] })
  const [selectedTask, setSelectedTask] = useState<any>(null)

  // SpacetimeDB polling (existing pattern)
  useEffect(() => {
    const poller = new SpacetimePoller((d: any) => setData(d))
    poller.start()
    return () => poller.stop()
  }, [])

  const navigate = useCallback((v: View) => {
    setView(v)
    setSelectedTask(null)
  }, [])

  useKeyboard(navigate)

  // Counts for sidebar badges
  const counts: Partial<Record<View, number>> = {
    'task-board': data.tasks?.filter((t: any) => t.status === 'running' || t.status === 'claimed').length || undefined,
    'runs': data.tasks?.length || undefined,
    'agents': data.agents?.length || undefined,
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '232px 1fr', height: '100vh', maxHeight: '100vh' }}>
      <Sidebar activeView={view} onNavigate={navigate} counts={counts} />

      <main style={{ overflowY: 'auto', overflowX: 'hidden', padding: '32px 32px 40px', position: 'relative' }}>
        {/* View container with crossfade transition */}
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

      {/* Task Detail Panel (Task Board drill-down) */}
      {selectedTask && view === 'task-board' && (
        <TaskDetailPanel task={selectedTask} onClose={() => setSelectedTask(null)} />
      )}
    </div>
  )
}

function PlaceholderView({ name, description }: { name: string; description: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
      <div style={{ fontSize: 22, fontWeight: 200, color: 'var(--text-primary)', letterSpacing: 0.3 }}>{name}</div>
      <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 8, fontWeight: 300 }}>{description}</div>
    </div>
  )
}

function TaskDetailPanel({ task, onClose }: { task: any; onClose: () => void }) {
  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0, width: 400,
      background: 'var(--bg-surface)', borderLeft: '1px solid var(--border-subtle)',
      padding: 'var(--sp-6)', overflowY: 'auto', zIndex: 20,
      boxShadow: 'var(--shadow-xl)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-5)' }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>Task Detail</div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 18 }}>×</button>
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 300, lineHeight: 1.6 }}>
        <div style={{ marginBottom: 8 }}><strong>ID:</strong> {task.id}</div>
        <div style={{ marginBottom: 8 }}><strong>Status:</strong> {task.status}</div>
        <div style={{ marginBottom: 8 }}><strong>Description:</strong> {task.description || task.payload}</div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Create AgentRegistry placeholder view**

```tsx
// dashboard/src/views/AgentRegistry.tsx
export default function AgentRegistry({ data }: { data: any }) {
  const agents = data?.agents ?? []

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--sp-6)' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 200, color: 'var(--text-primary)', letterSpacing: 0.3 }}>Agents</h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 5, fontWeight: 300 }}>
            {agents.length} registered agent{agents.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--sp-3)' }}>
        {agents.length === 0 && (
          <div className="panel panel-pad" style={{ gridColumn: '1 / -1', textAlign: 'center', padding: 'var(--sp-10)', color: 'var(--text-muted)', fontWeight: 300 }}>
            No agents registered
          </div>
        )}
        {agents.map((agent: any) => (
          <div key={agent.name} className="panel panel-pad">
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 'var(--sp-3)' }}>
              <div style={{
                width: 7, height: 7, borderRadius: '50%',
                background: agent.status === 'idle' || agent.status === 'active' ? 'var(--emerald-500)' : 'var(--text-dim)',
                boxShadow: agent.status === 'idle' || agent.status === 'active' ? '0 0 6px var(--emerald-glow)' : 'none',
              }} />
              <span style={{ fontSize: 14, fontWeight: 400, color: 'var(--text-primary)' }}>{agent.name}</span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 300 }}>
              {agent.capabilities || 'general'}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Run tests**

Run: `cd dashboard && npx vitest run src/__tests__/App.test.tsx`
Expected: 3 tests passed (may need adjustments based on how SpacetimePoller behaves in test env — mock if needed)

- [ ] **Step 6: Verify in browser**

Run: `cd dashboard && npm run dev`
Open http://localhost:3001 — verify:
- Grouped sidebar renders with three sections
- Clicking nav items switches views
- Theme toggle works (light/dark)
- Keyboard shortcuts 1-7 switch views

- [ ] **Step 7: Commit**

```bash
git add dashboard/src/App.tsx dashboard/src/hooks/useKeyboard.ts dashboard/src/views/AgentRegistry.tsx dashboard/src/__tests__/App.test.tsx
git commit -m "feat(dashboard): restructure App with grouped sidebar, keyboard shortcuts, AgentRegistry"
```

---

### Task 8: Restyle MissionControl

**Files:**
- Create: `dashboard/src/components/MetricCard.tsx`
- Create: `dashboard/src/components/Pipeline.tsx`
- Modify: `dashboard/src/views/MissionControl.tsx`

This is the most complex view. The approved mockup is the reference: `.superpowers/brainstorm/25878-1775975034/content/enterprise-dashboard.html`

- [ ] **Step 1: Create MetricCard component**

Build a reusable metric card with sparkline SVG and Popover integration. Accepts: `label`, `value`, `color`, `trend` (text + direction), `sparklinePoints` (optional array of numbers), `popoverContent` (optional ReactNode).

Key CSS: `border-radius: var(--r-lg)`, `background: var(--bg-surface)`, `border: 1px solid var(--border-subtle)`. Value in font-size 32px, weight 200, `font-variant-numeric: tabular-nums`. Sparkline as an SVG positioned `absolute bottom:0`, with gradient fill fading to transparent.

- [ ] **Step 2: Create Pipeline component**

Build the horizontal pipeline stage bar. Accepts: `stages` array with `{ name, status: 'done'|'active'|'waiting', detail }`. Uses CSS grid with `repeat(N, 1fr)`, 2px gap. Active stage gets a 2px rose bottom border with glow. Each stage wraps in `Popover` for drill-down.

- [ ] **Step 3: Rewrite MissionControl.tsx**

Structure:
1. Page header: title (22px, weight 200) + subtitle with live dot + time range buttons + "New Run" primary button
2. Metrics grid: 5 MetricCard components (Active, Completed, Success Rate, Cost, Latency)
3. Active Pipeline panel: Pipeline component + task detail bar with progress bar
4. Two-column grid: Services panel + Recent Runs panel
5. Pipeline Progress panel: scope tabs + gantt-style task timeline + ETA footer

All data from the `data` prop (SpacetimeDB polling). Where real data isn't available yet, use computed values from the data prop (e.g., count tasks by status for Active/Completed/Failed).

- [ ] **Step 4: Verify in browser**

Run: `cd dashboard && npm run dev`
Open http://localhost:3001 — Mission Control should render with:
- 5 metric cards with sparklines
- Pipeline bar showing stage status
- Services and Recent Runs panels
- All in Midnight Rose styling

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/components/MetricCard.tsx dashboard/src/components/Pipeline.tsx dashboard/src/views/MissionControl.tsx
git commit -m "feat(dashboard): redesign MissionControl with Midnight Rose styling"
```

---

### Task 9: Restyle TaskBoard

**Files:**
- Modify: `dashboard/src/views/TaskBoard.tsx`
- Modify: `dashboard/src/components/TaskCard.tsx`

- [ ] **Step 1: Restyle TaskBoard.tsx**

Replace all inline style objects with design tokens. Key changes:
- Page header: same pattern as MissionControl (22px weight-200 title)
- Kanban columns: `background: var(--bg-surface)`, `border: 1px solid var(--border-subtle)`, `border-radius: var(--r-lg)`
- Column headers: 10px weight-500 uppercase with letter-spacing 1.5px
- Running column header: `color: var(--rose-400)`; Done: `color: var(--emerald-400)`; Failed: `color: var(--red-500)`

- [ ] **Step 2: Restyle TaskCard.tsx**

Replace inline styles with design tokens. Running tasks get rose accent, completed get emerald, failed get red. Wrap each card in `<Popover>` with task detail (description, agent, duration, retry count).

- [ ] **Step 3: Verify in browser**

Check that the Task Board renders with the new styling, cards are clickable, and popovers appear on hover.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/views/TaskBoard.tsx dashboard/src/components/TaskCard.tsx
git commit -m "feat(dashboard): restyle TaskBoard with Midnight Rose design tokens"
```

---

### Task 10: Wire RunHistory + Restyle

**Files:**
- Modify: `dashboard/src/views/RunHistory.tsx`

The RunHistory view exists (209 lines) but was not wired into App.tsx routing (missing `view === 'runs'` case). Task 7 already wired it. Now restyle.

- [ ] **Step 1: Restyle RunHistory.tsx**

Apply Midnight Rose design tokens to all inline styles:
- Page header with title and "trigger run" form
- Run history table with column headers (9px uppercase), status dots, monospace cost/model values
- Active run status card with progress indicator
- Goal input field: `background: var(--bg-surface)`, `border: 1px solid var(--border-default)`, `border-radius: var(--r-sm)`

- [ ] **Step 2: Verify in browser**

Navigate to Run History via sidebar. Verify it renders and the run trigger form works.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/views/RunHistory.tsx
git commit -m "feat(dashboard): restyle RunHistory with Midnight Rose design tokens"
```

---

### Task 11: Restyle MemoryBrowser

**Files:**
- Modify: `dashboard/src/views/MemoryBrowser.tsx`

- [ ] **Step 1: Restyle MemoryBrowser.tsx**

Apply design tokens. Key changes:
- Search input: `background: var(--bg-surface)`, `border: 1px solid var(--border-default)`, placeholder color `var(--text-dim)`
- Memory entry list: panel styling, hover state with `var(--bg-hover)`
- Key/value display: key in `var(--text-secondary)`, value in monospace `var(--font-mono)`
- Store form: matching input/button styles
- Namespace filter: tab-style selector with active state

- [ ] **Step 2: Verify in browser**

Navigate to Memory view. Verify search, namespace filtering, and store operations render correctly.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/views/MemoryBrowser.tsx
git commit -m "feat(dashboard): restyle MemoryBrowser with Midnight Rose design tokens"
```

---

### Task 12: Restyle TrajectoryViewer

**Files:**
- Modify: `dashboard/src/views/TrajectoryViewer.tsx`

Note: This is visual-only restyling. The three-mode redesign (post-mortem/learning/audit) is Slice 3.

- [ ] **Step 1: Restyle TrajectoryViewer.tsx**

Apply design tokens. Key changes:
- File list sidebar: `background: var(--bg-surface)`, file items with hover states
- Step viewer: expandable sections with `border: 1px solid var(--border-subtle)`
- Command output blocks: monospace font, `background: rgba(0,0,0,0.3)` (dark within dark)
- Metadata badges: step count, model, exit status using rose/emerald/red accents
- Reasoning text: `color: var(--text-secondary)`, weight 300

- [ ] **Step 2: Verify in browser**

Navigate to Trajectories view. Verify file list loads and step expansion works.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/views/TrajectoryViewer.tsx
git commit -m "feat(dashboard): restyle TrajectoryViewer with Midnight Rose design tokens"
```

---

### Task 13: Python Test Updates

**Files:**
- Modify: `tests/test_sprint9.py` (or create new `tests/test_slice1.py`)

The Python test suite checks dashboard file existence and content. Update to reflect the new file structure.

- [ ] **Step 1: Write tests for new files**

```python
# tests/test_slice1.py
"""Slice 1: Glass Aurora Redesign — structural tests."""
import pathlib
import pytest

DASH = pathlib.Path(__file__).resolve().parents[1] / "dashboard" / "src"

class TestDesignSystem:
    def test_theme_css_exists(self):
        assert (DASH / "styles" / "theme.css").exists()

    def test_theme_css_has_dark_tokens(self):
        css = (DASH / "styles" / "theme.css").read_text()
        assert "--bg-void" in css
        assert "--rose-500" in css
        assert "--font-mono" in css

    def test_theme_css_has_light_mode(self):
        css = (DASH / "styles" / "theme.css").read_text()
        assert '[data-theme="light"]' in css

    def test_old_index_css_removed(self):
        assert not (DASH / "index.css").exists()

class TestComponents:
    def test_sidebar_exists(self):
        assert (DASH / "components" / "Sidebar.tsx").exists()

    def test_popover_exists(self):
        assert (DASH / "components" / "Popover.tsx").exists()

    def test_theme_toggle_exists(self):
        assert (DASH / "components" / "ThemeToggle.tsx").exists()

    def test_metric_card_exists(self):
        assert (DASH / "components" / "MetricCard.tsx").exists()

    def test_pipeline_exists(self):
        assert (DASH / "components" / "Pipeline.tsx").exists()

class TestViews:
    def test_agent_registry_exists(self):
        assert (DASH / "views" / "AgentRegistry.tsx").exists()

    def test_all_views_exist(self):
        views = ["MissionControl", "TaskBoard", "RunHistory", "TrajectoryViewer", "MemoryBrowser", "AgentRegistry"]
        for v in views:
            assert (DASH / "views" / f"{v}.tsx").exists(), f"Missing view: {v}"

class TestHooks:
    def test_use_theme_exists(self):
        assert (DASH / "hooks" / "useTheme.ts").exists()

    def test_use_keyboard_exists(self):
        assert (DASH / "hooks" / "useKeyboard.ts").exists()

class TestAppStructure:
    def test_app_imports_sidebar(self):
        app = (DASH / "App.tsx").read_text()
        assert "Sidebar" in app

    def test_app_has_grouped_nav(self):
        app = (DASH / "App.tsx").read_text()
        assert "observability" in app
        assert "agents" in app

    def test_index_html_has_theme_attr(self):
        html = (DASH.parent / "index.html").read_text()
        assert 'data-theme="dark"' in html

    def test_index_html_has_jetbrains_mono(self):
        html = (DASH.parent / "index.html").read_text()
        assert "JetBrains+Mono" in html or "JetBrains Mono" in html
```

- [ ] **Step 2: Run Python tests**

Run: `python3 -m pytest tests/test_slice1.py -v`
Expected: All tests pass

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All 289 existing tests + new tests pass. Fix any broken tests from the index.css removal or file restructuring.

- [ ] **Step 4: Commit**

```bash
git add tests/test_slice1.py
git commit -m "test: add Slice 1 structural tests for Glass Aurora redesign"
```

---

### Task 14: Final Integration + Visual QA

**Files:** None (verification only)

- [ ] **Step 1: Run all frontend tests**

Run: `cd dashboard && npm test`
Expected: All vitest tests pass

- [ ] **Step 2: Run all Python tests**

Run: `python3 -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Visual QA in browser**

Run: `cd dashboard && npm run dev`

Verify each view:
1. Mission Control: metric cards, pipeline, services, recent runs, pipeline progress
2. Task Board: kanban columns, task cards, detail panel
3. Run History: run table, trigger form
4. Trajectories: file list, step viewer
5. Memory: search, namespace filter, entry display
6. Observability: placeholder message
7. Agents: agent cards from SpacetimeDB

Verify cross-cutting:
- Dark/light mode toggle works on every view
- Keyboard shortcuts 1-7 switch views
- Popovers appear on hover with 150ms delay
- All text is readable in both themes
- Sidebar active indicator follows navigation

- [ ] **Step 4: Build check**

Run: `cd dashboard && npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(dashboard): Slice 1 complete — Glass Aurora Midnight Rose redesign"
```
