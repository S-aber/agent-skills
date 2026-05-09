<script setup>
const props = defineProps({
  skill: Object,
  showDelete: Boolean,
})
const emit = defineEmits(['delete'])

function onDelete() {
  if (confirm(`确定删除 "${props.skill.name}"？`)) {
    emit('delete', props.skill.id)
  }
}
</script>

<template>
  <div class="card">
    <div class="skill-header" style="display:flex;justify-content:space-between;align-items:start;margin-bottom:8px">
      <div>
        <strong>{{ skill.name }}</strong>
        <span :class="['badge', skill.source === 'public' ? 'badge-public' : 'badge-private']" style="margin-left:8px">
          {{ skill.source === 'public' ? '公共' : '私有' }}
        </span>
      </div>
      <button v-if="showDelete" class="btn btn-danger btn-sm" @click="onDelete">删除</button>
    </div>
    <p style="font-size:13px;color:var(--text-muted)">{{ skill.description }}</p>
  </div>
</template>
