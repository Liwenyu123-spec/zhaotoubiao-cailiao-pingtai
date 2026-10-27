import { api } from './http'

export interface SessionUser {
  username: string
  display_name: string
  role: string
}

export async function login(username: string, password: string) {
  const result = await api<{ access_token: string; user: SessionUser }>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  localStorage.setItem('access_token', result.access_token)
  localStorage.setItem('current_user', JSON.stringify(result.user))
  return result.user
}

export function readUser(): SessionUser | null {
  const raw = localStorage.getItem('current_user')
  if (!raw) return null
  try {
    return JSON.parse(raw) as SessionUser
  } catch {
    return null
  }
}

export async function logout() {
  await api('/api/auth/logout', { method: 'POST' }).catch(() => null)
  localStorage.removeItem('access_token')
  localStorage.removeItem('current_user')
}
