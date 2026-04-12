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

// ── Swarm Status (claude-flow MCP) ────────────────────────────────────────────

const MCP_URL = import.meta.env.VITE_MCP_URL ?? 'http://127.0.0.1:3100'

export interface SwarmAgent {
  agentId: string
  role: string
  status: string
  model: string
}

export interface SwarmStatus {
  swarmId: string
  status: string
  topology: string
  maxAgents: number
  agentCount: number
  taskCount: number
  agents: SwarmAgent[]
}

async function mcpCall(method: string, args: Record<string, unknown> = {}): Promise<unknown> {
  const res = await fetch(`${MCP_URL}/rpc`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: Date.now(),
      method: 'tools/call',
      params: { name: method, arguments: args },
    }),
  })
  if (!res.ok) throw new Error(`MCP error: ${res.status}`)
  const data = await res.json()
  const content = data.result?.content ?? []
  for (const item of content) {
    if (item.type === 'text') return JSON.parse(item.text)
  }
  return {}
}

export async function fetchSwarmStatus(): Promise<SwarmStatus> {
  const status = (await mcpCall('swarm_status')) as Record<string, unknown>
  const agentList = (await mcpCall('agent_list')) as { agents?: SwarmAgent[] }
  return {
    swarmId: String(status.swarmId ?? ''),
    status: String(status.status ?? 'unknown'),
    topology: String(status.topology ?? ''),
    maxAgents: Number(status.maxAgents ?? 0),
    agentCount: Number(status.agentCount ?? 0),
    taskCount: Number(status.taskCount ?? 0),
    agents: agentList.agents ?? [],
  }
}

// ── Live Data Types ──────────────────────────────────────────────────────────

export type TransportMode = 'websocket' | 'polling' | 'disconnected'

export interface LiveData {
  tasks: Task[]
  agents: Agent[]
  events: SpacetimeEvent[]
  connected: boolean
  lastUpdated: Date | null
  error: string | null
  transport: TransportMode
}

export type LiveDataCallback = (data: LiveData) => void

// ── WebSocket Client ────────────────────────────────────────────────────────
// Attempts WebSocket connection to SpacetimeDB for real-time push updates.
// Falls back to HTTP polling if WebSocket connection fails.

const WS_RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000] // exponential backoff

export class SpacetimeClient {
  private ws: WebSocket | null = null
  private pollIntervalId: ReturnType<typeof setInterval> | null = null
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  private reconnectAttempt = 0
  private transport: TransportMode = 'disconnected'
  private lastData: LiveData | null = null
  private stopped = false

  constructor(
    private cb: LiveDataCallback,
    private sessionRef?: string,
    private pollIntervalMs = 3000,
  ) {}

  start(): void {
    this.stopped = false
    this.tryWebSocket()
  }

  stop(): void {
    this.stopped = true
    this.closeWebSocket()
    this.stopPolling()
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }
  }

  getTransport(): TransportMode {
    return this.transport
  }

  // ── WebSocket connection ──────────────────────────────────────────────

  private tryWebSocket(): void {
    if (this.stopped) return

    try {
      // SpacetimeDB WebSocket endpoint for subscriptions
      const wsUrl = `${SPACETIME_URL}/database/subscribe/${DB_NAME}`
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        this.transport = 'websocket'
        this.reconnectAttempt = 0
        this.stopPolling() // Stop polling if it was running as fallback

        // Subscribe to table changes
        this.ws?.send(JSON.stringify({
          subscribe: {
            query_strings: [
              'SELECT * FROM tasks',
              'SELECT * FROM agents',
              'SELECT * FROM events',
            ],
          },
        }))

        // Still do an initial HTTP fetch for current state
        this.poll()
      }

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          // SpacetimeDB sends TransactionUpdate messages on data changes
          if (msg.TransactionUpdate || msg.SubscriptionUpdate || msg.type === 'transaction_update') {
            // Data changed — re-fetch current state via HTTP
            // (SpacetimeDB WS sends diffs, not full state; HTTP gives us the full picture)
            this.poll()
          }
        } catch {
          // Non-JSON message, ignore
        }
      }

      this.ws.onclose = () => {
        if (!this.stopped) {
          this.scheduleReconnect()
        }
      }

      this.ws.onerror = () => {
        // WebSocket failed — fall back to polling
        this.closeWebSocket()
        this.startPolling()
      }
    } catch {
      // WebSocket not available — fall back to polling
      this.startPolling()
    }
  }

  private closeWebSocket(): void {
    if (this.ws) {
      try { this.ws.close() } catch { /* ignore */ }
      this.ws = null
    }
  }

  private scheduleReconnect(): void {
    if (this.stopped) return

    // Start polling as fallback while reconnecting
    this.startPolling()

    const delay = WS_RECONNECT_DELAYS[Math.min(this.reconnectAttempt, WS_RECONNECT_DELAYS.length - 1)]
    this.reconnectAttempt++
    this.reconnectTimeout = setTimeout(() => {
      this.tryWebSocket()
    }, delay)
  }

  // ── HTTP Polling fallback ─────────────────────────────────────────────

  private startPolling(): void {
    if (this.pollIntervalId != null) return // Already polling
    this.transport = 'polling'
    this.poll()
    this.pollIntervalId = setInterval(() => this.poll(), this.pollIntervalMs)
  }

  private stopPolling(): void {
    if (this.pollIntervalId != null) {
      clearInterval(this.pollIntervalId)
      this.pollIntervalId = null
    }
  }

  private async poll(): Promise<void> {
    try {
      const [tasks, agents, events] = await Promise.all([
        fetchTasks(this.sessionRef),
        fetchAgents(),
        fetchEvents(30),
      ])
      this.lastData = {
        tasks, agents, events,
        connected: true,
        lastUpdated: new Date(),
        error: null,
        transport: this.transport,
      }
      this.cb(this.lastData)
    } catch (err) {
      this.cb({
        tasks: this.lastData?.tasks ?? [],
        agents: this.lastData?.agents ?? [],
        events: this.lastData?.events ?? [],
        connected: false,
        lastUpdated: this.lastData?.lastUpdated ?? null,
        error: err instanceof Error ? err.message : 'Connection failed',
        transport: this.transport,
      })
    }
  }
}

// ── Legacy Polling Client (kept for backwards compatibility) ─────────────────

export class SpacetimePoller {
  private client: SpacetimeClient

  constructor(cb: LiveDataCallback, sessionRef?: string) {
    this.client = new SpacetimeClient(cb, sessionRef)
  }

  start(intervalMs = 3000): void {
    // Legacy API: just start the unified client
    void intervalMs // interval is set in constructor
    this.client.start()
  }

  stop(): void {
    this.client.stop()
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
