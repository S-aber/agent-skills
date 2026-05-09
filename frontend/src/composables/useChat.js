import { ref, reactive, nextTick } from 'vue'
import { useAuth } from './useAuth.js'

const { API_BASE } = useAuth()

export function useChat() {
  const messages = ref([])
  const isLoading = ref(false)
  const error = ref('')
  const currentToolCall = ref(null) // { tool_name, input }
  const toolResults = reactive({}) // tool_use_id -> result

  async function fetchHistory(convId) {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
      }
      const res = await fetch(`${API_BASE}/conversations/${convId}/messages?limit=100`, { headers })
      if (!res.ok) throw await res.json()
      const data = await res.json()
      messages.value = data.map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        tool_calls: m.tool_calls || [],
        createdAt: new Date(m.created_at),
      }))
    } catch (e) {
      error.value = '加载历史消息失败'
    }
  }

  async function sendMessage(convId, content) {
    if (!content.trim() || isLoading.value) return

    const token = localStorage.getItem('access_token')

    // Add user message
    messages.value.push({
      id: Date.now().toString(),
      role: 'user',
      content: content.trim(),
      createdAt: new Date(),
    })

    isLoading.value = true
    error.value = ''
    currentToolCall.value = null
    Object.keys(toolResults).forEach(k => delete toolResults[k])

    try {
      const res = await fetch(`${API_BASE}/conversations/${convId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({ content: content.trim() }),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail?.message || err.error?.message || '请求失败')
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentAssistantId = null
      let assistantContent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let eventType = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
            continue
          }
          if (!line.startsWith('data: ')) continue

          const dataStr = line.slice(6)
          try {
            const data = JSON.parse(dataStr)
            await handleSSEEvent(eventType, data, {
              getCurrentAssistantId: () => currentAssistantId,
              setCurrentAssistantId: (id) => { currentAssistantId = id },
              getAssistantContent: () => assistantContent,
              setAssistantContent: (c) => { assistantContent = c },
              addToContent: (c) => { assistantContent += c },
              resetAssistant: () => { currentAssistantId = null; assistantContent = '' },
            })
          } catch (e) {
            // skip parse errors
          }
        }
      }
    } catch (e) {
      error.value = e.message
    } finally {
      isLoading.value = false
      currentToolCall.value = null
    }
  }

  async function handleSSEEvent(eventType, data, ctx) {
    switch (eventType) {
      case 'assistant':
        if (data.content) {
          ctx.addToContent(data.content)
          const existing = messages.value.find(m => m.id === ctx.getCurrentAssistantId())
          if (existing) {
            existing.content = ctx.getAssistantContent()
          } else {
            const id = Date.now().toString()
            ctx.setCurrentAssistantId(id)
            messages.value.push({
              id,
              role: 'assistant',
              content: ctx.getAssistantContent(),
              tool_calls: [],
              isStreaming: true,
              createdAt: new Date(),
            })
          }
        }
        break

      case 'tool_use':
        currentToolCall.value = {
          tool_use_id: data.tool_use_id,
          tool_name: data.tool_name,
          input: data.input,
        }
        // If assistant hasn't been created yet, create one
        if (!ctx.getCurrentAssistantId()) {
          const id = Date.now().toString()
          ctx.setCurrentAssistantId(id)
          messages.value.push({
            id,
            role: 'assistant',
            content: '',
            tool_calls: [],
            isStreaming: true,
            createdAt: new Date(),
          })
        }
        // Add tool call to assistant message
        const asst = messages.value.find(m => m.id === ctx.getCurrentAssistantId())
        if (asst && !asst.tool_calls.find(tc => tc.id === data.tool_use_id)) {
          asst.tool_calls.push({
            id: data.tool_use_id,
            name: data.tool_name,
            input: data.input,
          })
        }
        break

      case 'tool_result':
        toolResults[data.tool_use_id] = {
          content: data.content,
          is_error: data.is_error,
        }
        // Update the tool call with result
        const asst2 = messages.value.find(m => m.id === ctx.getCurrentAssistantId())
        if (asst2) {
          const tc = asst2.tool_calls.find(t => t.id === data.tool_use_id)
          if (tc) {
            tc.result = data.content
            tc.is_error = data.is_error
          }
        }
        currentToolCall.value = null
        break

      case 'error':
        error.value = data.message || '未知错误'
        break

      case 'done':
        // Mark streaming as complete
        const doneAsst = messages.value.find(m => m.id === ctx.getCurrentAssistantId())
        if (doneAsst) {
          doneAsst.isStreaming = false
        }
        ctx.resetAssistant()
        break
    }
    await nextTick()
  }

  return {
    messages, isLoading, error, currentToolCall, toolResults,
    fetchHistory, sendMessage,
  }
}
