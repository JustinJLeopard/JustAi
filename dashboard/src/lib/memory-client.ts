/**
 * JustAi — Memory Browser Client
 *
 * Browser-side client for claude-flow memory via MCP HTTP.
 * Proxied through Vite: /api/memory → http://127.0.0.1:3100
 */

// ── Types ──────────────────────────────────────────────────────────────────────

export interface MemoryEntry {
  key: string
  value: string
  namespace: string
  similarity?: number
  tags?: string[]
}

export interface MemoryStats {
  totalEntries: number
  backend: string
  namespaces: string[]
}

// ── JSON-RPC Transport ─────────────────────────────────────────────────────────

let initialized = false
let reqId = 0

async function rpc(method: string, params?: Record<string, unknown>): Promise<Record<string, unknown>> {
  const payload: Record<string, unknown> = {
    jsonrpc: '2.0',
    id: ++reqId,
    method,
  }
  if (params) payload.params = params

  const res = await fetch('/api/memory/rpc', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`MCP HTTP error: ${res.status}`)
  return res.json()
}

async function ensureInitialized(): Promise<void> {
  if (initialized) return
  await rpc('initialize', {
    protocolVersion: '2024-11-05',
    capabilities: {},
    clientInfo: { name: 'justai-dashboard', version: '1.0' },
  })
  initialized = true
}

async function callTool(name: string, args: Record<string, unknown>): Promise<Record<string, unknown>> {
  await ensureInitialized()
  try {
    const resp = await rpc('tools/call', { name, arguments: args })
    const result = (resp as any).result ?? {}
    const content = result.content ?? []
    if (!content.length) return {}
    const text = content[0]?.text ?? '{}'
    return JSON.parse(text)
  } catch (e) {
    // Re-init on server restart
    initialized = false
    await ensureInitialized()
    const resp = await rpc('tools/call', { name, arguments: args })
    const result = (resp as any).result ?? {}
    const content = result.content ?? []
    if (!content.length) return {}
    return JSON.parse(content[0]?.text ?? '{}')
  }
}

// ── Public API ─────────────────────────────────────────────────────────────────

export async function memoryHealth(): Promise<boolean> {
  try {
    const res = await fetch('/api/memory/health')
    const data = await res.json()
    return data.status === 'ok'
  } catch {
    return false
  }
}

export async function memoryStore(key: string, value: string, namespace = 'justai'): Promise<boolean> {
  const result = await callTool('memory_store', { key, value, namespace })
  return (result as any).success === true
}

export async function memoryRetrieve(key: string, namespace = 'justai'): Promise<string | null> {
  const result = await callTool('memory_retrieve', { key, namespace })
  return (result as any).value ?? null
}

export async function memorySearch(query: string, namespace = 'justai', limit = 20): Promise<MemoryEntry[]> {
  const result = await callTool('memory_search', { query, namespace, limit })
  return ((result as any).results ?? []).map((r: any) => ({
    key: r.key ?? '',
    value: r.value ?? '',
    namespace: r.namespace ?? namespace,
    similarity: r.similarity ?? 0,
    tags: r.tags ?? [],
  }))
}

export async function memoryList(namespace = 'justai'): Promise<MemoryEntry[]> {
  const result = await callTool('memory_list', { namespace })
  return ((result as any).entries ?? []).map((e: any) => ({
    key: e.key ?? '',
    value: e.value ?? '',
    namespace: e.namespace ?? namespace,
  }))
}

export async function memoryDelete(key: string, namespace = 'justai'): Promise<boolean> {
  const result = await callTool('memory_delete', { key, namespace })
  return (result as any).success === true
}

export async function memoryStats(): Promise<MemoryStats> {
  const result = await callTool('memory_stats', {})
  return {
    totalEntries: (result as any).totalEntries ?? 0,
    backend: (result as any).backend ?? '',
    namespaces: (result as any).namespaces ?? [],
  }
}
