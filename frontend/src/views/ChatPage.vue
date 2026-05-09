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

onMounted(async () => {
  try {
    conversation.value = await apiGet(`/conversations/${convId}`)
  } catch (e) {
    router.push('/conversations')
    return
  }
  await fetchHistory(convId)
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
  await sendMessage(convId, text)
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

      <div class="chat-input-area">
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
