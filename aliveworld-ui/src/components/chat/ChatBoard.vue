<!-- src/components/chat/ChatBoard.vue -->
<script setup>
import { onMounted, watch, nextTick } from 'vue';
import { gameStore } from '../../store/gameStore';
import { configStore } from '../../store/configStore';
import { uiStore } from '../../store/uiStore';
import { gameApi } from '../../api/gameApi';
import MessageBubble from './MessageBubble.vue';
import ChatInput from './ChatInput.vue';

// 自动滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    const c = document.getElementById('chat-container');
    if (c) c.scrollTop = c.scrollHeight;
  });
};

onMounted(scrollToBottom);
watch(() => gameStore.chatLog, scrollToBottom, { deep: true });

const initWorldState = async () => {
  if (!gameStore.sessionId || gameStore.isProcessing) return;
  gameStore.isProcessing = true;
  try {
    const res = await gameApi.processAction(gameStore.sessionId, {
      action: "【系统指令：世界初始化】请根据宇宙法则建立状态条(dynamic_bars)与人物属性(status_updates)，需包含'当前时间'属性，不要续写剧情。",
      plot_compass: configStore.story.plotCompass
    });
    const newMsgs = res.chat_messages.filter(m => m.role !== 'user');
    gameStore.chatLog.push(...newMsgs);
    gameStore.syncState(res.state);
  } catch (err) { uiStore.showToast("初始化失败", "error");
  } finally { gameStore.isProcessing = false; }
};
</script>

<template>
  <main class="flex-1 flex flex-col relative z-0 bg-aw_bg overflow-hidden">
    <div class="absolute inset-0 z-0 opacity-15 pointer-events-none"><img :src="gameStore.currentScene.img" class="w-full h-full object-cover blur-sm"></div>
    <div class="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 pb-4 z-10 custom-scrollbar scroll-smooth" id="chat-container">
      <div v-if="!gameStore.sessionId" class="h-full flex items-center justify-center flex-col text-center">
         <h2 class="text-4xl font-bold text-slate-300 mb-4 tracking-widest">A L I V E W O R L D</h2>
         <p class="text-slate-500">世界的齿轮尚未转动，请新建或载入档案。</p>
      </div>
      <template v-else>
        <MessageBubble v-for="(msg, idx) in gameStore.chatLog" :key="msg.id || `legacy-${idx}`" :msg="msg" />
        <div v-if="gameStore.chatLog.length === 1 && !gameStore.isProcessing" class="flex justify-center my-6 animate-pulse">
          <button @click="initWorldState" class="px-6 py-3 bg-indigo-600/80 hover:bg-indigo-500 text-white rounded-full font-bold shadow-lg shadow-indigo-900/50 transition border border-indigo-400/50 backdrop-blur">
            🌌 让 AI 降临并初始化世界状态
          </button>
        </div>
        <div v-if="gameStore.isProcessing" class="text-emerald-400 text-sm font-bold italic animate-pulse">🧠 主引擎双轨推演中...</div>
      </template>
    </div>
    <ChatInput />
  </main>
</template>
