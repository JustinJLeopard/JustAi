import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from '../App'

describe('App', () => {
  it('renders the sidebar with grouped navigation', () => {
    render(<App />)
    expect(screen.getByText('Operations')).toBeInTheDocument()
    expect(screen.getByText('Intelligence')).toBeInTheDocument()
    // 'System' may appear in multiple places (sidebar group label + MissionControl); just check at least one exists
    expect(screen.getAllByText('System').length).toBeGreaterThan(0)
  })

  it('renders JUSTAI logo', () => {
    render(<App />)
    expect(screen.getByText('JUSTAI')).toBeInTheDocument()
  })
})
