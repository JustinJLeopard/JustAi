import { useState, useEffect, useCallback } from 'react'
import {
  MemoryEntry, MemoryStats,
  memoryHealth, memoryList, memorySearch, memoryStore,
  memoryDelete, memoryStats, memoryRetrieve,
} from '@/lib/memory-client'

export function MemoryBrowser() {
  const [connected, setConnected] = useState(false)
  const [entries, setEntries] = useState<MemoryEntry[]>([])
  const [stats, setStats] = useState<MemoryStats | null>(null)
  const [selected, setSelected] = useState<MemoryEntry | null>(null)
  const [fullValue, setFullValue] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [namespace, setNamespace] = useState('justai')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Store form
  const [showStore, setShowStore] = useState(false)
  const [storeKey, setStoreKey] = useState('')
  const [storeValue, setStoreValue] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const ok = await memoryHealth()
      setConnected(ok)
      if (!ok) { setError('MCP server unreachable'); return }

      const [list, st] = await Promise.all([
        memoryList(namespace),
        memoryStats(),
      ])
      setEntries(list)
      setStats(st)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [namespace])

  useEffect(() => { refresh() }, [refresh])

  // Load full value when entry selected
  useEffect(() => {
    if (!selected) { setFullValue(null); return }
    memoryRetrieve(selected.key, namespace)
      .then(v => setFullValue(v))
      .catch(() => setFullValue(selected.value))
  }, [selected, namespace])

  const handleSearch = async () => {
    if (!searchQuery.trim()) { refresh(); return }
    setLoading(true)
    setError(null)
    try {
      const results = await memorySearch(searchQuery, namespace)
      setEntries(results)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleStore = async () => {
    if (!storeKey.trim() || !storeValue.trim()) return
    try {
      await memoryStore(storeKey, storeValue, namespace)
      setStoreKey('')
      setStoreValue('')
      setShowStore(false)
      refresh()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleDelete = async (key: string) => {
    try {
      await memoryDelete(key, namespace)
      if (selected?.key === key) { setSelected(null); setFullValue(null) }
      refresh()
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: 'calc(100vh - 120px)' }}>

      {/* Top Bar: Health + Stats + Actions */}
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: '10px', padding: '14px 20px',
        display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap',
      }}>
        {/* Health indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{
            width: '8px', height: '8px', borderRadius: '50%',
            background: connected ? 'var(--accent-green)' : 'var(--accent-red)',
            boxShadow: connected ? '0 0 6px var(--accent-green)' : 'none',
          }} />
          <span style={{ fontSize: '12px', color: connected ? 'var(--text-secondary)' : 'var(--accent-red)' }}>
            {connected ? 'MCP :3100' : 'Disconnected'}
          </span>
        </div>

        {stats && (
          <>
            <StatBadge label="Entries" value={String(stats.totalEntries)} />
            <StatBadge label="Backend" value={stats.backend || '—'} />
            <StatBadge label="Namespaces" value={stats.namespaces.join(', ') || '—'} />
          </>
        )}

        {/* Namespace selector */}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>NS:</label>
          <input
            value={namespace}
            onChange={e => setNamespace(e.target.value)}
            style={{
              width: '100px', padding: '4px 8px', fontSize: '12px',
              background: 'var(--bg-primary)', border: '1px solid var(--border)',
              borderRadius: '4px', color: 'var(--text-primary)',
            }}
          />
        </div>

        <button
          onClick={() => setShowStore(!showStore)}
          style={{
            padding: '5px 12px', fontSize: '12px', fontWeight: 500,
            background: 'var(--accent-blue)', color: '#fff',
            border: 'none', borderRadius: '6px', cursor: 'pointer',
          }}
        >
          + Store
        </button>

        <button
          onClick={refresh}
          style={{
            padding: '5px 12px', fontSize: '12px',
            background: 'transparent', color: 'var(--text-muted)',
            border: '1px solid var(--border)', borderRadius: '6px', cursor: 'pointer',
          }}
        >
          Refresh
        </button>
      </div>

      {/* Store Form (collapsible) */}
      {showStore && (
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--accent-blue)',
          borderRadius: '10px', padding: '14px 20px',
          display: 'flex', gap: '10px', alignItems: 'flex-end',
        }}>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Key</label>
            <input
              value={storeKey}
              onChange={e => setStoreKey(e.target.value)}
              placeholder="justai/my-key"
              style={{
                width: '100%', padding: '6px 8px', fontSize: '12px', marginTop: '4px',
                background: 'var(--bg-primary)', border: '1px solid var(--border)',
                borderRadius: '4px', color: 'var(--text-primary)',
              }}
            />
          </div>
          <div style={{ flex: 2 }}>
            <label style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Value</label>
            <input
              value={storeValue}
              onChange={e => setStoreValue(e.target.value)}
              placeholder="Value to store..."
              style={{
                width: '100%', padding: '6px 8px', fontSize: '12px', marginTop: '4px',
                background: 'var(--bg-primary)', border: '1px solid var(--border)',
                borderRadius: '4px', color: 'var(--text-primary)',
              }}
            />
          </div>
          <button
            onClick={handleStore}
            style={{
              padding: '6px 16px', fontSize: '12px', fontWeight: 500,
              background: 'var(--accent-green)', color: '#fff',
              border: 'none', borderRadius: '6px', cursor: 'pointer',
            }}
          >
            Save
          </button>
        </div>
      )}

      {/* Search Bar */}
      <div style={{
        display: 'flex', gap: '8px',
      }}>
        <input
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="Semantic search (HNSW vector) or leave empty to list all..."
          style={{
            flex: 1, padding: '8px 14px', fontSize: '13px',
            background: 'var(--bg-card)', border: '1px solid var(--border)',
            borderRadius: '8px', color: 'var(--text-primary)',
          }}
        />
        <button
          onClick={handleSearch}
          style={{
            padding: '8px 20px', fontSize: '13px', fontWeight: 500,
            background: 'var(--accent-purple)', color: '#fff',
            border: 'none', borderRadius: '8px', cursor: 'pointer',
          }}
        >
          Search
        </button>
      </div>

      {error && (
        <div style={{
          padding: '10px 14px', borderRadius: '8px',
          background: 'rgba(239,68,68,0.1)', border: '1px solid var(--accent-red)',
          color: 'var(--accent-red)', fontSize: '12px',
        }}>
          {error}
        </div>
      )}

      {/* Content Area */}
      <div style={{ flex: 1, display: 'flex', gap: '16px', overflow: 'hidden' }}>

        {/* Key List */}
        <div style={{
          width: '340px', flexShrink: 0,
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: '10px', overflow: 'auto',
        }}>
          <div style={{
            padding: '10px 16px', borderBottom: '1px solid var(--border)',
            fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)',
            textTransform: 'uppercase', letterSpacing: '1px',
          }}>
            {searchQuery ? 'Search Results' : 'All Keys'} ({entries.length})
          </div>

          {loading && (
            <div style={{ padding: '20px 16px', color: 'var(--text-muted)', fontSize: '12px' }}>
              Loading...
            </div>
          )}

          {!loading && entries.length === 0 && (
            <div style={{ padding: '20px 16px', color: 'var(--text-muted)', fontSize: '12px' }}>
              {connected ? 'No entries found.' : 'Connect to MCP to browse memory.'}
            </div>
          )}

          {entries.map(entry => {
            const active = selected?.key === entry.key
            return (
              <button
                key={entry.key}
                onClick={() => setSelected(entry)}
                style={{
                  width: '100%', display: 'block', textAlign: 'left',
                  padding: '10px 16px',
                  background: active ? 'var(--bg-primary)' : 'transparent',
                  borderLeft: active ? '2px solid var(--accent-blue)' : '2px solid transparent',
                  border: 'none', borderBottom: '1px solid var(--border)',
                  cursor: 'pointer',
                }}
              >
                <div style={{
                  fontSize: '12px', fontWeight: active ? 600 : 400,
                  color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {entry.key}
                </div>
                <div style={{
                  fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {entry.value.slice(0, 80)}
                </div>
                {entry.similarity !== undefined && entry.similarity > 0 && (
                  <div style={{ fontSize: '10px', color: 'var(--accent-purple)', marginTop: '2px' }}>
                    similarity: {entry.similarity.toFixed(3)}
                  </div>
                )}
              </button>
            )
          })}
        </div>

        {/* Value Detail */}
        <div style={{
          flex: 1, background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: '10px', overflow: 'auto', padding: '16px',
        }}>
          {!selected ? (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              height: '100%', color: 'var(--text-muted)', fontSize: '14px',
            }}>
              Select a key to view its value
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <h3 style={{
                  margin: 0, fontSize: '14px', fontWeight: 600,
                  color: 'var(--text-primary)', flex: 1,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {selected.key}
                </h3>
                <button
                  onClick={() => handleDelete(selected.key)}
                  style={{
                    padding: '3px 10px', fontSize: '11px',
                    background: 'rgba(239,68,68,0.1)', color: 'var(--accent-red)',
                    border: '1px solid var(--accent-red)', borderRadius: '4px',
                    cursor: 'pointer',
                  }}
                >
                  Delete
                </button>
              </div>

              {selected.namespace && (
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Namespace: {selected.namespace}
                </div>
              )}

              <pre style={{
                margin: 0, padding: '14px', borderRadius: '8px',
                background: 'var(--bg-primary)', border: '1px solid var(--border)',
                fontSize: '13px', lineHeight: 1.6, color: 'var(--text-secondary)',
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                flex: 1, overflow: 'auto',
              }}>
                {fullValue ?? selected.value}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StatBadge({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
      <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        {label}
      </span>
      <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>
        {value}
      </span>
    </div>
  )
}
