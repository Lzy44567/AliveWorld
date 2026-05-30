<!-- src/components/panels/SavesPanel.vue -->
<!-- 100% 完整底稿 (请直接覆盖原文件) -->

<script setup>
import { ref, computed } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { gameStore } from '../../store/gameStore';
import { gameApi } from '../../api/gameApi';
import { assetApi } from '../../api/assetApi';

const searchSaveKeyword = ref("");
const confirmDeleteId = ref(null);

const filteredSaves = computed(() => {
  if (!searchSaveKeyword.value) return assetStore.saves;
  return assetStore.saves.filter(s => 
    s.name.toLowerCase().includes(searchSaveKeyword.value.toLowerCase())
  );
});

// 读取存档
const loadSave = async (saveName) => {
  gameStore.isProcessing = true;
  try {
    const data = await gameApi.loadGame(saveName);
    gameStore.sessionId = data.session_id;
    gameStore.currentSaveName = saveName;
    gameStore.chatLog = data.chat_messages || [];
    gameStore.syncState(data.state);
    
    // 恢复基础设定显示（尽管 V2 已经弱化了全局强绑定，但用于兜底显示）
    assetStore.selectedStyle = data.style_name || "默认 (无)";
    assetStore.selectedWorldbook = data.worldbook_name || "无界域 (暂不加载)";
    
    // 🚀 核心修复：切换存档后，立即要求资产仓库去拉取该存档真实的沙盒文件夹数据！
    await assetStore.fetchLocalAssets(data.session_id);
    
  } catch (err) {
    alert("读取时间线失败！");
  } finally {
    gameStore.isProcessing = false;
  }
};

// 执行真实删除操作
const executeDelete = async (saveName) => {
  try {
    await assetApi.deleteSave(saveName);
    confirmDeleteId.value = null;
    
    // 如果粉碎的正是当前正在推演的世界，直接物理清屏！
    if (gameStore.currentSaveName === saveName) {
      gameStore.reset();
      assetStore.fetchLocalAssets(null); // 清空局内专属
    }
    
    await assetStore.fetchAssets();
  } catch (err) {
    alert("档案粉碎失败，请检查后端运行状态。");
  }
};
</script>

<template>
  <div class="flex flex-col h-full animate-[fadeIn_0.2s]">
    
    <!-- 顶部工具栏 -->
    <div class="flex gap-2 mb-4 shrink-0">
      <div class="flex-1 relative">
        <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-xs">🔍</span>
        <input v-model="searchSaveKeyword" class="w-full bg-slate-800 border border-slate-600 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 outline-none focus:border-indigo-500" placeholder="搜索记忆切片..." />
      </div>
      <button class="w-8 h-8 bg-slate-800 border border-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-amber-400 transition" title="收藏">⭐</button>
      <button class="px-3 h-8 bg-emerald-600/20 text-emerald-400 border border-emerald-700/50 rounded-lg hover:bg-emerald-600 hover:text-white transition text-xs font-bold whitespace-nowrap" @click="uiStore.modals.newGame = true">+ 新局</button>
    </div>
    
    <div class="flex justify-between items-center text-xs text-slate-500 mb-2 px-1">
      <span>记忆档案</span>
      <span>共 {{ filteredSaves.length }} 份</span>
    </div>
    
    <!-- 存档卡片列表 -->
    <div class="space-y-3 pb-8">
      <div v-for="save in filteredSaves" :key="save.id" class="bg-aw_panel border border-slate-700 rounded-xl p-3 hover:border-indigo-500 transition group shadow">
        
        <div class="flex justify-between items-start mb-2">
          <h4 class="text-sm font-bold text-slate-200 group-hover:text-indigo-400">{{ save.name }}</h4>
          <span class="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded border border-slate-700">{{ save.type }}</span>
        </div>
        
        <p class="text-xs text-slate-500 mb-3 line-clamp-1">{{ save.desc }}</p>
        
        <!-- 操作按钮栏 -->
        <div class="flex gap-2 relative">
          <button @click="loadSave(save.name)" class="flex-1 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white text-[10px] py-1.5 rounded font-bold transition">▶ 唤醒</button>
          
          <!-- 常规的垃圾桶按钮 -->
          <button v-if="confirmDeleteId !== save.name" @click="confirmDeleteId = save.name" class="w-10 bg-rose-900/30 hover:bg-rose-600 text-rose-400 hover:text-white rounded transition text-xs border border-rose-900/50 flex items-center justify-center">
            🗑
          </button>
          
          <!-- 展开后的防误触确认区 -->
          <div v-else class="flex gap-1">
            <button @click="executeDelete(save.name)" class="px-3 bg-rose-700 hover:bg-rose-600 text-white rounded transition text-[10px] font-bold shadow-lg border border-rose-500">确认粉碎</button>
            <button @click="confirmDeleteId = null" class="w-10 bg-slate-700 hover:bg-slate-600 text-slate-300 hover:text-white rounded transition text-xs flex items-center justify-center border border-slate-600">取消</button>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>