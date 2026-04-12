export default function AgentRegistry({ data }: { data: any }) {
  const agents = data?.agents ?? []

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--sp-6)' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 200, color: 'var(--text-primary)', letterSpacing: 0.3 }}>Agents</h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 5, fontWeight: 300 }}>
            {agents.length} registered agent{agents.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--sp-3)' }}>
        {agents.length === 0 && (
          <div className="panel panel-pad" style={{ gridColumn: '1 / -1', textAlign: 'center', padding: 'var(--sp-10)', color: 'var(--text-muted)', fontWeight: 300 }}>
            No agents registered
          </div>
        )}
        {agents.map((agent: any) => (
          <div key={agent.name} className="panel panel-pad">
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 'var(--sp-3)' }}>
              <div style={{
                width: 7, height: 7, borderRadius: '50%',
                background: agent.status === 'idle' || agent.status === 'active' ? 'var(--emerald-500)' : 'var(--text-dim)',
                boxShadow: agent.status === 'idle' || agent.status === 'active' ? '0 0 6px var(--emerald-glow)' : 'none',
              }} />
              <span style={{ fontSize: 14, fontWeight: 400, color: 'var(--text-primary)' }}>{agent.name}</span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 300 }}>
              {agent.capabilities || 'general'}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
