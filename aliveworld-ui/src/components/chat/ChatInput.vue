<!-- src/components/chat/ChatInput.vue -->
<script setup>
import { ref, watch } from 'vue';
import { gameStore } from '../../store/gameStore';
import { configStore, effectiveStorySettings } from '../../store/configStore';
import { gameApi } from '../../api/gameApi';
import { assetStore } from '../../store/assetStore';
import { uiStore } from '../../store/uiStore';
import { preferenceApi } from '../../api/preferenceApi';
import { preferenceStore } from '../../store/preferenceStore';
import { parsePreferenceMeta } from '../../utils/preferenceMeta';

const userInput = ref("");
const lastAction = ref("");
watch(() => effectiveStorySettings.value.aiSuggestions, (enabled) => {
  if (!enabled) gameStore.setActionSuggestions([]);
});

const submitAction = async (text = null) => {
  const rawInput = text || userInput.value.trim();
  if (!rawInput || !gameStore.sessionId || gameStore.isProcessing) return;
  const { action: finalAction, declarations } = parsePreferenceMeta(rawInput);
  if (!finalAction && !declarations.length) return;

  for (const declaration of declarations) {
    try {
      await preferenceApi.declare(declaration, gameStore.sessionId);
    } catch (error) {
      uiStore.showToast(error.message, 'error');
    }
  }
  if (declarations.length) {
    preferenceStore.refresh().catch(() => {});
    uiStore.showToast(finalAction ? '偏好已记录，继续执行本回合行动' : '偏好已记录，不消耗故事回合');
  }
  userInput.value = "";
  if (!finalAction) return;
  
  gameStore.chatLog.push({ role: "user", content: finalAction });
  lastAction.value = finalAction;
  gameStore.isProcessing = true;
  gameStore.setActionSuggestions([]);
  scrollToBottom();
  
  try {
    const res = await gameApi.processAction(gameStore.sessionId, {
      action: finalAction,
      plot_compass: configStore.story.plotCompass
    });
    
    const newMsgs = res.chat_messages.filter(m => m.role !== 'user');
    gameStore.chatLog.push(...newMsgs);
    gameStore.syncState(res.state);
    gameStore.setActionSuggestions(res.action_suggestions);
  } catch (err) {
    gameStore.chatLog.push({ role: "system", content: `⚠️ ${err.message || '推演失败，本回合未保存。'}` });
  } finally {
    gameStore.isProcessing = false;
    assetStore.fetchLocalAssets(gameStore.sessionId);
    preferenceStore.refresh().catch(() => {});
    scrollToBottom();
  }
};

const undoTurn = async () => {
  if (!gameStore.sessionId || gameStore.isProcessing) return;
  gameStore.isProcessing = true;
  try {
    const res = await gameApi.undoTurn(gameStore.sessionId);
    gameStore.chatLog = res.chat_messages;
    gameStore.syncState(res.state);
    gameStore.setActionSuggestions(res.action_suggestions);
  } catch (err) {
    // 撤回失败静默处理
  } finally {
    gameStore.isProcessing = false;
    assetStore.fetchLocalAssets(gameStore.sessionId);
    scrollToBottom();
  }
};

const retryTurn = async () => {
  if (!gameStore.sessionId || gameStore.isProcessing || !lastAction.value) return;
  gameStore.isProcessing = true;
  try {
    const res = await gameApi.retryTurn(gameStore.sessionId, {
      action: lastAction.value,
      plot_compass: configStore.story.plotCompass
    });
    gameStore.chatLog = res.full_chat;
    gameStore.syncState(res.state);
    gameStore.setActionSuggestions(res.action_suggestions);
  } catch (err) {
    alert("重试失败");
  } finally {
    gameStore.isProcessing = false;
    assetStore.fetchLocalAssets(gameStore.sessionId);
    scrollToBottom();
  }
};

const scrollToBottom = () => {
  setTimeout(() => {
    const c = document.getElementById('chat-container');
    if (c) {
      c.scrollTop = c.scrollHeight;
    }
  }, 100);
};

const insertPreference = () => {
  userInput.value = userInput.value.trim()
    ? `${userInput.value.trim()} [[偏好：]]`
    : '/偏好 ';
};
</script>

<template>
  <div class="w-full p-4 md:p-6 bg-aw_bg border-t border-slate-700 z-20 shrink-0 shadow-[0_-10px_30px_rgba(0,0,0,0.5)]">
    <div class="max-w-4xl mx-auto flex flex-col gap-2">
      
      <div class="grid grid-cols-1 gap-2 px-1 mb-1 md:grid-cols-2" v-if="effectiveStorySettings.aiSuggestions && !gameStore.isProcessing && gameStore.sessionId && gameStore.aiSuggestions.length > 0">
        <button v-for="(sug, idx) in gameStore.aiSuggestions" :key="`${idx}-${sug}`" @click="submitAction(sug)" class="flex min-w-0 items-start gap-2 rounded-xl border border-slate-600 bg-slate-800/80 px-3 py-2 text-left text-xs font-bold leading-relaxed text-slate-300 shadow-lg backdrop-blur transition hover:border-emerald-500 hover:bg-emerald-600/80 hover:text-white" :title="`点击直接执行选项 ${String.fromCharCode(65 + idx)}`">
          <span class="shrink-0 rounded bg-indigo-900/80 px-1.5 py-0.5 text-indigo-200">{{ String.fromCharCode(65 + idx) }}</span><span>{{ sug }}</span>
        </button>
      </div>

      <div class="relative flex gap-3 drop-shadow-2xl">
        <input v-model="userInput" @keyup.enter="submitAction()" :disabled="!gameStore.sessionId" class="flex-1 bg-slate-900 border border-slate-600 rounded-xl px-5 py-4 outline-none focus:border-indigo-500 text-slate-100 placeholder-slate-500 shadow-inner text-base" placeholder="描述你的行动，或输入 A / 1 并补充要求..." />

        <button @click="insertPreference" :disabled="!gameStore.sessionId || gameStore.isProcessing" class="px-3 py-2 rounded-xl border border-fuchsia-800/70 bg-fuchsia-950/40 text-xs text-fuchsia-200 hover:bg-fuchsia-900/50 disabled:opacity-40" title="插入玩家偏好说明；这部分不会成为角色台词">🪞 偏好</button>
        
        <div class="flex flex-col gap-1 justify-center">
           <button @click="undoTurn" :disabled="gameStore.isProcessing" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded text-[10px] border border-slate-700 transition disabled:opacity-50" title="撤回">⏪</button>
           <button @click="retryTurn" :disabled="gameStore.isProcessing" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded text-[10px] border border-slate-700 transition disabled:opacity-50" title="重试">🔄</button>
        </div>
        
        <button @click="submitAction()" :disabled="gameStore.isProcessing || !gameStore.sessionId" class="px-8 py-4 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-bold disabled:opacity-50 transition shadow-lg text-lg">发送</button>
      </div>
    </div>
  </div>
</template>
