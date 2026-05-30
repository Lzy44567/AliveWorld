<script setup>
import { gameStore } from '../../store/gameStore';
import MessageBubble from './MessageBubble.vue';
import ChatInput from './ChatInput.vue';
</script>

<template>
  <main class="flex-1 flex flex-col relative z-0 bg-aw_bg overflow-hidden">
    
    <!-- 🖼️ 场景背景层 -->
    <div class="absolute inset-0 z-0 opacity-15 pointer-events-none">
      <img :src="gameStore.currentScene.img" class="w-full h-full object-cover blur-sm">
    </div>
    
    <!-- 🎭 Galgame 立绘层 -->
    <div class="absolute bottom-0 right-12 z-0 pointer-events-none transition-all duration-700 ease-out" :class="gameStore.isSpeakerActive && gameStore.sessionId ? 'opacity-90 translate-y-0' : 'opacity-0 translate-y-10'">
      <div class="w-[450px] h-[650px] relative">
        <img :src="gameStore.currentSpeakerSprite" class="w-full h-full object-cover rounded-t-full shadow-2xl drop-shadow-[0_0_15px_rgba(0,0,0,0.8)]" style="mask-image: linear-gradient(to top, transparent 10%, black 50%); -webkit-mask-image: linear-gradient(to top, transparent 5%, black 40%);">
      </div>
    </div>

    <!-- 📜 聊天气泡滚动区 -->
    <div class="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 pb-48 z-10 custom-scrollbar" id="chat-container">
      
      <!-- 初始无连接状态 -->
      <div v-if="!gameStore.sessionId" class="h-full flex items-center justify-center flex-col text-center">
         <h2 class="text-4xl font-bold text-slate-300 mb-4 tracking-widest">A L I V E W O R L D</h2>
         <p class="text-slate-500">世界的齿轮尚未转动，请新建或载入档案。</p>
      </div>
      
      <!-- 对话流 -->
      <template v-else>
        <!-- 循环渲染单条气泡组件 -->
        <MessageBubble v-for="(msg, idx) in gameStore.chatLog" :key="idx" :msg="msg" />
        
        <!-- 引擎推演动画 -->
        <div v-if="gameStore.isProcessing" class="text-emerald-400 text-sm font-bold italic animate-pulse">
          🧠 引擎推演中...
        </div>
      </template>
    </div>

    <!-- ⌨️ 底部输入组件 -->
    <ChatInput />

  </main>
</template>