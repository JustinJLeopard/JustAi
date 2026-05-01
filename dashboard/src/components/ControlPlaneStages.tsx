import { type ReactNode } from 'react'
import { Popover } from './Popover'

export interface ControlPlaneStage {
  name: string
  status: 'done' | 'active' | 'waiting'
  detail: string
}

export interface ControlPlaneStagesProps {
  stages: ControlPlaneStage[]
  popoverData?: Record<string, ReactNode>
}

function StageCell({ stage }: { stage: ControlPlaneStage }) {
  const bgMap = {
    done:    'rgba(16,185,129,0.04)',
    active:  'rgba(244,63,94,0.06)',
    waiting: 'rgba(255,255,255,0.008)',
  }
  const nameColorMap = {
    done:    'var(--emerald-400)',
    active:  'var(--rose-400)',
    waiting: 'var(--text-dim)',
  }

  const isActive = stage.status === 'active'

  return (
    <div
      style={{
        padding: 'var(--sp-3) var(--sp-4)',
        textAlign: 'center',
        position: 'relative',
        background: bgMap[stage.status],
        transition: 'all var(--t-default)',
        cursor: 'default',
        borderBottom: isActive ? '2px solid var(--rose-500)' : '2px solid transparent',
        boxShadow: isActive ? '0 0 8px rgba(244,63,94,0.3)' : 'none',
      }}
    >
      <div style={{
        fontSize: 10, fontWeight: 500,
        textTransform: 'uppercase',
        letterSpacing: '2px',
        marginBottom: 3,
        color: nameColorMap[stage.status],
      }}>
        {stage.name}
      </div>
      <div style={{
        fontSize: 10, fontWeight: 300,
        color: 'var(--text-muted)',
        fontFamily: 'var(--font-mono)',
      }}>
        {stage.detail}
      </div>
    </div>
  )
}

export function ControlPlaneStages({ stages, popoverData = {} }: ControlPlaneStagesProps) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${stages.length}, 1fr)`,
      gap: 2,
      borderRadius: 'var(--r-md)',
      overflow: 'hidden',
      marginBottom: 'var(--sp-5)',
    }}>
      {stages.map(stage => {
        const popover = popoverData[stage.name]
        if (popover) {
          return (
            <Popover key={stage.name} content={popover} position="top">
              <StageCell stage={stage} />
            </Popover>
          )
        }
        return <StageCell key={stage.name} stage={stage} />
      })}
    </div>
  )
}
