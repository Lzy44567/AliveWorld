<!-- src/components/chat/ChatBoard.vue -->
<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { gameStore } from '../../store/gameStore';
import { configStore } from '../../store/configStore';
import { uiStore } from '../../store/uiStore';
import { gameApi } from '../../api/gameApi';
import MessageBubble from './MessageBubble.vue';
import ChatInput from './ChatInput.vue';
import { imageStore } from '../../store/imageStore';
import { useBottomAnchoredScroll } from '../../composables/useBottomAnchoredScroll';

const { container, positioned, updateFollowState, jumpToBottom, prepareAtBottom } = useBottomAnchoredScroll();
const content = ref(null);
let contentObserver = null;

onMounted(async () => {
  await prepareAtBottom();
  await nextTick();
  if (content.value && window.ResizeObserver) {
    contentObserver = new ResizeObserver(() => jumpToBottom());
    contentObserver.observe(content.value);
  }
});
onBeforeUnmount(() => contentObserver?.disconnect());
watch(() => gameStore.sessionId, prepareAtBottom, { flush: 'post' });
watch(() => gameStore.chatLog.length, () => jumpToBottom(), { flush: 'post' });
watch(() => gameStore.currentContext.preview, () => jumpToBottom(), { flush: 'post' });
watch(() => gameStore.currentContext.pendingAction, () => jumpToBottom(), { flush: 'post' });
watch(() => gameStore.sessionId, async (sessionId) => {
  imageStore.reset();
  if (sessionId) await imageStore.load(sessionId).catch(() => {});
}, { immediate: true });

const initWorldState = async () => {
  if (!gameStore.sessionId || gameStore.isProcessing) return;
  const sessionId = gameStore.sessionId;
  const context = gameStore.beginTask(sessionId, 'initialize');
  if (!context) return;
  try {
    const res = await (gameStore.streamingEnabled ? gameApi.processActionStream : gameApi.processAction)(sessionId, {
      action: "【系统指令：世界初始化】请根据宇宙法则建立状态条(dynamic_bars)与人物属性(status_updates)，需包含'当前时间'属性，不要续写剧情。",
      plot_compass: configStore.story.plotCompass
    }, text => { context.preview += text; });
    const newMsgs = res.chat_messages.filter(m => m.role !== 'user');
    gameStore.finishTask(sessionId, context => {
      context.chatLog.push(...newMsgs);
      gameStore.syncState(res.state, sessionId);
      gameStore.setActionSuggestions(res.action_suggestions, sessionId);
    });
  } catch (err) {
    gameStore.failTask(sessionId, err);
    uiStore.showToast(err.message || '初始化失败', 'error');
  }
};
</script>

<template>
  <main class="flex-1 flex flex-col relative z-0 bg-aw_bg overflow-hidden">
    <div class="absolute inset-0 z-0 opacity-15 pointer-events-none"><img :src="gameStore.currentScene.img" class="w-full h-full object-cover blur-sm"></div>
    <div ref="container" class="flex-1 overflow-y-auto p-4 md:p-8 pb-4 z-10 custom-scrollbar" :class="positioned?'opacity-100':'opacity-0'" id="chat-container" @scroll.passive="updateFollowState" @load.capture="jumpToBottom()">
      <div ref="content" class="min-h-full space-y-6">
      <div v-if="!gameStore.sessionId" class="h-full flex items-center justify-center flex-col text-center">
         <h2 class="text-4xl font-bold text-slate-300 mb-4 tracking-widest">A L I V E W O R L D</h2>
         <p class="text-slate-500">世界的齿轮尚未转动，请新建或载入档案。</p>
      </div>
      <template v-else>
        <MessageBubble v-for="(msg, idx) in gameStore.chatLog" :key="msg.id || `legacy-${idx}`" :msg="msg" />
        <div v-if="gameStore.chatLog.length === 1 && Object.keys(gameStore.dynamicBars).length === 0 && !gameStore.isProcessing" class="flex justify-center my-6 animate-pulse">
          <button @click="initWorldState" class="px-6 py-3 bg-indigo-600/80 hover:bg-indigo-500 text-white rounded-full font-bold shadow-lg shadow-indigo-900/50 transition border border-indigo-400/50 backdrop-blur">
            🌌 让 AI 降临并初始化世界状态
          </button>
        </div>
        <div v-if="gameStore.currentContext.pendingAction" class="ml-auto w-fit max-w-[85%] rounded-xl bg-indigo-600/70 p-4 whitespace-pre-wrap">{{ gameStore.currentContext.pendingAction }}<span class="block text-[10px] opacity-60">待完成 / 未保存</span></div>
        <div v-if="gameStore.currentContext.preview" data-testid="story-stream-preview" class="max-w-[85%] rounded-xl border border-slate-600 bg-slate-900/90 p-5"><div class="mb-2 text-[10px] text-amber-400">生成中 / 未保存</div><div class="whitespace-pre-wrap leading-relaxed text-slate-200">{{ gameStore.currentContext.preview }}</div></div>
        <div v-else-if="gameStore.isProcessing" class="text-emerald-400 text-sm font-bold italic animate-pulse">🧠 主引擎双轨推演中...</div>
        <p v-if="gameStore.currentContext.task.status==='failed'" class="text-xs text-rose-300">{{ gameStore.currentContext.task.error }}</p>
      </template>
      </div>
    </div>
    <ChatInput />
  </main>
</template>
