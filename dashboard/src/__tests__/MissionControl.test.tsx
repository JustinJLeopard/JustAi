import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MissionControl } from '../views/MissionControl'
import type { LiveData } from '@/lib/realtime'

// Mock the API client — MissionControl polls it on mount.
vi.mock('../lib/api-client', () => ({
  fetchHealth: vi.fn(),
  fetchRuns: vi.fn(),
  fetchObservabilitySummary: vi.fn(),
}))

import { fetchHealth, fetchRuns, fetchObservabilitySummary } from '../lib/api-client'

const idleData: LiveData = {
  tasks: [],
  agents: [],
  events: [],
  connected: true,
  lastUpdated: null,
  error: null,
  transport: 'polling',
}

/** What /api/health reports while no execution backend is integrated. */
const failClosedHealth = {
  services: [
    { name: 'LiteLLM', url: 'http://localhost:4000', ok: true, detail: 'models API reachable' },
    {
      name: 'safe-mini boundary',
      url: 'justai.runner_protocol',
      ok: false,
      detail: 'protocol present; concrete runner not integrated',
    },
    { name: 'claude-flow MCP', url: 'http://127.0.0.1:3100', ok: true, detail: 'healthy' },
  ],
  planning_ready: true,
  execution_ready: false,
  all_ok: false,
  timestamp: 0,
}

const readyHealth = {
  ...failClosedHealth,
  services: failClosedHealth.services.map(s =>
    s.name === 'safe-mini boundary' ? { ...s, ok: true, detail: 'runner integrated' } : s,
  ),
  execution_ready: true,
  all_ok: true,
}

describe('MissionControl readiness', () => {
  beforeEach(() => {
    vi.mocked(fetchRuns).mockResolvedValue([])
    vi.mocked(fetchObservabilitySummary).mockRejectedValue(new Error('no observability'))
  })

  it('says execution is unavailable while the run path fails closed', async () => {
    vi.mocked(fetchHealth).mockResolvedValue(failClosedHealth)

    render(<MissionControl data={idleData} />)

    // The dashboard renders a five-stage control plane including Execute. It
    // must not leave an operator to infer that the stage can run.
    await waitFor(() => {
      expect(screen.getByTestId('execution-unavailable')).toBeInTheDocument()
    })
    const banner = screen.getByTestId('execution-unavailable')
    expect(banner).toHaveTextContent(/execution unavailable/i)
    expect(banner).toHaveTextContent(/fails closed/i)

    // The probe the verdict comes from is named, not just its conclusion.
    expect(screen.getByText('safe-mini boundary')).toBeInTheDocument()
    expect(
      screen.getByText('protocol present; concrete runner not integrated'),
    ).toBeInTheDocument()
  })

  it('reports planning readiness separately from execution readiness', async () => {
    vi.mocked(fetchHealth).mockResolvedValue(failClosedHealth)

    render(<MissionControl data={idleData} />)

    await waitFor(() => {
      expect(screen.getByTestId('readiness-planning')).toHaveTextContent(/ready/i)
    })
    // Collapsing the two is the defect: planning works, execution does not.
    expect(screen.getByTestId('readiness-execution')).toHaveTextContent(/unavailable/i)
  })

  it('drops the unavailable claim once a runner is integrated', async () => {
    vi.mocked(fetchHealth).mockResolvedValue(readyHealth)

    render(<MissionControl data={idleData} />)

    await waitFor(() => {
      expect(screen.getByTestId('readiness-execution')).toHaveTextContent(/ready/i)
    })
    expect(screen.queryByTestId('execution-unavailable')).not.toBeInTheDocument()
  })
})
