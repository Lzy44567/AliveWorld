<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { feedbackApi } from '../../api/feedbackApi';

const categories = [
  ['bug', '功能错误'], ['ui', '界面与交互'], ['model', '模型与网络'],
  ['image', '生图'], ['suggestion', '内容建议'], ['other', '其他'],
];
const form = reactive({ category: 'bug', title: '', actual: '', expected: '', steps: '', trace_id: '', selected_log_ids: [] });
const context = ref({ environment: {}, recent_events: [] });
const preview = ref(null);
const busy = ref(false);
const message = ref('');
const error = ref('');

const canPreview = computed(() => form.title.trim() || form.actual.trim() || form.expected.trim());
const payload = () => ({ ...form, selected_log_ids: [...form.selected_log_ids] });

onMounted(async () => {
  try { context.value = await feedbackApi.context(); } catch (reason) { error.value = reason?.message || '暂时无法读取诊断摘要。'; }
});

async function refreshPreview() {
  busy.value = true; error.value = ''; message.value = '';
  try { preview.value = await feedbackApi.preview(payload()); }
  catch (reason) { error.value = reason?.message || '反馈预览失败。'; }
  finally { busy.value = false; }
}

async function copySummary() {
  if (!preview.value) await refreshPreview();
  if (!preview.value) return;
  await navigator.clipboard.writeText(preview.value.markdown);
  message.value = '反馈摘要已复制，可粘贴到 QQ、Discord 或 Issue。';
}

async function exportPackage() {
  busy.value = true; error.value = ''; message.value = '';
  try {
    const result = await feedbackApi.exportPackage(payload());
    const url = URL.createObjectURL(result.blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = result.filename; anchor.click();
    URL.revokeObjectURL(url);
    message.value = '诊断包已导出；发送前仍请检查是否包含你主动选择的私人日志。';
  } catch (reason) { error.value = reason?.message || '诊断包导出失败。'; }
  finally { busy.value = false; }
}

async function openIssue() {
  if (!preview.value) await refreshPreview();
  if (!preview.value || preview.value.blocked_by_secret_scan) {
    error.value = '内容疑似仍含密钥，不能直接打开 Issue。'; return;
  }
  const url = new URL('https://github.com/Lzy44567/AliveWorld/issues/new');
  url.searchParams.set('title', form.title || 'AliveWorld 玩家反馈');
  url.searchParams.set('body', preview.value.markdown);
  window.open(url.toString(), '_blank', 'noopener,noreferrer');
}
</script>

<template>
  <section class="space-y-4" data-testid="feedback-settings">
    <header>
      <h3 class="text-lg font-bold text-violet-300">💬 反馈与诊断</h3>
      <p class="mt-1 text-sm text-slate-400">不会自动上传任何内容。先在本机预览，再由你决定复制、导出或打开 Issue。</p>
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
        <textarea v-model="form.actual" rows="4" class="mt-1 w-full resize-y rounded-lg border border-slate-600 bg-slate-950 px-3 py-2"></textarea>
      </label>
      <label class="text-sm text-slate-300">你期望看到什么
        <textarea v-model="form.expected" rows="4" class="mt-1 w-full resize-y rounded-lg border border-slate-600 bg-slate-950 px-3 py-2"></textarea>
      </label>
    </div>
    <label class="block text-sm text-slate-300">复现步骤（可选）
      <textarea v-model="form.steps" rows="3" class="mt-1 w-full resize-y rounded-lg border border-slate-600 bg-slate-950 px-3 py-2"></textarea>
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
    <div class="flex flex-wrap gap-2">
      <button data-testid="feedback-preview" :disabled="busy || !canPreview" class="rounded-lg bg-violet-700 px-3 py-2 text-sm font-bold disabled:opacity-40" @click="refreshPreview">{{ busy ? '处理中…' : '生成安全预览' }}</button>
      <button :disabled="busy || !canPreview" class="rounded-lg border border-cyan-700 px-3 py-2 text-sm text-cyan-300 disabled:opacity-40" @click="copySummary">复制摘要</button>
      <button :disabled="busy || !canPreview" class="rounded-lg border border-emerald-700 px-3 py-2 text-sm text-emerald-300 disabled:opacity-40" @click="exportPackage">导出诊断包</button>
      <button :disabled="busy || !canPreview" class="rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-300 disabled:opacity-40" @click="openIssue">打开 GitHub Issue</button>
    </div>

    <pre v-if="preview" data-testid="feedback-preview-content" class="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl border border-slate-700 bg-slate-950 p-3 text-xs leading-5 text-slate-300 custom-scrollbar">{{ preview.markdown }}</pre>
  </section>
</template>
