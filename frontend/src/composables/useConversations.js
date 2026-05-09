import { ref } from 'vue'
import { useAuth } from './useAuth.js'

const { authHeaders, API_BASE, apiGet } = useAuth()

export function useConversations() {
  const conversations = ref([])
  const loading = ref(false)

  async function fetchConversations() {
    loading.value = true
    try {
      conversations.value = await apiGet('/conversations')
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  async function createConversation(title, skillIds, modelId) {
    const res = await fetch(`${API_BASE}/conversations`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        title,
        activated_skill_ids: skillIds,
        model_id: modelId,
      }),
    })
    if (!res.ok) throw await res.json()
    const conv = await res.json()
    await fetchConversations()
    return conv
  }

  async function deleteConversation(id) {
    const res = await fetch(`${API_BASE}/conversations/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    if (!res.ok) throw await res.json()
    conversations.value = conversations.value.filter(c => c.id !== id)
  }

  return {
    conversations, loading,
    fetchConversations, createConversation, deleteConversation,
  }
}
