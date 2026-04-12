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
