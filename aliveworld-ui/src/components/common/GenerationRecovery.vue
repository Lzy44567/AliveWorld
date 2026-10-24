<script setup>
import { ref, watch } from 'vue';
import { listRecovery, deleteRecovery } from '../../api/recoveryApi';
import { recoveryGuidance, recoveryExport } from '../../utils/recoveryPresentation';
import CopyTextButton from './CopyTextButton.vue';
import { uiStore } from '../../store/uiStore';
const props = defineProps({ kind: String, identity: String, busy: Boolean });
const emit = defineEmits(['restore']);
const drafts = ref([]), error = ref(''), deleting = ref('');
let revision = 0;
async function refresh() {
  const current = ++revision;
  if (!props.identity) { drafts.value = []; error.value = ''; return; }
  try {
    const result = await listRecovery(props.kind, props.identity);
    if (current === revision) { drafts.value = result; error.value = ''; }
  } catch (failure) { if (current === revision) error.value = failure.message; }
}
watch(() => [props.kind, props.identity], () => { drafts.value = []; refresh(); }, { immediate: true });
watch(() => props.busy, (value, previous) => { if (!value && previous) refresh(); });
async function remove(draft) {
  if (!window.confirm('删除这份未完成残稿？不会改变正式故事或资产。请先导出需要的文字。')) return;
  const kind = props.kind, identity = props.identity;
  deleting.value = draft.id;
  try {
    await deleteRecovery(kind, identity, draft.id);
    if (identity === props.identity && kind === props.kind) await refresh();
  } catch (failure) { uiStore.showToast(failure.message, 'error'); }
  finally { deleting.value = ''; }
}
function download(draft) {
  const url = URL.createObjectURL(new Blob([recoveryExport(draft)], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url; link.download = `AliveWorld-残稿-${draft.id}.txt`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
</script>
<template>
  <details v-if="drafts.length || error" data-testid="generation-recovery" class="rounded-lg border border-amber-900/70 bg-slate-900/80 p-3 text-xs text-slate-300">
    <summary class="cursor-pointer text-amber-300">未完成内容 · {{ drafts.length }} 份本地残稿</summary>
    <p class="mt-3 text-slate-400">独立保留，不进入正式对话、记忆、状态或资产。只恢复原请求，不自动结算残稿；再次发送可能产生费用。</p>
    <p v-if="error" class="mt-2 text-rose-300">{{ error }} <button @click="refresh" class="text-cyan-300">重新读取</button></p>
    <details v-for="draft in drafts" :key="draft.id" data-testid="recovery-item" class="mt-3 border-t border-slate-700 pt-3">
      <summary class="cursor-pointer">{{ new Date(draft.created_at).toLocaleString() }} · {{ draft.text.slice(0, 40) }}</summary>
      <p class="my-3 text-amber-200">{{ recoveryGuidance[draft.reason] || recoveryGuidance.generation_or_save }}</p>
      <p class="mb-2 whitespace-pre-wrap text-slate-400">原请求：{{ draft.request || '本次是重掷等操作，没有独立输入；请在当前界面选择下一步。' }}</p>
      <div class="max-h-96 overflow-auto whitespace-pre-wrap select-text rounded bg-slate-950 p-3 leading-relaxed" data-testid="recovery-text">{{ draft.text }}</div>
      <div class="mt-3 flex flex-wrap items-center gap-3">
        <CopyTextButton :text="draft.text" />
        <button @click="download(draft)" class="text-cyan-300">导出文本</button>
        <button v-if="draft.request" :disabled="busy" @click="emit('restore', draft.request)" class="text-cyan-300 disabled:opacity-40">原请求放回输入框</button>
        <button :disabled="busy || Boolean(deleting)" @click="remove(draft)" class="text-slate-400 disabled:opacity-40">删除残稿</button>
      </div>
    </details>
  </details>
</template>
