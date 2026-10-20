<script setup>
defineProps({ tab: String });
const emit = defineEmits(['update:tab', 'close']);
const tabs = [['profile','人物'],['world','世界与偏好'],['memory','记忆与关系'],['settings','会话设置']];
</script>
<template>
  <aside data-testid="character-details" class="absolute xl:static xl:shrink-0 right-0 inset-y-0 w-80 max-w-full z-20 bg-slate-900 border-l border-slate-700 shadow-xl flex flex-col min-h-0">
    <div class="flex justify-between items-center p-4"><h3 class="font-bold">会话资料</h3><button aria-label="关闭资料" class="text-slate-400 p-1" @click="emit('close')">✕</button></div>
    <nav aria-label="会话资料分类" class="grid grid-cols-2 gap-1 px-3 pb-3 border-b border-slate-800">
      <button v-for="[id,label] in tabs" :key="id" :data-testid="`character-details-${id}`" :aria-pressed="tab===id" class="rounded-lg px-2 py-2 text-sm" :class="tab===id ? 'bg-indigo-600/25 text-indigo-200' : 'text-slate-400 hover:bg-slate-800'" @click="emit('update:tab',id)">{{ label }}</button>
    </nav>
    <div class="overflow-y-auto min-h-0 flex-1 p-4 custom-scrollbar"><slot /></div>
  </aside>
</template>
