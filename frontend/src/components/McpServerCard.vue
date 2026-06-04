<script setup>
const props = defineProps({
  server: Object,
  showToggle: Boolean,
  showDelete: Boolean,
})
const emit = defineEmits(['delete', 'toggle'])

function onDelete() {
  if (confirm(`确定删除 "${props.server.name}"？`)) {
    emit('delete', props.server.id)
  }
}
</script>

<template>
  <div class="card" :class="{ 'card-disabled': !server.enabled }">
    <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:8px">
      <div>
        <strong>{{ server.name }}</strong>
        <span :class="['badge', server.source === 'public' ? 'badge-public' : 'badge-private']" style="margin-left:8px">
          {{ server.source === 'public' ? '公共' : '私有' }}
        </span>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <label v-if="showToggle" class="toggle-switch">
          <input
            type="checkbox"
            :checked="server.enabled"
            @change="emit('toggle', server.id)"
          />
          <span class="toggle-slider"></span>
        </label>
        <button v-if="showDelete" class="btn btn-danger btn-sm" @click="onDelete">删除</button>
      </div>
    </div>
    <p style="font-size:13px;color:var(--text-muted);margin-bottom:4px">{{ server.description }}</p>
    <p style="font-size:12px;color:var(--text-muted)">
      {{ server.command }} {{ server.args?.join(' ') || '' }}
    </p>
  </div>
</template>

<style scoped>
.card-disabled {
  opacity: 0.55;
}
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
  cursor: pointer;
}
.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.toggle-slider {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: #555;
  border-radius: 22px;
  transition: 0.2s;
}
.toggle-slider::before {
  content: '';
  position: absolute;
  height: 16px; width: 16px;
  left: 3px; bottom: 3px;
  background: white;
  border-radius: 50%;
  transition: 0.2s;
}
input:checked + .toggle-slider {
  background: var(--primary, #4a90d9);
}
input:checked + .toggle-slider::before {
  transform: translateX(18px);
}
</style>
