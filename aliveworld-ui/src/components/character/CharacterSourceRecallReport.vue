<script setup>
defineProps({ report:Object, session:Object, disabled:Boolean });
const emit = defineEmits(['source']);
const labels = {sent:'关联旧原文已送入请求',budget:'预算或来源闭包不足，未发送',limit:'超过完整原文上限，未发送'};
</script>
<template>
  <details data-testid="character-source-recall-report" class="mb-3 text-xs text-slate-400">
    <summary class="cursor-pointer">本次原文取材</summary>
    <p class="mt-2">最多4条关联旧消息、共4000字符，保持完整原文；已发送不等于模型一定采用。查看来源不会自动增加模型可见内容。</p>
    <p v-if="!report" class="mt-2">尚无本次原文取材信息</p><p v-else-if="!report.entries.length" class="mt-2">本次没有可说明的公开旧原文召回；近期消息不重复计入。</p>
    <ul v-else class="mt-2 space-y-2"><li v-for="e in report.entries" :key="e.entry_id" class="break-words"><p>{{ session.ledger?.find(item=>item.entry_id===e.entry_id)?.content?.slice(0,60) || '公开记忆（本轮可能已更新）' }}</p><p :class="e.state==='sent'?'text-indigo-300':'text-amber-300'">{{ labels[e.state] }}</p><button v-if="session.ledger?.some(item=>item.entry_id===e.entry_id)" :disabled="disabled" class="mt-1 underline disabled:opacity-40" @click="emit('source',e.entry_id)">查看当前来源</button></li></ul>
  </details>
</template>
