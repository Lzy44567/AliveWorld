<script setup>
import { computed } from 'vue';
const props = defineProps({ turn: Object, userName: String, aiName: String });
const content = message => typeof message === 'string' ? message : message?.content || '';
const initial = name => Array.from(name || '?')[0];
const time = computed(() => {
  const date = new Date(props.turn.created_at);
  return Number.isFinite(date.getTime()) ? date.toLocaleString(undefined, { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
});
</script>
<template>
  <div class="space-y-4" data-testid="character-message-pair">
    <time v-if="time" class="block text-center text-[11px] text-slate-500">{{ time }}</time>
    <div class="flex items-start justify-end gap-2 md:gap-3">
      <div class="min-w-0 max-w-[calc(100%_-_3rem)] md:max-w-[72%]">
        <p class="mb-1 text-right text-[11px] text-slate-500">{{ userName || '我' }}</p>
        <p class="rounded-xl rounded-tr-sm bg-indigo-700/70 px-4 py-3 whitespace-pre-wrap break-words select-text leading-relaxed" data-testid="character-user-message">{{ content(turn.user_message) }}</p>
      </div>
      <span aria-hidden="true" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-800 text-sm">{{ initial(userName || '我') }}</span>
    </div>
    <div class="flex items-start gap-2 md:gap-3">
      <span aria-hidden="true" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-700 text-sm">{{ initial(aiName) }}</span>
      <div class="min-w-0 max-w-[calc(100%_-_3rem)] md:max-w-[72%]">
        <p class="mb-1 text-[11px] text-slate-500">{{ aiName || '角色' }}</p>
        <p class="rounded-xl rounded-tl-sm bg-slate-800 px-4 py-3 whitespace-pre-wrap break-words select-text leading-relaxed" data-testid="character-ai-message">{{ content(turn.ai_message) }}</p>
      </div>
    </div>
  </div>
</template>
