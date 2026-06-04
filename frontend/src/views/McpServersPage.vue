<script setup>
import { ref, onMounted } from 'vue'
import { useMcp } from '../composables/useMcp.js'
import McpServerCard from '../components/McpServerCard.vue'

const {
  myServers, publicServers, loading, error,
  fetchMyServers, fetchPublicServers, uploadServer, deleteServer, toggleServer
} = useMcp()

const activeTab = ref('private')
const uploading = ref(false)

onMounted(() => {
  fetchMyServers()
  fetchPublicServers()
})

async function handleUpload(file, isPublic) {
  uploading.value = true
  try {
    await uploadServer(file, isPublic)
  } catch (e) {
    alert(e.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

function onFileChange(e, isPublic) {
  const file = e.target.files[0]
  if (file) handleUpload(file, isPublic)
  e.target.value = ''
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>MCP 服务管理</h1>
      <div style="display:flex;gap:8px">
        <label class="btn btn-outline btn-sm" style="cursor:pointer">
          {{ uploading ? '上传中...' : '+ 私有 MCP' }}
          <input type="file" accept=".zip" style="display:none" @change="onFileChange($event, false)" :disabled="uploading" />
        </label>
        <label class="btn btn-primary btn-sm" style="cursor:pointer">
          {{ uploading ? '上传中...' : '+ 公共 MCP' }}
          <input type="file" accept=".zip" style="display:none" @change="onFileChange($event, true)" :disabled="uploading" />
        </label>
      </div>
    </div>

    <div class="tabs">
      <button :class="['tab', { active: activeTab === 'private' }]" @click="activeTab = 'private'">
        我的 MCP ({{ myServers.length }})
      </button>
      <button :class="['tab', { active: activeTab === 'public' }]" @click="activeTab = 'public'">
        公共 MCP ({{ publicServers.length }})
      </button>
    </div>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <div v-if="loading && activeTab === 'private'" class="loading">加载中...</div>

    <div v-if="activeTab === 'private'">
      <div v-if="myServers.length === 0 && !loading" class="empty">
        <p>还没有 MCP 服务</p>
        <p style="font-size:13px;margin-top:4px">点击上方按钮上传 MCP.zip 文件</p>
      </div>
      <div class="grid" v-else>
        <McpServerCard
          v-for="s in myServers" :key="s.id"
          :server="s" :show-toggle="true" :show-delete="true"
          @delete="deleteServer" @toggle="toggleServer"
        />
      </div>
    </div>

    <div v-if="activeTab === 'public'">
      <div v-if="publicServers.length === 0" class="empty">
        <p>还没有公共 MCP 服务</p>
      </div>
      <div class="grid grid-2" v-else>
        <McpServerCard v-for="s in publicServers" :key="s.id" :server="s" />
      </div>
    </div>
  </div>
</template>
