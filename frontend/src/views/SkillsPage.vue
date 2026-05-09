<script setup>
import { ref, onMounted } from 'vue'
import { useSkills } from '../composables/useSkills.js'
import SkillCard from '../components/SkillCard.vue'

const { mySkills, publicSkills, loading, error, fetchMySkills, fetchPublicSkills, uploadSkill, deleteSkill } = useSkills()

const activeTab = ref('private')
const uploadRef = ref(null)
const uploading = ref(false)

onMounted(() => {
  fetchMySkills()
  fetchPublicSkills()
})

async function handleUpload(file, isPublic) {
  uploading.value = true
  try {
    await uploadSkill(file, isPublic)
  } catch (e) {
    alert(e.detail?.message || e.error?.message || '上传失败')
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
      <h1>Skill 管理</h1>
      <div style="display:flex;gap:8px">
        <label class="btn btn-outline btn-sm" style="cursor:pointer">
          {{ uploading ? '上传中...' : '+ 私有 Skill' }}
          <input type="file" accept=".md" style="display:none" @change="onFileChange($event, false)" :disabled="uploading" />
        </label>
        <label class="btn btn-primary btn-sm" style="cursor:pointer">
          {{ uploading ? '上传中...' : '+ 公共 Skill' }}
          <input type="file" accept=".md" style="display:none" @change="onFileChange($event, true)" :disabled="uploading" />
        </label>
      </div>
    </div>

    <div class="tabs">
      <button :class="['tab', { active: activeTab === 'private' }]" @click="activeTab = 'private'">
        我的 Skill ({{ mySkills.length }})
      </button>
      <button :class="['tab', { active: activeTab === 'public' }]" @click="activeTab = 'public'">
        公共 Skill ({{ publicSkills.length }})
      </button>
    </div>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <div v-if="loading && activeTab === 'private'" class="loading">加载中...</div>

    <div v-if="activeTab === 'private'">
      <div v-if="mySkills.length === 0 && !loading" class="empty">
        <p>还没有私有 Skill</p>
        <p style="font-size:13px;margin-top:4px">点击上方按钮上传 SKILL.md 文件</p>
      </div>
      <div class="grid" v-else>
        <SkillCard v-for="s in mySkills" :key="s.id" :skill="s" :show-delete="true" @delete="deleteSkill" />
      </div>
    </div>

    <div v-if="activeTab === 'public'">
      <div v-if="publicSkills.length === 0" class="empty">
        <p>还没有公共 Skill</p>
      </div>
      <div class="grid grid-2" v-else>
        <SkillCard v-for="s in publicSkills" :key="s.id" :skill="s" />
      </div>
    </div>
  </div>
</template>
