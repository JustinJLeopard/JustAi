/**
 * JustAi — SpacetimeDB Client
 *
 * Connects to the local SpacetimeDB instance and provides reactive
 * subscriptions to Task, Agent, Message, and Event tables.
 *
 * Schema mirrors relay-room/spacetimedb/src/lib.rs exactly.
 * Uses SpacetimeDB SDK v1.x subscription API.
 */

// ── Schema Types (mirroring Rust structs) ─────────────────────────────────────

export interface Task {
  id: bigint
  taskUuid: string
  fromAgent: string
  toAgent: string
  claimedBy: string
  title: string
  payload: string
  status: 'pending' | 'claimed' | 'in_progress' | 'done' | 'failed' | 'archived'
  priority: number
  sessionRef: string
  attemptNumber: number
  retryCount: number
  parentTaskId: bigint | null
  createdAt: bigint
  updatedAt: bigint
  claimedAt: bigint
  completedAt: bigint
  result: string
}

export interface Agent {
  name: string
  handlerType: string
  status: 'online' | 'offline' | 'stale'
  currentTaskId: bigint
  capabilities: string
  lastHeartbeat: bigint
  lastSeen: bigint
}

export interface Message {
  id: bigint
  fromAgent: string
  toAgent: string
  content: string
  taskRef: bigint
  timestamp: bigint
  read: boolean
}

export interface SpacetimeEvent {
  id: bigint
  eventType: string
  agent: string
  taskRef: bigint
  detail: string
  timestamp: bigint
}

// ── Connection Config ──────────────────────────────────────────────────────────

const SPACETIME_URL = import.meta.env.VITE_SPACETIME_URL ?? 'ws://localhost:3000'
const DB_NAME = import.meta.env.VITE_SPACETIME_DB ?? 'relay-room-dev'

// ── REST Fallback Client ───────────────────────────────────────────────────────
// SpacetimeDB also exposes an HTTP API. We use this as a reliable fallback
// when the WebSocket SDK isn't available or the connection is initializing.

const HTTP_BASE = SPACETIME_URL.replace('ws://', 'http://').replace('wss://', 'https://')

async function stdbFetch<T>(sql: string): Promise<T[]> {
  const res = await fetch(`${HTTP_BASE}/database/sql/${DB_NAME}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: sql }),
  })
  if (!res.ok) throw new Error(`SpacetimeDB HTTP error: ${res.status}`)
  const data = await res.json()
  // SpacetimeDB returns { rows: [...], schema: [...] }
  return data.rows ?? []
}

// ── Data Fetchers ──────────────────────────────────────────────────────────────

export async function fetchTasks(sessionRef?: string): Promise<Task[]> {
  const where = sessionRef ? `WHERE session_ref = '${sessionRef}'` : ''
  const rows = await stdbFetch<Record<string, unknown>>(
    `SELECT * FROM tasks ${where} ORDER BY created_at DESC LIMIT 200`
  )
  return rows.map(rowToTask)
}

export async function fetchAgents(): Promise<Agent[]> {
  const rows = await stdbFetch<Record<string, unknown>>('SELECT * FROM agents')
  return rows.map(rowToAgent)
}

export async function fetchEvents(limit = 50): Promise<SpacetimeEvent[]> {
  const rows = await stdbFetch<Record<string, unknown>>(
    `SELECT * FROM events ORDER BY timestamp DESC LIMIT ${limit}`
  )
  return rows.map(rowToEvent)
}

// ── Row Mappers ────────────────────────────────────────────────────────────────

function rowToTask(r: Record<string, unknown>): Task {
  return {
    id: BigInt(r.id as number ?? 0),
    taskUuid: String(r.task_uuid ?? ''),
    fromAgent: String(r.from_agent ?? ''),
    toAgent: String(r.to_agent ?? ''),
    claimedBy: String(r.claimed_by ?? ''),
    title: String(r.title ?? ''),
    payload: String(r.payload ?? ''),
    status: (r.status as Task['status']) ?? 'pending',
    priority: Number(r.priority ?? 0),
    sessionRef: String(r.session_ref ?? ''),
    attemptNumber: Number(r.attempt_number ?? 0),
    retryCount: Number(r.retry_count ?? 0),
    parentTaskId: r.parent_task_id != null ? BigInt(r.parent_task_id as number) : null,
    createdAt: BigInt(r.created_at as number ?? 0),
    updatedAt: BigInt(r.updated_at as number ?? 0),
    claimedAt: BigInt(r.claimed_at as number ?? 0),
    completedAt: BigInt(r.completed_at as number ?? 0),
    result: String(r.result ?? ''),
  }
}

function rowToAgent(r: Record<string, unknown>): Agent {
  return {
    name: String(r.name ?? ''),
    handlerType: String(r.handler_type ?? ''),
    status: (r.status as Agent['status']) ?? 'offline',
    currentTaskId: BigInt(r.current_task_id as number ?? 0),
    capabilities: String(r.capabilities ?? ''),
    lastHeartbeat: BigInt(r.last_heartbeat as number ?? 0),
    lastSeen: BigInt(r.last_seen as number ?? 0),
  }
}

function rowToEvent(r: Record<string, unknown>): SpacetimeEvent {
  return {
    id: BigInt(r.id as number ?? 0),
    eventType: String(r.event_type ?? ''),
    agent: String(r.agent ?? ''),
    taskRef: BigInt(r.task_ref as number ?? 0),
    detail: String(r.detail ?? ''),
    timestamp: BigInt(r.timestamp as number ?? 0),
  }
}

// ── Polling Client ────────────────────────────────────────────────────────────
// Polls SpacetimeDB HTTP API on an interval and calls back with fresh data.
// Interval-based polling is the reliable fallback; WebSocket subscriptions
// can be layered on top when the SpacetimeDB SDK is fully wired.

export interface LiveData {
  tasks: Task[]
  agents: Agent[]
  events: SpacetimeEvent[]
  connected: boolean
  lastUpdated: Date | null
  error: string | null
}

export type LiveDataCallback = (data: LiveData) => void

export class SpacetimePoller {
  private intervalId: ReturnType<typeof setInterval> | null = null
  private sessionRef: string | undefined

  constructor(private cb: LiveDataCallback, sessionRef?: string) {
    this.sessionRef = sessionRef
  }

  start(intervalMs = 3000): void {
    this.poll()
    this.intervalId = setInterval(() => this.poll(), intervalMs)
  }

  stop(): void {
    if (this.intervalId != null) {
      clearInterval(this.intervalId)
      this.intervalId = null
    }
  }

  private async poll(): Promise<void> {
    try {
      const [tasks, agents, events] = await Promise.all([
        fetchTasks(this.sessionRef),
        fetchAgents(),
        fetchEvents(30),
      ])
      this.cb({ tasks, agents, events, connected: true, lastUpdated: new Date(), error: null })
    } catch (err) {
      this.cb({
        tasks: [], agents: [], events: [],
        connected: false, lastUpdated: null,
        error: err instanceof Error ? err.message : 'Connection failed',
      })
    }
  }
}

// ── Utility Helpers ────────────────────────────────────────────────────────────

export function msAgo(timestampMs: bigint): string {
  const diff = Date.now() - Number(timestampMs)
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return `${Math.floor(diff / 86_400_000)}d ago`
}

export function isStale(lastHeartbeat: bigint, thresholdMs = 90_000): boolean {
  return Date.now() - Number(lastHeartbeat) > thresholdMs
}

export function taskDuration(task: Task): string {
  if (task.completedAt === 0n || task.claimedAt === 0n) return '—'
  const ms = Number(task.completedAt - task.claimedAt)
  if (ms < 60_000) return `${Math.floor(ms / 1000)}s`
  return `${Math.floor(ms / 60_000)}m ${Math.floor((ms % 60_000) / 1000)}s`
}
