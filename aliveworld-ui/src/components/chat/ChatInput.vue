<!-- src/components/chat/ChatInput.vue -->
<script setup>
import { watch } from 'vue';
import { gameStore } from '../../store/gameStore';
import { configStore, effectiveStorySettings } from '../../store/configStore';
import { gameApi } from '../../api/gameApi';
import { assetStore } from '../../store/assetStore';
import { uiStore } from '../../store/uiStore';
import { preferenceApi } from '../../api/preferenceApi';
import { preferenceStore } from '../../store/preferenceStore';
import { parsePreferenceMeta } from '../../utils/preferenceMeta';

watch(() => effectiveStorySettings.value.aiSuggestions, (enabled) => {
  if (!enabled) gameStore.setActionSuggestions([]);
});

const submitAction = async (text = null) => {
  const rawInput = text || gameStore.draftInput.trim();
  if (!rawInput || !gameStore.sessionId || gameStore.isProcessing) return;
  const sessionId = gameStore.sessionId;
  const initiatingContext = gameStore.contextFor(sessionId);
  const plotCompass = configStore.story.plotCompass;
  const { action: finalAction, declarations } = parsePreferenceMeta(rawInput);
  if (!finalAction && !declarations.length) return;

  for (const declaration of declarations) {
    try {
      await preferenceApi.declare(declaration, sessionId);
    } catch (error) {
      uiStore.showToast(error.message, 'error');
    }
  }
  if (declarations.length) {
    preferenceStore.refresh().catch(() => {});
    uiStore.showToast(finalAction ? '偏好已记录，继续执行本回合行动' : '偏好已记录，不消耗故事回合');
  }
  initiatingContext.draftInput = "";
  if (!finalAction) return;
  
  const context = gameStore.beginTask(sessionId, 'turn');
  if (!context) return;
  context.pendingAction = finalAction;
  context.lastAction = finalAction;
  
  try {
    const res = await (gameStore.streamingEnabled ? gameApi.processActionStream : gameApi.processAction)(sessionId, {
      action: finalAction,
      plot_compass: plotCompass
    }, text => { context.preview += text; });
    
    const newMsgs = res.chat_messages;
    gameStore.finishTask(sessionId, target => {
      target.chatLog.push(...newMsgs);
      gameStore.syncState(res.state, sessionId);
      gameStore.setActionSuggestions(res.action_suggestions, sessionId);
    });
  } catch (err) {
    context.draftInput = context.draftInput || finalAction;
    gameStore.failTask(sessionId, err);
  } finally {
    context.pendingAction = '';
    if (context.isProcessing) gameStore.failTask(sessionId, '请求未正常完成');
    if (gameStore.sessionId === sessionId) assetStore.fetchLocalAssets(sessionId);
    preferenceStore.refresh().catch(() => {});
  }
};

const undoTurn = async () => {
  if (!gameStore.sessionId || gameStore.isProcessing) return;
  const sessionId = gameStore.sessionId;
  if (!gameStore.beginTask(sessionId, 'undo')) return;
  try {
    const res = await gameApi.undoTurn(sessionId);
    gameStore.finishTask(sessionId, context => {
      context.chatLog = res.chat_messages;
      gameStore.syncState(res.state, sessionId);
      gameStore.setActionSuggestions(res.action_suggestions, sessionId);
    });
  } catch (err) {
    gameStore.failTask(sessionId, err);
  } finally {
    if (gameStore.sessionId === sessionId) assetStore.fetchLocalAssets(sessionId);
  }
};

const retryTurn = async () => {
  if (!gameStore.sessionId || gameStore.isProcessing || !gameStore.lastAction) return;
  const sessionId = gameStore.sessionId;
  const lastAction = gameStore.lastAction;
  const context = gameStore.beginTask(sessionId, 'retry');
  if (!context) return;
  try {
    const res = await (gameStore.streamingEnabled ? gameApi.retryTurnStream : gameApi.retryTurn)(sessionId, {
      action: lastAction,
      plot_compass: configStore.story.plotCompass
    }, text => { context.preview += text; });
    gameStore.finishTask(sessionId, context => {
      context.chatLog = res.full_chat;
      gameStore.syncState(res.state, sessionId);
      gameStore.setActionSuggestions(res.action_suggestions, sessionId);
    });
  } catch (err) {
    gameStore.failTask(sessionId, err);
    uiStore.showToast(err.message || '重试失败', 'error');
  } finally {
    if (gameStore.sessionId === sessionId) assetStore.fetchLocalAssets(sessionId);
  }
};

const insertPreference = () => {
  gameStore.draftInput = gameStore.draftInput.trim()
    ? `${gameStore.draftInput.trim()} [[偏好：]]`
    : '/偏好 ';
};
</script>

<template>
  <div class="w-full p-4 md:p-6 bg-aw_bg border-t border-slate-700 z-20 shrink-0 shadow-[0_-10px_30px_rgba(0,0,0,0.5)]">
    <div class="max-w-4xl mx-auto flex flex-col gap-2">
      <label class="self-end text-[10px] text-slate-500"><input data-testid="story-stream-toggle" v-model="gameStore.streamingEnabled" type="checkbox" :disabled="gameStore.isProcessing" /> 流式输出</label>
      
      <div class="grid grid-cols-1 gap-2 px-1 mb-1 md:grid-cols-2" v-if="effectiveStorySettings.aiSuggestions && !gameStore.isProcessing && gameStore.sessionId && gameStore.aiSuggestions.length > 0">
        <button v-for="(sug, idx) in gameStore.aiSuggestions" :key="`${idx}-${sug}`" @click="submitAction(sug)" class="flex min-w-0 items-start gap-2 rounded-xl border border-slate-600 bg-slate-800/80 px-3 py-2 text-left text-xs font-bold leading-relaxed text-slate-300 shadow-lg backdrop-blur transition hover:border-emerald-500 hover:bg-emerald-600/80 hover:text-white" :title="`点击直接执行选项 ${String.fromCharCode(65 + idx)}`">
          <span class="shrink-0 rounded bg-indigo-900/80 px-1.5 py-0.5 text-indigo-200">{{ String.fromCharCode(65 + idx) }}</span><span>{{ sug }}</span>
        </button>
      </div>

      <div class="relative flex gap-3 drop-shadow-2xl">
        <input data-testid="story-action-input" v-model="gameStore.draftInput" @keyup.enter="submitAction()" :disabled="!gameStore.sessionId" class="flex-1 bg-slate-900 border border-slate-600 rounded-xl px-5 py-4 outline-none focus:border-indigo-500 text-slate-100 placeholder-slate-500 shadow-inner text-base" placeholder="描述你的行动，或输入 A / 1 并补充要求..." />

        <button @click="insertPreference" :disabled="!gameStore.sessionId || gameStore.isProcessing" class="px-3 py-2 rounded-xl border border-fuchsia-800/70 bg-fuchsia-950/40 text-xs text-fuchsia-200 hover:bg-fuchsia-900/50 disabled:opacity-40" title="插入玩家偏好说明；这部分不会成为角色台词">🪞 偏好</button>
        
        <div class="flex flex-col gap-1 justify-center">
           <button data-testid="story-undo" @click="undoTurn" :disabled="gameStore.isProcessing" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded text-[10px] border border-slate-700 transition disabled:opacity-50" title="撤回">⏪</button>
           <button data-testid="story-retry" @click="retryTurn" :disabled="gameStore.isProcessing" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded text-[10px] border border-slate-700 transition disabled:opacity-50" title="重试">🔄</button>
        </div>
        
        <button data-testid="story-action-submit" @click="submitAction()" :disabled="gameStore.isProcessing || !gameStore.sessionId" class="px-8 py-4 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-bold disabled:opacity-50 transition shadow-lg text-lg">发送</button>
      </div>
    </div>
  </div>
</template>
