<script setup>
import { ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { gameStore } from '../../store/gameStore';
import { gameApi } from '../../api/gameApi';

const searchSaveKeyword = ref("");

// [真实接通] 读档请求
const loadSave = async (saveName) => {
  gameStore.isProcessing = true;
  try {
    const data = await gameApi.loadGame(saveName);
    gameStore.sessionId = data.session_id;
    gameStore.chatLog = data.chat_messages || [];
    gameStore.syncState(data.state);
    
    // 如果之前配了特定的文风和世界书，这里恢复它们
    assetStore.selectedStyle = data.style_name || "默认 (无)";
    assetStore.selectedWorldbook = data.worldbook_name || "无界域 (暂不加载)";
  } catch (err) {
    alert("读取时间线失败！");
  } finally {
    gameStore.isProcessing = false;
  }
};
</script>

<template>
  <div class="flex flex-col h-full animate-[fadeIn_0.2s]">
    <div class="flex gap-2 mb-4 shrink-0">
      <div class="flex-1 relative">
        <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-xs">🔍</span>
        <input v-model="searchSaveKeyword" class="w-full bg-slate-800 border border-slate-600 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 outline-none focus:border-indigo-500" placeholder="搜索记忆切片..." />
      </div>
      <button class="w-8 h-8 bg-slate-800 border border-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-amber-400 transition" title="收藏">⭐</button>
      <button class="px-3 h-8 bg-emerald-600/20 text-emerald-400 border border-emerald-700/50 rounded-lg hover:bg-emerald-600 hover:text-white transition text-xs font-bold whitespace-nowrap" @click="uiStore.modals.newGame = true">+ 新局</button>
    </div>
    
    <div class="flex justify-between items-center text-xs text-slate-500 mb-2 px-1"><span>记忆档案</span><span>共 {{assetStore.saves.length}} 份</span></div>
    
    <div class="space-y-3 pb-8">
      <div v-for="save in assetStore.saves" :key="save.id" class="bg-aw_panel border border-slate-700 rounded-xl p-3 hover:border-indigo-500 transition cursor-pointer group shadow">
        <div class="flex justify-between items-start mb-2">
          <h4 class="text-sm font-bold text-slate-200 group-hover:text-indigo-400">{{ save.name }}</h4>
          <span class="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded border border-slate-700">{{ save.type }}</span>
        </div>
        <p class="text-xs text-slate-500 mb-3 line-clamp-1">{{ save.desc }}</p>
        <div class="flex gap-2">
          <button @click="loadSave(save.name)" class="flex-1 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white text-[10px] py-1.5 rounded font-bold transition">▶ 唤醒</button>
          <button class="px-3 bg-rose-900/30 hover:bg-rose-600 text-rose-400 hover:text-white rounded transition text-xs border border-rose-900/50">🗑</button>
        </div>
      </div>
    </div>
  </div>
</template>