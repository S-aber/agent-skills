<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConversations } from '../composables/useConversations.js'
import SkillSelector from '../components/SkillSelector.vue'

const router = useRouter()
const { conversations, loading, fetchConversations, createConversation, deleteConversation } = useConversations()

const showCreate = ref(false)
const newConv = ref({ title: '', model_id: 'gpt-4o', skillIds: [] })
const creating = ref(false)
const error = ref('')

onMounted(fetchConversations)

async function handleCreate() {
  if (!newConv.value.title.trim()) { error.value = '请输入标题'; return }
  creating.value = true; error.value = ''
  try {
    const conv = await createConversation(newConv.value.title, newConv.value.skillIds, newConv.value.model_id)
    showCreate.value = false
    newConv.value = { title: '', model_id: 'gpt-4o', skillIds: [] }
    router.push(`/chat/${conv.id}`)
  } catch (e) {
    error.value = e.detail?.message || e.error?.message || '创建失败'
  } finally {
    creating.value = false
  }
}

function openChat(id) {
  router.push(`/chat/${id}`)
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>我的会话</h1>
      <button class="btn btn-primary" @click="showCreate = true">+ 新建会话</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-if="!loading && conversations.length === 0" class="empty">
      <p>还没有会话</p>
      <p style="font-size:13px;margin-top:4px">创建一个会话来开始与 AI Agent 对话</p>
    </div>

    <div class="grid" v-else>
      <div v-for="conv in conversations" :key="conv.id" class="card"
        style="display:flex;justify-content:space-between;align-items:center;cursor:pointer"
        @click="openChat(conv.id)">
        <div>
          <div style="font-weight:500;margin-bottom:4px">{{ conv.title }}</div>
          <div style="font-size:13px;color:var(--text-muted)">
            模型: {{ conv.model_id }} · {{ conv.activated_skill_ids?.length || 0 }} 个 Skill · {{ new Date(conv.created_at).toLocaleString() }}
          </div>
        </div>
        <button class="btn btn-danger btn-sm" @click.stop="deleteConversation(conv.id)">删除</button>
      </div>
    </div>

    <!-- Create modal -->
    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal">
        <h2>新建会话</h2>
        <div v-if="error" class="error-msg">{{ error }}</div>
        <div class="form-group">
          <label>会话标题</label>
          <input v-model="newConv.title" class="form-input" placeholder="例如：代码审查" />
        </div>
        <div class="form-group">
          <label>模型</label>
          <select v-model="newConv.model_id" class="form-input">
            <option value="gpt-4o">gpt-4o</option>
          </select>
        </div>
        <SkillSelector v-model="newConv.skillIds" />
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showCreate = false">取消</button>
          <button class="btn btn-primary" :disabled="creating" @click="handleCreate">
            {{ creating ? '创建中...' : '创建并开始对话' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
