<script setup>
import { ref } from 'vue';

defineProps({
  label: { type: String, default: '长文本编辑' },
  placeholder: { type: String, default: '' },
  textareaClass: { type: String, default: '' },
});
const model = defineModel({ type: String, default: '' });
const expanded = ref(false);
</script>

<template>
  <div class="relative">
    <textarea v-model="model" :placeholder="placeholder" :class="textareaClass" class="block w-full pr-10" />
    <button type="button" @click="expanded = true" class="absolute right-2 top-2 rounded border border-slate-600 bg-slate-900/90 px-1.5 py-1 text-[10px] text-slate-300 hover:border-indigo-500 hover:text-white" :title="`全屏编辑${label}`">⛶</button>
    <Teleport to="body">
      <div v-if="expanded" class="fixed inset-0 z-[120] flex flex-col bg-slate-950/95 p-5 backdrop-blur-sm">
        <header class="mb-3 flex items-center justify-between"><h3 class="font-bold text-slate-100">{{ label }}</h3><button type="button" @click="expanded = false" class="rounded bg-indigo-700 px-4 py-2 text-sm font-bold text-white">完成</button></header>
        <textarea v-model="model" autofocus :placeholder="placeholder" class="min-h-0 flex-1 resize-none rounded-xl border border-slate-700 bg-slate-900 p-5 text-base leading-7 text-slate-100 outline-none focus:border-indigo-500" />
      </div>
    </Teleport>
  </div>
</template>
