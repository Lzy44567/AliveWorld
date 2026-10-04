<script setup>
defineProps({ report: { type: Object, default: null } });
</script>
<template>
  <details v-if="report" data-testid="character-world-report" class="mt-3 text-xs text-slate-400">
    <summary class="cursor-pointer">本次请求的世界书匹配计划</summary>
    <p class="mt-2">常驻规则 {{ report.resident_count }} 条；普通条目计划发送 {{ report.entries.filter(item=>item.planned).length }} 条。</p>
    <p v-if="report.omitted_by_limit || report.omitted_by_budget" class="mt-2 text-amber-300">条数上限省略 {{ report.omitted_by_limit }} 条；上下文预算省略 {{ report.omitted_by_budget }} 条。</p>
    <p v-if="!report.entries.length" class="mt-2">没有命中普通条目。</p>
    <ul class="mt-2 space-y-2"><li v-for="(item,index) in report.entries" :key="index" class="rounded bg-slate-950 p-2 select-text break-words">
      {{ item.entry_name || '未命名条目' }} · {{ item.source==='current'?'本次输入':`近第${item.turn_distance}回合聊天` }} · {{ item.planned?'计划发送':'预算省略' }}
    </li></ul>
    <p class="mt-2 text-slate-500">仅展示本次请求的上下文计划，不代表请求已成功，也不是角色记忆；重载后不保留。</p>
  </details>
</template>
