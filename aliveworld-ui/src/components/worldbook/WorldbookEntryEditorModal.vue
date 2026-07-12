<script setup>
import ExpandableTextarea from '../common/ExpandableTextarea.vue';
import SystemTagInput from '../common/SystemTagInput.vue';

defineProps({ entry: { type: Object, required: true }, title: { type: String, default: '编辑世界书条目' } });
defineEmits(['save', 'cancel']);
</script>

<template>
  <Teleport to="body"><div class="fixed inset-0 z-[125] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"><section class="flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-indigo-700/70 bg-slate-950 shadow-2xl"><header class="flex items-center justify-between border-b border-slate-800 px-5 py-3"><h3 class="font-bold text-indigo-300">{{ title }}</h3><button @click="$emit('cancel')" class="text-xl text-slate-400">✕</button></header><div class="min-h-0 flex-1 space-y-4 overflow-y-auto p-5"><div class="grid grid-cols-2 gap-4"><label class="text-xs text-slate-400">条目名称<input v-model="entry.name" class="mt-1 w-full rounded border border-slate-700 bg-slate-900 p-2 text-sm text-white"></label><label class="text-xs text-slate-400">触发关键词<input v-model="entry.keys" class="mt-1 w-full rounded border border-slate-700 bg-slate-900 p-2 text-sm text-white"></label></div><div><label class="text-xs text-slate-400">条目内容</label><ExpandableTextarea v-model="entry.content" :label="`世界书条目：${entry.name || '未命名'}`" textarea-class="mt-1 h-64 rounded border border-slate-700 bg-slate-900 p-3 text-sm text-white" /></div><SystemTagInput v-model="entry.tagsText" /><label class="flex items-center justify-between rounded border border-slate-700 p-3 text-xs text-slate-300"><span>启用此条目</span><input type="checkbox" v-model="entry.is_active"></label></div><footer class="flex justify-end gap-2 border-t border-slate-800 p-4"><button @click="$emit('cancel')" class="rounded bg-slate-700 px-4 py-2 text-sm text-white">取消</button><button @click="$emit('save')" class="rounded bg-indigo-700 px-4 py-2 text-sm font-bold text-white">保存条目</button></footer></section></div></Teleport>
</template>
