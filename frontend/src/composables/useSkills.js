import { ref } from 'vue'
import { useAuth } from './useAuth.js'

const { authHeaders, API_BASE } = useAuth()

export function useSkills() {
  const mySkills = ref([])
  const publicSkills = ref([])
  const loading = ref(false)
  const error = ref('')

  async function fetchMySkills() {
    loading.value = true
    error.value = ''
    try {
      const res = await fetch(`${API_BASE}/skills`, { headers: authHeaders() })
      if (!res.ok) throw await res.json()
      mySkills.value = await res.json()
    } catch (e) {
      error.value = e.detail?.message || e.error?.message || '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchPublicSkills() {
    error.value = ''
    try {
      const res = await fetch(`${API_BASE}/skills/public`)
      if (!res.ok) throw await res.json()
      publicSkills.value = await res.json()
    } catch (e) {
      error.value = e.detail?.message || e.error?.message || '加载失败'
    }
  }

  async function uploadSkill(file, isPublic = false) {
    const formData = new FormData()
    formData.append('file', file)
    const endpoint = isPublic ? '/skills/public/upload' : '/skills/upload'
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Authorization': authHeaders()['Authorization'] },
      body: formData,
    })
    if (!res.ok) throw await res.json()
    await fetchMySkills()
    if (isPublic) await fetchPublicSkills()
  }

  async function deleteSkill(id) {
    const res = await fetch(`${API_BASE}/skills/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    if (!res.ok) throw await res.json()
    mySkills.value = mySkills.value.filter(s => s.id !== id)
  }

  return {
    mySkills, publicSkills, loading, error,
    fetchMySkills, fetchPublicSkills, uploadSkill, deleteSkill,
  }
}
