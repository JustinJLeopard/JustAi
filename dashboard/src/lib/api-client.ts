/**
 * JustAi — Dashboard API Client
 *
 * Fetches health, runs, config from the Python API server (:3002).
 * Proxied through Vite at /api/*.
 */

export interface ServiceHealth {
  name: string
  url: string
  ok: boolean
  detail: string
}

export interface HealthData {
  services: ServiceHealth[]
  all_ok: boolean
  timestamp: number
}

export interface RunEntry {
  key: string
  goal?: string
  intent?: string
  tasks?: string
  done?: string
  failed?: string
  duration?: string
  session?: string
}

export interface ConfigData {
  version: string
  session_ref: string
  auto_mode: boolean
  litellm_url: string
  planner_model: string
  spacetimedb_url: string
}

export interface RunStatus {
  id?: string
  goal?: string
  status: string
  task_count?: number
  duration?: number
  error?: string
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function fetchHealth(): Promise<HealthData> {
  return apiFetch('/api/health')
}

export async function fetchRuns(limit = 20): Promise<RunEntry[]> {
  return apiFetch(`/api/runs?limit=${limit}`)
}

export async function fetchConfig(): Promise<ConfigData> {
  return apiFetch('/api/config')
}

export async function fetchRunStatus(): Promise<RunStatus> {
  return apiFetch('/api/run/status')
}

export async function triggerRun(goal: string, auto = false, session = ''): Promise<{ started: boolean; run_id?: string; error?: string }> {
  const res = await fetch('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal, auto, session }),
  })
  return res.json()
}
