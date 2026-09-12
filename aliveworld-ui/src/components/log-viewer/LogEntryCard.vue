<script setup>
import { computed } from 'vue';
import { copyText } from '../../utils/clipboard';
import { downloadJson } from '../../utils/download';

const props = defineProps({ entry:{ type:Object, required:true }, traceActive:{ type:Boolean, default:false }, selected:{ type:Boolean, default:false } });
const emit = defineEmits(['select-trace', 'toggle-selection']);
const phaseText = { request:'请求', response:'响应', event:'事件' };
const statusText = { sent:'已发送', success:'成功', error:'失败', info:'信息', legacy:'旧日志' };
const prettyDetails = computed(() => {
  const value = props.entry.details;
  if (typeof value !== 'string') return JSON.stringify(value, null, 2);
  try { return JSON.stringify(JSON.parse(value), null, 2); }
  catch (_) { return value; }
});
const statusClass = computed(() => props.entry.status === 'error' || props.entry.level === 'error'
  ? 'border-rose-800/70 bg-rose-950/20 text-rose-300'
  : props.entry.status === 'success'
    ? 'border-emerald-900/70 bg-emerald-950/20 text-emerald-300'
    : 'border-slate-700 bg-slate-900/60 text-slate-300');
const serializedEntry = computed(() => JSON.stringify(props.entry, null, 2));
const entryKey = computed(() => props.entry.id || [props.entry.time, props.entry.task, props.entry.phase, props.entry.summary].join(':'));
const copyEntry = async () => { await copyText(serializedEntry.value); };
const exportEntry = () => downloadJson(`AliveWorld-log-${entryKey.value}`, props.entry);
</script>

<template>
  <details data-testid="log-entry" class="group overflow-hidden rounded-xl border select-text" :class="statusClass">
    <summary class="grid cursor-pointer list-none grid-cols-[auto_5.5rem_5.5rem_minmax(0,1fr)_auto] items-center gap-2 px-3 py-2.5 hover:bg-white/[.03]">
      <input type="checkbox" :checked="selected" aria-label="选择这条日志" @click.stop @change="emit('toggle-selection', entryKey)" />
      <span class="font-mono text-[10px] text-slate-500">{{ entry.time }}</span>
      <span class="truncate text-[10px] font-bold">{{ entry.category_label || '系统' }} · {{ phaseText[entry.phase] || entry.phase }}</span>
      <span class="min-w-0"><b class="mr-2 text-xs text-slate-200">{{ entry.task }}</b><span class="text-[11px] text-slate-400">{{ entry.summary }}</span></span>
      <span class="flex items-center gap-2">
        <button type="button" data-testid="copy-log-entry" title="复制完整日志" @click.prevent.stop="copyEntry" class="rounded border border-slate-700 px-2 py-0.5 text-[9px] text-slate-400 hover:text-cyan-200">复制</button>
        <button type="button" data-testid="export-log-entry" title="导出这一条日志" @click.prevent.stop="exportEntry" class="rounded border border-slate-700 px-2 py-0.5 text-[9px] text-slate-400 hover:text-emerald-200">导出</button>
        <button v-if="entry.trace_id" data-testid="trace-log-entry" @click.prevent.stop="$emit('select-trace', entry.trace_id)" class="rounded border px-2 py-0.5 font-mono text-[9px]" :class="traceActive?'border-indigo-400 bg-indigo-900/70 text-indigo-100':'border-slate-700 text-slate-500 hover:text-indigo-300'">{{ entry.trace_id }}</button>
        <span class="rounded bg-black/20 px-2 py-0.5 text-[9px]">{{ statusText[entry.status] || entry.status }}</span>
        <span class="text-[10px] text-slate-500 transition group-open:rotate-180">▼</span>
      </span>
    </summary>
    <div class="border-t border-slate-800 bg-black/30 p-3">
      <div class="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-500"><span>级别：{{ entry.level }}</span><span v-if="entry.story_id">故事：{{ entry.story_id }}</span><span v-if="entry.task_id">任务：{{ entry.task_id }}</span></div>
      <pre class="custom-scrollbar max-h-[45vh] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-black/50 p-3 font-mono text-[11px] leading-relaxed text-slate-300">{{ prettyDetails }}</pre>
    </div>
  </details>
</template>
