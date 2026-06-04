import { ref } from 'vue'
import { useAuth } from './useAuth.js'

const { authHeaders, API_BASE } = useAuth()

export function useMcp() {
  const myServers = ref([])
  const publicServers = ref([])
  const loading = ref(false)
  const error = ref('')

  async function fetchMyServers() {
    loading.value = true
    error.value = ''
    try {
      const res = await fetch(`${API_BASE}/mcp/servers`, { headers: authHeaders() })
      if (!res.ok) throw await res.json()
      myServers.value = await res.json()
    } catch (e) {
      error.value = e.detail?.message || e.error?.message || '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchPublicServers() {
    error.value = ''
    try {
      const res = await fetch(`${API_BASE}/mcp/servers/public`)
      if (!res.ok) throw await res.json()
      publicServers.value = await res.json()
    } catch (e) {
      error.value = e.detail?.message || e.error?.message || '加载失败'
    }
  }

  async function uploadServer(file, isPublic = false) {
    const formData = new FormData()
    formData.append('file', file)
    const endpoint = isPublic ? '/mcp/servers/public/upload' : '/mcp/servers/upload'
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Authorization': authHeaders()['Authorization'] },
      body: formData,
    })
    if (!res.ok) {
      const body = await res.json()
      const msg = typeof body?.detail === 'string' ? body.detail : (body?.detail?.message || '上传失败')
      throw new Error(msg)
    }
    await fetchMyServers()
    if (isPublic) await fetchPublicServers()
  }

  async function deleteServer(id) {
    const res = await fetch(`${API_BASE}/mcp/servers/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    if (!res.ok) throw await res.json()
    myServers.value = myServers.value.filter(s => s.id !== id)
  }

  async function toggleServer(id) {
    const res = await fetch(`${API_BASE}/mcp/servers/${id}/toggle`, {
      method: 'PATCH',
      headers: authHeaders(),
    })
    if (!res.ok) throw await res.json()
    const updated = await res.json()
    const list = myServers.value
    const idx = list.findIndex(s => s.id === id)
    if (idx !== -1) {
      list[idx] = { ...list[idx], enabled: updated.enabled }
    }
  }

  return {
    myServers, publicServers, loading, error,
    fetchMyServers, fetchPublicServers, uploadServer, deleteServer, toggleServer,
  }
}
