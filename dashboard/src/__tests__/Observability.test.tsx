import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Observability } from '../views/Observability'

// Mock the API client
vi.mock('../lib/api-client', () => ({
  fetchCostData: vi.fn(),
  fetchLatencyData: vi.fn(),
  fetchQualityData: vi.fn(),
}))

import { fetchCostData, fetchLatencyData, fetchQualityData } from '../lib/api-client'

const emptyCost = { daily: [], total: 0, by_model: {}, by_stage: {}, models: [], input_tokens: 0, output_tokens: 0 }
const emptyLatency = { daily: [], p50: 0, p90: 0, p99: 0, avg_ms: 0, bottleneck: '', by_stage: {} }
const emptyQuality = { daily: [], overall_rate: 0, failure_categories: {}, first_try_total: 0, retry_total: 0, cost_quality: [], ai_insight: '' }

const sampleCost = {
  daily: [
    { date: '2026-04-10', total: 0.15, running_total: 0.15, by_model: { 'gpt-5.4': 0.15 }, by_stage: { planner: 0.10 }, input_tokens: 500, output_tokens: 200 },
    { date: '2026-04-11', total: 0.28, running_total: 0.43, by_model: { 'gpt-5.4': 0.20, 'claude-opus': 0.08 }, by_stage: { planner: 0.15 }, input_tokens: 800, output_tokens: 300 },
    { date: '2026-04-12', total: 0.42, running_total: 0.85, by_model: { 'gpt-5.4': 0.25, 'claude-opus': 0.17 }, by_stage: { planner: 0.10 }, input_tokens: 1200, output_tokens: 500 },
  ],
  total: 0.85,
  by_model: { 'gpt-5.4': 0.60, 'claude-opus': 0.25 },
  by_stage: { planner: 0.35, reviewer: 0.20, synthesizer: 0.15, 'intent-gate': 0.15 },
  models: ['gpt-5.4', 'claude-opus'],
  input_tokens: 2500,
  output_tokens: 1000,
}

const sampleLatency = {
  daily: [
    { date: '2026-04-12', avg_ms: 2100, p50: 1800, p90: 3200, p99: 5100, by_stage: {} },
  ],
  p50: 1800,
  p90: 3200,
  p99: 5100,
  avg_ms: 2100,
  bottleneck: 'planner',
  by_stage: { planner: 1200, reviewer: 500, synthesizer: 400 },
}

const sampleQuality = {
  daily: [
    { date: '2026-04-12', total: 10, success: 8, failed: 2, rate: 0.8, first_try: 6, retry: 2 },
  ],
  overall_rate: 0.8,
  failure_categories: { timeout: 1, 'agent error': 1 },
  first_try_total: 6,
  retry_total: 2,
  cost_quality: [
    { cost: 0.05, success: 1, session_id: 'run-1' },
    { cost: 0.08, success: 0, session_id: 'run-2' },
  ],
  ai_insight: 'Strong first-try success rate (75%) — plans are well-formed.',
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Observability', () => {
  it('renders the page title', async () => {
    ;(fetchCostData as any).mockResolvedValue(emptyCost)
    ;(fetchLatencyData as any).mockResolvedValue(emptyLatency)
    ;(fetchQualityData as any).mockResolvedValue(emptyQuality)

    render(<Observability />)
    expect(screen.getByText('Observability')).toBeInTheDocument()
  })

  it('shows time range selector buttons', async () => {
    ;(fetchCostData as any).mockResolvedValue(emptyCost)
    ;(fetchLatencyData as any).mockResolvedValue(emptyLatency)
    ;(fetchQualityData as any).mockResolvedValue(emptyQuality)

    render(<Observability />)
    expect(screen.getByText('7d')).toBeInTheDocument()
    expect(screen.getByText('30d')).toBeInTheDocument()
  })

  it('shows loading state initially', () => {
    ;(fetchCostData as any).mockReturnValue(new Promise(() => {}))
    ;(fetchLatencyData as any).mockReturnValue(new Promise(() => {}))
    ;(fetchQualityData as any).mockReturnValue(new Promise(() => {}))

    render(<Observability />)
    expect(screen.getByText('Loading observability data...')).toBeInTheDocument()
  })

  it('shows empty state when no data', async () => {
    ;(fetchCostData as any).mockResolvedValue(emptyCost)
    ;(fetchLatencyData as any).mockResolvedValue(emptyLatency)
    ;(fetchQualityData as any).mockResolvedValue(emptyQuality)

    render(<Observability />)
    await waitFor(() => {
      expect(screen.getByText('Run a control-plane sprint to generate cost data')).toBeInTheDocument()
    })
  })

  it('renders section labels for all three panels', async () => {
    ;(fetchCostData as any).mockResolvedValue(emptyCost)
    ;(fetchLatencyData as any).mockResolvedValue(emptyLatency)
    ;(fetchQualityData as any).mockResolvedValue(emptyQuality)

    render(<Observability />)
    await waitFor(() => {
      expect(screen.getByText('Cost')).toBeInTheDocument()
      expect(screen.getByText('Latency')).toBeInTheDocument()
      expect(screen.getByText('Quality')).toBeInTheDocument()
    })
  })

  it('displays cost total when data is present', async () => {
    ;(fetchCostData as any).mockResolvedValue(sampleCost)
    ;(fetchLatencyData as any).mockResolvedValue(sampleLatency)
    ;(fetchQualityData as any).mockResolvedValue(sampleQuality)

    render(<Observability />)
    await waitFor(() => {
      expect(screen.getByText('$0.85')).toBeInTheDocument()
    })
  })

  it('displays latency avg when data is present', async () => {
    ;(fetchCostData as any).mockResolvedValue(sampleCost)
    ;(fetchLatencyData as any).mockResolvedValue(sampleLatency)
    ;(fetchQualityData as any).mockResolvedValue(sampleQuality)

    render(<Observability />)
    await waitFor(() => {
      expect(screen.getByText('2.1s')).toBeInTheDocument()
    })
  })

  it('displays quality rate when data is present', async () => {
    ;(fetchCostData as any).mockResolvedValue(sampleCost)
    ;(fetchLatencyData as any).mockResolvedValue(sampleLatency)
    ;(fetchQualityData as any).mockResolvedValue(sampleQuality)

    render(<Observability />)
    await waitFor(() => {
      expect(screen.getByText('80%')).toBeInTheDocument()
    })
  })

  it('shows bottleneck callout when present', async () => {
    ;(fetchCostData as any).mockResolvedValue(sampleCost)
    ;(fetchLatencyData as any).mockResolvedValue(sampleLatency)
    ;(fetchQualityData as any).mockResolvedValue(sampleQuality)

    render(<Observability />)
    await waitFor(() => {
      expect(screen.getByText(/is your bottleneck/)).toBeInTheDocument()
    })
  })

  it('shows AI insight when present', async () => {
    ;(fetchCostData as any).mockResolvedValue(sampleCost)
    ;(fetchLatencyData as any).mockResolvedValue(sampleLatency)
    ;(fetchQualityData as any).mockResolvedValue(sampleQuality)

    render(<Observability />)
    await waitFor(() => {
      expect(screen.getByText('AI Insight')).toBeInTheDocument()
    })
  })

  it('shows token counts in cost panel', async () => {
    ;(fetchCostData as any).mockResolvedValue(sampleCost)
    ;(fetchLatencyData as any).mockResolvedValue(sampleLatency)
    ;(fetchQualityData as any).mockResolvedValue(sampleQuality)

    render(<Observability />)
    await waitFor(() => {
      expect(screen.getByText(/2,500 in/)).toBeInTheDocument()
    })
  })

  it('handles API failure gracefully', async () => {
    ;(fetchCostData as any).mockRejectedValue(new Error('Network error'))
    ;(fetchLatencyData as any).mockRejectedValue(new Error('Network error'))
    ;(fetchQualityData as any).mockRejectedValue(new Error('Network error'))

    render(<Observability />)
    await waitFor(() => {
      // Should show empty state, not crash
      expect(screen.getByText('Observability')).toBeInTheDocument()
    })
  })
})
