<script setup>
defineProps({ notice: Object });
defineEmits(['close']);
</script>
<template>
  <div v-if="notice" data-testid="character-memory-notice" role="status" class="mx-3 mt-2 flex items-center justify-between gap-3 rounded-lg border border-indigo-800 bg-indigo-950/40 px-3 py-2 text-xs text-indigo-200">
    <span>已自动选取 {{ notice.entry_ids.length }} 条重要记忆，可在会话资料中查看或取消。</span>
    <button class="shrink-0 text-slate-400" aria-label="关闭记忆提示" @click="$emit('close')">✕</button>
  </div>
</template>
