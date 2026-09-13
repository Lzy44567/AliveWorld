<script setup>
import { computed, onMounted, ref } from 'vue';
import { developerApi } from '../../api/developerApi';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';

const configured = ref(false);
const unlocked = ref(false);
const password = ref('');
const confirmation = ref('');
const slices = ref([]);
const variables = ref([]);
const selectedId = ref('');
const draft = ref('');
const variableQuery = ref('');
const showAllVariables = ref(false);
const activeVariable = ref(null);
const promptEditor = ref(null);
const busy = ref(false);
const error = ref('');
const notice = ref('');

const selected = computed(() => slices.value.find(item => item.id === selectedId.value) || null);
const grouped = computed(() => Object.groupBy
  ? Object.groupBy(slices.value, item => item.task)
  : slices.value.reduce((out, item) => ((out[item.task] ||= []).push(item), out), {}));
const applicableVariables = computed(() => {
  const query = variableQuery.value.trim().toLowerCase();
  return variables.value.filter(item => (showAllVariables.value || !selected.value || item.allowedTasks.includes(selected.value.task))
    && (!query || `${item.id} ${item.label} ${item.description} ${(item.legacyAliases || []).join(' ')}`.toLowerCase().includes(query)));
});

onMounted(async () => {
  try { configured.value = (await developerApi.status()).configured; }
  catch (reason) { error.value = reason.message; }
  try { await loadPrompts(); } catch { /* Session unlock is intentionally ephemeral. */ }
});

async function loadPrompts() {
  const result = await developerApi.prompts();
  slices.value = result.slices || [];
  variables.value = result.variables || [];
  unlocked.value = true;
  if (!selectedId.value && slices.value.length) select(slices.value[0]);
  else if (selected.value) draft.value = selected.value.active;
}

function select(item) {
  selectedId.value = item.id;
  draft.value = item.active;
  activeVariable.value = null;
  error.value = ''; notice.value = '';
}

function inspectVariable(item) {
  activeVariable.value = activeVariable.value?.id === item.id ? null : item;
}

function insertVariable(item) {
  if (!selected.value?.editable) return;
  promptEditor.value?.insertText(item.syntax);
}

async function enter() {
  error.value = ''; notice.value = '';
  if (!configured.value && password.value !== confirmation.value) {
    error.value = '两次输入的密码不一致。'; return;
  }
  busy.value = true;
  try {
    if (configured.value) await developerApi.unlock(password.value);
    else { await developerApi.setup(password.value); configured.value = true; }
    password.value = ''; confirmation.value = '';
    await loadPrompts();
  } catch (reason) { error.value = reason.message; }
  finally { busy.value = false; }
}

async function save() {
  if (!selected.value?.editable) return;
  busy.value = true; error.value = ''; notice.value = '';
  try {
    await developerApi.savePrompt(selected.value.id, draft.value);
    await loadPrompts(); notice.value = '已保存为新的本地覆盖版本。';
  } catch (reason) { error.value = reason.message; }
  finally { busy.value = false; }
}

async function restore() {
  if (!selected.value || !confirm('恢复官方基线？当前覆盖不会再参与后续请求。')) return;
  busy.value = true; error.value = ''; notice.value = '';
  try {
    await developerApi.restorePrompt(selected.value.id);
    await loadPrompts(); notice.value = '已恢复官方基线。';
  } catch (reason) { error.value = reason.message; }
  finally { busy.value = false; }
}

async function lock() {
  await developerApi.lock(); unlocked.value = false; slices.value = []; selectedId.value = '';
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

    <template v-else>
      <div class="flex justify-between items-center rounded-lg border border-emerald-700/50 bg-emerald-950/20 p-3">
        <span class="text-sm text-emerald-300">本次运行已解锁；关闭应用后需要重新输入。</span>
        <button class="text-sm text-slate-300 hover:text-white" @click="lock">立即锁定</button>
      </div>
      <div class="grid grid-cols-[14rem_minmax(0,1fr)] gap-4 min-h-[440px]">
        <div class="rounded-xl border border-slate-700 bg-slate-900/40 p-2 overflow-y-auto max-h-[58vh] custom-scrollbar">
          <div v-for="(items, task) in grouped" :key="task" class="mb-3">
            <div class="px-2 py-1 text-xs uppercase tracking-wide text-slate-500">{{ task }}</div>
            <button v-for="item in items" :key="item.id" @click="select(item)"
              class="w-full text-left rounded-lg px-2 py-2 mb-1 border" :data-prompt-slice="item.id"
              :class="selectedId === item.id ? 'border-cyan-500 bg-cyan-950/30' : 'border-transparent hover:bg-slate-800'">
              <div class="text-sm font-semibold">{{ item.title }}</div>
              <div class="text-[11px] mt-1" :class="item.editable ? 'text-slate-400' : 'text-amber-500'">
                {{ item.source === 'override' ? `本地覆盖 v${item.overrideVersion}` : '官方基线' }} · {{ item.editable ? '可编辑' : '尚未迁移' }}
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
          <div v-if="!selected.editable" class="rounded-lg border border-amber-700/50 bg-amber-950/20 p-3 text-sm text-amber-200">该切片仅登记来源，尚未接入安全覆盖；编辑不会被伪装成已生效。</div>
          <ExpandableTextarea ref="promptEditor" v-model="draft" data-testid="prompt-slice-editor" :readonly="!selected.editable" :label="`提示词：${selected.title}`" textarea-class="min-h-[280px] rounded-lg border border-slate-600 bg-slate-950 p-3 font-mono text-xs leading-5 resize-y read-only:opacity-70" />
          <details class="rounded-lg border border-slate-700 bg-slate-900/35 p-3" data-testid="prompt-variable-browser">
            <summary class="cursor-pointer text-sm font-bold text-slate-200">变量表 · {{ applicableVariables.length }} 个{{ showAllVariables ? '已登记' : '适用于当前任务' }}</summary>
            <div class="mt-3 space-y-2">
              <div class="flex items-center gap-3"><input v-model="variableQuery" data-testid="prompt-variable-search" class="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs" placeholder="搜索中文名称、用途或变量 ID" /><label class="flex shrink-0 items-center gap-1.5 text-[10px] text-slate-400"><input v-model="showAllVariables" type="checkbox" />显示全部</label></div>
              <p v-if="!applicableVariables.length" class="text-xs text-slate-500">当前任务没有匹配的变量。</p>
              <div v-for="item in applicableVariables" :key="item.id" class="rounded-lg border border-slate-800 bg-slate-950/65 p-2.5">
                <div class="flex items-start justify-between gap-3"><button type="button" class="min-w-0 text-left" :title="item.description" @click="inspectVariable(item)"><span class="text-xs font-bold text-cyan-200">{{ item.label }}</span><code class="ml-2 text-[10px] text-slate-500">{{ item.syntax }}</code><p class="mt-1 line-clamp-2 text-[10px] leading-4 text-slate-400">{{ item.description }}</p></button><button type="button" class="shrink-0 rounded bg-cyan-900 px-2 py-1 text-[10px] text-cyan-200 disabled:opacity-35" :disabled="!selected.editable || !item.allowedTasks.includes(selected.task)" :title="item.allowedTasks.includes(selected.task) ? `插入 ${item.syntax}` : '此变量不适用于当前提示词任务'" :aria-label="`插入变量：${item.label}`" @click="insertVariable(item)">{{ item.allowedTasks.includes(selected.task) ? '插入' : '不适用' }}</button></div>
                <div v-if="activeVariable?.id === item.id" class="mt-2 grid gap-1 border-t border-slate-800 pt-2 text-[10px] text-slate-500 sm:grid-cols-2"><span>来源：{{ item.owner }}</span><span>类型：{{ item.value_type }}</span><span>空值：{{ item.emptyBehavior }}</span><span>敏感级别：{{ item.sensitivity }}</span><span>缓存级别：{{ item.cacheClass }}</span><span v-if="item.legacyAliases?.length">旧名称：{{ item.legacyAliases.join('、') }}</span></div>
              </div>
            </div>
          </details>
          <details v-if="selected.source === 'override'" class="rounded-lg border border-slate-700 p-3">
            <summary class="cursor-pointer text-sm font-bold">对照官方基线</summary>
            <pre class="mt-3 whitespace-pre-wrap text-xs text-slate-400 max-h-48 overflow-auto select-text">{{ selected.baseline }}</pre>
          </details>
          <div class="flex gap-2">
            <button class="rounded-lg bg-cyan-700 px-4 py-2 font-bold hover:bg-cyan-600 disabled:opacity-50" :disabled="busy || !selected.editable || draft === selected.active" @click="save">保存新覆盖版本</button>
            <button v-if="selected.source === 'override'" class="rounded-lg border border-slate-600 px-4 py-2 hover:bg-slate-800 disabled:opacity-50" :disabled="busy" @click="restore">恢复官方基线</button>
          </div>
        </div>
      </div>
    </template>
    <p v-if="error" class="text-sm text-rose-400">{{ error }}</p>
    <p v-if="notice" class="text-sm text-emerald-400">{{ notice }}</p>
  </section>
</template>
