<script setup>
import { ref, onMounted } from 'vue'
import { useSkills } from '../composables/useSkills.js'

const { mySkills, publicSkills, fetchMySkills, fetchPublicSkills } = useSkills()
const selected = ref([])

const emit = defineEmits(['update:modelValue'])
const props = defineProps({ modelValue: { type: Array, default: () => [] } })

onMounted(async () => {
  await Promise.all([fetchMySkills(), fetchPublicSkills()])
  selected.value = [...props.modelValue]
})

function toggle(id) {
  const idx = selected.value.indexOf(id)
  if (idx >= 0) {
    selected.value.splice(idx, 1)
  } else {
    selected.value.push(id)
  }
  emit('update:modelValue', selected.value)
}

const allSkills = computed(() => [...mySkills.value, ...publicSkills.value])
import { computed } from 'vue'
</script>

<template>
  <div>
    <p style="font-size:13px;color:var(--text-muted);margin-bottom:8px">选择要激活的 Skill（最多20个）</p>
    <div v-for="skill in allSkills" :key="skill.id"
      :class="['skill-checkbox', { selected: selected.includes(skill.id) }]"
      @click="toggle(skill.id)">
      <input type="checkbox" :checked="selected.includes(skill.id)" />
      <div>
        <div class="skill-name">
          {{ skill.name }}
          <span :class="['badge', skill.source === 'public' ? 'badge-public' : 'badge-private']" style="margin-left:6px">
            {{ skill.source === 'public' ? '公共' : '私有' }}
          </span>
        </div>
        <div class="skill-desc">{{ skill.description }}</div>
      </div>
    </div>
    <p v-if="allSkills.length === 0" style="color:var(--text-muted);font-size:13px">暂无可用的 Skill，请先上传</p>
  </div>
</template>
