<script setup>
import { ref } from 'vue';
import { gameStore } from '../../store/gameStore';
import { configStore } from '../../store/configStore';
import { gameApi } from '../../api/gameApi';
import { assetStore } from '../../store/assetStore';

const userInput = ref("");
const lastAction = ref("");

const submitAction = async (text = null) => {
  const finalAction = text || userInput.value.trim();
  if (!finalAction || !gameStore.sessionId || gameStore.isProcessing) return;
  
  gameStore.chatLog.push({ role: "user", content: finalAction });
  lastAction.value = finalAction;
  userInput.value = "";
  gameStore.isProcessing = true;
  scrollToBottom();
  
  try {
    const res = await gameApi.processAction(gameStore.sessionId, {
      action: finalAction,
      override_style: assetStore.selectedStyle,
      override_worldbook: assetStore.selectedWorldbook
    });
    
    const newMsgs = res.chat_messages.filter(m => m.role !== 'user');
    gameStore.chatLog.push(...newMsgs);
    gameStore.syncState(res.state);
  } catch (err) {
    gameStore.chatLog.push({ role: "system", content: "⚠️ 虚空风暴：推演失败，已被拦截。" });
  } finally {
    gameStore.isProcessing = false;
    scrollToBottom();
  }
};

const undoTurn = async () => { /* 保持不变 */ };
const retryTurn = async () => { /* 保持不变 */ };

// 【修复】改为 nextTick 或延迟以确保 DOM 渲染完再滚动
const scrollToBottom = () => {
  setTimeout(() => {
    const c = document.getElementById('chat-container');
    if (c) c.scrollTop = c.scrollHeight;
  }, 100);
};
</script>

<template>
  <!-- 【修复核心】去掉 absolute，变成 flex 的 bottom block -->
  <div class="w-full p-4 md:p-6 bg-aw_bg border-t border-slate-700 z-20 shrink-0 shadow-[0_-10px_30px_rgba(0,0,0,0.5)]">
    <div class="max-w-4xl mx-auto flex flex-col gap-2">
      
      <!-- 灵感建议 -->
      <div class="flex gap-2 px-1 mb-1 overflow-x-auto custom-scrollbar" v-if="configStore.settings.aiSuggestions && !gameStore.isProcessing && gameStore.sessionId && gameStore.aiSuggestions.length > 0">
        <button v-for="(sug, idx) in gameStore.aiSuggestions" :key="idx" @click="submitAction(sug)" class="px-4 py-2 text-xs font-bold bg-slate-800/80 hover:bg-emerald-600/80 text-slate-300 hover:text-white border border-slate-600 hover:border-emerald-500 rounded-full transition whitespace-nowrap backdrop-blur shadow-lg">
          💡 {{ sug }}
        </button>
      </div>

      <!-- 输入框 -->
      <div class="relative flex gap-3 drop-shadow-2xl">
        <input v-model="userInput" @keyup.enter="submitAction()" :disabled="gameStore.isProcessing || !gameStore.sessionId" class="flex-1 bg-slate-900 border border-slate-600 rounded-xl px-5 py-4 outline-none focus:border-indigo-500 text-slate-100 placeholder-slate-500 shadow-inner text-base" placeholder="描述你的行动..." />
        
        <div class="flex flex-col gap-1 justify-center">
           <button @click="undoTurn" :disabled="gameStore.isProcessing" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded text-[10px] border border-slate-700 transition disabled:opacity-50" title="撤回">⏪</button>
           <button @click="retryTurn" :disabled="gameStore.isProcessing" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded text-[10px] border border-slate-700 transition disabled:opacity-50" title="重试">🔄</button>
        </div>
        
        <button @click="submitAction()" :disabled="gameStore.isProcessing || !gameStore.sessionId" class="px-8 py-4 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-bold disabled:opacity-50 transition shadow-lg text-lg">发送</button>
      </div>
    </div>
  </div>
</template>