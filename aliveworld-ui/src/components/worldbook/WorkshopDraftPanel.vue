<script setup>
import { computed, ref } from 'vue';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';
import { useDeleteConfirmation } from '../../composables/useDeleteConfirmation';

const props = defineProps({ draft: { type: Object, required: true }, editingEntry: { type: Object, default: null } });
const emit = defineEmits(['addEntry', 'editEntry', 'cancelEdit', 'saveEntry', 'toggleEntry', 'deleteEntry', 'askAi']);
const overview = defineModel('overview', { type: String, default: '' });
const axioms = defineModel('axioms', { type: String, default: '' });
const tab = ref('overview');
const search = ref('');
const { confirmDeleteId, requestDelete, cancelDelete } = useDeleteConfirmation();
const filteredEntries = computed(() => {
  const keyword = search.value.trim().toLowerCase();
  if (!keyword) return props.draft.entries || [];
  return (props.draft.entries || []).filter(entry => [entry.name, entry.keys, entry.content, ...(entry.tags || [])].some(value => String(value || '').toLowerCase().includes(keyword)));
});
const confirmDelete = (entry) => { emit('deleteEntry', entry); cancelDelete(); };
</script>

<template>
  <aside class="flex min-h-0 flex-col">
    <nav class="flex shrink-0 border-b border-slate-800 p-2 text-xs">
      <button v-for="item in [{id:'overview',label:'总览'},{id:'axioms',label:'公理'},{id:'entries',label:`条目 ${draft.entries?.length || 0}`} ]" :key="item.id" @click="tab=item.id" class="flex-1 rounded px-2 py-2" :class="tab===item.id?'bg-indigo-800 text-white':'text-slate-400 hover:bg-slate-900'">{{ item.label }}</button>
    </nav>
    <div class="min-h-0 flex-1 overflow-y-auto p-4 custom-scrollbar">
      <section v-if="tab === 'overview'">
        <h3 class="font-bold text-slate-200">世界概述</h3><p class="mt-1 text-[10px] text-slate-500">世界背景、总体印象和希望重点呈现的体验。</p>
        <ExpandableTextarea v-model="overview" label="工坊世界概述" textarea-class="mt-3 h-64 rounded border border-slate-800 bg-slate-900 p-3 text-xs text-slate-300" />
        <p class="mt-3 text-[10px] text-emerald-400">停止输入后自动保存到工坊草稿</p>
      </section>
      <section v-else-if="tab === 'axioms'">
        <h3 class="font-bold text-amber-300">世界公理</h3><p class="mt-1 text-[10px] text-slate-500">每行一条，描述世界内部真实成立的底层规则。</p>
        <ExpandableTextarea v-model="axioms" label="工坊世界公理" textarea-class="mt-3 h-64 rounded border border-amber-900/60 bg-slate-900 p-3 text-xs text-slate-300" />
        <p class="mt-3 text-[10px] text-emerald-400">停止输入后自动保存到工坊草稿</p>
      </section>
      <section v-else>
        <div class="flex gap-2"><input v-model="search" placeholder="搜索名称、触发词、标签或内容" class="min-w-0 flex-1 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white"><button @click="emit('addEntry')" class="rounded bg-indigo-700 px-3 text-xs text-white">+ 新增</button></div>
        <div v-if="editingEntry" class="mt-3 rounded-lg border border-indigo-700/60 bg-indigo-950/20 p-3"><div class="text-xs font-bold text-indigo-300">{{ editingEntry.isNew ? '新增条目' : '编辑条目' }}</div><input v-model="editingEntry.name" placeholder="条目名" class="mt-2 w-full rounded border border-slate-700 bg-slate-950 p-2 text-xs text-white"><input v-model="editingEntry.keys" placeholder="触发词" class="mt-2 w-full rounded border border-slate-700 bg-slate-950 p-2 text-xs text-white"><ExpandableTextarea v-model="editingEntry.content" :label="`工坊条目：${editingEntry.name || '未命名'}`" placeholder="条目内容" textarea-class="mt-2 h-40 rounded border border-slate-700 bg-slate-950 p-2 text-xs text-white" /><input v-model="editingEntry.tagsText" placeholder="标签，逗号分隔" class="mt-2 w-full rounded border border-slate-700 bg-slate-950 p-2 text-xs text-white"><div class="mt-2 flex gap-2"><button @click="emit('saveEntry')" class="rounded bg-emerald-700 px-2 py-1 text-[10px] text-white">保存</button><button @click="emit('cancelEdit')" class="rounded bg-slate-700 px-2 py-1 text-[10px] text-white">取消</button></div></div>
        <div class="mt-3 space-y-2"><div v-for="entry in filteredEntries" :key="entry.id" class="rounded-lg border border-slate-800 bg-slate-900 p-3" :class="entry.is_active===false?'opacity-50':''"><div class="flex justify-between gap-2"><div class="min-w-0"><div class="truncate text-xs font-bold text-slate-200">{{ entry.name }}</div><div class="mt-1 truncate text-[10px] text-slate-500">触发：{{ entry.keys || '无' }}</div></div><button @click="emit('toggleEntry',entry)" class="text-[9px]" :class="entry.is_active===false?'text-slate-500':'text-emerald-400'">{{ entry.is_active===false?'已关闭':'已启用' }}</button></div><div class="mt-2 flex flex-wrap gap-1"><span v-for="tag in entry.tags" :key="tag" class="rounded bg-slate-800 px-1 text-[9px] text-indigo-300">{{ tag }}</span></div><div class="mt-2 flex gap-1"><button @click="emit('editEntry',entry)" class="rounded bg-slate-800 px-2 py-1 text-[9px] text-slate-300">编辑</button><button @click="emit('askAi',entry)" class="rounded bg-violet-900/60 px-2 py-1 text-[9px] text-violet-300">让AI修改</button><button v-if="confirmDeleteId !== entry.id" @click="requestDelete(entry.id)" class="rounded bg-rose-950 px-2 py-1 text-[9px] text-rose-400">删除</button><span v-else :data-delete-confirm-id="entry.id" class="flex gap-1"><button @click="confirmDelete(entry)" class="rounded bg-rose-700 px-2 py-1 text-[9px] text-white">确认</button><button @click="cancelDelete" class="rounded bg-slate-700 px-2 py-1 text-[9px] text-white">取消</button></span></div></div></div>
      </section>
    </div>
  </aside>
</template>

<style scoped>
[data-delete-confirm-id] button:first-child { order: 2; }
[data-delete-confirm-id] button:last-child { order: 1; }
</style>
