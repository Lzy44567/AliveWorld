<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetApi } from '../../api/assetApi';
import LogEntryCard from '../log-viewer/LogEntryCard.vue';

const logs = ref([]);
const loading = ref(false);
const activeCategory = ref('');
const activeTrace = ref('');
const query = ref('');
let pollTimer = null;

const categories = [
  ['', '全部'], ['story', '正文'], ['future', '未来'], ['undercurrent', '暗流'],
  ['worldbook', '世界书'], ['workshop', '工坊'], ['memory', '记忆'],
  ['preference', '偏好'], ['image', '生图'], ['system', '系统'],
];
const visibleLogs = computed(() => {
  const needle = query.value.trim().toLowerCase();
  if (!needle) return logs.value;
  return logs.value.filter(item => `${item.task} ${item.summary} ${item.trace_id}`.toLowerCase().includes(needle));
});

const fetchLogs = async ({ quiet = false } = {}) => {
  if (!quiet) loading.value = true;
  try {
    const res = await assetApi.getSystemLogs({ category:activeCategory.value, traceId:activeTrace.value, limit:800 });
    logs.value = res.logs || [];
  } catch (err) { console.error('无法拉取后端日志', err); }
  finally { loading.value = false; }
};
const selectTrace = traceId => { activeTrace.value = traceId || ''; };
watch([activeCategory, activeTrace], () => fetchLogs());
onMounted(() => {
  fetchLogs();
  pollTimer = window.setInterval(() => fetchLogs({ quiet:true }), 2500);
});
onUnmounted(() => { if (pollTimer) window.clearInterval(pollTimer); });
</script>

<template>
  <div class="fixed inset-0 z-[70] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
    <section class="flex h-[78vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-600 bg-slate-950 shadow-2xl" role="dialog" aria-modal="true" aria-label="运行日志">
      <header class="border-b border-slate-700 bg-slate-900 p-4">
        <div class="flex items-start justify-between gap-3">
          <div><h2 class="flex items-center gap-2 text-base font-bold text-slate-200"><span>💻</span> 运行日志</h2><p class="mt-1 text-[11px] text-slate-500">默认只显示安全摘要；展开后可核对实际请求与响应。日志只保存在本机。</p></div>
          <button @click="uiStore.modals.terminal=false" class="rounded-lg px-2 py-1 text-slate-500 hover:bg-slate-800 hover:text-white">✕</button>
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-2">
          <button v-for="item in categories" :key="item[0]" @click="activeCategory=item[0]" class="rounded-full border px-3 py-1 text-[11px] transition" :class="activeCategory===item[0]?'border-cyan-500 bg-cyan-950/60 text-cyan-200':'border-slate-700 text-slate-400 hover:border-slate-500'">{{ item[1] }}</button>
        </div>
        <div class="mt-3 flex gap-2">
          <input v-model="query" class="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200 outline-none focus:border-cyan-600" placeholder="搜索来源、摘要或 trace ID…" />
          <button v-if="activeTrace" @click="activeTrace=''" class="rounded-lg border border-indigo-700 bg-indigo-950/40 px-3 text-[11px] text-indigo-200">退出关联追踪 {{ activeTrace }}</button>
          <button @click="fetchLogs()" :disabled="loading" class="rounded-lg bg-slate-700 px-3 text-xs font-bold text-slate-200 disabled:opacity-50">{{ loading?'刷新中…':'刷新' }}</button>
        </div>
      </header>

      <div id="terminal-log-container" class="custom-scrollbar flex-1 overflow-y-auto p-4">
        <div v-if="!visibleLogs.length" class="grid h-full place-items-center text-sm text-slate-600">当前筛选条件下没有日志</div>
        <div v-else class="space-y-2">
          <LogEntryCard v-for="log in visibleLogs" :key="log.id" :entry="log" :trace-active="activeTrace===log.trace_id" @select-trace="selectTrace" />
        </div>
      </div>
    </section>
  </div>
</template>
