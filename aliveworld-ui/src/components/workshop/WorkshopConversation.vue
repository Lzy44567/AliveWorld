<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import GenerationRetryStatus from '../common/GenerationRetryStatus.vue';
import { workshopStore } from '../../store/workshopStore';
import CopyTextButton from '../common/CopyTextButton.vue';
import WorkshopReviewList from './WorkshopReviewList.vue';
import WorkshopSettingsDialog from './WorkshopSettingsDialog.vue';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';
import { useBottomAnchoredScroll } from '../../composables/useBottomAnchoredScroll';
defineProps({ focused: Boolean });
defineEmits(['toggle-focus']);

const settingsOpen = ref(false);
const focusEntry = computed(() => workshopStore.draft?.entries?.find(e => e.id === workshopStore.context.focusEntryId));
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
  <main data-testid="workshop-main" class="flex min-h-0 min-w-0 flex-1 flex-col bg-slate-950/55">
    <template v-if="workshopStore.workshopId">
      <header class="border-b border-slate-800 bg-slate-950/75 px-3 py-2 shrink-0">
        <button class="float-right ml-3 rounded px-2 py-1 text-xs text-slate-400 hover:bg-slate-800 hover:text-cyan-200" data-testid="workshop-focus-toggle" :aria-pressed="focused" :title="focused ? '退出专注阅读（Esc）' : '收起两侧栏与说明，展开对话区域'" @click="$emit('toggle-focus')">{{ focused ? '退出专注' : '专注阅读' }}</button>
        <div class="flex items-center justify-between gap-2">
          <div class="min-w-0"><div class="flex items-center gap-2"><h2 class="truncate text-sm font-bold text-cyan-200">{{ workshopStore.typeInfo.icon }} {{ workshopStore.typeInfo.label }}工坊<span v-if="workshopStore.assetName"> · {{ workshopStore.assetName }}</span></h2><span v-if="workshopStore.dirty" class="text-[10px] text-amber-400">草稿已自动保存</span></div></div>
          <div class="flex gap-2"><button v-if="workshopStore.published" data-testid="workshop-new-round" class="rounded bg-cyan-700 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-30" :disabled="workshopStore.busy" @click="workshopStore.startNewRound">继续编辑</button><template v-else><button class="rounded bg-slate-800 px-3 py-1.5 text-xs text-slate-300" @click="workshopStore.undo">撤销</button><button data-testid="workshop-publish" class="rounded bg-emerald-700 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-30" :disabled="workshopStore.busy || !workshopStore.dirty" @click="workshopStore.publish">发布草稿</button></template></div>
        </div>
      </header>
      <WorkshopSettingsDialog :open="settingsOpen" @close="settingsOpen=false" />
      <button v-if="workshopStore.context.focusEntryId" class="shrink-0 truncate px-3 py-1 text-left text-xs text-violet-300" @click="settingsOpen=true">定向重写：{{ focusEntry?.name || '目标已移除' }} · 仅生成待审修改</button>

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
        <div v-if="workshopStore.context.preview" data-testid="workshop-stream-preview" class="max-w-[84%] select-text rounded-xl bg-slate-800 p-3"><div class="mb-2 text-[10px] text-amber-400">{{ workshopStore.context.busy ? '生成中 / 未保存' : '未完成残稿 · 可选择复制，未修改资产；重试前请保存需要的文字' }}</div><div class="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{{ workshopStore.context.preview }}</div></div>
        <div v-else-if="workshopStore.activity==='chat'" class="w-fit rounded-xl bg-slate-800 p-3 text-sm text-slate-400">{{ waitingText }}</div>
        <p v-if="workshopStore.context.task.status==='failed'" class="text-xs text-rose-300">{{ workshopStore.context.task.error }}</p>
        <div v-if="workshopStore.context.failedMessage" class="ml-auto max-w-[84%] rounded-xl border border-slate-700 p-3 text-sm text-slate-300 select-text" data-testid="workshop-failed-input">
          <div class="flex items-center justify-between text-xs text-slate-400"><span>未完成 · 未保存</span><button title="编辑这条请求" aria-label="编辑未完成请求" @click="workshopStore.editFailedMessage">✎</button></div>
          <p class="mt-2 whitespace-pre-wrap">{{ workshopStore.context.failedMessage }}</p>
        </div>
        <WorkshopReviewList v-for="source in ['proposed', 'pending']" :key="source" :source="source" :operations="workshopStore[source]" :workshop-id="workshopStore.workshopId" :busy="workshopStore.busy || workshopStore.published" @review="(list, ids, accept) => workshopStore.reviewSelection(list, ids, accept)" />
        <div v-if="workshopStore.suggestions.length" class="mb-2 flex flex-wrap gap-1"><button v-for="item in workshopStore.suggestions" :key="item" class="rounded-full border border-cyan-800 px-2 py-1 text-[10px] text-cyan-300" @click="workshopStore.input=item">{{ item }}</button></div>
      </section>

      <footer class="border-t border-slate-800 bg-slate-950/80 px-3 py-2 shrink-0">
        <div class="mb-2 flex flex-wrap items-center justify-between gap-2"><button data-testid="workshop-settings-toggle" class="rounded px-2 py-1 text-xs text-cyan-300 hover:bg-slate-800" @click="settingsOpen=true">创作设置 · {{ workshopStore.activeMode.label }}</button><div class="flex rounded-lg border border-slate-700 bg-slate-900 p-0.5 text-[10px]"><button class="rounded px-2 py-1" :class="!workshopStore.commitChanges?'bg-cyan-800 text-white':'text-slate-500'" @click="workshopStore.commitChanges=false">先讨论方案</button><button class="rounded px-2 py-1" :class="workshopStore.commitChanges?'bg-emerald-800 text-white':'text-slate-500'" @click="workshopStore.commitChanges=true">允许 AI 修改草稿</button></div></div>
        <div class="flex gap-2"><ExpandableTextarea v-model="workshopStore.input" label="工坊消息" wrapper-class="min-w-0 flex-1" textarea-class="h-16 rounded-lg border border-slate-700 bg-slate-900 p-3 text-sm text-slate-200" :placeholder="`${workshopStore.activeMode.description} Ctrl+Enter 发送`" @keydown.ctrl.enter.prevent="workshopStore.send()" /><button v-if="workshopStore.context.activity === 'chat'" data-testid="workshop-stop" aria-label="停止生成" title="停止生成" class="w-16 shrink-0 rounded-lg bg-slate-700 text-white disabled:opacity-40" :disabled="workshopStore.context.stopping" @click="workshopStore.stop">{{ workshopStore.context.stopping ? '正在停止' : '■ 停止' }}</button><button v-else class="w-20 rounded-lg bg-cyan-700 text-sm font-bold text-white disabled:opacity-40" :disabled="workshopStore.busy" @click="workshopStore.send()">{{ workshopStore.busy?'处理中':'发送' }}</button></div>
      </footer>
    </template>
    <div v-else class="flex flex-1 items-center justify-center p-8 text-center"><div><div class="text-5xl">🧰</div><h2 class="mt-4 text-lg font-bold text-cyan-200">选择一个创作对象</h2><p class="mt-2 max-w-md text-xs leading-relaxed text-slate-500">从右侧选择世界书、角色、文风或实体；偏好卡可以直接进入。工坊会复用当前主界面，但不会载入或推进故事。</p></div></div>
  </main>
</template>
