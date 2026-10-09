<script setup>
const props = defineProps({ selected: Array, eligible: Array, store: Object });
const emit = defineEmits(['select', 'apply']);
function apply(enabled) {
  if (enabled && !window.confirm(`仅为已勾选的 ${props.selected.length} 个现有会话开启并恢复主动联系。会额外调用模型、产生费用；全部会话共享每日次数上限。新会话不会自动开启。确定？`)) return;
  emit('apply', enabled);
}
const reason = code => ({ REVISION_CONFLICT: '对话已变化，请重新勾选后重试', SCHEMA_READ_ONLY: '旧格式或只读，不会自动升级', SESSION_NOT_FOUND: '会话不存在', SESSION_DELETED: '会话已删除' }[code] || '未完成，请刷新核对');
</script>
<template>
  <div data-testid="character-contact-batch" class="space-y-2 text-xs">
    <p class="text-slate-400">仅操作勾选的现有会话，最多100个。新会话默认关闭。</p>
    <div class="flex gap-3"><button data-testid="character-contact-select-all" :disabled="store.contactBatchBusy" @click="emit('select', eligible.slice(0,100).map(s=>s.session_id))">全选当前结果</button><button :disabled="store.contactBatchBusy" @click="emit('select', [])">清空</button></div>
    <div class="flex gap-3"><button data-testid="character-contact-batch-enable" class="text-indigo-200" :disabled="!selected.length || store.contactBatchBusy" @click="apply(true)">开启 {{ selected.length }} 个</button><button data-testid="character-contact-batch-disable" class="text-amber-200" :disabled="!selected.length || store.contactBatchBusy" @click="apply(false)">关闭 {{ selected.length }} 个</button></div>
    <p v-if="store.contactBatchError" class="text-rose-300">{{ store.contactBatchError }}</p>
    <ul data-testid="character-contact-batch-results" class="max-h-24 overflow-y-auto text-slate-400"><li v-for="r in store.contactBatchResults" :key="r.session_id">{{ store.sessions.find(s=>s.session_id===r.session_id)?.title || r.session_id }}：{{ r.ok ? '已保存' : reason(r.code) }}</li></ul>
  </div>
</template>
