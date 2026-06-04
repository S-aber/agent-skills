<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useChat } from '../composables/useChat.js'
import { useAuth } from '../composables/useAuth.js'
import MessageBubble from '../components/MessageBubble.vue'

const route = useRoute()
const router = useRouter()
const { apiGet } = useAuth()
const { messages, isLoading, error, currentToolCall, fetchHistory, sendMessage } = useChat()

const convId = route.params.id
const conversation = ref(null)
const inputText = ref('')
const messagesEl = ref(null)

// --- File upload state ---
const API_BASE = '/api/v1'
const uploadedFiles = ref([])
const uploadLoading = ref(false)
const fileInputEl = ref(null)

function triggerFileSelect() {
  fileInputEl.value?.click()
}

async function handleFileSelected(e) {
  const file = e.target.files[0]
  if (!file) return

  uploadLoading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('conversation_id', convId)

    const token = localStorage.getItem('access_token')
    const res = await fetch(`${API_BASE}/uploads`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData,
    })
    if (!res.ok) throw await res.json()
    const data = await res.json()
    data._new = true
    uploadedFiles.value.push(data)
  } catch (e) {
    error.value = e?.detail?.message || e?.error?.message || '文件上传失败'
  } finally {
    uploadLoading.value = false
    // Reset input so same file can be re-selected
    e.target.value = ''
  }
}

async function fetchUploads() {
  try {
    const headers = {
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
    }
    const res = await fetch(`${API_BASE}/uploads/${convId}`, { headers })
    if (!res.ok) return
    uploadedFiles.value = await res.json()
  } catch (_) { /* ignore */ }
}

async function deleteUpload(filename) {
  try {
    const token = localStorage.getItem('access_token')
    const res = await fetch(`${API_BASE}/uploads/${convId}/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` },
    })
    if (!res.ok) throw await res.json()
    uploadedFiles.value = uploadedFiles.value.filter(f => f.filename !== filename)
  } catch (e) {
    error.value = e?.detail?.message || '删除失败'
  }
}

onMounted(async () => {
  try {
    conversation.value = await apiGet(`/conversations/${convId}`)
  } catch (e) {
    router.push('/conversations')
    return
  }
  await fetchHistory(convId)
  await fetchUploads()
  scrollToBottom()
})

watch(messages, () => scrollToBottom(), { deep: true })

function scrollToBottom() {
  nextTick(() => {
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight
    }
  })
}

async function handleSend() {
  const text = inputText.value
  inputText.value = ''

  const pendingFiles = uploadedFiles.value.filter(f => f._new)
  // Remove _new marker
  for (const f of uploadedFiles.value) delete f._new

  let content = text
  if (pendingFiles.length > 0) {
    const fileLines = pendingFiles.map(f => `[上传文件] ${f.path}`).join('\n')
    content = fileLines + '\n' + text
  }

  if (!content.trim()) return

  await sendMessage(convId, content)
  scrollToBottom()
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}
</script>

<template>
  <div v-if="conversation">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <div>
        <h1 style="font-size:18px;margin-bottom:4px">{{ conversation.title }}</h1>
        <span style="font-size:13px;color:var(--text-muted)">
          模型: {{ conversation.model_id }} · {{ conversation.activated_skill_ids?.length || 0 }} 个 Skill 激活
        </span>
      </div>
      <button class="btn btn-outline btn-sm" @click="router.push('/conversations')">← 返回</button>
    </div>

    <div class="chat-container">
      <div class="chat-messages" ref="messagesEl">
        <div v-if="messages.length === 0" class="empty">
          <p>开始与 AI Agent 对话</p>
          <p style="font-size:13px;margin-top:4px">Agent 可以调用 Skill 和内置工具来完成任务</p>
        </div>

        <MessageBubble v-for="msg in messages" :key="msg.id" :message="msg" />

        <div v-if="currentToolCall" class="tool-indicator">
          <span class="streaming-dot"></span>
          正在执行: {{ currentToolCall.tool_name }}
        </div>

        <div v-if="error" class="error-msg">{{ error }}</div>
      </div>

      <!-- Uploaded files bar -->
      <div v-if="uploadedFiles.length > 0" class="upload-files-bar">
        <div v-for="f in uploadedFiles" :key="f.filename" class="upload-file-tag">
          <span class="upload-file-icon">📄</span>
          <span class="upload-file-name" :title="f.path">{{ f.filename }}</span>
          <button class="upload-file-remove" @click="deleteUpload(f.filename)">&times;</button>
        </div>
      </div>

      <div class="chat-input-area">
        <input
          ref="fileInputEl"
          type="file"
          style="display:none"
          @change="handleFileSelected"
        />
        <button
          class="btn btn-outline btn-sm upload-btn"
          :disabled="isLoading || uploadLoading"
          @click="triggerFileSelect"
          :title="uploadLoading ? '上传中...' : '上传文件'"
        >
          {{ uploadLoading ? '⏳' : '📎' }}
        </button>
        <textarea
          v-model="inputText"
          @keydown="handleKeydown"
          placeholder="输入消息，Enter 发送，Shift+Enter 换行"
          :disabled="isLoading"
          rows="2"
        ></textarea>
        <button class="btn btn-primary" :disabled="isLoading || !inputText.trim()" @click="handleSend">
          {{ isLoading ? '...' : '发送' }}
        </button>
      </div>
    </div>
  </div>
</template>
