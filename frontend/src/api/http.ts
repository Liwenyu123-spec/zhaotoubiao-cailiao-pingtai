export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = localStorage.getItem('access_token')
  if (options.body && !headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(path, { ...options, headers })
  const data = await response.json().catch(() => null)
  if (response.status === 401 && path !== '/api/auth/login') {
    localStorage.removeItem('access_token')
    localStorage.removeItem('current_user')
    if (location.pathname !== '/login') location.assign('/login')
  }
  if (!response.ok) {
    const detail = data && typeof data === 'object' && 'detail' in data ? String(data.detail) : ''
    throw new Error(detail || `请求失败（${response.status}）`)
  }
  return data as T
}
