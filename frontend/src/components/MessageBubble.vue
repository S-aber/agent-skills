<script setup>
import ToolCallBlock from './ToolCallBlock.vue'

const props = defineProps({
  message: Object,
})
</script>

<template>
  <div :class="['message', `role-${message.role}`]">
    <div class="message-content">
      {{ message.content }}
    </div>
    <div v-if="message.tool_calls?.length > 0" style="margin-top:6px">
      <ToolCallBlock
        v-for="tc in message.tool_calls"
        :key="tc.id"
        :tool-call="tc"
      />
    </div>
    <div v-if="message.isStreaming" style="margin-top:4px">
      <span class="streaming-dot"></span>
    </div>
  </div>
</template>
