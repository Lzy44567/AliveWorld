<script setup>
import { computed } from 'vue';
const props = defineProps({ row: Object, userId: String, userName: String, aiName: String });
const own = computed(() => props.row.message.speaker_instance_id === props.userId);
const name = computed(() => own.value ? props.userName || '我' : props.aiName || '角色');
</script>
<template>
  <div data-testid="character-message-row" :data-message-id="row.key" :data-temporary="row.temporary" class="space-y-2">
    <details v-if="row.ooc_note" data-testid="character-turn-ooc" class="text-xs text-slate-400 border border-slate-800 rounded-lg px-3 py-2">
      <summary class="cursor-pointer">本次场外提示（非角色台词）</summary>
      <p class="whitespace-pre-wrap break-words select-text mt-2">{{ row.ooc_note }}</p>
    </details>
    <div class="flex items-start gap-2 md:gap-3" :class="own ? 'flex-row-reverse' : ''">
      <span aria-hidden="true" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm" :class="own ? 'bg-indigo-800' : 'bg-slate-700'">{{ Array.from(name)[0] }}</span>
      <div class="min-w-0 max-w-[calc(100%_-_3rem)] md:max-w-[72%]">
        <p class="mb-1 text-[11px] text-slate-500" :class="own ? 'text-right' : ''">{{ name }}<span v-if="row.temporary" class="ml-2 text-amber-300">生成中 · 未保存</span></p>
        <!-- Text updates in this same keyed bubble. Confirmation does not replay an animation. -->
        <p :data-testid="own ? 'character-user-message' : 'character-ai-message'" class="rounded-xl px-4 py-3 whitespace-pre-wrap break-words select-text leading-relaxed" :class="own ? 'rounded-tr-sm bg-indigo-700/70' : 'rounded-tl-sm bg-slate-800'">{{ row.message.content }}<span v-if="row.temporary && !row.ended" aria-hidden="true" class="inline-block ml-1 h-3 w-px bg-slate-400"></span></p>
      </div>
    </div>
  </div>
</template>
