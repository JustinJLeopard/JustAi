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

  // Collect known namespaces for tab filter
  const knownNamespaces = stats?.namespaces?.length
    ? stats.namespaces
    : ['justai']

  const inputStyle = {
    background: 'var(--bg-surface)',
    border: '1px solid var(--border-default)',
    borderRadius: 'var(--r-sm)',
    color: 'var(--text-primary)',
    outline: 'none',
    fontFamily: 'var(--font-sans)',
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: 'calc(100vh - 120px)' }}>

      {/* Page Header */}
      <div>
        <div style={{ fontSize: '22px', fontWeight: 200, color: 'var(--text-primary)', letterSpacing: '-0.3px' }}>
          Memory
        </div>
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          {connected ? 'MCP :3100 connected' : 'Disconnected'}
        </div>
      </div>

      {/* Top Bar: Health + Stats + Actions */}
      <div style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--r-md)',
        padding: '14px 20px',
        display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap',
      }}>
        {/* Health indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{
            width: '8px', height: '8px', borderRadius: '50%',
            background: connected ? 'var(--emerald-400)' : 'var(--red-500)',
            boxShadow: connected ? '0 0 6px var(--emerald-glow)' : 'none',
          }} />
          <span style={{ fontSize: '12px', color: connected ? 'var(--text-secondary)' : 'var(--red-500)' }}>
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

        {/* Namespace input */}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <label style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' as const, letterSpacing: '0.5px' }}>NS:</label>
          <input
            value={namespace}
            onChange={e => setNamespace(e.target.value)}
            style={{
              ...inputStyle,
              width: '100px', padding: '4px 8px', fontSize: '12px',
            }}
          />
        </div>

        <button
          onClick={() => setShowStore(!showStore)}
          style={{
            padding: '5px 12px', fontSize: '12px', fontWeight: 500,
            background: 'rgba(244,63,94,0.1)',
            color: 'var(--rose-400)',
            border: '1px solid rgba(244,63,94,0.2)',
            borderRadius: 'var(--r-sm)', cursor: 'pointer',
            transition: 'opacity var(--t-fast)',
          }}
        >
          + Store
        </button>

        <button
          onClick={refresh}
          style={{
            padding: '5px 12px', fontSize: '12px',
            background: 'transparent', color: 'var(--text-secondary)',
            border: '1px solid var(--border-default)', borderRadius: 'var(--r-sm)', cursor: 'pointer',
            transition: 'border-color var(--t-fast)',
          }}
        >
          Refresh
        </button>
      </div>

      {/* Namespace Filter Tabs */}
      <div style={{ display: 'flex', gap: '4px' }}>
        {knownNamespaces.map(ns => (
          <button
            key={ns}
            onClick={() => setNamespace(ns)}
            style={{
              padding: '4px 12px', fontSize: '12px',
              background: namespace === ns ? 'var(--bg-elevated)' : 'transparent',
              color: namespace === ns ? 'var(--text-primary)' : 'var(--text-secondary)',
              border: `1px solid ${namespace === ns ? 'var(--border-default)' : 'var(--border-subtle)'}`,
              borderRadius: 'var(--r-sm)', cursor: 'pointer',
              transition: 'all var(--t-fast)',
            }}
          >
            {ns}
          </button>
        ))}
      </div>

      {/* Store Form (collapsible) */}
      {showStore && (
        <div style={{
          background: 'var(--bg-surface)',
          border: '1px solid rgba(244,63,94,0.2)',
          borderRadius: 'var(--r-md)',
          padding: '14px 20px',
          display: 'flex', gap: '10px', alignItems: 'flex-end',
        }}>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: '10px', color: 'var(--text-tertiary)', textTransform: 'uppercase' as const, letterSpacing: '0.5px' }}>Key</label>
            <input
              value={storeKey}
              onChange={e => setStoreKey(e.target.value)}
              placeholder="justai/my-key"
              style={{
                ...inputStyle,
                width: '100%', padding: '6px 8px', fontSize: '12px', marginTop: '4px',
                display: 'block',
              }}
            />
          </div>
          <div style={{ flex: 2 }}>
            <label style={{ fontSize: '10px', color: 'var(--text-tertiary)', textTransform: 'uppercase' as const, letterSpacing: '0.5px' }}>Value</label>
            <input
              value={storeValue}
              onChange={e => setStoreValue(e.target.value)}
              placeholder="Value to store..."
              style={{
                ...inputStyle,
                width: '100%', padding: '6px 8px', fontSize: '12px', marginTop: '4px',
                display: 'block',
              }}
            />
          </div>
          <button
            onClick={handleStore}
            style={{
              padding: '6px 16px', fontSize: '12px', fontWeight: 500,
              background: 'rgba(52,211,153,0.1)',
              color: 'var(--emerald-400)',
              border: '1px solid rgba(52,211,153,0.2)',
              borderRadius: 'var(--r-sm)', cursor: 'pointer',
            }}
          >
            Save
          </button>
        </div>
      )}

      {/* Search Bar */}
      <div style={{ display: 'flex', gap: '8px' }}>
        <input
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="Semantic search (HNSW vector) or leave empty to list all..."
          style={{
            ...inputStyle,
            flex: 1, padding: '8px 14px', fontSize: '13px',
          }}
        />
        <button
          onClick={handleSearch}
          style={{
            padding: '8px 20px', fontSize: '13px', fontWeight: 500,
            background: 'rgba(244,63,94,0.1)',
            color: 'var(--rose-400)',
            border: '1px solid rgba(244,63,94,0.2)',
            borderRadius: 'var(--r-sm)', cursor: 'pointer',
          }}
        >
          Search
        </button>
      </div>

      {error && (
        <div style={{
          padding: '10px 14px', borderRadius: 'var(--r-sm)',
          background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
          color: 'var(--red-500)', fontSize: '12px',
        }}>
          {error}
        </div>
      )}

      {/* Content Area */}
      <div style={{ flex: 1, display: 'flex', gap: '16px', overflow: 'hidden' }}>

        {/* Key List */}
        <div style={{
          width: '340px', flexShrink: 0,
          background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-md)', overflow: 'auto',
        }}>
          <div style={{
            padding: '10px 16px', borderBottom: '1px solid var(--border-subtle)',
            fontSize: '9px', fontWeight: 600, color: 'var(--text-tertiary)',
            textTransform: 'uppercase' as const, letterSpacing: '0.8px',
          }}>
            {searchQuery ? 'Search Results' : 'All Keys'} ({entries.length})
          </div>

          {loading && (
            <div style={{ padding: '20px 16px', color: 'var(--text-tertiary)', fontSize: '12px' }}>
              Loading...
            </div>
          )}

          {!loading && entries.length === 0 && (
            <div style={{ padding: '20px 16px', color: 'var(--text-tertiary)', fontSize: '12px' }}>
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
                  background: active ? 'var(--bg-elevated)' : 'transparent',
                  borderLeft: active ? '2px solid var(--rose-500)' : '2px solid transparent',
                  border: 'none', borderBottom: '1px solid var(--border-subtle)',
                  cursor: 'pointer',
                  transition: 'background var(--t-fast)',
                }}
                onMouseEnter={e => { if (!active) (e.currentTarget as HTMLButtonElement).style.background = 'var(--bg-hover)' }}
                onMouseLeave={e => { if (!active) (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
              >
                <div style={{
                  fontSize: '12px',
                  color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                }}>
                  {entry.key}
                </div>
                <div style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '2px',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                }}>
                  {entry.value.slice(0, 80)}
                </div>
                {entry.similarity !== undefined && entry.similarity > 0 && (
                  <div style={{ fontSize: '10px', color: 'var(--rose-400)', marginTop: '2px' }}>
                    similarity: {entry.similarity.toFixed(3)}
                  </div>
                )}
              </button>
            )
          })}
        </div>

        {/* Value Detail */}
        <div style={{
          flex: 1,
          background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-md)', overflow: 'auto', padding: '16px',
        }}>
          {!selected ? (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              height: '100%', color: 'var(--text-tertiary)', fontSize: '14px',
            }}>
              Select a key to view its value
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <h3 style={{
                  margin: 0, fontSize: '14px', fontWeight: 400,
                  color: 'var(--text-secondary)', flex: 1,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                }}>
                  {selected.key}
                </h3>
                <button
                  onClick={() => handleDelete(selected.key)}
                  style={{
                    padding: '3px 10px', fontSize: '11px',
                    background: 'rgba(239,68,68,0.08)', color: 'var(--red-500)',
                    border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--r-sm)',
                    cursor: 'pointer',
                  }}
                >
                  Delete
                </button>
              </div>

              {selected.namespace && (
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                  Namespace: {selected.namespace}
                </div>
              )}

              <pre style={{
                margin: 0, padding: '14px', borderRadius: 'var(--r-sm)',
                background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)',
                fontFamily: 'var(--font-mono)',
                fontSize: '11px', lineHeight: 1.6, color: 'var(--text-secondary)',
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
      <span style={{ fontSize: '9px', color: 'var(--text-tertiary)', textTransform: 'uppercase' as const, letterSpacing: '0.8px', fontWeight: 600 }}>
        {label}
      </span>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>
        {value}
      </span>
    </div>
  )
}
