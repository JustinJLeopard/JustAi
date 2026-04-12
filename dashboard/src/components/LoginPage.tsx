import { useState } from 'react'
import { login } from '@/lib/auth'

interface LoginPageProps {
  onLogin: () => void
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const result = await login(username, password)
    setLoading(false)

    if (result.success) {
      onLogin()
    } else {
      setError(result.error || 'Login failed')
    }
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100vh', background: 'var(--bg-primary)',
    }}>
      <div style={{
        width: 360, padding: 'var(--sp-8)',
        background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--r-lg)', boxShadow: 'var(--shadow-lg)',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 'var(--sp-8)' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 10,
          }}>
            <div style={{
              width: 20, height: 20, transform: 'rotate(45deg)',
              background: 'linear-gradient(135deg, var(--rose-500), var(--rose-600))',
              borderRadius: 3, boxShadow: '0 0 12px rgba(244,63,94,0.3)',
            }} />
            <span style={{
              fontSize: 18, fontWeight: 300, letterSpacing: 5,
              color: 'var(--text-primary)',
            }}>
              JUSTAI
            </span>
          </div>
          <div style={{
            fontSize: 12, color: 'var(--text-muted)', marginTop: 8, fontWeight: 300,
          }}>
            Sign in to continue
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 'var(--sp-4)' }}>
            <label style={{
              display: 'block', fontSize: 10, fontWeight: 500,
              color: 'var(--text-muted)', textTransform: 'uppercase',
              letterSpacing: '1.5px', marginBottom: 6,
            }}>
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoFocus
              style={{
                width: '100%', padding: '10px 14px',
                background: 'var(--bg-elevated)', border: '1px solid var(--border-default)',
                borderRadius: 'var(--r-sm)', color: 'var(--text-primary)',
                fontSize: 13, fontWeight: 300, fontFamily: 'var(--font-sans)',
                outline: 'none', transition: 'border-color var(--t-fast)',
                boxSizing: 'border-box',
              }}
              onFocus={e => e.target.style.borderColor = 'var(--rose-500)'}
              onBlur={e => e.target.style.borderColor = 'var(--border-default)'}
            />
          </div>

          <div style={{ marginBottom: 'var(--sp-6)' }}>
            <label style={{
              display: 'block', fontSize: 10, fontWeight: 500,
              color: 'var(--text-muted)', textTransform: 'uppercase',
              letterSpacing: '1.5px', marginBottom: 6,
            }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              style={{
                width: '100%', padding: '10px 14px',
                background: 'var(--bg-elevated)', border: '1px solid var(--border-default)',
                borderRadius: 'var(--r-sm)', color: 'var(--text-primary)',
                fontSize: 13, fontWeight: 300, fontFamily: 'var(--font-sans)',
                outline: 'none', transition: 'border-color var(--t-fast)',
                boxSizing: 'border-box',
              }}
              onFocus={e => e.target.style.borderColor = 'var(--rose-500)'}
              onBlur={e => e.target.style.borderColor = 'var(--border-default)'}
            />
          </div>

          {error && (
            <div style={{
              padding: '8px 12px', marginBottom: 'var(--sp-4)',
              background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
              borderRadius: 'var(--r-sm)', color: 'var(--red-500)',
              fontSize: 12, fontWeight: 300,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username || !password}
            style={{
              width: '100%', padding: '11px',
              background: loading ? 'var(--bg-elevated)' : 'var(--rose-600)',
              border: 'none', borderRadius: 'var(--r-sm)',
              color: '#fff', fontSize: 13, fontWeight: 400,
              fontFamily: 'var(--font-sans)', letterSpacing: '0.3px',
              cursor: loading ? 'wait' : 'pointer',
              transition: 'all var(--t-fast)',
              opacity: (!username || !password) ? 0.5 : 1,
            }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
