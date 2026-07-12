<script setup>
import { computed, onMounted, ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { worldbookWorkshopApi } from '../../api/worldbookWorkshopApi';

const workshopId = ref('');
const draft = ref({ overview: '', axioms: [], entries: [] });
const pending = ref([]);
const messages = ref([]);
const suggestions = ref([]);
const input = ref('');
const mode = ref('expand');
const busy = ref(false);
const dirty = ref(false);
const editingEntry = ref(null);
const overviewDraft = ref('');
const axiomsDraft = ref('');

const modes = [
  { id: 'create', label: '从一句话创建', description: '根据一句核心想法、题材和偏好建立概述、公理与首批条目。' },
  { id: 'expand', label: '拓展新领域', description: '横向补充尚未覆盖的地区、制度、文化、职业或生活细节。' },
  { id: 'evolve', label: '演化已有设定', description: '从已有公理推导逻辑后果，检查关联、缺口与冲突。' },
];
const activeMode = computed(() => modes.find(item => item.id === mode.value));
const worldbookNames = computed(() => assetStore.availableWorldbooks || []);

const close = () => { uiStore.modals.worldbookWorkshop = false; };
const sync = (data) => {
  workshopId.value = data.workshop_id || workshopId.value;
  draft.value = data.draft || draft.value;
  pending.value = data.pending || [];
  dirty.value = Boolean(data.dirty);
  overviewDraft.value = draft.value.overview || '';
  axiomsDraft.value = (draft.value.axioms || []).join('\n');
  if (data.messages) messages.value = data.messages;
  if (data.suggested_actions) suggestions.value = data.suggested_actions;
};

const loadWorldbook = async (name) => {
  if (!name || busy.value) return;
  busy.value = true;
  editingEntry.value = null;
  try {
    uiStore.workshopWorldbookName = name;
    const data = await worldbookWorkshopApi.start(name);
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
  try { sync(await worldbookWorkshopApi.chat(workshopId.value, message, mode.value)); }
  catch (e) { uiStore.showToast(e.message, 'error'); }
  finally { busy.value = false; }
};

const applyManual = async (operations) => {
  try { sync(await worldbookWorkshopApi.operations(workshopId.value, operations, true)); return true; }
  catch (e) { uiStore.showToast(e.message, 'error'); return false; }
};

const saveBookHeader = async () => {
  await applyManual([
    { op: 'update_overview', overview: overviewDraft.value },
    { op: 'set_axioms', axioms: axiomsDraft.value.split(/\r?\n/).map(item => item.trim()).filter(Boolean) },
  ]);
};

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
  if (!window.confirm(`确定从草稿中删除条目“${entry.name}”吗？仍可通过撤销恢复。`)) return;
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
            <div v-for="(msg, index) in messages" :key="index" class="max-w-[85%] rounded-xl p-3 text-sm" :class="msg.role==='user'?'ml-auto bg-indigo-700 text-white':'bg-slate-800 text-slate-200'">{{ msg.content }}</div>
            <div v-if="pending.length" class="rounded-xl border border-amber-700/60 bg-amber-950/30 p-3"><div class="mb-2 text-xs font-bold text-amber-300">需要确认的高影响修改</div><div v-for="op in pending" :key="op.operation_id" class="mb-2 rounded bg-black/30 p-2 text-xs text-slate-300"><div>{{ op.op }} · {{ op.entry?.name || op.entry_id || '世界公理' }}</div><div class="mt-2 flex gap-2"><button @click="decide(op.operation_id,true)" class="rounded bg-emerald-700 px-2 py-1">接受</button><button @click="decide(op.operation_id,false)" class="rounded bg-rose-800 px-2 py-1">拒绝</button></div></div></div>
          </div>
          <div class="border-t border-slate-800 p-3"><div v-if="suggestions.length" class="mb-2 flex flex-wrap gap-1"><button v-for="item in suggestions" :key="item" @click="send(item)" class="rounded-full border border-indigo-800 px-2 py-1 text-[10px] text-indigo-300">{{ item }}</button></div><div class="flex gap-2"><textarea v-model="input" @keydown.ctrl.enter.prevent="send()" class="h-20 flex-1 rounded-lg border border-slate-700 bg-slate-900 p-3 text-sm text-slate-200" :placeholder="`${activeMode.description} Ctrl+Enter发送`"></textarea><button @click="send()" :disabled="busy" class="w-20 rounded-lg bg-indigo-700 text-sm font-bold text-white disabled:opacity-50">{{ busy ? '处理中' : '发送' }}</button></div></div>
        </section>

        <aside class="overflow-y-auto p-4">
          <div class="flex items-center justify-between"><h3 class="font-bold text-slate-200">当前草稿</h3><button @click="startAddEntry" class="rounded bg-indigo-800 px-2 py-1 text-[10px] text-white">+ 手动新增条目</button></div>
          <label class="mt-3 block text-[10px] text-slate-500">世界概述</label><textarea v-model="overviewDraft" class="mt-1 h-20 w-full rounded border border-slate-800 bg-slate-900 p-2 text-xs text-slate-300"></textarea>
          <label class="mt-3 block text-[10px] text-amber-400">世界公理（每行一条）</label><textarea v-model="axiomsDraft" class="mt-1 h-20 w-full rounded border border-amber-900/60 bg-slate-900 p-2 text-xs text-slate-300"></textarea><button @click="saveBookHeader" class="mt-2 rounded bg-slate-700 px-2 py-1 text-[10px] text-white">保存概述与公理到草稿</button>

          <div v-if="editingEntry" class="mt-4 rounded-lg border border-indigo-700/60 bg-indigo-950/20 p-3"><div class="text-xs font-bold text-indigo-300">{{ editingEntry.isNew ? '新增条目' : '编辑条目' }}</div><input v-model="editingEntry.name" placeholder="条目名" class="mt-2 w-full rounded border border-slate-700 bg-slate-950 p-2 text-xs text-white"><input v-model="editingEntry.keys" placeholder="触发词" class="mt-2 w-full rounded border border-slate-700 bg-slate-950 p-2 text-xs text-white"><textarea v-model="editingEntry.content" placeholder="条目内容" class="mt-2 h-24 w-full rounded border border-slate-700 bg-slate-950 p-2 text-xs text-white"></textarea><input v-model="editingEntry.tagsText" placeholder="标签，逗号分隔" class="mt-2 w-full rounded border border-slate-700 bg-slate-950 p-2 text-xs text-white"><div class="mt-2 flex gap-2"><button @click="saveEntry" class="rounded bg-emerald-700 px-2 py-1 text-[10px] text-white">保存到草稿</button><button @click="cancelEditEntry" class="rounded bg-slate-700 px-2 py-1 text-[10px] text-white">取消</button></div></div>

          <div class="mt-4 space-y-2"><div v-for="entry in draft.entries" :key="entry.id" class="rounded-lg border border-slate-800 bg-slate-900 p-2" :class="entry.is_active===false?'opacity-50':''"><div class="flex items-start justify-between gap-2"><div class="min-w-0"><div class="truncate text-xs font-bold text-slate-300">{{ entry.name }}</div><div class="mt-1 line-clamp-3 text-[10px] text-slate-500">{{ entry.content }}</div></div><button @click="toggleEntry(entry)" class="shrink-0 text-[9px]" :class="entry.is_active===false?'text-slate-500':'text-emerald-400'">{{ entry.is_active===false?'已关闭':'已启用' }}</button></div><div class="mt-1 flex flex-wrap gap-1"><span v-for="tag in entry.tags" :key="tag" class="rounded bg-slate-800 px-1 text-[9px] text-indigo-300">{{ tag }}</span></div><div class="mt-2 flex gap-1"><button @click="startEditEntry(entry)" class="rounded bg-slate-800 px-2 py-1 text-[9px] text-slate-300">编辑</button><button @click="askAiToEdit(entry)" class="rounded bg-violet-900/60 px-2 py-1 text-[9px] text-violet-300">让AI修改</button><button @click="deleteEntry(entry)" class="rounded bg-rose-950 px-2 py-1 text-[9px] text-rose-400">删除</button></div></div></div>
        </aside>
      </div>
    </div>
  </div>
</template>
