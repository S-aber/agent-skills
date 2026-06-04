<script setup>
import { ref } from 'vue'

const props = defineProps({
  toolCall: Object,
})

const expanded = ref(false)

function toggle() {
  expanded.value = !expanded.value
}

function formatInput(obj) {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}
</script>

<template>
  <div class="tool-call">
    <div class="tool-call-header" @click="toggle">
      <span>
        {{ expanded ? '▾' : '▸' }}
        {{ toolCall.name }}
      </span>
      <span style="font-size:11px;color:var(--text-muted)">
        {{ toolCall.result !== undefined ? (toolCall.is_error ? '✗ 失败' : '✓ 完成') : '执行中...' }}
      </span>
    </div>
    <div v-if="expanded" class="tool-call-body">
      <div v-if="Object.keys(toolCall.input || {}).length > 0" style="margin-bottom:8px">
        <strong>输入:</strong>
        <pre>{{ formatInput(toolCall.input) }}</pre>
      </div>
      <div v-if="toolCall.result">
        <strong>输出:</strong>
        <pre>{{ toolCall.result }}</pre>
      </div>
    </div>
  </div>
</template>
