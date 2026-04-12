/**
 * JustAi — Dashboard Auth Client
 *
 * Manages JWT token storage and auth state.
 * When JUSTAI_AUTH_ENABLED is false (default), all requests pass through.
 */

const TOKEN_KEY = 'justai_token'

export interface AuthUser {
  username: string
  role: 'admin' | 'operator'
}

export interface AuthState {
  authenticated: boolean
  user: AuthUser | null
  authEnabled: boolean
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export async function login(username: string, password: string): Promise<{ success: boolean; error?: string }> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  const data = await res.json()
  if (res.ok && data.token) {
    setToken(data.token)
    return { success: true }
  }
  return { success: false, error: data.error || 'Login failed' }
}

export async function checkAuth(): Promise<AuthState> {
  const token = getToken()
  try {
    const res = await fetch('/api/auth/me', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    const data = await res.json()

    if (data.auth_enabled === false) {
      // Auth not enabled — everyone is admin
      return { authenticated: true, user: { username: 'local', role: 'admin' }, authEnabled: false }
    }

    if (res.ok && data.username) {
      return { authenticated: true, user: { username: data.username, role: data.role }, authEnabled: true }
    }

    clearToken()
    return { authenticated: false, user: null, authEnabled: true }
  } catch {
    // API unreachable — allow through (single-user mode)
    return { authenticated: true, user: { username: 'local', role: 'admin' }, authEnabled: false }
  }
}

export function logout(): void {
  clearToken()
  window.location.reload()
}
