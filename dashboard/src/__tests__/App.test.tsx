import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import App from '../App'

// Mock auth to bypass login gate
vi.mock('../lib/auth', () => ({
  checkAuth: vi.fn().mockResolvedValue({
    authenticated: true,
    user: { username: 'local', role: 'admin' },
    authEnabled: false,
  }),
  getToken: vi.fn().mockReturnValue(null),
  setToken: vi.fn(),
  clearToken: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
}))

describe('App', () => {
  it('renders the sidebar with grouped navigation', async () => {
    render(<App />)
    await waitFor(() => {
      expect(screen.getByText('Operations')).toBeInTheDocument()
      expect(screen.getByText('Intelligence')).toBeInTheDocument()
      expect(screen.getAllByText('System').length).toBeGreaterThan(0)
    })
  })

  it('renders JUSTAI logo', async () => {
    render(<App />)
    await waitFor(() => {
      expect(screen.getByText('JUSTAI')).toBeInTheDocument()
    })
  })
})
