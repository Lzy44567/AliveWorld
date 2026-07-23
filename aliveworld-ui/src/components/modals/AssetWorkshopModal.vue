<script setup>
import { computed, onMounted, ref } from 'vue';
import { assetWorkshopApi } from '../../api/assetWorkshopApi';
import { assetStore } from '../../store/assetStore';
import { gameStore } from '../../store/gameStore';
import { uiStore } from '../../store/uiStore';

const id = ref('');
const draft = ref({});
const proposed = ref([]);
const messages = ref([]);
const suggestions = ref([]);
const dirty = ref(false);
const busy = ref(false);
const activity = ref('');
const input = ref('');
const mode = ref('refine');
const commitChanges = ref(false);
const edit = ref({});
const type = computed(() => uiStore.workshopAssetType);
const labels = {
  characters: { icon: '🎭', name: '角色卡', color: 'text-indigo-300' },
  styles: { icon: '📜', name: '文风卡', color: 'text-rose-300' },
  entities: { icon: '👾', name: '实体卡', color: 'text-purple-300' },
};
const currentLabel = computed(() => labels[type.value] || labels.characters);
const modes = [
  { id: 'create', label: '从核心想法创建', description: '从一句核心想法建立较完整的资产草稿。' },
  { id: 'refine', label: '细化与修改', description: '围绕玩家指定的问题补充、修正并保持一致性。' },
  { id: 'review', label: '审阅与去俗套', description: '检查矛盾、空洞描述、俗套化和执行难点。' },
];
const activeMode = computed(() => modes.find(item => item.id === mode.value));

function sync(data) {
  id.value = data.workshop_id || id.value;
  draft.value = data.draft || draft.value;
  edit.value = JSON.parse(JSON.stringify(draft.value));
  proposed.value = data.proposed || [];
  messages.value = data.messages || messages.value;
  suggestions.value = data.suggested_actions || [];
  dirty.value = Boolean(data.dirty);
}

onMounted(async () => {
  busy.value = true; activity.value = 'loading';
  try {
    const data = await assetWorkshopApi.start(
      type.value, uiStore.workshopAssetName, uiStore.workshopAssetSessionId
    );
    sync(data);
    if (data.resumed) uiStore.showToast(`已恢复“${data.asset_name}”尚未发布的工坊草稿`);
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { busy.value = false; activity.value = ''; }
});

async function send(text = input.value) {
  const message = text.trim();
  if (!message || busy.value || !id.value) return;
  input.value = '';
  messages.value = [...messages.value, { role: 'user', content: message, optimistic: true }];
  busy.value = true; activity.value = 'chat';
  try { sync(await assetWorkshopApi.chat(id.value, message, mode.value, commitChanges.value)); }
  catch (error) {
    messages.value = messages.value.map(item => item.optimistic ? { ...item, failed: true } : item);
    uiStore.showToast(error.message, 'error');
  } finally { busy.value = false; activity.value = ''; }
}

async function apply(operations) {
  busy.value = true;
  try { sync(await assetWorkshopApi.operations(id.value, operations)); return true; }
  catch (error) { uiStore.showToast(error.message, 'error'); return false; }
  finally { busy.value = false; }
}
async function submitProposal() {
  if (proposed.value.length) await apply(proposed.value);
}
async function saveManual() {
  const changes = {};
  const fields = type.value === 'characters'
    ? ['tags', 'description', 'starting_scene', 'is_player']
    : type.value === 'styles'
      ? ['tags', 'content']
      : ['tags', 'description', 'motive', 'status', 'mechanisms', 'plans', 'recent_actions', 'triggers', 'relationships', 'importance', 'is_active'];
  for (const field of fields) changes[field] = edit.value[field];
  await apply([{ op: 'update_fields', changes, reason: '玩家手动编辑' }]);
}
async function undo() {
  try { sync(await assetWorkshopApi.undo(id.value)); }
  catch (error) { uiStore.showToast(error.message, 'error'); }
}
async function publish() {
  busy.value = true;
  try {
    sync(await assetWorkshopApi.publish(id.value));
    if (uiStore.workshopAssetSessionId) await assetStore.fetchLocalAssets(gameStore.sessionId);
    else await assetStore.fetchAssets();
    uiStore.showToast(`${currentLabel.value.name}草稿已发布`);
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { busy.value = false; }
}
function close() { uiStore.modals.assetWorkshop = false; }
function back() { close(); uiStore.modals.workshopHub = true; }
function addTrigger() { (edit.value.triggers ||= []).push({ condition: '', result: '' }); }
function addRelationship() { (edit.value.relationships ||= []).push({ target: '', relation: '' }); }
const lines = value => Array.isArray(value) ? value.join('\n') : String(value || '');
const setLines = (field, value) => { edit.value[field] = value.split(/\r?\n/).map(item => item.trim()).filter(Boolean); };
</script>

<template>
  <div class="fixed inset-0 z-[95] flex items-center justify-center bg-black/85 p-4 backdrop-blur-sm">
    <div class="flex h-[92vh] w-full max-w-7xl flex-col overflow-hidden rounded-2xl border border-cyan-800/60 bg-slate-950 shadow-2xl">
      <header class="flex items-center justify-between border-b border-slate-800 px-5 py-3">
        <div class="flex items-center gap-3"><button class="rounded bg-slate-800 px-2 py-1 text-xs text-slate-300" @click="back">← 总工坊</button><div><div class="flex items-center gap-2"><h2 class="font-bold" :class="currentLabel.color">{{ currentLabel.icon }} {{ currentLabel.name }}工坊 · {{ draft.name }}</h2><span v-if="dirty" class="text-[10px] text-amber-400">未发布草稿已保存</span></div><p class="text-[10px] text-slate-500">讨论和草稿独立保存，不推进正文时间</p></div></div>
        <div class="flex gap-2"><button class="toolbar-btn" @click="undo">撤销</button><button class="rounded bg-emerald-700 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-40" :disabled="busy || !dirty" @click="publish">发布</button><button class="px-2 text-slate-400" @click="close">✕</button></div>
      </header>
      <div class="grid min-h-0 flex-1 grid-cols-[1fr_450px]">
        <section class="flex min-h-0 flex-col border-r border-slate-800">
          <div class="border-b border-slate-800 p-3"><div class="flex gap-2"><button v-for="item in modes" :key="item.id" class="rounded px-3 py-1.5 text-xs" :class="mode===item.id?'bg-cyan-700 text-white':'bg-slate-900 text-slate-400'" @click="mode=item.id">{{ item.label }}</button></div><p class="mt-2 text-[10px] text-slate-500">{{ activeMode.description }}</p></div>
          <div class="flex-1 space-y-3 overflow-y-auto p-4 custom-scrollbar">
            <p v-if="activity==='loading'" class="text-sm text-slate-500">正在载入或恢复工坊草稿……</p>
            <div v-for="(message,index) in messages" :key="index" class="w-fit max-w-[86%] whitespace-pre-wrap rounded-xl p-3 text-sm leading-relaxed" :class="message.role==='user'?'ml-auto bg-cyan-700 text-white':'bg-slate-800 text-slate-200'">{{ message.content }}<span v-if="message.failed" class="ml-2 text-xs text-rose-200">发送失败</span></div>
            <div v-if="activity==='chat'" class="w-fit rounded-xl bg-slate-800 p-3 text-sm text-slate-400">工坊 AI 正在梳理目标、取舍与修改方案……</div>
            <div v-if="proposed.length" class="rounded-xl border border-cyan-700/60 bg-cyan-950/25 p-3"><div class="flex items-center justify-between"><div><h3 class="text-xs font-bold text-cyan-300">AI 拟议修改 · 尚未写入</h3><p class="mt-1 text-[10px] text-slate-500">审阅后只写入工坊草稿，发布前不会改变资产。</p></div><button class="rounded bg-cyan-700 px-3 py-1.5 text-xs text-white" @click="submitProposal">提交方案</button></div><div v-for="op in proposed" :key="op.operation_id" class="mt-2 rounded bg-black/25 p-2 text-xs text-slate-300">{{ op.reason || '修改资产字段' }}：{{ Object.keys(op.changes || {}).join('、') }}</div></div>
          </div>
          <footer class="border-t border-slate-800 p-3"><div class="mb-2 flex items-center justify-between"><div class="flex rounded-lg border border-slate-700 bg-slate-900 p-0.5 text-[10px]"><button class="rounded px-2 py-1" :class="!commitChanges?'bg-cyan-800 text-white':'text-slate-500'" @click="commitChanges=false">先讨论方案</button><button class="rounded px-2 py-1" :class="commitChanges?'bg-emerald-800 text-white':'text-slate-500'" @click="commitChanges=true">允许 AI 修改草稿</button></div></div><div v-if="suggestions.length" class="mb-2 flex flex-wrap gap-1"><button v-for="item in suggestions" :key="item" class="rounded-full border border-cyan-800 px-2 py-1 text-[10px] text-cyan-300" @click="input=item">{{ item }}</button></div><div class="flex gap-2"><textarea v-model="input" class="h-20 flex-1 rounded-lg border border-slate-700 bg-slate-900 p-3 text-sm text-slate-200" :placeholder="`${activeMode.description} Ctrl+Enter 发送`" @keydown.ctrl.enter.prevent="send()"></textarea><button class="w-20 rounded-lg bg-cyan-700 text-sm font-bold text-white" :disabled="busy" @click="send()">{{ busy?'处理中':'发送' }}</button></div></footer>
        </section>

        <aside class="min-h-0 overflow-y-auto bg-slate-900/35 p-4 custom-scrollbar">
          <div class="mb-3 flex items-center justify-between"><div><h3 class="text-sm font-bold text-slate-200">当前草稿</h3><p class="text-[10px] text-slate-500">可直接调整；点击“保存到草稿”后仍需发布</p></div><button class="rounded bg-cyan-800 px-3 py-1.5 text-xs text-white" @click="saveManual">保存到草稿</button></div>
          <div class="space-y-3">
            <label class="block"><span class="field-label">标签（逗号分隔）</span><input :value="(edit.tags||[]).join(', ')" class="field" @input="edit.tags=$event.target.value.split(/[,，]/).map(v=>v.trim()).filter(Boolean)" /></label>
            <template v-if="type==='characters'">
              <label class="flex items-center gap-2 rounded border border-slate-700 p-2 text-xs text-slate-300"><input v-model="edit.is_player" type="checkbox">玩家扮演角色</label>
              <label class="block"><span class="field-label">人物设定</span><textarea v-model="edit.description" class="field h-64"></textarea></label>
              <label class="block"><span class="field-label">登场情境</span><textarea v-model="edit.starting_scene" class="field h-24"></textarea></label>
            </template>
            <template v-else-if="type==='styles'">
              <label class="block"><span class="field-label">文风规范</span><textarea v-model="edit.content" class="field h-[55vh]"></textarea></label>
            </template>
            <template v-else>
              <label class="block"><span class="field-label">描述</span><textarea v-model="edit.description" class="field h-20"></textarea></label>
              <div class="grid grid-cols-2 gap-2"><label><span class="field-label">动机</span><textarea v-model="edit.motive" class="field h-28"></textarea></label><label><span class="field-label">状态</span><textarea v-model="edit.status" class="field h-28"></textarea></label></div>
              <label v-for="field in ['mechanisms','plans','recent_actions']" :key="field" class="block"><span class="field-label">{{ {mechanisms:'机制',plans:'计划',recent_actions:'近期行动'}[field] }}（每行一项）</span><textarea :value="lines(edit[field])" class="field h-24" @input="setLines(field,$event.target.value)"></textarea></label>
              <section class="rounded border border-slate-700 p-2"><div class="flex justify-between text-xs font-bold text-slate-300"><span>触发器</span><button class="text-cyan-300" @click="addTrigger">＋添加</button></div><div v-for="(item,index) in edit.triggers||[]" :key="index" class="mt-2 grid grid-cols-[1fr_1fr_auto] gap-1"><input v-model="item.condition" class="field" placeholder="条件"><input v-model="item.result" class="field" placeholder="结果"><button class="text-rose-400" @click="edit.triggers.splice(index,1)">✕</button></div></section>
              <section class="rounded border border-slate-700 p-2"><div class="flex justify-between text-xs font-bold text-slate-300"><span>关系</span><button class="text-cyan-300" @click="addRelationship">＋添加</button></div><div v-for="(item,index) in edit.relationships||[]" :key="index" class="mt-2 grid grid-cols-[1fr_1fr_auto] gap-1"><input v-model="item.target" class="field" placeholder="对象"><input v-model="item.relation" class="field" placeholder="关系"><button class="text-rose-400" @click="edit.relationships.splice(index,1)">✕</button></div></section>
              <label class="block"><span class="field-label">重要性 0-1</span><input v-model.number="edit.importance" type="number" min="0" max="1" step="0.1" class="field"></label>
            </template>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>

<style scoped>
.toolbar-btn { border-radius: .4rem; background: rgb(51 65 85 / .8); padding: .35rem .65rem; font-size: .7rem; color: rgb(203 213 225); }
.field-label { display: block; margin-bottom: .3rem; font-size: .68rem; color: rgb(148 163 184); }
.field { width: 100%; border: 1px solid rgb(51 65 85); border-radius: .45rem; background: rgb(15 23 42); padding: .5rem .6rem; font-size: .72rem; color: rgb(226 232 240); }
</style>
