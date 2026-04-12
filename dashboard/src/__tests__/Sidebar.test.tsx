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
