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
