<script setup>
defineProps({ opening: Object, name: String });
</script>
<template>
  <div data-testid="character-opening-message" class="flex items-start gap-2 md:gap-3">
    <span aria-hidden="true" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-700">{{ Array.from(name || '?')[0] }}</span>
    <div class="min-w-0 max-w-[calc(100%_-_3rem)] md:max-w-[72%]">
      <p class="mb-1 text-[11px] text-slate-400">{{ name || '角色' }} · 预设开场 <time>{{ new Date(opening.created_at).toLocaleString() }}</time></p>
      <p class="rounded-xl rounded-tl-sm bg-slate-800 px-4 py-3 whitespace-pre-wrap break-words select-text leading-relaxed">{{ opening.content }}</p>
    </div>
  </div>
</template>
