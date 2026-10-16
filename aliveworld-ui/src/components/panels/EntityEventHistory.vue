<script setup>
import { computed } from 'vue';
const props = defineProps({ events: { type: Array, default: () => [] }, total: { type: Number, default: 0 }, source: { type: String, default: '' } });
const labels = { plan: '计划 · 尚未执行', action: '已执行行动', fact: '已发生事实', entity_died: '实体消亡', entity_created: '实体建档' };
const visible = computed(() => props.events.filter(item => !props.source || (item.current_entity_name || item.entity) === props.source).slice().reverse());
</script>

<template>
  <details class="rounded-xl border border-slate-700 bg-slate-900/60 p-3" data-testid="entity-event-history">
    <summary class="cursor-pointer text-sm font-bold text-fuchsia-200">幕后行动记录（{{ visible.length }}）</summary>
    <p class="my-2 text-xs text-slate-400">这是幕后资料，不代表玩家角色知情；计划不等于完成，行动也不保证目标成功。</p>
    <p v-if="total > events.length" class="mb-2 text-xs text-slate-500">仅展示最近 {{ events.length }} 条，完整历史仍保存在故事中。</p>
    <p v-if="!visible.length" class="text-xs text-slate-500">暂无相关记录。</p>
    <article v-for="(item, index) in visible" :key="index" class="mt-2 rounded-lg border border-slate-800 p-3" data-testid="entity-event-row">
      <div class="flex flex-wrap justify-between gap-2 text-xs"><span class="text-fuchsia-300">{{ labels[item.kind] || '历史记录' }} · {{ item.entity || '未命名来源' }}</span><span class="text-slate-500">{{ item.details?.world_time || `记录批次 ${item.tick}` }}</span></div>
      <p class="mt-2 whitespace-pre-wrap text-sm text-slate-200">{{ item.summary }}</p>
      <details class="mt-2 text-xs text-slate-400"><summary class="cursor-pointer">依据与知情范围</summary>
        <p class="mt-2 whitespace-pre-wrap">依据：{{ item.details?.basis || '旧记录未提供依据' }}</p>
        <p class="mt-1">明确知情者：{{ item.details?.known_to?.join('、') || '未记录，不默认玩家角色已知' }}</p>
        <p v-if="item.details?.entity_id" class="mt-1 break-all text-slate-500">来源身份：{{ item.details.entity_id }}</p>
      </details>
    </article>
  </details>
</template>
