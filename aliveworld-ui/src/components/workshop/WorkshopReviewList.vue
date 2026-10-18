<script setup>
import { ref, watch } from 'vue';
const props = defineProps({ operations: Array, source: String, workshopId: String, busy: Boolean });
const emit = defineEmits(['review']);
const selected = ref([]);
watch(() => [props.workshopId, props.operations], () => { selected.value = []; });
const label = operation => ({ update_fields: '修改资产字段', add_preference: '新增偏好', update_preference: '修改偏好', set_status: '改变偏好状态', delete_preference: '删除偏好', add_entry: '新增条目', update_entry: '修改条目', deactivate_entry: '关闭条目', request_delete: '申请删除', delete_entry: '删除条目', update_overview: '修改概述', set_axioms: '修改公理' })[operation.op] || operation.op;
const fields = { tags: '标签', description: '人物设定', starting_scene: '登场情境', content: '文风规范', role_fields: '角色结构', motive: '动机', status: '状态', mechanisms: '机制', plans: '计划', recent_actions: '近期行动', triggers: '触发条件', relationships: '关系', importance: '重要程度', statement: '偏好内容', category: '分类', polarity: '倾向', sensitive: '敏感内容', id: '编号', preference: '偏好编号' };
const values = { active: '启用', candidate: '候选', rejected: '拒绝', inactive: '停用', prefer: '喜欢', avoid: '避免' };
const format = value => Array.isArray(value) ? value.map(format).join('、')
  : value && typeof value === 'object' ? Object.entries(value).map(([key, item]) => `${fields[key] || key}：${format(item)}`).join('\n')
  : typeof value === 'boolean' ? (value ? '是' : '否') : values[value] || String(value ?? '');
const detail = operation => operation.entry?.content || operation.overview
  || operation.axioms?.join('\n') || format(operation.preference || operation.changes || { preference: operation.preference_id, status: operation.status });
const review = (ids, accept) => emit('review', props.source, ids, accept);
</script>

<template>
  <section v-if="operations.length" class="rounded-xl border border-cyan-800 bg-cyan-950/20 p-3" :data-testid="`workshop-review-${source}`">
    <h3 class="text-xs font-bold text-cyan-200">{{ source === 'pending' ? '高影响修改 · 请仔细确认' : 'AI 拟议修改 · 尚未写入' }}</h3>
    <p class="mt-1 text-[10px] text-slate-400">接受只写入当前工坊草稿，发布后才生效；未选项继续保留。</p>
    <div class="mt-2 flex flex-wrap gap-3 text-xs">
      <button :disabled="busy" @click="selected = operations.map(item => item.operation_id)">全选</button>
      <button :disabled="busy" @click="review(operations.map(item => item.operation_id), true)">接受全部</button>
      <button :disabled="busy" @click="review(operations.map(item => item.operation_id), false)">拒绝全部</button>
    </div>
    <div v-if="selected.length" class="mt-2 flex flex-wrap gap-3 rounded bg-slate-800 p-2 text-xs" data-testid="workshop-review-selection">
      <span>已选 {{ selected.length }} 项</span>
      <button :disabled="busy" @click="review(selected, true)">接受所选</button>
      <button :disabled="busy" @click="review(selected, false)">拒绝所选</button>
      <button :disabled="busy" @click="selected = []">取消选择</button>
    </div>
    <article v-for="operation in operations" :key="operation.operation_id" class="mt-2 rounded-lg bg-black/25 p-3 text-xs text-slate-300">
      <label class="flex items-start gap-2">
        <input v-model="selected" :value="operation.operation_id" type="checkbox" :disabled="busy" :aria-label="`选择${operation.entry?.name || operation.entry_id || label(operation)}`" />
        <span>{{ label(operation) }} · {{ operation.entry?.name || operation.entry_id || '' }}</span>
      </label>
      <p class="mt-2 whitespace-pre-wrap select-text">{{ detail(operation) }}</p>
      <p v-if="operation.reason" class="mt-1 text-slate-400">{{ operation.reason }}</p>
      <div class="mt-2 flex gap-2">
        <button class="rounded bg-emerald-800 px-2 py-1 disabled:opacity-40" :disabled="busy" @click="review([operation.operation_id], true)">接受</button>
        <button class="rounded bg-slate-700 px-2 py-1 disabled:opacity-40" :disabled="busy" @click="review([operation.operation_id], false)">拒绝</button>
      </div>
    </article>
  </section>
</template>
