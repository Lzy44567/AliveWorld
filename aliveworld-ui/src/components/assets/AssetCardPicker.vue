<script setup>
import { computed, ref } from 'vue';
import CharacterAssetCard from './CharacterAssetCard.vue';
const props = defineProps({ items: { type: Array, default: () => [] }, title: String, modelValue: String, emptyLabel: String });
const emit = defineEmits(['update:modelValue', 'close']);
const query = ref('');
const filtered = computed(() => props.items.filter(item => [item.name, item.desc, item.description, ...(item.tags || [])].join(' ').toLocaleLowerCase().includes(query.value.trim().toLocaleLowerCase())));
function select(name) { emit('update:modelValue', name); emit('close'); }
const portraitUrl = item => item.portrait?.scope === 'global' && item.portrait?.path ? `/api/v1/game/images/global-portraits/${encodeURIComponent(item.portrait.path)}` : '';
</script>

<template>
  <div class="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-3 md:p-6" @click.self="emit('close')" @keydown.esc="emit('close')">
    <section role="dialog" aria-modal="true" :aria-label="title" data-testid="asset-card-picker" class="flex max-h-[90vh] w-full max-w-5xl flex-col rounded-2xl border border-slate-600 bg-slate-900 shadow-2xl">
      <header class="flex items-center justify-between border-b border-slate-700 p-4"><h3 class="font-bold text-slate-200">{{ title }}</h3><button type="button" @click="emit('close')" aria-label="关闭选择">✕</button></header>
      <div class="flex flex-wrap gap-3 p-4"><input v-model="query" autofocus data-testid="asset-picker-search" aria-label="搜索资产" placeholder="搜索名称、标签或简介" class="min-w-0 flex-1 rounded-lg border border-slate-600 bg-slate-950 p-2 text-slate-200"><button v-if="emptyLabel" type="button" class="rounded-lg border border-slate-600 px-3 text-slate-300" @click="select('')">{{ emptyLabel }}</button></div>
      <div class="min-h-0 overflow-y-auto p-4 pt-0"><div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3"><CharacterAssetCard v-for="item in filtered" :key="item.name" :item="item" :portrait-url="portraitUrl(item)" scope="global" selectable :selected="modelValue===item.name" @select="select(item.name)" /></div><p v-if="!filtered.length" class="py-10 text-center text-slate-400">{{ items.length ? '没有匹配的资产' : '暂无可选择的资产，请先创建或导入' }}</p></div>
    </section>
  </div>
</template>
