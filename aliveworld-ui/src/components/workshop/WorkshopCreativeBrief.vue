<script setup>
import { ref, watch } from 'vue';
import { workshopStore } from '../../store/workshopStore';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';

const text = ref('');
const saved = ref('');
let workshopId = '';
watch(() => [workshopStore.workshopId, workshopStore.context.creativeBrief], ([id, brief]) => {
  if (id !== workshopId || text.value === saved.value) text.value = brief || '';
  workshopId = id;
  saved.value = brief || '';
}, { immediate: true });

async function save() {
  const id = workshopStore.workshopId;
  if (await workshopStore.saveCreativeBrief(text.value)) {
    if (id === workshopStore.workshopId) text.value = workshopStore.context.creativeBrief;
  }
}
</script>

<template>
  <details class="mt-3 rounded border border-slate-700 p-2" data-testid="workshop-creative-brief">
    <summary class="cursor-pointer text-xs text-slate-300">创作目标 · {{ workshopStore.context.creativeBrief ? '已保存，持续参考' : workshopStore.type === 'preferences' ? '可选，由你填写' : '可选，AI 可从讨论中整理' }}</summary>
    <p class="my-2 text-[10px] text-slate-400">希望探索什么、重点写什么、避免什么。只指导工坊，不是资产事实或已确认偏好；修改后请保存，草稿撤销不改变此目标。</p>
    <p v-if="workshopStore.type === 'preferences'" class="mb-2 text-[10px] text-slate-400">仅使用你主动填写的目标，不从行为证据自动提炼；新一轮不会自动继承。</p>
    <ExpandableTextarea v-model="text" label="创作目标" :maxlength="2000" :disabled="workshopStore.published || workshopStore.busy" textarea-class="h-24 rounded border border-slate-700 bg-slate-900 p-2 text-xs text-slate-200" />
    <div class="mt-2 flex items-center gap-3 text-xs">
      <button v-if="!workshopStore.published" class="rounded bg-cyan-800 px-3 py-1 disabled:opacity-40" :disabled="workshopStore.busy || text === saved || text.length > 2000" @click="save">保存目标</button>
      <span class="text-slate-400">{{ text.length }}/2000{{ text !== saved ? ' · 未保存' : '' }}</span>
    </div>
  </details>
</template>
