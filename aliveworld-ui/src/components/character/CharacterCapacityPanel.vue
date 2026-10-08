<script setup>
defineProps({ report: Object, loading: Boolean, error: String, open: Boolean });
const emit = defineEmits(['toggle', 'refresh']);
</script>
<template>
  <details data-testid="character-capacity-panel" :open="open" class="mt-5 text-sm" @toggle="emit('toggle',$event.target.open)">
    <summary class="cursor-pointer text-indigo-200">容量与保存</summary>
    <div class="mt-3 space-y-3 text-xs text-slate-400 break-words">
      <button data-testid="character-capacity-refresh" class="text-cyan-300 disabled:opacity-40" :disabled="loading" @click="emit('refresh')">{{ loading?'读取中…':'刷新状态' }}</button>
      <p v-if="error" role="status">{{ error }}</p>
      <template v-else-if="report">
        <p data-testid="character-capacity-turns">{{ report.version===2 ? '逻辑消息组' : '正式回合' }}：{{ (report.public_counts.formal_groups || report.public_counts.formal_turns).used }} / {{ (report.public_counts.formal_groups || report.public_counts.formal_turns).limit }}</p>
        <details><summary class="cursor-pointer">技术操作记录</summary><p class="mt-2">请求：{{ report.public_counts.actions.used }} / {{ report.public_counts.actions.limit }}<br>尝试：{{ report.public_counts.attempts.used }} / {{ report.public_counts.attempts.limit }}</p></details>
        <p v-if="report.recording_pressure!=='normal'" class="text-amber-300">内部保存空间{{ report.recording_pressure==='near'?'接近上限':'已达到某项上限' }}；不代表所有聊天操作都被禁止。</p>
        <p v-if="report.operation_capacity.send==='blocked'" class="text-amber-300">当前记录容量已阻止新增发送。</p>
        <p v-if="report.operation_capacity.undo==='blocked'" class="text-amber-300">技术记录已满，撤回、重试和重生成也受限。</p>
      </template>
      <p>未显示阻塞不保证能保存；忙碌、权限、上下文和模型结果仍需校验。</p>
      <p>当前上限：512正式回合、2048账本条目、128活动记忆、32 MiB会话文件。本区不展示私有记忆数量。</p>
      <p>撤回会保留归档并增加操作记录，不等于清理空间。取消重要或高光不删除账本，不释放记忆槽。</p>
      <p>达到上限不会自动删除原文或建立新会话；新会话也不会自动继承此对话的记忆。</p>
    </div>
  </details>
</template>
