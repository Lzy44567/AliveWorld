<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';
import InlineDeleteConfirm from '../common/InlineDeleteConfirm.vue';
import WorldbookEntryEditorModal from '../worldbook/WorldbookEntryEditorModal.vue';
import { useDeleteConfirmation } from '../../composables/useDeleteConfirmation';
import { workshopStore } from '../../store/workshopStore';

const tab = ref('overview');
const search = ref('');
const overview = ref('');
const axioms = ref([]);
const entryEditor = ref(null);
const axiomEditor = ref(null);
const batchAxiomsOpen = ref(false);
const { confirmDeleteId, requestDelete, cancelDelete } = useDeleteConfirmation();

let headerSaveTimer = null;
let boundWorkshopId = '';
let lastRemoteHeader = '';
let lastSavedHeader = '';

const stripAxiomPrefix = value => String(value || '')
  .replace(/^\s*(?:(?:\d+|[一二三四五六七八九十]+)[.、．)]|[-*•])\s*/, '')
  .trim();
const normalizedAxioms = values => values.map(stripAxiomPrefix).filter(Boolean);
const headerSignature = (summary = overview.value, rules = axioms.value) =>
  JSON.stringify([String(summary || ''), normalizedAxioms(rules || [])]);
const remoteHeaderSignature = draft =>
  headerSignature(draft?.overview || '', Array.isArray(draft?.axioms) ? draft.axioms : []);

const axiomsText = computed({
  get: () => axioms.value.map((item, index) => `${index + 1}. ${item}`).join('\n'),
  set: value => { axioms.value = normalizedAxioms(String(value || '').split(/\r?\n/)); },
});

const entries = computed(() => {
  const keyword = search.value.trim().toLowerCase();
  const source = workshopStore.draft?.entries || [];
  const filtered = keyword
    ? source.filter(entry => [entry.name, entry.keys, entry.content, ...(entry.tags || [])]
      .some(value => String(value || '').toLowerCase().includes(keyword)))
    : source;
  return [...filtered].sort((left, right) => {
    const leftPinned = (left.tags || []).includes('常驻') ? 1 : 0;
    const rightPinned = (right.tags || []).includes('常驻') ? 1 : 0;
    return rightPinned - leftPinned;
  });
});

const syncHeaderFromStore = () => {
  const id = workshopStore.workshopId;
  const remote = remoteHeaderSignature(workshopStore.draft);
  const local = headerSignature();
  if (id !== boundWorkshopId) {
    if (headerSaveTimer) window.clearTimeout(headerSaveTimer);
    boundWorkshopId = id;
    overview.value = workshopStore.draft?.overview || '';
    axioms.value = [...(workshopStore.draft?.axioms || [])];
    lastRemoteHeader = remote;
    lastSavedHeader = remote;
    entryEditor.value = null;
    axiomEditor.value = null;
    return;
  }
  if (remote !== lastRemoteHeader) {
    lastRemoteHeader = remote;
    if (local === lastSavedHeader) {
      overview.value = workshopStore.draft?.overview || '';
      axioms.value = [...(workshopStore.draft?.axioms || [])];
      lastSavedHeader = remote;
    }
  }
};

watch(
  () => [
    workshopStore.workshopId,
    workshopStore.draft?.overview,
    JSON.stringify(workshopStore.draft?.axioms || []),
  ],
  syncHeaderFromStore,
  { immediate: true },
);

async function saveHeader(targetWorkshopId = workshopStore.workshopId) {
  if (headerSaveTimer) window.clearTimeout(headerSaveTimer);
  headerSaveTimer = null;
  if (!targetWorkshopId || targetWorkshopId !== workshopStore.workshopId) return;
  const signature = headerSignature();
  if (signature === lastSavedHeader) return;
  const saved = await workshopStore.saveFields({
    overview: overview.value,
    axioms: normalizedAxioms(axioms.value),
  });
  if (saved) lastSavedHeader = signature;
}

watch([overview, axioms], () => {
  if (!workshopStore.workshopId || headerSignature() === lastSavedHeader) return;
  if (headerSaveTimer) window.clearTimeout(headerSaveTimer);
  const targetWorkshopId = workshopStore.workshopId;
  headerSaveTimer = window.setTimeout(() => saveHeader(targetWorkshopId), 650);
}, { deep: true });

onBeforeUnmount(() => {
  if (headerSaveTimer) {
    window.clearTimeout(headerSaveTimer);
    saveHeader(boundWorkshopId);
  }
});

function startEntry(entry = null) {
  entryEditor.value = entry
    ? { ...JSON.parse(JSON.stringify(entry)), tagsText: (entry.tags || []).join(', '), isNew: false }
    : { id: '', name: '', keys: '', content: '', tagsText: '', is_active: true, isNew: true };
}

async function saveEntry() {
  const item = entryEditor.value;
  if (!item?.name?.trim() || !item?.content?.trim()) return;
  const entry = {
    name: item.name.trim(),
    keys: item.keys || '',
    content: item.content.trim(),
    tags: item.tagsText.split(/[,，]/).map(value => value.trim()).filter(Boolean),
    is_active: item.is_active !== false,
  };
  const operation = item.isNew
    ? { op: 'add_entry', entry }
    : { op: 'update_entry', entry_id: item.id, changes: entry };
  if (await workshopStore.applyOperations([operation], true)) entryEditor.value = null;
}

const toggleEntry = entry => workshopStore.applyOperations([{
  op: 'update_entry',
  entry_id: entry.id,
  changes: { is_active: entry.is_active === false },
}], true);

const togglePinned = entry => {
  const tags = [...(entry.tags || [])];
  const index = tags.indexOf('常驻');
  if (index >= 0) tags.splice(index, 1);
  else tags.push('常驻');
  return workshopStore.applyOperations([{
    op: 'update_entry',
    entry_id: entry.id,
    changes: { tags },
  }], true);
};

async function deleteEntry(entry) {
  if (await workshopStore.applyOperations([{ op: 'delete_entry', entry_id: entry.id }], true)) {
    cancelDelete();
  }
}

function beginAxiom(index = -1) {
  axiomEditor.value = {
    index,
    text: index >= 0 ? axioms.value[index] : '',
  };
}

function saveAxiom() {
  const text = stripAxiomPrefix(axiomEditor.value?.text);
  if (!text) return;
  const next = [...axioms.value];
  if (axiomEditor.value.index >= 0) next[axiomEditor.value.index] = text;
  else next.push(text);
  axioms.value = next;
  axiomEditor.value = null;
}

function deleteAxiom(index) {
  axioms.value = axioms.value.filter((_, itemIndex) => itemIndex !== index);
  cancelDelete();
}
</script>

<template>
  <div>
    <nav class="sticky top-0 z-10 -mx-4 -mt-4 mb-4 flex border-b border-slate-800 bg-aw_panel p-2 text-[10px] shadow">
      <button
        v-for="item in [
          { id: 'overview', label: '概述' },
          { id: 'axioms', label: `公理 ${axioms.length}` },
          { id: 'entries', label: `条目 ${workshopStore.draft?.entries?.length || 0}` },
        ]"
        :key="item.id"
        class="flex-1 rounded px-2 py-2"
        :class="tab === item.id ? 'bg-cyan-800 text-white' : 'text-slate-400 hover:bg-slate-900'"
        @click="tab = item.id"
      >{{ item.label }}</button>
    </nav>

    <section v-if="tab === 'overview'">
      <h3 class="text-xs font-bold text-cyan-200">世界概述</h3>
      <p class="mt-1 text-[10px] leading-relaxed text-slate-500">描述世界背景、总体印象和希望重点呈现的体验；它不是不可违背的公理。</p>
      <ExpandableTextarea
        v-model="overview"
        label="工坊世界概述"
        textarea-class="mt-3 h-72 rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs leading-relaxed text-slate-200"
      />
      <p class="mt-3 text-[10px] text-emerald-500">停止输入后自动保存到工坊草稿</p>
    </section>

    <section v-else-if="tab === 'axioms'">
      <div class="flex items-start justify-between gap-2">
        <div>
          <h3 class="text-xs font-bold text-amber-300">世界公理</h3>
          <p class="mt-1 text-[10px] leading-relaxed text-slate-500">一格一条，描述世界内部真实成立的底层规则；保存时自动去除 1.、1、和项目符号。</p>
        </div>
        <div class="flex shrink-0 gap-1">
          <button class="rounded bg-slate-800 px-2 py-1 text-[9px] text-slate-300" @click="batchAxiomsOpen = true">⛶ 批量编辑</button>
          <button class="rounded bg-amber-900/70 px-2 py-1 text-[9px] text-amber-200" @click="beginAxiom()">＋ 新增</button>
        </div>
      </div>

      <div v-if="axiomEditor?.index === -1" class="mt-3 rounded-xl border border-amber-700/70 bg-amber-950/20 p-3">
        <textarea v-model="axiomEditor.text" autofocus class="field h-28" placeholder="输入一条新的世界公理"></textarea>
        <div class="mt-2 flex justify-end gap-1">
          <button class="small-button bg-slate-800" @click="axiomEditor = null">取消</button>
          <button class="small-button bg-amber-700 text-white" @click="saveAxiom">添加公理</button>
        </div>
      </div>

      <ol class="mt-3 space-y-2">
        <li
          v-for="(axiom, index) in axioms"
          :key="`${index}-${axiom}`"
          class="rounded-xl border border-amber-900/45 bg-amber-950/15 p-3"
        >
          <template v-if="axiomEditor?.index === index">
            <textarea v-model="axiomEditor.text" autofocus class="field h-28"></textarea>
            <div class="mt-2 flex justify-end gap-1">
              <button class="small-button bg-slate-800" @click="axiomEditor = null">取消</button>
              <button class="small-button bg-amber-700 text-white" @click="saveAxiom">保存</button>
            </div>
          </template>
          <template v-else>
            <div class="flex items-start gap-2">
              <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-900/60 text-[9px] font-bold text-amber-200">{{ index + 1 }}</span>
              <p class="min-w-0 flex-1 text-xs leading-relaxed text-slate-300">{{ axiom }}</p>
            </div>
            <div class="mt-3 flex flex-wrap justify-end gap-1">
              <button class="small-button bg-violet-950 text-violet-300" @click="workshopStore.prepareWorldbookAxiomPrompt(axiom, index)">让 AI 讨论修改</button>
              <button class="small-button bg-slate-800 text-slate-300" @click="beginAxiom(index)">编辑</button>
              <InlineDeleteConfirm
                compact
                :active="confirmDeleteId === `axiom-${index}`"
                :confirm-id="`axiom-${index}`"
                @request="requestDelete(`axiom-${index}`)"
                @cancel="cancelDelete"
                @confirm="deleteAxiom(index)"
              />
            </div>
          </template>
        </li>
      </ol>
      <p v-if="!axioms.length && !axiomEditor" class="mt-4 rounded-lg border border-dashed border-slate-700 p-5 text-center text-xs text-slate-500">尚未建立世界公理。</p>
      <p class="mt-3 text-[10px] text-emerald-500">修改后自动保存到工坊草稿</p>
    </section>

    <section v-else>
      <div class="sticky top-9 z-[9] -mx-1 flex gap-2 bg-aw_panel px-1 pb-3 pt-1">
        <input v-model="search" class="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-[10px] text-white" placeholder="搜索名称、触发词、标签或内容">
        <button class="rounded-lg bg-indigo-700 px-3 text-[10px] text-white" @click="startEntry()">＋ 新增</button>
      </div>
      <p class="mb-2 text-[9px] leading-relaxed text-slate-600">⭐ 表示“常驻”：条目置顶，并在世界书启用时始终进入正文上下文。</p>
      <div class="space-y-2">
        <article
          v-for="entry in entries"
          :key="entry.id"
          class="rounded-xl border border-slate-700 bg-slate-900/65 p-3"
          :class="entry.is_active === false ? 'opacity-50' : ''"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="truncate text-xs font-bold text-slate-200">{{ entry.name }}</div>
              <div class="mt-1 truncate text-[9px] text-slate-500">触发：{{ entry.keys || '无' }}</div>
            </div>
            <div class="flex shrink-0 items-center gap-1">
              <button
                class="rounded px-1.5 py-1 text-[10px]"
                :class="(entry.tags || []).includes('常驻') ? 'bg-amber-900/60 text-amber-300' : 'bg-slate-800 text-slate-600'"
                :title="(entry.tags || []).includes('常驻') ? '取消常驻' : '设为常驻并置顶'"
                @click="togglePinned(entry)"
              >⭐</button>
              <button class="text-[9px]" :class="entry.is_active === false ? 'text-slate-500' : 'text-emerald-400'" @click="toggleEntry(entry)">{{ entry.is_active === false ? '已关闭' : '已启用' }}</button>
            </div>
          </div>
          <div class="mt-2 flex flex-wrap gap-1"><span v-for="tag in entry.tags" :key="tag" class="rounded bg-slate-800 px-1.5 py-0.5 text-[9px] text-indigo-300">{{ tag }}</span></div>
          <p class="mt-2 line-clamp-3 text-[10px] leading-relaxed text-slate-500">{{ entry.content }}</p>
          <div class="mt-3 flex flex-wrap gap-1">
            <button class="small-button bg-slate-800 text-slate-300" @click="startEntry(entry)">编辑</button>
            <button class="small-button bg-violet-950 text-violet-300" @click="workshopStore.prepareWorldbookEntryPrompt(entry)">让 AI 修改</button>
            <InlineDeleteConfirm
              compact
              :active="confirmDeleteId === entry.id"
              :confirm-id="entry.id"
              @request="requestDelete(entry.id)"
              @cancel="cancelDelete"
              @confirm="deleteEntry(entry)"
            />
          </div>
        </article>
      </div>
      <p v-if="!entries.length" class="rounded-lg border border-dashed border-slate-700 p-5 text-center text-xs text-slate-500">没有符合条件的条目。</p>
    </section>

    <WorldbookEntryEditorModal
      v-if="entryEditor"
      :entry="entryEditor"
      :title="entryEditor.isNew ? '新增工坊条目' : `编辑工坊条目 · ${entryEditor.name}`"
      @save="saveEntry"
      @cancel="entryEditor = null"
    />

    <Teleport to="body">
      <div v-if="batchAxiomsOpen" class="fixed inset-0 z-[125] flex flex-col bg-slate-950/95 p-5 backdrop-blur-sm">
        <header class="mb-3 flex items-center justify-between">
          <div><h3 class="font-bold text-amber-200">批量编辑世界公理</h3><p class="mt-1 text-xs text-slate-500">每行一条；可输入 1.、1、或项目符号，保存时自动标准化。</p></div>
          <button class="rounded bg-amber-700 px-4 py-2 text-sm font-bold text-white" @click="batchAxiomsOpen = false">完成</button>
        </header>
        <textarea v-model="axiomsText" autofocus class="min-h-0 flex-1 resize-none rounded-xl border border-amber-900/60 bg-slate-900 p-5 text-base leading-7 text-slate-100 outline-none focus:border-amber-600"></textarea>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.field {
  width: 100%;
  border: 1px solid rgb(51 65 85);
  border-radius: .5rem;
  background: rgb(15 23 42);
  padding: .6rem;
  font-size: .75rem;
  color: rgb(226 232 240);
}
.small-button {
  border-radius: .35rem;
  padding: .3rem .5rem;
  font-size: .58rem;
}
</style>
