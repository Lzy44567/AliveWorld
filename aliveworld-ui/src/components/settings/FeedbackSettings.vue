<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref, toRefs, watch } from 'vue';
import { feedbackApi } from '../../api/feedbackApi';
import { createFeedbackOperation, feedbackFingerprint } from '../../utils/feedbackOperation';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';

const categories = [
  ['bug', '功能错误'], ['ui', '界面与交互'], ['model', '模型与网络'],
  ['image', '生图'], ['suggestion', '内容建议'], ['other', '其他'],
];
const form = reactive({ category: 'bug', title: '', actual: '', expected: '', steps: '', trace_id: '', selected_log_ids: [] });
const context = ref({ environment: {}, recent_events: [] });
const state = reactive({ preview: null, busy: false, message: '', error: '', issueUrl: '' });
const { preview, busy, message, error, issueUrl } = toRefs(state);
let disposed = false;

const canPreview = computed(() => form.title.trim() || form.actual.trim() || form.expected.trim());
const operations = createFeedbackOperation({
  state, getForm: () => form, api: feedbackApi,
  clipboard: markdown => navigator.clipboard.writeText(markdown),
  openWindow: url => window.open(url, '_blank', 'noopener,noreferrer'),
  download: result => {
    const url = URL.createObjectURL(result.blob);
    try {
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = result.filename; anchor.click();
    } finally { URL.revokeObjectURL(url); }
  },
});
watch(() => feedbackFingerprint(form), operations.invalidate, { flush: 'sync' });
onBeforeUnmount(() => { disposed = true; operations.dispose(); });

onMounted(async () => {
  try { const result = await feedbackApi.context(); if (!disposed) context.value = result; }
  catch { if (!disposed) error.value = '暂时无法读取诊断摘要。'; }
});

const refreshPreview = () => operations.run('preview');
const copySummary = () => operations.run('copy');
const exportPackage = () => operations.run('export');
const openIssue = () => operations.run('issue');
</script>

<template>
  <section class="space-y-4" data-testid="feedback-settings">
    <header>
      <h3 class="text-lg font-bold text-violet-300">💬 反馈与诊断 · 已实装</h3>
      <p class="mt-1 text-sm text-slate-400">仅在本机整理，需手动发送给开发者；不会自动提交。打开预填 Issue 后也需要你手动提交。</p>
    </header>

    <div class="grid gap-3 sm:grid-cols-2">
      <label class="text-sm text-slate-300">反馈分类
        <select v-model="form.category" class="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2">
          <option v-for="item in categories" :key="item[0]" :value="item[0]">{{ item[1] }}</option>
        </select>
      </label>
      <label class="text-sm text-slate-300">相关 Trace ID（可选）
        <input v-model="form.trace_id" class="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2" placeholder="可从日志复制" />
      </label>
    </div>
    <label class="block text-sm text-slate-300">标题
      <input v-model="form.title" data-testid="feedback-title" class="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2" placeholder="一句话说明问题" />
    </label>
    <div class="grid gap-3 sm:grid-cols-2">
      <label class="text-sm text-slate-300">实际发生了什么
        <ExpandableTextarea v-model="form.actual" label="实际发生了什么" rows="4" textarea-class="mt-1 resize-y rounded-lg border border-slate-600 bg-slate-950 px-3 py-2" />
      </label>
      <label class="text-sm text-slate-300">你期望看到什么
        <ExpandableTextarea v-model="form.expected" label="你期望看到什么" rows="4" textarea-class="mt-1 resize-y rounded-lg border border-slate-600 bg-slate-950 px-3 py-2" />
      </label>
    </div>
    <label class="block text-sm text-slate-300">复现步骤（可选）
      <ExpandableTextarea v-model="form.steps" label="反馈：复现步骤" rows="3" textarea-class="mt-1 resize-y rounded-lg border border-slate-600 bg-slate-950 px-3 py-2" />
    </label>

    <details v-if="context.recent_events?.length" class="rounded-xl border border-slate-700 bg-slate-900/40 p-3">
      <summary class="cursor-pointer text-sm font-bold text-slate-200">选择要附带的日志（默认不附带）</summary>
      <p class="mt-2 text-xs text-amber-300">日志可能包含故事正文；只有你勾选的条目才进入诊断包。</p>
      <label v-for="event in context.recent_events" :key="event.id" class="mt-2 flex gap-2 rounded-lg border border-slate-800 p-2 text-xs text-slate-300">
        <input v-model="form.selected_log_ids" type="checkbox" :value="event.id" />
        <span><b>{{ event.category_label }}</b> · {{ event.time }} · {{ event.summary }} <code v-if="event.trace_id">{{ event.trace_id }}</code></span>
      </label>
    </details>

    <p v-if="error" class="rounded-lg border border-rose-700 bg-rose-950/30 p-3 text-sm text-rose-200">{{ error }}</p>
    <p v-if="message" class="rounded-lg border border-emerald-700 bg-emerald-950/25 p-3 text-sm text-emerald-200">{{ message }}</p>
    <a v-if="issueUrl" :href="issueUrl" target="_blank" rel="noopener noreferrer" class="block text-sm text-cyan-300 underline">继续打开预填 Issue</a>
    <div class="flex flex-wrap gap-2">
      <button data-testid="feedback-preview" :disabled="busy || !canPreview" class="rounded-lg bg-violet-700 px-3 py-2 text-sm font-bold disabled:opacity-40" @click="refreshPreview">{{ busy ? '处理中…' : '生成安全预览' }}</button>
      <button :disabled="busy || !canPreview" class="rounded-lg border border-cyan-700 px-3 py-2 text-sm text-cyan-300 disabled:opacity-40" @click="copySummary">复制摘要</button>
      <button :disabled="busy || !canPreview" class="rounded-lg border border-emerald-700 px-3 py-2 text-sm text-emerald-300 disabled:opacity-40" @click="exportPackage">导出诊断包</button>
      <button :disabled="busy || !canPreview" class="rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-300 disabled:opacity-40" @click="openIssue">打开 GitHub Issue</button>
    </div>

    <pre v-if="preview" data-testid="feedback-preview-content" class="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl border border-slate-700 bg-slate-950 p-3 text-xs leading-5 text-slate-300 custom-scrollbar">{{ preview.markdown }}</pre>
  </section>
</template>
