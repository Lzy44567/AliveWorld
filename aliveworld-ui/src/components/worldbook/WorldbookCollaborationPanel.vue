<script setup>
import { computed, ref, watch } from 'vue';
import { worldbookCollaboration } from '../../api/worldbookCollaborationApi';
import { gameStore } from '../../store/gameStore';
import { assetStore } from '../../store/assetStore';
import { pendingConflictIds, selectedConflictIds, MAX_CONFLICT_BATCH } from '../../utils/worldbookConflictSelection';

const data = ref(null);
const error = ref('');
const busy = ref(false);
const expanded = ref(false);
const selected = ref([]);
const pendingOnly = ref(false);
let requestVersion = 0;
const records = computed(() => data.value?.conflicts || []);
const selectedIds = computed(() => selectedConflictIds(records.value, selected.value));
const visibleRecords = computed(() => [...records.value].reverse().filter(item => !pendingOnly.value || (item.current && item.status === 'pending')));
const pending = computed(() => data.value?.conflicts.filter(item => item.current && item.status === 'pending').length || 0);
const status = item => !item.current ? '来源已变化 · 不再生效' : ({ disabled: '本局已停用', restored: '已恢复 / 不再自动停用', pending: '待你处理' }[item.status]);
async function refresh() {
  if (busy.value) return;
  const id = gameStore.sessionId;
  const version = ++requestVersion;
  if (!id) { data.value = null; return; }
  try {
    const next = await worldbookCollaboration(id);
    if (id === gameStore.sessionId && version === requestVersion) { data.value = next; error.value = ''; selected.value = []; }
  } catch (e) { if (id === gameStore.sessionId && version === requestVersion) error.value = e.message; }
}
async function update(change) {
  const id = gameStore.sessionId;
  const version = ++requestVersion;
  busy.value = true;
  try {
    const next = await worldbookCollaboration(id, { expected_revision: data.value.revision, ...change });
    if (id === gameStore.sessionId && version === requestVersion) { data.value = next; error.value = ''; selected.value = []; }
  } catch (e) { if (id === gameStore.sessionId && version === requestVersion) error.value = e.message; }
  finally { if (version === requestVersion) busy.value = false; }
}
function decideSelected(decision) {
  if (selectedIds.value.length) update({ decisions: selectedIds.value.map(conflict_id => ({ conflict_id, decision })) });
}
watch(() => gameStore.sessionId, () => {
  ++requestVersion; busy.value = false; data.value = null; error.value = ''; selected.value = []; pendingOnly.value = false; expanded.value = false;
});
watch(() => [gameStore.sessionId, gameStore.chatLog.length, assetStore.worlds.local], refresh, { immediate: true });
</script>

<template>
  <section v-if="gameStore.sessionId" class="mb-3 rounded-xl border border-slate-700 bg-slate-900/70 p-3 text-xs" aria-label="世界书协作">
    <div class="flex items-center justify-between gap-2">
      <h3 class="font-semibold text-slate-200">世界书协作</h3>
      <button class="text-slate-400 hover:text-cyan-300" @click="refresh">刷新</button>
    </div>
    <p v-if="error" role="alert" class="mt-2 text-rose-300">{{ error }}</p>
    <template v-if="data">
      <p class="my-2 leading-5 text-slate-400">主书决定世界规则，其他书补充知识。仅影响当前故事。</p>
      <p v-if="!data.primary_book && data.books.length > 1" class="mb-2 text-amber-300">请选择一本主书；选择前不会自动停用冲突条目。</p>
      <div class="flex flex-wrap gap-2">
        <button v-for="book in data.books" :key="book.id" :disabled="busy || !book.active" :aria-pressed="data.primary_book === book.id"
          :aria-label="`${book.name} ${!book.active ? '已封存' : data.primary_book === book.id ? '主书' : '设为主书'}`"
          class="max-w-full rounded-lg border px-2 py-1.5 text-left disabled:opacity-40"
          :class="data.primary_book === book.id ? 'border-cyan-600 bg-cyan-950 text-cyan-200' : 'border-slate-600 text-slate-300 hover:border-cyan-700'"
          @click="update({ primary_book: book.id })">
          <span class="break-words">{{ book.name }}</span><span class="ml-1 text-[10px]">{{ !book.active ? '已封存' : data.primary_book === book.id ? '主书' : '设为主书' }}</span>
        </button>
      </div>
      <details class="mt-3 text-slate-400">
        <summary class="cursor-pointer">冲突处理设置</summary>
        <label class="mt-2 flex items-start gap-2"><input type="checkbox" :checked="data.auto_disable" :disabled="busy" @change="update({ auto_disable: $event.target.checked })" />自动停用有依据的次书冲突条目</label>
        <label class="mt-2 flex items-start gap-2"><input type="checkbox" :checked="data.review" :disabled="busy" @change="update({ review: $event.target.checked })" />新冲突先由我逐条确认</label>
        <p class="mt-2 leading-5">关闭自动处理只影响新判断；已有停用请在下方恢复。不会额外调用模型检查。</p>
      </details>
      <button v-if="data.conflicts.length" class="mt-3 text-cyan-300" :aria-expanded="expanded" @click="expanded = !expanded">{{ expanded ? '收起' : '查看' }}冲突记录 · {{ data.conflicts.length }} 条<span v-if="pending">（{{ pending }} 条待处理）</span></button>
      <div v-if="expanded" class="mt-2 space-y-3">
        <p class="text-slate-400">以下是模型判断，可能有误。详情可能涉及世界设定。</p>
        <div class="flex flex-wrap items-center gap-3 text-cyan-300">
          <label class="flex items-center gap-1 text-slate-300"><input type="checkbox" v-model="pendingOnly" :disabled="busy" />仅看待审</label>
          <button :disabled="busy || !pending" @click="selected = pendingConflictIds(records)">{{ pending > MAX_CONFLICT_BATCH ? '选前100条待审' : '全选待审' }}（{{ Math.min(pending, MAX_CONFLICT_BATCH) }}）</button>
          <button :disabled="busy || !selected.length" @click="selected = []">清空选择</button>
        </div>
        <div class="max-h-[55vh] space-y-3 overflow-y-auto pr-1">
        <p v-if="!visibleRecords.length" class="text-slate-500">没有待审冲突。</p>
        <article v-for="item in visibleRecords" :key="item.id" class="rounded-lg border border-slate-700 p-2">
          <label v-if="item.current" class="mb-2 flex items-center gap-2 text-slate-400"><input type="checkbox" v-model="selected" :value="item.id" :aria-label="`选择冲突 ${item.disable_label}`" :disabled="busy || (!selected.includes(item.id) && selectedIds.length >= MAX_CONFLICT_BATCH)" />选择此条</label>
          <p class="text-slate-200">{{ item.disable_label }}</p>
          <p class="mt-1 text-cyan-300">{{ status(item) }}</p>
          <p class="mt-2 text-slate-400">保留：{{ item.keep_label }} · 回合记录 #{{ item.turn_id }}</p>
          <p class="mt-1 whitespace-pre-wrap text-slate-300">{{ item.reason }}（{{ item.scope }}）</p>
          <details class="mt-2 text-slate-400"><summary class="cursor-pointer">查看双方依据</summary><p class="mt-1 whitespace-pre-wrap">主书：{{ item.keep_quote }}</p><p class="mt-1 whitespace-pre-wrap">次书：{{ item.disable_quote }}</p></details>
          <div v-if="item.current" class="mt-2 flex gap-3">
            <button v-if="item.status !== 'disabled'" :disabled="busy" class="text-amber-300" @click="update({ conflict_id: item.id, decision: 'disable' })">停用此条</button>
            <button v-if="item.status !== 'restored'" :disabled="busy" class="text-cyan-300" @click="update({ conflict_id: item.id, decision: 'restore' })">{{ item.status === 'pending' ? '保留此条' : '恢复此条' }}</button>
          </div>
        </article>
        <div class="sticky bottom-0 flex flex-wrap items-center gap-2 rounded-lg border border-slate-600 bg-slate-950 p-2 text-xs shadow-lg" data-testid="worldbook-conflict-batch">
          <span class="text-slate-300">已选 {{ selectedIds.length }} 条</span>
          <button :disabled="busy || !selectedIds.length" class="rounded border border-amber-800 px-2 py-1 text-amber-300 disabled:opacity-30" @click="decideSelected('disable')">停用选中</button>
          <button :disabled="busy || !selectedIds.length" class="rounded border border-cyan-800 px-2 py-1 text-cyan-300 disabled:opacity-30" @click="decideSelected('restore')">保留/恢复选中</button>
        </div>
        </div>
      </div>
    </template>
  </section>
</template>
