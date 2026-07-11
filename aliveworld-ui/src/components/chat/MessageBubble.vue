<!-- src/components/chat/MessageBubble.vue -->
<script setup>
import { computed } from 'vue';
import { gameStore } from '../../store/gameStore';
import { effectiveStorySettings } from '../../store/configStore';
import { uiStore } from '../../store/uiStore';
import { gameApi } from '../../api/gameApi';
import { assetStore } from '../../store/assetStore';
import { formatUndercurrentDebug } from '../../utils/entityVisibility';

const props = defineProps({
  msg: {
    type: Object,
    required: true
  }
});

const entityDebugText = computed(() => {
  if (props.msg.role !== 'undercurrent') return '';
  return formatUndercurrentDebug(props.msg.content, effectiveStorySettings.value, assetStore.entities.local);
});

const doReroll = async () => {
  if (!gameStore.sessionId || gameStore.isProcessing) return;
  gameStore.isProcessing = true;
  try {
    const res = await gameApi.rerollTurn(gameStore.sessionId, {
      entities_enabled: effectiveStorySettings.value.entitiesEnabled
    });
    gameStore.chatLog = res.chat_messages;
    gameStore.syncState(res.state);
    
    // 自动滚动到底部
    setTimeout(() => {
      const c = document.getElementById('chat-container');
      if (c) c.scrollTop = c.scrollHeight;
    }, 100);
  } catch (e) {
    uiStore.showToast("命运已成定局，此处无法重掷", "error");
  } finally {
    gameStore.isProcessing = false;
    assetStore.fetchLocalAssets(gameStore.sessionId); // 刷新实体库
  }
};
</script>

<template>
  <div class="flex flex-col" :class="msg.role === 'user' ? 'items-end' : 'items-start'">
    
    <!-- 🎲 命运观测器 (N*n 折叠面板) -->
    <div v-if="msg.role === 'reactions' && effectiveStorySettings.showFutures" class="w-full max-w-[85%] bg-amber-950/60 border border-amber-700/50 rounded-xl overflow-hidden backdrop-blur-md shadow-lg mb-2">
      <details class="group">
        <summary class="cursor-pointer px-4 py-2.5 text-xs text-amber-400 font-bold flex justify-between items-center hover:bg-amber-900/50 transition select-none">
          <span>🎲 观测到 {{ msg.content.length }} 种时间线</span>
          <span class="group-open:rotate-180 transition">▼</span>
        </summary>
        <div class="px-4 py-3 border-t border-amber-900/50 space-y-2">
          <div v-for="r in msg.content" :key="r.id" class="flex items-center gap-3 text-xs text-amber-200 bg-black/40 p-2 rounded hover:bg-black/60 transition">
            <div class="w-10 text-center font-mono font-bold bg-amber-600/40 rounded px-1">{{ r.weight }}%</div>
            <div class="flex-1">{{ r.description }}</div>
          </div>
        </div>
      </details>
    </div>

    <!-- 🎯 命运掷骰裁定结果 -->
    <div v-else-if="msg.role === 'system' && effectiveStorySettings.showDice" class="text-xs text-rose-400 mb-2 px-4 py-2 bg-rose-950/80 border border-rose-700/50 rounded-lg backdrop-blur-md italic shadow-md max-w-[85%] flex justify-between items-center group">
      <span>{{ msg.content }}</span>
      <button v-if="effectiveStorySettings.allowReroll" @click="doReroll" class="hidden group-hover:block px-3 py-1 bg-rose-800 hover:bg-rose-600 text-white rounded text-[10px] font-bold transition ml-4 shadow shrink-0">
        🔄 重掷
      </button>
    </div>

    <!-- 🌌 暗流实体推演结果 -->
    <div v-else-if="entityDebugText" class="text-xs text-purple-400 mb-2 px-4 py-2 bg-purple-950/60 border border-purple-800/50 rounded-lg backdrop-blur-md italic shadow-md max-w-[85%] shadow-purple-900/20">
      <span class="flex items-center gap-2"><span>👾</span> {{ entityDebugText }}</span>
    </div>

    <div v-else-if="msg.role === 'influence' && effectiveStorySettings.showInfluenceBubbles" class="text-xs text-fuchsia-300 mb-2 px-4 py-2 bg-fuchsia-950/50 border border-fuchsia-800/50 rounded-lg max-w-[85%]">
      <div class="font-bold">🕸️ 暗流影响已触发</div>
      <div class="mt-1">{{ msg.content.summary }}</div>
      <div class="mt-1 text-fuchsia-400/80">结果：{{ msg.content.result }}</div>
      <div class="mt-1 font-mono text-[9px] text-slate-500">{{ msg.content.id }}</div>
    </div>

    <!-- 💬 玩家与 AI 对话正文 -->
    <div v-else-if="msg.role === 'user' || msg.role === 'ai'" class="max-w-[85%] rounded-2xl p-5 whitespace-pre-wrap leading-relaxed shadow-2xl text-[15px] backdrop-blur-md" 
         :class="msg.role === 'user' ? 'bg-indigo-600/95 text-white rounded-br-sm' : 'bg-slate-900/90 border border-slate-600 text-slate-200 rounded-bl-sm'">
      {{ gameStore.formatContent(msg.content) }}
    </div>

  </div>
</template>
