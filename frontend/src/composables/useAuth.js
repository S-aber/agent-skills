import { ref, computed } from 'vue'

const API_BASE = '/api/v1'

const accessToken = ref(localStorage.getItem('access_token') || '')
const username = ref(localStorage.getItem('username') || '')

export function useAuth() {
  const isLoggedIn = computed(() => !!accessToken.value)

  function setToken(token, user) {
    accessToken.value = token
    username.value = user
    localStorage.setItem('access_token', token)
    localStorage.setItem('username', user)
  }

  function clearToken() {
    accessToken.value = ''
    username.value = ''
    localStorage.removeItem('access_token')
    localStorage.removeItem('username')
  }

  async function login(uname, password) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: uname, password }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail?.message || err.error?.message || '登录失败')
    }
    const data = await res.json()
    setToken(data.access_token, uname)
    return data
  }

  async function register(uname, password) {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: uname, password }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail?.message || err.error?.message || '注册失败')
    }
    const data = await res.json()
    setToken(data.access_token, uname)
    return data
  }

  function logout() {
    clearToken()
    window.location.href = '/login'
  }

  function authHeaders() {
    return {
      'Authorization': `Bearer ${accessToken.value}`,
      'Content-Type': 'application/json',
    }
  }

  async function apiGet(path) {
    const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() })
    if (res.status === 401) { clearToken(); window.location.href = '/login'; return }
    if (!res.ok) throw await res.json()
    return res.json()
  }

  async function apiPost(path, body) {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(body),
    })
    if (res.status === 401) { clearToken(); window.location.href = '/login'; return }
    if (!res.ok) throw await res.json()
    return res.json()
  }

  async function apiDelete(path) {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    if (res.status === 401) { clearToken(); window.location.href = '/login'; return }
    if (!res.ok) throw await res.json()
    return res.json()
  }

  return {
    accessToken, username, isLoggedIn,
    login, register, logout,
    apiGet, apiPost, apiDelete, authHeaders, API_BASE,
  }
}
