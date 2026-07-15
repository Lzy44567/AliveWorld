<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { worldbookWorkshopApi } from '../../api/worldbookWorkshopApi';
import WorkshopDraftPanel from '../worldbook/WorkshopDraftPanel.vue';

const workshopId = ref('');
const draft = ref({ overview: '', axioms: [], entries: [] });
const pending = ref([]);
const proposed = ref([]);
const messages = ref([]);
const suggestions = ref([]);
const input = ref('');
const mode = ref('expand');
const busy = ref(false);
const commitChanges = ref(false);
const dirty = ref(false);
const editingEntry = ref(null);
const overviewDraft = ref('');
const axiomsDraft = ref('');
let headerSaveTimer = null;
let syncingHeader = false;

const modes = [
  { id: 'create', label: '从一句话创建', description: '根据一句核心想法、题材和偏好建立概述、公理与首批条目。' },
  { id: 'expand', label: '拓展新领域', description: '横向补充尚未覆盖的地区、制度、文化、职业或生活细节。' },
  { id: 'evolve', label: '演化已有设定', description: '从已有公理推导逻辑后果，检查关联、缺口与冲突。' },
];
const activeMode = computed(() => modes.find(item => item.id === mode.value));
const worldbookNames = computed(() => uiStore.workshopSessionId
  ? (assetStore.worlds.local || []).map(item => item.name)
  : (assetStore.availableWorldbooks || []));

const close = async () => {
  if (await saveBookHeader() === false) return;
  uiStore.modals.worldbookWorkshop = false;
};
const sync = (data) => {
  workshopId.value = data.workshop_id || workshopId.value;
  draft.value = data.draft || draft.value;
  pending.value = data.pending || [];
  proposed.value = data.proposed || [];
  dirty.value = Boolean(data.dirty);
  syncingHeader = true;
  overviewDraft.value = draft.value.overview || '';
  axiomsDraft.value = (draft.value.axioms || []).join('\n');
  syncingHeader = false;
  if (data.messages) messages.value = data.messages;
  if (data.suggested_actions) suggestions.value = data.suggested_actions;
};

const loadWorldbook = async (name) => {
  if (!name || busy.value) return;
  if (workshopId.value && await saveBookHeader() === false) return;
  busy.value = true;
  editingEntry.value = null;
  try {
    uiStore.workshopWorldbookName = name;
    const data = await worldbookWorkshopApi.start(name, uiStore.workshopSessionId || null);
    sync(data);
    if (data.resumed) uiStore.showToast('已恢复这本世界书尚未发布的工坊草稿');
  } catch (e) { uiStore.showToast(e.message, 'error'); }
  finally { busy.value = false; }
};

onMounted(() => loadWorldbook(uiStore.workshopWorldbookName));

const send = async (text = input.value) => {
  const message = text.trim();
  if (!message || busy.value) return;
  input.value = '';
  busy.value = true;
  try { sync(await worldbookWorkshopApi.chat(workshopId.value, message, mode.value, commitChanges.value)); }
  catch (e) { uiStore.showToast(e.message, 'error'); }
  finally { busy.value = false; }
};

const operationLabel = (op) => ({
  add_entry: '新增条目', update_entry: '修改条目', deactivate_entry: '关闭条目',
  request_delete: '申请删除条目', delete_entry: '删除条目', update_overview: '修改世界概述', set_axioms: '重设世界公理',
})[op.op] || op.op;
const operationTarget = (op) => op.entry?.name || op.entry_id || (op.op === 'set_axioms' ? '世界公理' : op.op === 'update_overview' ? '世界概述' : '世界书');
const submitProposal = async () => {
  if (!proposed.value.length || busy.value) return;
  busy.value = true;
  try { sync(await worldbookWorkshopApi.operations(workshopId.value, proposed.value, false)); }
  catch (e) { uiStore.showToast(e.message, 'error'); }
  finally { busy.value = false; }
};

const applyManual = async (operations, syncResponse = true) => {
  try {
    const data = await worldbookWorkshopApi.operations(workshopId.value, operations, true);
    if (syncResponse) sync(data);
    else {
      draft.value = data.draft || draft.value;
      pending.value = data.pending || [];
      dirty.value = Boolean(data.dirty);
    }
    return true;
  }
  catch (e) { uiStore.showToast(e.message, 'error'); return false; }
};

const saveBookHeader = async () => {
  if (headerSaveTimer) window.clearTimeout(headerSaveTimer);
  headerSaveTimer = null;
  if (!workshopId.value || syncingHeader) return true;
  return applyManual([
    { op: 'update_overview', overview: overviewDraft.value },
    { op: 'set_axioms', axioms: axiomsDraft.value.split(/\r?\n/).map(item => item.trim()).filter(Boolean) },
  ], false);
};
watch([overviewDraft, axiomsDraft], () => {
  if (syncingHeader || !workshopId.value) return;
  if (headerSaveTimer) window.clearTimeout(headerSaveTimer);
  headerSaveTimer = window.setTimeout(saveBookHeader, 800);
}, { flush: 'sync' });
onBeforeUnmount(() => { if (headerSaveTimer) window.clearTimeout(headerSaveTimer); });

const startAddEntry = () => { editingEntry.value = { isNew: true, id: '', name: '', keys: '', content: '', tagsText: '', is_active: true }; };
const startEditEntry = (entry) => { editingEntry.value = { ...JSON.parse(JSON.stringify(entry)), isNew: false, tagsText: (entry.tags || []).join(', ') }; };
const cancelEditEntry = () => { editingEntry.value = null; };
const saveEntry = async () => {
  const item = editingEntry.value;
  const tags = item.tagsText.split(/[,，]/).map(tag => tag.trim()).filter(Boolean);
  const operation = item.isNew
    ? { op: 'add_entry', entry: { name: item.name, keys: item.keys, content: item.content, tags, is_active: item.is_active } }
    : { op: 'update_entry', entry_id: item.id, changes: { name: item.name, keys: item.keys, content: item.content, tags, is_active: item.is_active } };
  if (await applyManual([operation])) editingEntry.value = null;
};
const toggleEntry = (entry) => applyManual([{ op: 'update_entry', entry_id: entry.id, changes: { is_active: entry.is_active === false } }]);
const deleteEntry = async (entry) => {
  await applyManual([{ op: 'delete_entry', entry_id: entry.id }]);
};
const askAiToEdit = (entry) => {
  input.value = `请修改指定条目“${entry.name}”（entry_id: ${entry.id}）。我的要求是：`;
  mode.value = 'evolve';
};

const decide = async (operationId, approve) => {
  try { sync(approve ? await worldbookWorkshopApi.approve(workshopId.value, operationId) : await worldbookWorkshopApi.reject(workshopId.value, operationId)); }
  catch (e) { uiStore.showToast(e.message, 'error'); }
};
const undo = async () => {
  try { sync(await worldbookWorkshopApi.undo(workshopId.value)); editingEntry.value = null; }
  catch (e) { uiStore.showToast(e.message, 'error'); }
};
const publish = async () => {
  try {
    if (await saveBookHeader() === false) return;
    const isTemplate = draft.value.is_template === true || (draft.value.tags || []).includes('模板');
    const publishName = isTemplate ? window.prompt('模板不能被覆盖，请输入个人世界书名称：', `${draft.value.name || '新世界书'}_个人版`) : null;
    if (isTemplate && !publishName) return;
    sync(await worldbookWorkshopApi.publish(workshopId.value, publishName));
    await assetStore.fetchAssets();
    uiStore.showToast('世界书草稿已发布');
  } catch (e) { uiStore.showToast(e.message, 'error'); }
};
</script>

<template>
  <div class="fixed inset-0 z-[90] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
    <div class="flex h-[90vh] w-full max-w-7xl flex-col overflow-hidden rounded-2xl border border-indigo-700/60 bg-slate-950 shadow-2xl">
      <header class="flex items-center justify-between border-b border-slate-800 px-5 py-3">
        <div class="flex items-center gap-3"><div><h2 class="font-bold text-indigo-300">🧭 世界书工坊</h2><p class="text-[10px] text-slate-500">草稿每轮自动保存，关闭后可恢复；不推进故事时间</p></div><select :value="uiStore.workshopWorldbookName" @change="loadWorldbook($event.target.value)" class="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"><option v-for="name in worldbookNames" :key="name" :value="name">{{ name }}</option></select><span v-if="dirty" class="text-[10px] text-amber-400">未发布草稿已保存</span></div>
        <div class="flex gap-2"><button @click="undo" class="rounded bg-slate-800 px-3 py-1.5 text-xs text-slate-300">撤销</button><button @click="publish" class="rounded bg-emerald-700 px-3 py-1.5 text-xs font-bold text-white">发布草稿</button><button @click="close" class="px-2 text-slate-400">✕</button></div>
      </header>
      <div class="grid min-h-0 flex-1 grid-cols-[1fr_420px]">
        <section class="flex min-h-0 flex-col border-r border-slate-800">
          <div class="border-b border-slate-800 p-3"><div class="flex gap-2"><button v-for="item in modes" :key="item.id" @click="mode=item.id" class="rounded px-3 py-1.5 text-xs" :class="mode===item.id?'bg-indigo-700 text-white':'bg-slate-900 text-slate-400'">{{ item.label }}</button></div><p class="mt-2 text-[10px] text-slate-500">{{ activeMode.description }}</p></div>
          <div class="flex-1 space-y-3 overflow-y-auto p-4">
            <div v-if="busy && !messages.length" class="text-sm text-slate-500">正在载入或恢复工坊草稿……</div>
            <div v-for="(msg, index) in messages" :key="index" class="max-w-[85%] whitespace-pre-wrap rounded-xl p-3 text-sm leading-relaxed" :class="msg.role==='user'?'ml-auto bg-indigo-700 text-white':'bg-slate-800 text-slate-200'">{{ msg.content }}</div>
            <div v-if="proposed.length" class="rounded-xl border border-cyan-700/60 bg-cyan-950/25 p-3"><div class="flex items-center justify-between gap-3"><div><div class="text-xs font-bold text-cyan-300">AI 拟议修改 · 尚未写入</div><p class="mt-1 text-[10px] text-slate-500">先审阅方案；提交后低风险修改进入草稿，高影响修改仍需逐项确认。</p></div><button @click="submitProposal" :disabled="busy" class="shrink-0 rounded bg-cyan-700 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50">提交此方案</button></div><div v-for="op in proposed" :key="op.operation_id" class="mt-2 rounded-lg border border-cyan-900/50 bg-black/25 p-3 text-xs text-slate-300"><div class="font-bold text-cyan-200">{{ operationLabel(op) }} · {{ operationTarget(op) }}</div><ol v-if="op.op==='set_axioms'" class="mt-2 list-decimal space-y-1 pl-5 text-slate-300"><li v-for="axiom in op.axioms" :key="axiom">{{ axiom }}</li></ol><p v-else-if="op.op==='update_overview'" class="mt-2 whitespace-pre-wrap text-slate-400">{{ op.overview }}</p><p v-else-if="op.op==='add_entry'" class="mt-2 whitespace-pre-wrap text-slate-400">{{ op.entry?.content }}</p><p v-else-if="op.op==='update_entry'" class="mt-2 whitespace-pre-wrap text-slate-400">{{ op.changes?.content || '将修改名称、触发词、标签或启用状态；可在右侧草稿中继续审阅。' }}</p></div></div>
            <div v-if="pending.length" class="rounded-xl border border-amber-700/60 bg-amber-950/30 p-3"><div class="mb-2 text-xs font-bold text-amber-300">需要确认的高影响修改</div><div v-for="op in pending" :key="op.operation_id" class="mb-2 rounded bg-black/30 p-3 text-xs text-slate-300"><div class="font-bold">{{ operationLabel(op) }} · {{ operationTarget(op) }}</div><ol v-if="op.op==='set_axioms'" class="mt-2 list-decimal space-y-1 pl-5"><li v-for="axiom in op.axioms" :key="axiom">{{ axiom }}</li></ol><p v-else-if="op.entry?.content" class="mt-2 whitespace-pre-wrap text-slate-400">{{ op.entry.content }}</p><p v-else-if="op.changes?.content" class="mt-2 whitespace-pre-wrap text-slate-400">{{ op.changes.content }}</p><div class="mt-3 flex gap-2"><button @click="decide(op.operation_id,true)" class="rounded bg-emerald-700 px-3 py-1">接受并写入</button><button @click="decide(op.operation_id,false)" class="rounded bg-rose-800 px-3 py-1">拒绝</button></div></div></div>
          </div>
          <div class="border-t border-slate-800 p-3"><div class="mb-2 flex items-center justify-between gap-3"><div class="flex rounded-lg border border-slate-700 bg-slate-900 p-0.5 text-[10px]"><button @click="commitChanges=false" class="rounded px-2 py-1" :class="!commitChanges?'bg-cyan-800 text-white':'text-slate-500'">先讨论方案</button><button @click="commitChanges=true" class="rounded px-2 py-1" :class="commitChanges?'bg-emerald-800 text-white':'text-slate-500'">允许 AI 修改草稿</button></div><span class="text-[10px] text-slate-500">{{ commitChanges ? '低风险修改直接进入草稿；公理与删除仍需确认' : 'AI 只提出可审阅方案，不改变草稿' }}</span></div><div v-if="suggestions.length" class="mb-2 flex flex-wrap gap-1"><button v-for="item in suggestions" :key="item" @click="input=item" class="rounded-full border border-indigo-800 px-2 py-1 text-left text-[10px] text-indigo-300" title="填入输入框，可修改后发送">{{ item }}</button></div><div class="flex gap-2"><textarea v-model="input" @keydown.ctrl.enter.prevent="send()" class="h-20 flex-1 rounded-lg border border-slate-700 bg-slate-900 p-3 text-sm text-slate-200" :placeholder="`${activeMode.description} Ctrl+Enter发送`"></textarea><button @click="send()" :disabled="busy" class="w-20 rounded-lg bg-indigo-700 text-sm font-bold text-white disabled:opacity-50">{{ busy ? '处理中' : '发送' }}</button></div></div>
        </section>

        <WorkshopDraftPanel v-model:overview="overviewDraft" v-model:axioms="axiomsDraft" :draft="draft" :editing-entry="editingEntry" @add-entry="startAddEntry" @edit-entry="startEditEntry" @cancel-edit="cancelEditEntry" @save-entry="saveEntry" @toggle-entry="toggleEntry" @delete-entry="deleteEntry" @ask-ai="askAiToEdit" />
      </div>
    </div>
  </div>
</template>
