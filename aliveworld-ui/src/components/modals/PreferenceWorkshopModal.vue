<script setup>
import { computed, onMounted, ref } from 'vue';
import { preferenceWorkshopApi } from '../../api/preferenceWorkshopApi';
import { preferenceStore } from '../../store/preferenceStore';
import { gameStore } from '../../store/gameStore';
import { uiStore } from '../../store/uiStore';

const workshopId = ref('');
const draft = ref([]);
const pending = ref([]);
const proposed = ref([]);
const messages = ref([]);
const suggestions = ref([]);
const dirty = ref(false);
const busy = ref(false);
const activity = ref('');
const input = ref('');
const mode = ref('discover');
const commitChanges = ref(false);
const editing = ref(null);

const modes = [
  { id: 'discover', label: '探索偏好', description: '从自述和证据探索可能原因，保留竞争解释。' },
  { id: 'refine', label: '修正表述', description: '细化已有偏好的措辞、分类、边界和适用范围。' },
  { id: 'balance', label: '平衡与去重复', description: '检查冲突、迎合过度和审美疲劳风险。' },
];
const categories = {
  story: '剧情发展', adult: '色情内容', action: '动作描写', character: '角色偏好',
  relationship: '关系互动', visual: '视觉与生图', boundary: '边界', other: '其他'
};
const activeMode = computed(() => modes.find(item => item.id === mode.value));
const grouped = computed(() => {
  const result = {};
  for (const item of draft.value) (result[item.category] ||= []).push(item);
  return result;
});

function sync(data) {
  workshopId.value = data.workshop_id || workshopId.value;
  draft.value = data.draft || [];
  pending.value = data.pending || [];
  proposed.value = data.proposed || [];
  messages.value = data.messages || messages.value;
  suggestions.value = data.suggested_actions || [];
  dirty.value = Boolean(data.dirty);
}

onMounted(async () => {
  busy.value = true;
  activity.value = 'loading';
  try {
    const data = await preferenceWorkshopApi.start(gameStore.sessionId || '');
    sync(data);
    if (data.rebased) uiStore.showToast('正式偏好卡已有新变化：旧草稿已安全合并到最新版');
    else if (data.resumed) uiStore.showToast('已恢复尚未发布的偏好工坊草稿');
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  } finally {
    busy.value = false;
    activity.value = '';
  }
});

async function send(text = input.value) {
  const message = text.trim();
  if (!message || busy.value || !workshopId.value) return;
  input.value = '';
  messages.value = [...messages.value, { role: 'user', content: message, optimistic: true }];
  busy.value = true;
  activity.value = 'chat';
  try {
    sync(await preferenceWorkshopApi.chat(
      workshopId.value, message, mode.value, commitChanges.value
    ));
  } catch (error) {
    messages.value = messages.value.map(item => item.optimistic ? { ...item, failed: true } : item);
    uiStore.showToast(error.message, 'error');
  } finally {
    busy.value = false;
    activity.value = '';
  }
}

async function applyOperations(operations, confirmHighRisk = true) {
  if (busy.value) return false;
  busy.value = true;
  try {
    sync(await preferenceWorkshopApi.operations(workshopId.value, operations, confirmHighRisk));
    return true;
  } catch (error) {
    uiStore.showToast(error.message, 'error');
    return false;
  } finally {
    busy.value = false;
  }
}

const startAdd = () => {
  editing.value = {
    isNew: true, statement: '', category: 'story', polarity: 'prefer',
    status: 'candidate', sensitive: false
  };
};
const startEdit = item => { editing.value = { ...JSON.parse(JSON.stringify(item)), isNew: false }; };
const cancelEdit = () => { editing.value = null; };
async function saveEdit() {
  const item = editing.value;
  if (!item?.statement?.trim()) return uiStore.showToast('偏好内容不能为空', 'error');
  const operation = item.isNew
    ? { op: 'add_preference', preference: {
        statement: item.statement, category: item.category, polarity: item.polarity,
        status: item.status, sensitive: item.sensitive
      } }
    : { op: 'update_preference', preference_id: item.id, changes: {
        statement: item.statement, category: item.category, polarity: item.polarity,
        status: item.status, sensitive: item.sensitive
      } };
  if (await applyOperations([operation], true)) editing.value = null;
}

const setStatus = (item, status) =>
  applyOperations([{ op: 'set_status', preference_id: item.id, status }], true);
const requestDelete = item =>
  applyOperations([{ op: 'delete_preference', preference_id: item.id }], false);

async function submitProposal() {
  if (proposed.value.length) await applyOperations(proposed.value, false);
}
async function decide(operationId, approve) {
  try {
    sync(approve
      ? await preferenceWorkshopApi.approve(workshopId.value, operationId)
      : await preferenceWorkshopApi.reject(workshopId.value, operationId));
  } catch (error) { uiStore.showToast(error.message, 'error'); }
}
async function undo() {
  try { sync(await preferenceWorkshopApi.undo(workshopId.value)); editing.value = null; }
  catch (error) { uiStore.showToast(error.message, 'error'); }
}
async function publish() {
  if (pending.value.length) return uiStore.showToast('请先处理待确认修改', 'error');
  busy.value = true;
  try {
    sync(await preferenceWorkshopApi.publish(workshopId.value));
    await preferenceStore.refresh();
    uiStore.showToast('偏好草稿已发布到正式偏好卡');
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { busy.value = false; }
}
const close = () => { uiStore.modals.preferenceWorkshop = false; };
const back = () => { close(); uiStore.modals.workshopHub = true; };

const operationLabel = operation => ({
  add_preference: '新增偏好', update_preference: '修改偏好',
  set_status: '改变状态', delete_preference: '删除偏好'
})[operation.op] || operation.op;
const operationText = operation =>
  operation.preference?.statement
  || draft.value.find(item => item.id === operation.preference_id)?.statement
  || operation.preference_id;
</script>

<template>
  <div class="fixed inset-0 z-[95] flex items-center justify-center bg-black/85 p-4 backdrop-blur-sm">
    <div class="flex h-[92vh] w-full max-w-7xl flex-col overflow-hidden rounded-2xl border border-fuchsia-700/60 bg-slate-950 shadow-2xl">
      <header class="flex items-center justify-between border-b border-slate-800 px-5 py-3">
        <div>
          <div class="flex items-center gap-2"><button class="toolbar-btn" @click="back">← 总工坊</button><h2 class="font-bold text-fuchsia-300">🪞 用户偏好工坊</h2><span v-if="dirty" class="text-[10px] text-amber-400">未发布草稿已保存</span></div>
          <p class="text-[10px] text-slate-500">对话与草稿自动保存，不推进故事；AI 不能修改后验概率和证据</p>
        </div>
        <div class="flex gap-2">
          <button class="toolbar-btn" @click="undo">撤销草稿修改</button>
          <button class="rounded bg-emerald-700 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-40" :disabled="busy || !dirty" @click="publish">发布到偏好卡</button>
          <button class="px-2 text-slate-400 hover:text-white" @click="close">✕</button>
        </div>
      </header>

      <div class="grid min-h-0 flex-1 grid-cols-[1fr_430px]">
        <section class="flex min-h-0 flex-col border-r border-slate-800">
          <div class="border-b border-slate-800 p-3">
            <div class="flex flex-wrap gap-2">
              <button v-for="item in modes" :key="item.id" class="rounded px-3 py-1.5 text-xs" :class="mode===item.id?'bg-fuchsia-700 text-white':'bg-slate-900 text-slate-400'" @click="mode=item.id">{{ item.label }}</button>
            </div>
            <p class="mt-2 text-[10px] text-slate-500">{{ activeMode.description }}</p>
          </div>

          <div class="flex-1 space-y-3 overflow-y-auto p-4 custom-scrollbar">
            <p v-if="activity==='loading'" class="text-sm text-slate-500">正在载入或恢复偏好草稿……</p>
            <div v-for="(message, index) in messages" :key="index" class="w-fit max-w-[86%] whitespace-pre-wrap rounded-xl p-3 text-sm leading-relaxed" :class="message.role==='user'?'ml-auto bg-fuchsia-700 text-white':'bg-slate-800 text-slate-200'">
              {{ message.content }}<span v-if="message.failed" class="ml-2 text-xs text-rose-200">发送失败</span>
            </div>
            <div v-if="activity==='chat'" class="w-fit rounded-xl bg-slate-800 p-3 text-sm text-slate-400">偏好工坊 AI 正在分析证据、替代解释与取舍……</div>

            <section v-if="proposed.length" class="rounded-xl border border-cyan-700/60 bg-cyan-950/25 p-3">
              <div class="flex items-center justify-between gap-3">
                <div><h3 class="text-xs font-bold text-cyan-300">AI 拟议修改 · 尚未写入</h3><p class="mt-1 text-[10px] text-slate-500">提交后只进入草稿；启用和删除仍需单独确认。</p></div>
                <button class="rounded bg-cyan-700 px-3 py-1.5 text-xs font-bold text-white" @click="submitProposal">提交方案</button>
              </div>
              <div v-for="operation in proposed" :key="operation.operation_id" class="mt-2 rounded-lg bg-black/25 p-2 text-xs text-slate-300">
                <strong class="text-cyan-200">{{ operationLabel(operation) }}</strong> · {{ operationText(operation) }}
              </div>
            </section>

            <section v-if="pending.length" class="rounded-xl border border-amber-700/60 bg-amber-950/25 p-3">
              <h3 class="text-xs font-bold text-amber-300">需要确认的启用或删除</h3>
              <div v-for="operation in pending" :key="operation.operation_id" class="mt-2 rounded-lg bg-black/25 p-3 text-xs text-slate-300">
                <strong>{{ operationLabel(operation) }}</strong> · {{ operationText(operation) }}
                <div class="mt-2 flex gap-2"><button class="rounded bg-emerald-700 px-2 py-1" @click="decide(operation.operation_id,true)">确认</button><button class="rounded bg-slate-700 px-2 py-1" @click="decide(operation.operation_id,false)">拒绝</button></div>
              </div>
            </section>
          </div>

          <footer class="border-t border-slate-800 p-3">
            <div class="mb-2 flex items-center justify-between gap-3">
              <div class="flex rounded-lg border border-slate-700 bg-slate-900 p-0.5 text-[10px]"><button class="rounded px-2 py-1" :class="!commitChanges?'bg-cyan-800 text-white':'text-slate-500'" @click="commitChanges=false">先讨论方案</button><button class="rounded px-2 py-1" :class="commitChanges?'bg-emerald-800 text-white':'text-slate-500'" @click="commitChanges=true">允许 AI 修改草稿</button></div>
              <span class="text-[10px] text-slate-500">{{ commitChanges ? '低风险修改进入草稿；启用和删除仍需确认' : 'AI 只提出方案，不改变草稿' }}</span>
            </div>
            <div v-if="suggestions.length" class="mb-2 flex flex-wrap gap-1"><button v-for="item in suggestions" :key="item" class="rounded-full border border-fuchsia-800 px-2 py-1 text-left text-[10px] text-fuchsia-300" @click="input=item">{{ item }}</button></div>
            <div class="flex gap-2"><textarea v-model="input" class="h-20 flex-1 rounded-lg border border-slate-700 bg-slate-900 p-3 text-sm text-slate-200" :placeholder="`${activeMode.description} Ctrl+Enter 发送`" @keydown.ctrl.enter.prevent="send()"></textarea><button class="w-20 rounded-lg bg-fuchsia-700 text-sm font-bold text-white disabled:opacity-40" :disabled="busy" @click="send()">{{ busy ? '处理中' : '发送' }}</button></div>
          </footer>
        </section>

        <aside class="min-h-0 overflow-y-auto bg-slate-900/35 p-4 custom-scrollbar">
          <div class="mb-3 flex items-center justify-between"><div><h3 class="text-sm font-bold text-slate-200">当前偏好草稿</h3><p class="text-[10px] text-slate-500">{{ draft.length }} 条；正式偏好卡不会在发布前改变</p></div><button class="rounded bg-fuchsia-900/60 px-3 py-1.5 text-xs text-fuchsia-200" @click="startAdd">＋ 新增</button></div>

          <section v-if="editing" class="mb-4 space-y-2 rounded-xl border border-fuchsia-700/60 bg-slate-950 p-3">
            <textarea v-model="editing.statement" class="h-24 w-full rounded border border-slate-700 bg-slate-900 p-2 text-xs text-slate-200" placeholder="描述希望获得或回避的体验"></textarea>
            <div class="grid grid-cols-2 gap-2"><select v-model="editing.category" class="field"><option v-for="(label,key) in categories" :key="key" :value="key">{{ label }}</option></select><select v-model="editing.polarity" class="field"><option value="prefer">希望出现</option><option value="avoid">希望回避</option></select><select v-model="editing.status" class="field"><option value="candidate">候选</option><option value="active">已生效</option><option value="disabled">已停用</option></select><label class="field flex items-center gap-2"><input v-model="editing.sensitive" type="checkbox">敏感内容</label></div>
            <div class="flex justify-end gap-2"><button class="toolbar-btn" @click="cancelEdit">取消</button><button class="rounded bg-emerald-700 px-3 py-1.5 text-xs text-white" @click="saveEdit">保存到草稿</button></div>
          </section>

          <section v-for="(items, category) in grouped" :key="category" class="mb-4">
            <h4 class="mb-2 text-xs font-bold text-fuchsia-300">{{ categories[category] || category }}</h4>
            <article v-for="item in items" :key="item.id" class="mb-2 rounded-xl border border-slate-700 bg-slate-950/70 p-3">
              <div class="flex items-start justify-between gap-2"><p class="text-xs leading-relaxed text-slate-200">{{ item.statement }}</p><span class="shrink-0 rounded border border-slate-700 px-1.5 py-0.5 text-[9px]" :class="item.status==='active'?'text-emerald-300':item.status==='candidate'?'text-amber-300':'text-slate-500'">{{ item.status==='active'?'已生效':item.status==='candidate'?'候选':'已停用' }}</span></div>
              <div class="mt-2 flex flex-wrap gap-1 text-[10px]"><button class="toolbar-btn" @click="startEdit(item)">编辑</button><button v-if="item.status!=='active'" class="toolbar-btn text-emerald-300" @click="setStatus(item,'active')">启用</button><button v-else class="toolbar-btn" @click="setStatus(item,'disabled')">停用</button><button class="toolbar-btn text-rose-300" @click="requestDelete(item)">删除</button></div>
            </article>
          </section>
          <p v-if="!draft.length && !editing" class="rounded-lg border border-dashed border-slate-700 p-6 text-center text-xs text-slate-500">偏好草稿为空。可以先与 AI 讨论，或手动新增一条。</p>
        </aside>
      </div>
    </div>
  </div>
</template>

<style scoped>
.toolbar-btn { border-radius: .4rem; background: rgb(51 65 85 / .8); padding: .35rem .65rem; font-size: .7rem; color: rgb(203 213 225); }
.toolbar-btn:hover { background: rgb(71 85 105); }
.field { width: 100%; border: 1px solid rgb(51 65 85); border-radius: .4rem; background: rgb(15 23 42); padding: .45rem .55rem; font-size: .7rem; color: rgb(203 213 225); }
</style>
