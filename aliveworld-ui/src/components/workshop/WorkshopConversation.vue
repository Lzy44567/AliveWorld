<script setup>
import { computed, onMounted, watch } from 'vue';
import { workshopStore } from '../../store/workshopStore';
import CopyTextButton from '../common/CopyTextButton.vue';
import WorkshopReviewList from './WorkshopReviewList.vue';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';
import { useBottomAnchoredScroll } from '../../composables/useBottomAnchoredScroll';

const { container, positioned, updateFollowState, jumpToBottom, prepareAtBottom } = useBottomAnchoredScroll();
onMounted(prepareAtBottom);
watch(() => workshopStore.workshopId, prepareAtBottom, { flush: 'post' });
watch(() => workshopStore.messages.length, () => jumpToBottom(), { flush: 'post' });
watch(() => workshopStore.context.preview, () => jumpToBottom(), { flush: 'post' });
watch(() => workshopStore.context.pendingMessage, () => jumpToBottom(), { flush: 'post' });

const operationLabel = operation => ({
  add_entry: '新增条目', update_entry: '修改条目', deactivate_entry: '关闭条目',
  request_delete: '申请删除', update_overview: '修改概述', set_axioms: '修改公理',
  add_preference: '新增偏好', update_preference: '修改偏好',
  set_status: '改变偏好状态', delete_preference: '删除偏好',
  update_fields: '修改资产字段',
})[operation.op] || operation.op;
const operationTarget = operation =>
  operation.entry?.name || operation.entry_id || operation.preference?.statement
  || operation.preference_id || Object.keys(operation.changes || {}).join('、') || workshopStore.assetName;
const waitingText = computed(() => ({
  worldbooks: '世界书工坊正在检查设定关系与推导链……',
  characters: '角色工坊正在梳理人物目标、矛盾与表现方式……',
  styles: '文风工坊正在比较叙事规范与执行效果……',
  entities: '实体工坊正在区分动机、机制、计划与行动……',
  preferences: '偏好工坊正在分析证据、替代解释与取舍……',
})[workshopStore.type]);
const historyTime = value => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
};
</script>

<template>
  <main class="flex min-w-0 flex-1 flex-col bg-slate-950/55">
    <template v-if="workshopStore.workshopId">
      <header class="border-b border-slate-800 bg-slate-950/75 px-5 py-3">
        <div class="flex items-center justify-between gap-4">
          <div><div class="flex items-center gap-2"><h2 class="font-bold text-cyan-200">{{ workshopStore.typeInfo.icon }} {{ workshopStore.typeInfo.label }}工坊<span v-if="workshopStore.assetName"> · {{ workshopStore.assetName }}</span></h2><span v-if="workshopStore.dirty" class="text-[10px] text-amber-400">草稿已自动保存</span></div><p class="mt-1 text-[10px] text-slate-500">不推进故事时间；发布前不会改变正式资产</p></div>
          <div class="flex gap-2"><button v-if="workshopStore.published" data-testid="workshop-new-round" class="rounded bg-cyan-700 px-3 py-1.5 text-xs font-bold text-white" @click="workshopStore.startNewRound">开启新一轮</button><template v-else><button class="rounded bg-slate-800 px-3 py-1.5 text-xs text-slate-300" @click="workshopStore.undo">撤销</button><button data-testid="workshop-publish" class="rounded bg-emerald-700 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-30" :disabled="workshopStore.busy || !workshopStore.dirty" @click="workshopStore.publish">发布草稿</button></template></div>
        </div>
        <div class="mt-3 flex flex-wrap gap-2"><button v-for="item in workshopStore.modes" :key="item.id" class="rounded px-3 py-1 text-[10px]" :class="workshopStore.mode===item.id?'bg-cyan-800 text-white':'bg-slate-900 text-slate-500'" :title="item.description" @click="workshopStore.mode=item.id">{{ item.label }}</button></div>
        <p class="mt-2 text-[10px] leading-relaxed text-cyan-300/70">{{ workshopStore.activeMode.description }}</p>
      </header>

      <section ref="container" class="min-h-0 flex-1 space-y-3 overflow-y-auto p-5 custom-scrollbar" :class="positioned?'opacity-100':'opacity-0'" data-testid="workshop-conversation" @scroll.passive="updateFollowState">
        <section v-if="workshopStore.history.length" data-testid="workshop-history" class="space-y-2 rounded-xl border border-slate-700 bg-slate-950/55 p-3">
          <div><h3 class="text-xs font-bold text-slate-300">已发布的讨论记录 · {{ workshopStore.history.length }} 轮</h3><p class="mt-1 text-[10px] text-slate-500">历史只读；新的修改会进入独立草稿。</p></div>
          <details v-for="(record, historyIndex) in workshopStore.history" :key="record.workshop_id" :open="historyIndex===0 && !workshopStore.messages.length" class="rounded-lg border border-slate-800 bg-black/20">
            <summary class="cursor-pointer px-3 py-2 text-[10px] text-slate-400">第 {{ workshopStore.history.length-historyIndex }} 轮 · {{ historyTime(record.published_at) }} · {{ record.messages.length }} 条消息</summary>
            <div class="space-y-2 border-t border-slate-800 p-3"><div v-for="(message,index) in record.messages" :key="index" class="w-fit max-w-[90%] whitespace-pre-wrap rounded-lg p-2 text-xs leading-relaxed select-text" :class="message.role==='user'?'ml-auto bg-cyan-950 text-cyan-100':'bg-slate-800 text-slate-300'">{{ message.content }}</div></div>
          </details>
        </section>
        <div v-if="workshopStore.published" class="rounded-xl border border-emerald-800/60 bg-emerald-950/25 p-3 text-xs text-emerald-200">这一轮已经发布，聊天与修改记录会继续保存在本机。需要继续讨论时，请开启新一轮草稿。</div>
        <p v-if="workshopStore.activity==='loading'" class="text-sm text-slate-500">正在载入或恢复工坊草稿……</p>
        <div v-for="(message,index) in workshopStore.messages" :key="index" class="group relative w-fit max-w-[84%] whitespace-pre-wrap rounded-xl p-3 pr-14 text-sm leading-relaxed select-text cursor-text" :class="message.role==='user'?'ml-auto bg-cyan-700 text-white':'bg-slate-800 text-slate-200'">{{ message.content }}<span v-if="message.failed" class="ml-2 text-xs text-rose-200">发送失败</span><CopyTextButton :text="message.content" class="absolute right-2 top-2 opacity-70 group-hover:opacity-100" /></div>
        <div v-if="workshopStore.context.pendingMessage" class="ml-auto w-fit max-w-[84%] whitespace-pre-wrap rounded-xl bg-cyan-700/70 p-3 text-sm text-white">{{ workshopStore.context.pendingMessage }}<span class="block text-[10px] opacity-60">待完成 / 未保存</span></div>
        <div v-if="workshopStore.context.preview" data-testid="workshop-stream-preview" class="max-w-[84%] rounded-xl bg-slate-800 p-3"><div class="mb-2 text-[10px] text-amber-400">生成中 / 未保存</div><div class="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{{ workshopStore.context.preview }}</div></div>
        <div v-else-if="workshopStore.activity==='chat'" class="w-fit rounded-xl bg-slate-800 p-3 text-sm text-slate-400">{{ waitingText }}</div>
        <p v-if="workshopStore.context.task.status==='failed'" class="text-xs text-rose-300">{{ workshopStore.context.task.error }}</p>
        <template v-if="workshopStore.type === 'worldbooks'">
          <WorkshopReviewList v-for="source in ['proposed', 'pending']" :key="source" :source="source" :operations="workshopStore[source]" :workshop-id="workshopStore.workshopId" :busy="workshopStore.busy" @review="(list, ids, accept) => workshopStore.reviewSelection(list, ids, accept)" />
        </template>
        <section v-if="workshopStore.type !== 'worldbooks' && workshopStore.proposed.length" class="rounded-xl border border-cyan-700/60 bg-cyan-950/25 p-3">
          <div class="flex items-center justify-between"><div><h3 class="text-xs font-bold text-cyan-300">AI 拟议修改 · 尚未写入</h3><p class="mt-1 text-[10px] text-slate-500">先审阅，再写入工坊草稿。</p></div><button class="rounded bg-cyan-700 px-3 py-1.5 text-xs font-bold text-white" @click="workshopStore.submitProposal">提交方案</button></div>
          <div v-for="operation in workshopStore.proposed" :key="operation.operation_id" class="mt-2 rounded-lg bg-black/25 p-2 text-xs text-slate-300">
            <strong class="text-cyan-200">{{ operationLabel(operation) }}</strong> · {{ operationTarget(operation) }}
            <ol v-if="operation.op==='set_axioms'" class="mt-2 list-decimal space-y-1 pl-5 text-slate-300"><li v-for="axiom in operation.axioms" :key="axiom">{{ axiom }}</li></ol>
            <p v-else-if="operation.op==='update_overview'" class="mt-2 whitespace-pre-wrap text-slate-400">{{ operation.overview }}</p>
            <p v-else-if="operation.op==='add_entry'" class="mt-2 whitespace-pre-wrap text-slate-400">{{ operation.entry?.content }}</p>
            <p v-else-if="operation.op==='update_entry'" class="mt-2 whitespace-pre-wrap text-slate-400">{{ operation.changes?.content || '将修改名称、触发词、标签或启用状态；可在左侧草稿中继续审阅。' }}</p>
            <p v-if="operation.reason" class="mt-1 text-slate-500">{{ operation.reason }}</p>
          </div>
        </section>
        <section v-if="workshopStore.type !== 'worldbooks' && workshopStore.pending.length" class="rounded-xl border border-amber-700/60 bg-amber-950/25 p-3">
          <h3 class="text-xs font-bold text-amber-300">需要玩家确认的高影响修改</h3>
          <div v-for="operation in workshopStore.pending" :key="operation.operation_id" class="mt-2 rounded-lg bg-black/25 p-3 text-xs text-slate-300">
            <strong>{{ operationLabel(operation) }}</strong> · {{ operationTarget(operation) }}
            <ol v-if="operation.op==='set_axioms'" class="mt-2 list-decimal space-y-1 pl-5"><li v-for="axiom in operation.axioms" :key="axiom">{{ axiom }}</li></ol>
            <p v-else-if="operation.entry?.content" class="mt-2 whitespace-pre-wrap text-slate-400">{{ operation.entry.content }}</p>
            <p v-else-if="operation.changes?.content" class="mt-2 whitespace-pre-wrap text-slate-400">{{ operation.changes.content }}</p>
            <div class="mt-2 flex gap-2"><button class="rounded bg-emerald-700 px-2 py-1" @click="workshopStore.decide(operation.operation_id,true)">接受</button><button class="rounded bg-slate-700 px-2 py-1" @click="workshopStore.decide(operation.operation_id,false)">拒绝</button></div>
          </div>
        </section>
      </section>

      <footer v-if="!workshopStore.published" class="border-t border-slate-800 bg-slate-950/80 p-3">
        <label class="mb-2 block text-right text-[10px] text-slate-500"><input data-testid="workshop-stream-toggle" v-model="workshopStore.streamingEnabled" type="checkbox" :disabled="workshopStore.busy" /> 流式输出</label>
        <div class="mb-2 flex items-center justify-between gap-3"><div class="flex rounded-lg border border-slate-700 bg-slate-900 p-0.5 text-[10px]"><button class="rounded px-2 py-1" :class="!workshopStore.commitChanges?'bg-cyan-800 text-white':'text-slate-500'" @click="workshopStore.commitChanges=false">先讨论方案</button><button class="rounded px-2 py-1" :class="workshopStore.commitChanges?'bg-emerald-800 text-white':'text-slate-500'" @click="workshopStore.commitChanges=true">允许 AI 修改草稿</button></div><span class="text-[10px] text-slate-500">{{ workshopStore.commitChanges?'低风险修改可进入草稿':'AI 只提出方案' }}</span></div>
        <div v-if="workshopStore.suggestions.length" class="mb-2 flex flex-wrap gap-1"><button v-for="item in workshopStore.suggestions" :key="item" class="rounded-full border border-cyan-800 px-2 py-1 text-[10px] text-cyan-300" @click="workshopStore.input=item">{{ item }}</button></div>
        <div class="flex gap-2"><ExpandableTextarea v-model="workshopStore.input" label="工坊消息" wrapper-class="flex-1" textarea-class="h-20 rounded-lg border border-slate-700 bg-slate-900 p-3 text-sm text-slate-200" :placeholder="`${workshopStore.activeMode.description} Ctrl+Enter 发送`" @keydown.ctrl.enter.prevent="workshopStore.send()" /><button class="w-20 rounded-lg bg-cyan-700 text-sm font-bold text-white disabled:opacity-40" :disabled="workshopStore.busy" @click="workshopStore.send()">{{ workshopStore.busy?'处理中':'发送' }}</button></div>
      </footer>
      <footer v-else class="border-t border-slate-800 bg-slate-950/80 p-3 text-center"><button data-testid="workshop-new-round-footer" class="rounded-lg bg-cyan-700 px-5 py-2 text-sm font-bold text-white" @click="workshopStore.startNewRound">开启新一轮讨论</button></footer>
    </template>
    <div v-else class="flex flex-1 items-center justify-center p-8 text-center"><div><div class="text-5xl">🧰</div><h2 class="mt-4 text-lg font-bold text-cyan-200">选择一个创作对象</h2><p class="mt-2 max-w-md text-xs leading-relaxed text-slate-500">从右侧选择世界书、角色、文风或实体；偏好卡可以直接进入。工坊会复用当前主界面，但不会载入或推进故事。</p></div></div>
  </main>
</template>
