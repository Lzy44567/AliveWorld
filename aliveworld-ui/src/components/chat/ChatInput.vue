<script setup>
import { ref } from 'vue';
import { gameStore } from '../../store/gameStore';
import { configStore } from '../../store/configStore';
import { gameApi } from '../../api/gameApi';
import { assetStore } from '../../store/assetStore';

const userInput = ref("");
const lastAction = ref(""); // 用于重试

// [真实接入] 执行玩家行动
const submitAction = async (text = null) => {
  const finalAction = text || userInput.value.trim();
  if (!finalAction || !gameStore.sessionId || gameStore.isProcessing) return;
  
  // 1. 玩家发言上屏
  gameStore.chatLog.push({ role: "user", content: finalAction });
  lastAction.value = finalAction;
  userInput.value = "";
  gameStore.isProcessing = true;
  scrollToBottom();
  
  // 2. 发送给 Python 后端
  try {
    const res = await gameApi.processAction(gameStore.sessionId, {
      action: finalAction,
      override_style: assetStore.selectedStyle,
      override_worldbook: assetStore.selectedWorldbook
    });
    
    // 3. 将后端返回的新消息(AI结算和命运掷骰)拼接到聊天记录
    const newMsgs = res.chat_messages.filter(m => m.role !== 'user');
    gameStore.chatLog.push(...newMsgs);
    
    // 4. 更新左侧雷达状态(血量、实体等)
    gameStore.syncState(res.state);
  } catch (err) {
    gameStore.chatLog.push({ role: "system", content: "⚠️ 虚空风暴：连接中断或推演失败，已拦截。" });
  } finally {
    gameStore.isProcessing = false;
    scrollToBottom();
  }
};

// [新增] 撤回上一回合
const undoTurn = async () => {
  if (!gameStore.sessionId || gameStore.isProcessing) return;
  gameStore.isProcessing = true;
  try {
    const res = await gameApi.undoTurn(gameStore.sessionId);
    gameStore.chatLog = res.chat_messages;
    gameStore.syncState(res.state);
  } catch (err) {
    alert("无法撤回更早的记忆");
  } finally {
    gameStore.isProcessing = false;
    scrollToBottom();
  }
};

// [新增] 重试上一回合
const retryTurn = async () => {
  if (!gameStore.sessionId || gameStore.isProcessing || !lastAction.value) return;
  gameStore.isProcessing = true;
  try {
    const res = await gameApi.retryTurn(gameStore.sessionId, {
      action: lastAction.value,
      override_style: assetStore.selectedStyle,
      override_worldbook: assetStore.selectedWorldbook
    });
    gameStore.chatLog = res.full_chat;
    gameStore.syncState(res.state);
  } catch (err) {
    alert("重试失败");
  } finally {
    gameStore.isProcessing = false;
    scrollToBottom();
  }
};

const scrollToBottom = () => {
  setTimeout(() => {
    const c = document.getElementById('chat-container');
    if (c) c.scrollTop = c.scrollHeight;
  }, 100);
};
</script>

<template>
  <div class="absolute bottom-0 w-full p-6 bg-gradient-to-t from-aw_bg via-aw_bg/95 to-transparent z-20">
    <div class="max-w-4xl mx-auto flex flex-col gap-2">
      
      <!-- 💡 灵感建议 -->
      <div class="flex gap-2 px-1 mb-1 overflow-x-auto custom-scrollbar" v-if="configStore.settings.aiSuggestions && !gameStore.isProcessing && gameStore.sessionId">
        <button v-for="(sug, idx) in gameStore.aiSuggestions" :key="idx" @click="submitAction(sug)" class="px-4 py-2 text-xs font-bold bg-slate-800/80 hover:bg-emerald-600/80 text-slate-300 hover:text-white border border-slate-600 hover:border-emerald-500 rounded-full transition whitespace-nowrap backdrop-blur shadow-lg">
          💡 {{ sug }}
        </button>
      </div>

      <!-- ⌨️ 输入框组 -->
      <div class="relative flex gap-3 drop-shadow-2xl">
        <input v-model="userInput" @keyup.enter="submitAction()" :disabled="gameStore.isProcessing || !gameStore.sessionId" class="flex-1 bg-slate-900/90 border border-slate-600 rounded-xl px-5 py-4 outline-none focus:border-indigo-500 text-slate-100 placeholder-slate-500 shadow-inner text-base backdrop-blur" placeholder="描述你的行动..." />
        
        <!-- 附加操作 -->
        <div class="flex flex-col gap-1 justify-center">
           <button @click="undoTurn" :disabled="gameStore.isProcessing" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded text-[10px] border border-slate-700 transition disabled:opacity-50" title="撤回">⏪</button>
           <button @click="retryTurn" :disabled="gameStore.isProcessing" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded text-[10px] border border-slate-700 transition disabled:opacity-50" title="重试">🔄</button>
        </div>
        
        <button @click="submitAction()" :disabled="gameStore.isProcessing || !gameStore.sessionId" class="px-8 py-4 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-bold disabled:opacity-50 transition shadow-lg text-lg">发送</button>
      </div>
      
    </div>
  </div>
</template>