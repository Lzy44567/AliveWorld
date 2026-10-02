<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref, toRefs } from 'vue';
import { developerApi } from '../../api/developerApi';
import { promptModes, visiblePrompts, groupPrompts } from '../../utils/promptNavigation';
import { createPromptDraft, promptDraftState } from '../../utils/promptDraft';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';

const configured = ref(false);
const password = ref('');
const confirmation = ref('');
const promptEditor = ref(null);
const state = reactive(promptDraftState());
const { unlocked, coverage, recentRequests, selectedId, mode, variableQuery,
  showAllVariables, activeVariable, busy, error, notice } = toRefs(state);
const controller = createPromptDraft({ state, api: developerApi, confirmDiscard: message => window.confirm(message) });
const selected = computed(controller.selected);
const available = computed(controller.available);
const dirty = computed(controller.dirty);
const draft = computed({ get: () => state.draft, set: controller.setDraft });
const grouped = computed(() => groupPrompts(visiblePrompts(state.slices, mode.value)));
const { select, changeMode, refreshDiagnostics, save, restore, lock, loadPrompts } = controller;
defineExpose({ canLeave: controller.allowLeave });
let disposed = false;
const beforeUnload = event => {
  if (!controller.dirty()) return;
  event.preventDefault(); event.returnValue = '';
};
window.addEventListener('beforeunload', beforeUnload);
onBeforeUnmount(() => { disposed = true; controller.dispose(); window.removeEventListener('beforeunload', beforeUnload); });

const applicableVariables = computed(() => {
  const query = variableQuery.value.trim().toLowerCase();
  return state.variables.filter(item => (showAllVariables.value || !selected.value || item.allowedTasks.includes(selected.value.task))
    && (!query || `${item.id} ${item.label} ${item.description} ${(item.legacyAliases || []).join(' ')}`.toLowerCase().includes(query)));
});

onMounted(async () => {
  busy.value = true;
  try { const result = await developerApi.status(); if (!disposed) configured.value = result.configured; }
  catch (reason) { if (!disposed) error.value = reason.message; }
  try { await loadPrompts(); } catch { /* Initial session unlock is intentionally ephemeral. */ }
  finally { if (!disposed) busy.value = false; }
});

function inspectVariable(item) {
  activeVariable.value = activeVariable.value?.id === item.id ? null : item;
}

function insertVariable(item) {
  if (!controller.canEdit() || !item.allowedTasks.includes(selected.value.task)) return;
  promptEditor.value?.insertText(item.syntax);
}

async function enter() {
  if (busy.value || disposed) return;
  error.value = ''; notice.value = '';
  if (!configured.value && password.value !== confirmation.value) {
    error.value = '两次输入的密码不一致。'; return;
  }
  busy.value = true;
  try {
    if (configured.value) await developerApi.unlock(password.value);
    else { await developerApi.setup(password.value); configured.value = true; }
    if (disposed) return;
    password.value = ''; confirmation.value = '';
    await loadPrompts();
  } catch (reason) { if (!disposed) error.value = reason.message; }
  finally { if (!disposed) busy.value = false; }
}
</script>

<template>
  <section class="space-y-4" data-testid="developer-settings">
    <div>
      <h3 class="text-lg font-bold text-amber-300">🧰 开发者模式</h3>
      <p class="text-sm text-slate-400 mt-1">用于检查真实请求中的提示词切片。密码只防止误操作，不是源码加密或 DRM。</p>
    </div>

    <div v-if="!unlocked" class="rounded-xl border border-slate-700 bg-slate-900/50 p-5 space-y-3">
      <h4 class="font-bold">{{ configured ? '输入开发者密码' : '首次设置开发者密码' }}</h4>
      <input v-model="password" data-testid="developer-password" type="password" autocomplete="current-password" class="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2" placeholder="至少 8 个字符" @keyup.enter="enter" />
      <input v-if="!configured" v-model="confirmation" type="password" class="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2" placeholder="再次输入密码" @keyup.enter="enter" />
      <button class="rounded-lg bg-cyan-700 px-4 py-2 font-bold hover:bg-cyan-600 disabled:opacity-50" :disabled="busy" @click="enter">{{ busy ? '处理中…' : (configured ? '解锁' : '设置并解锁') }}</button>
    </div>

    <template v-if="unlocked || selectedId">
      <div class="flex gap-2" role="tablist" aria-label="提示词模式">
        <button v-for="item in promptModes" :key="item.id" type="button" role="tab" :aria-selected="mode === item.id" :data-testid="`prompt-mode-${item.id}`" :disabled="busy" @click="changeMode(item.id)" class="rounded-lg border px-4 py-2 text-sm disabled:opacity-40" :class="mode === item.id ? 'border-cyan-500 bg-cyan-950/30 text-cyan-200' : 'border-slate-700 text-slate-400'">{{ item.label }}</button>
      </div>
      <details class="rounded-lg border border-slate-700 p-3 text-xs" data-testid="prompt-request-diagnostics">
        <summary class="cursor-pointer">任务覆盖与最近请求预算</summary>
        <p class="my-2 text-slate-400">{{ Object.entries(coverage).map(([task, state]) => `${task}：${state === 'integrated' ? '已接入' : '待迁移'}`).join('；') }}</p>
        <button class="text-cyan-300 disabled:opacity-40" :disabled="busy || !unlocked" @click="refreshDiagnostics">刷新请求记录</button>
        <p v-if="!recentRequests.length" class="mt-2 text-slate-500">本次运行尚无请求记录。token为估算；缓存统计以供应商返回为准。</p>
        <details v-for="request in recentRequests" :key="request.traceId" class="mt-2 border-t border-slate-800 pt-2">
          <summary class="cursor-pointer">{{ request.task }} · {{ request.traceId }} · {{ request.status }} · 输入约{{ request.budget.estimatedInputTokens }}/{{ request.budget.inputLimit }} tokens</summary>
          <p class="my-2 text-slate-400">窗口 {{ request.budget.contextWindow }}（{{ request.budget.windowSource === 'configured' ? '用户配置' : '保守默认' }}）；输出预留 {{ request.budget.outputReserve }}；误差余量 {{ request.budget.margin }}。缓存命中 {{ request.usage.cacheHitTokens ?? '不可得' }}；总耗时 {{ request.elapsedMs ?? '不可得' }} ms。</p>
          <div v-for="source in request.budget.sources" :key="source.id" class="text-slate-500">{{ source.id }}：约 {{ source.estimatedTokens }} tokens</div>
        </details>
      </details>
      <div class="flex justify-between items-center rounded-lg border border-emerald-700/50 bg-emerald-950/20 p-3">
        <span class="text-sm text-emerald-300">{{ unlocked ? '本次运行已解锁；关闭应用后需要重新输入。' : '认证已失效；当前草稿仅保留在内存，可复制。' }}</span>
        <button class="text-sm text-slate-300 hover:text-white disabled:opacity-40" :disabled="busy" @click="lock">立即锁定</button>
      </div>
      <div class="grid grid-cols-[14rem_minmax(0,1fr)] gap-4 min-h-[440px]">
        <div class="rounded-xl border border-slate-700 bg-slate-900/40 p-2 overflow-y-auto max-h-[58vh] custom-scrollbar">
          <div v-for="(items, task) in grouped" :key="task" class="mb-3">
            <div class="px-2 py-1 text-xs uppercase tracking-wide text-slate-500">{{ task }}</div>
            <button v-for="item in items" :key="item.id" :disabled="busy" @click="select(item)"
              class="w-full text-left rounded-lg px-2 py-2 mb-1 border" :data-prompt-slice="item.id"
              :class="selectedId === item.id ? 'border-cyan-500 bg-cyan-950/30' : 'border-transparent hover:bg-slate-800'">
              <div class="text-sm font-semibold">{{ item.title }}</div>
              <div class="text-[11px] mt-1" :class="item.editable ? 'text-slate-400' : 'text-amber-500'">
                {{ item.source === 'override' ? `本地覆盖 v${item.overrideVersion}` : '官方基线' }} · {{ item.editable ? '已接入 · 可编辑' : (item.migrationStatus === 'integrated' ? '已接入 · 只读契约' : '尚未迁移') }}
              </div>
            </button>
          </div>
        </div>
        <div v-if="selected" class="space-y-3 min-w-0">
          <div>
            <div class="flex items-center gap-2"><h4 class="font-bold">{{ selected.title }}</h4><code class="text-xs text-cyan-400">{{ selected.id }}</code></div>
            <p class="text-sm text-slate-400 mt-1">{{ selected.description }}</p>
            <div class="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
              <span>约 {{ selected.estimatedTokens }} tokens</span>
              <span>·</span><span>层级 {{ selected.layer }}</span><span>·</span><span>缓存 {{ selected.cacheClass }}</span>
              <template v-if="selected.variableDetails?.length"><span>· 变量</span><button v-for="item in selected.variableDetails" :key="item.id" type="button" class="rounded border border-slate-700 px-1.5 py-0.5 text-cyan-300 hover:border-cyan-600" :title="item.description" @click="inspectVariable(item)">{{ item.label }} <span aria-hidden="true">?</span></button></template>
              <span v-else>· 无变量</span>
            </div>
          </div>
          <div v-if="!selected.editable" class="rounded-lg border border-amber-700/50 bg-amber-950/20 p-3 text-sm text-amber-200">{{ selected.migrationStatus === 'integrated' ? '该切片已参与真实请求，目前只读。实际分段占用、输入预算和缓存用量可在对应请求日志中查看；未报告的缓存数据标为不可得。' : '该切片仅登记来源，尚未接入安全覆盖。' }}</div>
          <p v-if="!available" class="text-sm text-amber-300">切片已不可用；当前内容保留供复制，不能保存。</p>
          <p v-if="dirty" data-testid="prompt-dirty" class="text-xs text-amber-300">有未保存修改</p>
          <ExpandableTextarea ref="promptEditor" v-model="draft" data-testid="prompt-slice-editor" :disabled="busy" :readonly="!selected.editable || !unlocked || !available" :label="`提示词：${selected.title}`" textarea-class="min-h-[280px] rounded-lg border border-slate-600 bg-slate-950 p-3 font-mono text-xs leading-5 resize-y read-only:opacity-70" />
          <details class="rounded-lg border border-slate-700 bg-slate-900/35 p-3" data-testid="prompt-variable-browser">
            <summary class="cursor-pointer text-sm font-bold text-slate-200">变量表 · {{ applicableVariables.length }} 个{{ showAllVariables ? '已登记' : '适用于当前任务' }}</summary>
            <div class="mt-3 space-y-2">
              <div class="flex items-center gap-3"><input v-model="variableQuery" data-testid="prompt-variable-search" class="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs" placeholder="搜索中文名称、用途或变量 ID" /><label class="flex shrink-0 items-center gap-1.5 text-[10px] text-slate-400"><input v-model="showAllVariables" type="checkbox" />显示全部</label></div>
              <p v-if="!applicableVariables.length" class="text-xs text-slate-500">当前任务没有匹配的变量。</p>
              <div v-for="item in applicableVariables" :key="item.id" class="rounded-lg border border-slate-800 bg-slate-950/65 p-2.5">
                <div class="flex items-start justify-between gap-3"><button type="button" class="min-w-0 text-left" :title="item.description" @click="inspectVariable(item)"><span class="text-xs font-bold text-cyan-200">{{ item.label }}</span><code class="ml-2 text-[10px] text-slate-500">{{ item.syntax }}</code><p class="mt-1 line-clamp-2 text-[10px] leading-4 text-slate-400">{{ item.description }}</p></button><button type="button" class="shrink-0 rounded bg-cyan-900 px-2 py-1 text-[10px] text-cyan-200 disabled:opacity-35" :disabled="busy || !unlocked || !available || !selected.editable || !item.allowedTasks.includes(selected.task)" :title="item.allowedTasks.includes(selected.task) ? `插入 ${item.syntax}` : '此变量不适用于当前提示词任务'" :aria-label="`插入变量：${item.label}`" @click="insertVariable(item)">{{ item.allowedTasks.includes(selected.task) ? '插入' : '不适用' }}</button></div>
                <div v-if="activeVariable?.id === item.id" class="mt-2 grid gap-1 border-t border-slate-800 pt-2 text-[10px] text-slate-500 sm:grid-cols-2"><span>来源：{{ item.owner }}</span><span>类型：{{ item.value_type }}</span><span>空值：{{ item.emptyBehavior }}</span><span>敏感级别：{{ item.sensitivity }}</span><span>缓存级别：{{ item.cacheClass }}</span><span v-if="item.legacyAliases?.length">旧名称：{{ item.legacyAliases.join('、') }}</span></div>
              </div>
            </div>
          </details>
          <details v-if="selected.source === 'override'" class="rounded-lg border border-slate-700 p-3">
            <summary class="cursor-pointer text-sm font-bold">对照官方基线</summary>
            <pre class="mt-3 whitespace-pre-wrap text-xs text-slate-400 max-h-48 overflow-auto select-text">{{ selected.baseline }}</pre>
          </details>
          <div class="flex gap-2">
            <button class="rounded-lg bg-cyan-700 px-4 py-2 font-bold hover:bg-cyan-600 disabled:opacity-50" :disabled="busy || !unlocked || !available || !selected.editable || !dirty" @click="save">保存新覆盖版本</button>
            <button v-if="selected.source === 'override'" class="rounded-lg border border-slate-600 px-4 py-2 hover:bg-slate-800 disabled:opacity-50" :disabled="busy || !unlocked || !available || !selected.editable" @click="restore">恢复官方基线</button>
          </div>
        </div>
        <p v-else data-testid="prompt-mode-empty" class="text-sm text-slate-400">{{ mode === 'character' ? '角色提示词尚未接入，暂无可管理切片' : '当前分类暂无可管理切片' }}</p>
      </div>
    </template>
    <p v-if="error" class="text-sm text-rose-400">{{ error }}</p>
    <p v-if="notice" class="text-sm text-emerald-400">{{ notice }}</p>
  </section>
</template>
