import { type ReactNode } from 'react'
import { Popover } from './Popover'

export interface MetricCardProps {
  label: string
  value: string
  color: string
  trend?: string
  trendDirection?: 'up' | 'down' | 'flat'
  sparklinePoints?: number[]
  sparklineColor?: string
  popoverContent?: ReactNode
}

function Sparkline({ points, color }: { points: number[]; color: string }) {
  if (points.length < 2) return null

  const w = 200
  const h = 36
  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min || 1

  const toX = (i: number) => (i / (points.length - 1)) * w
  const toY = (v: number) => h - ((v - min) / range) * (h - 4) - 2

  const pts = points.map((v, i) => `${toX(i)},${toY(v)}`).join(' ')
  const polyPts = `0,${h} ${pts} ${w},${h}`

  const gradId = `spark-${color.replace(/[^a-z0-9]/gi, '')}`

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      style={{
        position: 'absolute',
        bottom: 0, left: 0, right: 0,
        height: 36,
        pointerEvents: 'none',
        display: 'block',
      }}
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.18" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={polyPts} fill={`url(#${gradId})`} />
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="1.2"
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity="0.6"
      />
    </svg>
  )
}

function CardInner({
  label, value, color, trend, trendDirection, sparklinePoints, sparklineColor,
}: Omit<MetricCardProps, 'popoverContent'>) {
  const trendColor =
    trendDirection === 'up'   ? 'var(--emerald-400)' :
    trendDirection === 'down' ? 'var(--red-500)' :
    'var(--text-muted)'

  return (
    <div
      style={{
        padding: 'var(--sp-4) var(--sp-4) var(--sp-3)',
        borderRadius: 'var(--r-lg)',
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        position: 'relative',
        overflow: 'hidden',
        transition: 'all var(--t-default)',
        cursor: 'default',
      }}
      onMouseEnter={e => {
        const el = e.currentTarget as HTMLDivElement
        el.style.borderColor = 'var(--border-hover)'
        el.style.background = 'var(--bg-elevated)'
        el.style.boxShadow = 'var(--shadow-md)'
        el.style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={e => {
        const el = e.currentTarget as HTMLDivElement
        el.style.borderColor = 'var(--border-subtle)'
        el.style.background = 'var(--bg-surface)'
        el.style.boxShadow = ''
        el.style.transform = ''
      }}
    >
      <div style={{
        fontSize: 10, fontWeight: 500,
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        letterSpacing: '1.8px',
        marginBottom: 'var(--sp-2)',
      }}>
        {label}
      </div>

      <div style={{
        fontSize: 32, fontWeight: 200,
        lineHeight: 1,
        color,
        marginBottom: 'var(--sp-2)',
        fontVariantNumeric: 'tabular-nums',
      }}>
        {value}
      </div>

      {trend && (
        <div style={{
          fontSize: 11, fontWeight: 400,
          letterSpacing: '0.2px',
          color: trendColor,
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--sp-1)',
        }}>
          {trend}
        </div>
      )}

      {sparklinePoints && sparklinePoints.length >= 2 && (
        <Sparkline
          points={sparklinePoints}
          color={sparklineColor ?? color}
        />
      )}
    </div>
  )
}

export function MetricCard(props: MetricCardProps) {
  const { popoverContent, ...rest } = props

  if (!popoverContent) {
    return <CardInner {...rest} />
  }

  return (
    <Popover content={popoverContent} position="bottom">
      <CardInner {...rest} />
    </Popover>
  )
}
