<!-- src/components/chat/ChatBoard.vue -->
<!-- 100% 完整底稿 (请直接覆盖原文件) -->

<script setup>
import { gameStore } from '../../store/gameStore';
import { configStore } from '../../store/configStore';
import { uiStore } from '../../store/uiStore';
import { gameApi } from '../../api/gameApi';
import MessageBubble from './MessageBubble.vue';
import ChatInput from './ChatInput.vue';

// 🚀 问题 8 解决方案：一键要求 AI 进行环境初始化，建立左侧雷达状态
const initWorldState = async () => {
  if (!gameStore.sessionId || gameStore.isProcessing) return;
  gameStore.isProcessing = true;
  try {
    const res = await gameApi.processAction(gameStore.sessionId, {
      action: "【系统指令：世界初始化】请根据当前的宇宙法则与出场人物，观察并建立符合该世界观的动态状态条(dynamic_bars)与人物属性(status_updates)，无需续写剧情，直接建立状态基底即可。",
      plot_compass: configStore.localSettings.plotCompass
    });
    const newMsgs = res.chat_messages.filter(m => m.role !== 'user');
    gameStore.chatLog.push(...newMsgs);
    gameStore.syncState(res.state);
    
    setTimeout(() => {
      const c = document.getElementById('chat-container');
      if (c) c.scrollTop = c.scrollHeight;
    }, 100);
  } catch (err) {
    uiStore.showToast("初始化降临失败", "error");
  } finally {
    gameStore.isProcessing = false;
  }
};
</script>

<template>
  <main class="flex-1 flex flex-col relative z-0 bg-aw_bg overflow-hidden">
    
    <div class="absolute inset-0 z-0 opacity-15 pointer-events-none">
      <img :src="gameStore.currentScene.img" class="w-full h-full object-cover blur-sm">
    </div>
    
    <div class="absolute bottom-0 right-12 z-0 pointer-events-none transition-all duration-700 ease-out" :class="gameStore.isSpeakerActive && gameStore.sessionId ? 'opacity-90 translate-y-0' : 'opacity-0 translate-y-10'">
      <div class="w-[450px] h-[650px] relative">
        <img :src="gameStore.currentSpeakerSprite" class="w-full h-full object-cover rounded-t-full shadow-2xl drop-shadow-[0_0_15px_rgba(0,0,0,0.8)]" style="mask-image: linear-gradient(to top, transparent 10%, black 50%); -webkit-mask-image: linear-gradient(to top, transparent 5%, black 40%);">
      </div>
    </div>

    <div class="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 pb-4 z-10 custom-scrollbar scroll-smooth" id="chat-container">
      
      <div v-if="!gameStore.sessionId" class="h-full flex items-center justify-center flex-col text-center">
         <h2 class="text-4xl font-bold text-slate-300 mb-4 tracking-widest">A L I V E W O R L D</h2>
         <p class="text-slate-500">世界的齿轮尚未转动，请新建或载入档案。</p>
      </div>
      
      <template v-else>
        <MessageBubble v-for="(msg, idx) in gameStore.chatLog" :key="idx" :msg="msg" />
        
        <!-- 🚀 聊天刚建立时显示的初始化按钮 -->
        <div v-if="gameStore.chatLog.length === 1 && !gameStore.isProcessing" class="flex justify-center my-6 animate-pulse">
          <button @click="initWorldState" class="px-6 py-3 bg-indigo-600/80 hover:bg-indigo-500 text-white rounded-full font-bold shadow-lg shadow-indigo-900/50 transition border border-indigo-400/50 flex items-center gap-2 backdrop-blur">
            <span>🌌</span> 让 AI 降临并初始化世界状态
          </button>
        </div>
        
        <div v-if="gameStore.isProcessing" class="text-emerald-400 text-sm font-bold italic animate-pulse">
          🧠 主引擎双轨推演中...
        </div>
      </template>
    </div>

    <ChatInput />
  </main>
</template>