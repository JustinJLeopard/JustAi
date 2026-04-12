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
