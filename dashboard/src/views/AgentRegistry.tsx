import { useState, useEffect } from 'react'
import { fetchSwarmStatus, type SwarmStatus } from '@/lib/spacetime'

export default function AgentRegistry({ data }: { data: any }) {
  const agents = data?.agents ?? []
  const [swarm, setSwarm] = useState<SwarmStatus | null>(null)
  const [swarmError, setSwarmError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const s = await fetchSwarmStatus()
        if (active) { setSwarm(s); setSwarmError(null) }
      } catch (e) {
        if (active) setSwarmError(e instanceof Error ? e.message : 'Swarm unreachable')
      }
    }
    poll()
    const id = setInterval(poll, 5000)
    return () => { active = false; clearInterval(id) }
  }, [])

  const totalAgents = agents.length + (swarm?.agents?.length ?? 0)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--sp-6)' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 200, color: 'var(--text-primary)', letterSpacing: 0.3 }}>Agents</h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 5, fontWeight: 300 }}>
            {totalAgents} registered agent{totalAgents !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      {/* Swarm Status Bar */}
      <div className="panel panel-pad" style={{ marginBottom: 'var(--sp-4)', padding: 'var(--sp-3) var(--sp-4)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-4)', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
            <div style={{
              width: 7, height: 7, borderRadius: '50%',
              background: swarm?.status === 'running' ? 'var(--emerald-500)' : 'var(--text-dim)',
              boxShadow: swarm?.status === 'running' ? '0 0 6px var(--emerald-glow)' : 'none',
            }} />
            <span style={{ fontSize: 13, fontWeight: 400, color: 'var(--text-primary)' }}>
              Swarm
            </span>
          </div>
          {swarm ? (
            <>
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 300 }}>
                {swarm.topology} / {swarm.status}
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 300 }}>
                {swarm.agentCount}/{swarm.maxAgents} agents
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 300 }}>
                {swarm.taskCount} tasks
              </span>
              <span style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'monospace' }}>
                {swarm.swarmId}
              </span>
            </>
          ) : swarmError ? (
            <span style={{ fontSize: 11, color: 'var(--rose-400)', fontWeight: 300 }}>{swarmError}</span>
          ) : (
            <span style={{ fontSize: 11, color: 'var(--text-dim)', fontWeight: 300 }}>connecting...</span>
          )}
        </div>
      </div>

      {/* Agent Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--sp-3)' }}>
        {totalAgents === 0 && (
          <div className="panel panel-pad" style={{ gridColumn: '1 / -1', textAlign: 'center', padding: 'var(--sp-10)', color: 'var(--text-muted)', fontWeight: 300 }}>
            No agents registered
          </div>
        )}

        {/* control-plane data agents */}
        {agents.map((agent: any) => (
          <div key={agent.name} className="panel panel-pad">
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 'var(--sp-3)' }}>
              <div style={{
                width: 7, height: 7, borderRadius: '50%',
                background: agent.status === 'idle' || agent.status === 'active' ? 'var(--emerald-500)' : 'var(--text-dim)',
                boxShadow: agent.status === 'idle' || agent.status === 'active' ? '0 0 6px var(--emerald-glow)' : 'none',
              }} />
              <span style={{ fontSize: 14, fontWeight: 400, color: 'var(--text-primary)' }}>{agent.name}</span>
              <span style={{ fontSize: 10, color: 'var(--text-dim)', marginLeft: 'auto' }}>control-plane</span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 300 }}>
              {agent.capabilities || 'general'}
            </div>
          </div>
        ))}

        {/* Swarm agents */}
        {swarm?.agents?.map((agent) => (
          <div key={agent.agentId} className="panel panel-pad">
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 'var(--sp-3)' }}>
              <div style={{
                width: 7, height: 7, borderRadius: '50%',
                background: agent.status === 'registered' || agent.status === 'active' ? 'var(--sky-400)' : 'var(--text-dim)',
                boxShadow: agent.status === 'registered' || agent.status === 'active' ? '0 0 6px var(--sky-glow, rgba(56,189,248,0.3))' : 'none',
              }} />
              <span style={{ fontSize: 14, fontWeight: 400, color: 'var(--text-primary)' }}>{agent.role || agent.agentId}</span>
              <span style={{ fontSize: 10, color: 'var(--sky-400)', marginLeft: 'auto' }}>swarm</span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 300 }}>
              {agent.model || 'worker'} / {agent.status}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
