import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { TrajectoryViewer } from '../views/TrajectoryViewer'

// Mock trajectory client
vi.mock('../lib/trajectories', () => ({
  listTrajectories: vi.fn(),
  loadTrajectory: vi.fn(),
  parseSteps: vi.fn(),
}))

// Mock API client
vi.mock('../lib/api-client', () => ({
  fetchTrajectoryAnalysis: vi.fn(),
  fetchTrajectoryPatterns: vi.fn(),
  fetchTrajectoryAudit: vi.fn(),
}))

import { listTrajectories, loadTrajectory, parseSteps } from '../lib/trajectories'
import { fetchTrajectoryAnalysis, fetchTrajectoryPatterns, fetchTrajectoryAudit } from '../lib/api-client'

const emptyPatterns = {
  total_trajectories: 0,
  avg_steps: 0,
  avg_cost: 0,
  success_rate: 0,
  common_failures: [],
  suggestions: ['No trajectory data available.'],
  efficiency_trend: [],
}

const samplePatterns = {
  total_trajectories: 5,
  avg_steps: 22,
  avg_cost: 0.04,
  success_rate: 0.8,
  common_failures: [{ pattern: 'bash: test failure', count: 2 }],
  suggestions: ['Success rate is improving but below 80%.'],
  efficiency_trend: [
    { date: '2026-04-11', runs: 3, avg_steps: 20, avg_cost: 0.03, success_rate: 0.67 },
    { date: '2026-04-12', runs: 2, avg_steps: 24, avg_cost: 0.05, success_rate: 1.0 },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  ;(listTrajectories as any).mockResolvedValue([])
  ;(loadTrajectory as any).mockResolvedValue(null)
  ;(parseSteps as any).mockReturnValue([])
  ;(fetchTrajectoryAnalysis as any).mockResolvedValue(null)
  ;(fetchTrajectoryPatterns as any).mockResolvedValue(emptyPatterns)
  ;(fetchTrajectoryAudit as any).mockResolvedValue(null)
})

describe('TrajectoryViewer', () => {
  it('renders the page title', () => {
    render(<TrajectoryViewer />)
    expect(screen.getByText('Trajectories')).toBeInTheDocument()
  })

  it('shows three mode tabs', () => {
    render(<TrajectoryViewer />)
    expect(screen.getByText('Post-Mortem')).toBeInTheDocument()
    expect(screen.getByText('Learning')).toBeInTheDocument()
    expect(screen.getByText('Audit')).toBeInTheDocument()
  })

  it('starts in Post-Mortem mode', () => {
    render(<TrajectoryViewer />)
    expect(screen.getByText('Select a trajectory to analyze')).toBeInTheDocument()
  })

  it('switches to Learning mode on tab click', async () => {
    ;(fetchTrajectoryPatterns as any).mockResolvedValue(samplePatterns)

    render(<TrajectoryViewer />)
    fireEvent.click(screen.getByText('Learning'))

    await waitFor(() => {
      expect(screen.getByText('AI Suggestions')).toBeInTheDocument()
    })
  })

  it('switches to Audit mode on tab click', () => {
    render(<TrajectoryViewer />)
    fireEvent.click(screen.getByText('Audit'))
    expect(screen.getByText('Select a trajectory to audit')).toBeInTheDocument()
  })

  it('Learning mode shows pattern metrics', async () => {
    ;(fetchTrajectoryPatterns as any).mockResolvedValue(samplePatterns)

    render(<TrajectoryViewer />)
    fireEvent.click(screen.getByText('Learning'))

    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument()  // total trajectories
      expect(screen.getByText('80%')).toBeInTheDocument()  // success rate
    })
  })

  it('Learning mode shows suggestions', async () => {
    ;(fetchTrajectoryPatterns as any).mockResolvedValue(samplePatterns)

    render(<TrajectoryViewer />)
    fireEvent.click(screen.getByText('Learning'))

    await waitFor(() => {
      expect(screen.getByText(/improving but below 80%/)).toBeInTheDocument()
    })
  })

  it('Learning mode shows common failures', async () => {
    ;(fetchTrajectoryPatterns as any).mockResolvedValue(samplePatterns)

    render(<TrajectoryViewer />)
    fireEvent.click(screen.getByText('Learning'))

    await waitFor(() => {
      expect(screen.getByText('Common Failure Patterns')).toBeInTheDocument()
    })
  })

  it('shows empty state when no trajectory data in Learning mode', async () => {
    ;(fetchTrajectoryPatterns as any).mockResolvedValue(emptyPatterns)

    render(<TrajectoryViewer />)
    fireEvent.click(screen.getByText('Learning'))

    await waitFor(() => {
      expect(screen.getByText(/No trajectory data available/)).toBeInTheDocument()
    })
  })

  it('handles API failure gracefully', async () => {
    ;(fetchTrajectoryPatterns as any).mockRejectedValue(new Error('fail'))

    render(<TrajectoryViewer />)
    fireEvent.click(screen.getByText('Learning'))

    // Should not crash
    await waitFor(() => {
      expect(screen.getByText('Trajectories')).toBeInTheDocument()
    })
  })
})
