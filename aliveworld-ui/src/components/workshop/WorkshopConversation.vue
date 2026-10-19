<script setup>
import { computed, onMounted, watch } from 'vue';
import GenerationRetryStatus from '../common/GenerationRetryStatus.vue';
import { workshopStore } from '../../store/workshopStore';
import CopyTextButton from '../common/CopyTextButton.vue';
import WorkshopReviewList from './WorkshopReviewList.vue';
import WorkshopCreativeBrief from './WorkshopCreativeBrief.vue';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';
import { useBottomAnchoredScroll } from '../../composables/useBottomAnchoredScroll';
defineProps({ focused: Boolean });
defineEmits(['toggle-focus']);

const { container, positioned, updateFollowState, jumpToBottom, prepareAtBottom } = useBottomAnchoredScroll();
onMounted(prepareAtBottom);
watch(() => workshopStore.workshopId, prepareAtBottom, { flush: 'post' });
watch(() => workshopStore.messages.length, () => jumpToBottom(), { flush: 'post' });
watch(() => workshopStore.context.preview, () => jumpToBottom(), { flush: 'post' });
watch(() => workshopStore.context.pendingMessage, () => jumpToBottom(), { flush: 'post' });

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
        <button class="float-right ml-3 rounded px-2 py-1 text-xs text-slate-400 hover:bg-slate-800 hover:text-cyan-200" data-testid="workshop-focus-toggle" :aria-pressed="focused" :title="focused ? '退出专注阅读（Esc）' : '收起两侧栏与说明，展开对话区域'" @click="$emit('toggle-focus')">{{ focused ? '退出专注' : '专注阅读' }}</button>
        <div class="flex items-center justify-between gap-4">
          <div><div class="flex items-center gap-2"><h2 class="font-bold text-cyan-200">{{ workshopStore.typeInfo.icon }} {{ workshopStore.typeInfo.label }}工坊<span v-if="workshopStore.assetName"> · {{ workshopStore.assetName }}</span></h2><span v-if="workshopStore.dirty" class="text-[10px] text-amber-400">草稿已自动保存</span></div><p class="mt-1 text-[10px] text-slate-500">不推进故事时间；发布前不会改变正式资产</p></div>
          <div class="flex gap-2"><button v-if="workshopStore.published" data-testid="workshop-new-round" class="rounded bg-cyan-700 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-30" :disabled="workshopStore.busy" @click="workshopStore.startNewRound">继续编辑</button><template v-else><button class="rounded bg-slate-800 px-3 py-1.5 text-xs text-slate-300" @click="workshopStore.undo">撤销</button><button data-testid="workshop-publish" class="rounded bg-emerald-700 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-30" :disabled="workshopStore.busy || !workshopStore.dirty" @click="workshopStore.publish">发布草稿</button></template></div>
        </div>
        <div v-show="!focused" class="mt-3 flex flex-wrap gap-2"><button v-for="item in workshopStore.modes" :key="item.id" class="rounded px-3 py-1 text-[10px]" :class="workshopStore.mode===item.id?'bg-cyan-800 text-white':'bg-slate-900 text-slate-500'" :title="item.description" @click="workshopStore.mode=item.id">{{ item.label }}</button></div>
        <p v-show="!focused" class="mt-2 text-[10px] leading-relaxed text-cyan-300/70">{{ workshopStore.activeMode.description }}</p>
        <WorkshopCreativeBrief v-show="!focused" />
      </header>

      <section ref="container" class="min-h-0 flex-1 space-y-3 overflow-y-auto p-5 custom-scrollbar" :class="positioned?'opacity-100':'opacity-0'" data-testid="workshop-conversation" @scroll.passive="updateFollowState">
        <section v-if="workshopStore.history.length" data-testid="workshop-history" class="space-y-2 rounded-xl border border-slate-700 bg-slate-950/55 p-3">
          <div><h3 class="text-xs font-bold text-slate-300">已发布的讨论记录 · {{ workshopStore.history.length }} 轮</h3><p class="mt-1 text-[10px] text-slate-500">历史只读；新的修改会进入独立草稿。</p></div>
          <details v-for="(record, historyIndex) in workshopStore.history" :key="record.workshop_id" :open="historyIndex===0 && !workshopStore.messages.length" class="rounded-lg border border-slate-800 bg-black/20">
            <summary class="cursor-pointer px-3 py-2 text-[10px] text-slate-400">第 {{ workshopStore.history.length-historyIndex }} 轮 · {{ historyTime(record.published_at) }} · {{ record.messages.length }} 条消息</summary>
            <div class="space-y-2 border-t border-slate-800 p-3"><div v-for="(message,index) in record.messages" :key="index" class="w-fit max-w-[90%] whitespace-pre-wrap rounded-lg p-2 text-xs leading-relaxed select-text" :class="message.role==='user'?'ml-auto bg-cyan-950 text-cyan-100':'bg-slate-800 text-slate-300'">{{ message.content }}</div></div>
          </details>
        </section>
        <div v-if="workshopStore.published" class="rounded-xl border border-emerald-800/60 bg-emerald-950/25 p-3 text-xs text-emerald-200">已保存发布检查点。直接发送下一条消息即可继续创作；新修改仍需发布才生效，旧讨论保留。</div>
        <GenerationRetryStatus kind="workshop" :identity="workshopStore.workshopId" :request-id="workshopStore.context.generationId" />
        <p v-if="workshopStore.activity==='loading'" class="text-sm text-slate-500">正在载入或恢复工坊草稿……</p>
        <div v-for="(message,index) in workshopStore.messages" :key="index" class="group relative w-fit max-w-[84%] whitespace-pre-wrap rounded-xl p-3 pr-14 text-sm leading-relaxed select-text cursor-text" :class="message.role==='user'?'ml-auto bg-cyan-700 text-white':'bg-slate-800 text-slate-200'">{{ message.content }}<span v-if="message.failed" class="ml-2 text-xs text-rose-200">发送失败</span><CopyTextButton :text="message.content" class="absolute right-2 top-2 opacity-70 group-hover:opacity-100" /></div>
        <div v-if="workshopStore.context.pendingMessage" class="ml-auto w-fit max-w-[84%] whitespace-pre-wrap rounded-xl bg-cyan-700/70 p-3 text-sm text-white">{{ workshopStore.context.pendingMessage }}<span class="block text-[10px] opacity-60">待完成 / 未保存</span></div>
        <div v-if="workshopStore.context.preview" data-testid="workshop-stream-preview" class="max-w-[84%] rounded-xl bg-slate-800 p-3"><div class="mb-2 text-[10px] text-amber-400">生成中 / 未保存</div><div class="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{{ workshopStore.context.preview }}</div></div>
        <div v-else-if="workshopStore.activity==='chat'" class="w-fit rounded-xl bg-slate-800 p-3 text-sm text-slate-400">{{ waitingText }}</div>
        <p v-if="workshopStore.context.task.status==='failed'" class="text-xs text-rose-300">{{ workshopStore.context.task.error }}</p>
        <div v-if="workshopStore.context.failedMessage" class="ml-auto max-w-[84%] rounded-xl border border-slate-700 p-3 text-sm text-slate-300 select-text" data-testid="workshop-failed-input">
          <div class="flex items-center justify-between text-xs text-slate-400"><span>未完成 · 未保存</span><button title="编辑这条请求" aria-label="编辑未完成请求" @click="workshopStore.editFailedMessage">✎</button></div>
          <p class="mt-2 whitespace-pre-wrap">{{ workshopStore.context.failedMessage }}</p>
        </div>
        <WorkshopReviewList v-for="source in ['proposed', 'pending']" :key="source" :source="source" :operations="workshopStore[source]" :workshop-id="workshopStore.workshopId" :busy="workshopStore.busy || workshopStore.published" @review="(list, ids, accept) => workshopStore.reviewSelection(list, ids, accept)" />
      </section>

      <footer class="border-t border-slate-800 bg-slate-950/80 p-3">
        <details class="mb-2 text-[10px] text-slate-400" data-testid="workshop-context-settings">
          <summary class="cursor-pointer">创作记忆 · {{ workshopStore.context.useHistory ? '参考已发布讨论' : '仅参考本轮讨论' }}</summary>
          <label class="mt-2 block"><input v-model="workshopStore.context.useHistory" type="checkbox" :disabled="workshopStore.busy" /> 参考同一资产的已发布讨论</label>
          <p class="mt-1">不额外调用模型；历史原文按相关性和长度选取，会增加本次输入token，不保证召回所有细节。重要约束可写入创作目标。刷新后恢复默认设置。</p>
          <p v-if="workshopStore.type === 'preferences'" class="mt-1 text-amber-400">默认关闭。开启后会把旧偏好讨论片段发送给当前模型，其中可能包含敏感内容。</p>
          <p v-if="workshopStore.context.contextInfo" class="mt-1" data-testid="workshop-context-info">上次请求：近期 {{ workshopStore.context.contextInfo.recent_count }} 条，历史节选 {{ workshopStore.context.contextInfo.excerpt_count }} 条；可用原文共 {{ workshopStore.context.contextInfo.available_messages }} 条。</p>
        </details>
        <label class="mb-2 block text-right text-[10px] text-slate-500"><input data-testid="workshop-stream-toggle" v-model="workshopStore.streamingEnabled" type="checkbox" :disabled="workshopStore.busy" /> 流式输出</label>
        <div class="mb-2 flex items-center justify-between gap-3"><div class="flex rounded-lg border border-slate-700 bg-slate-900 p-0.5 text-[10px]"><button class="rounded px-2 py-1" :class="!workshopStore.commitChanges?'bg-cyan-800 text-white':'text-slate-500'" @click="workshopStore.commitChanges=false">先讨论方案</button><button class="rounded px-2 py-1" :class="workshopStore.commitChanges?'bg-emerald-800 text-white':'text-slate-500'" @click="workshopStore.commitChanges=true">允许 AI 修改草稿</button></div><span class="text-[10px] text-slate-500">{{ workshopStore.commitChanges?'低风险修改可进入草稿':'AI 只提出方案' }}</span></div>
        <div v-if="workshopStore.suggestions.length" class="mb-2 flex flex-wrap gap-1"><button v-for="item in workshopStore.suggestions" :key="item" class="rounded-full border border-cyan-800 px-2 py-1 text-[10px] text-cyan-300" @click="workshopStore.input=item">{{ item }}</button></div>
        <div class="flex gap-2"><ExpandableTextarea v-model="workshopStore.input" label="工坊消息" wrapper-class="flex-1" textarea-class="h-20 rounded-lg border border-slate-700 bg-slate-900 p-3 text-sm text-slate-200" :placeholder="`${workshopStore.activeMode.description} Ctrl+Enter 发送`" @keydown.ctrl.enter.prevent="workshopStore.send()" /><button v-if="workshopStore.context.activity === 'chat'" data-testid="workshop-stop" aria-label="停止生成" title="停止生成" class="w-20 rounded-lg bg-slate-700 text-white disabled:opacity-40" :disabled="workshopStore.context.stopping" @click="workshopStore.stop">{{ workshopStore.context.stopping ? '正在停止' : '■ 停止' }}</button><button v-else class="w-20 rounded-lg bg-cyan-700 text-sm font-bold text-white disabled:opacity-40" :disabled="workshopStore.busy" @click="workshopStore.send()">{{ workshopStore.busy?'处理中':'发送' }}</button></div>
      </footer>
    </template>
    <div v-else class="flex flex-1 items-center justify-center p-8 text-center"><div><div class="text-5xl">🧰</div><h2 class="mt-4 text-lg font-bold text-cyan-200">选择一个创作对象</h2><p class="mt-2 max-w-md text-xs leading-relaxed text-slate-500">从右侧选择世界书、角色、文风或实体；偏好卡可以直接进入。工坊会复用当前主界面，但不会载入或推进故事。</p></div></div>
  </main>
</template>
