<!-- src/components/panels/SavesPanel.vue -->
<!-- 100% 完整底稿 (请直接覆盖原文件) -->

<script setup>
import { ref, computed, onBeforeUnmount, onMounted } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { gameStore } from '../../store/gameStore';
import { gameApi } from '../../api/gameApi';
import { assetApi } from '../../api/assetApi';
import { configStore } from '../../store/configStore';
import { useDeleteConfirmation } from '../../composables/useDeleteConfirmation';
import AssetLifecycleModal from '../modals/AssetLifecycleModal.vue';

const searchSaveKeyword = ref("");
const { confirmDeleteId, requestDelete, cancelDelete } = useDeleteConfirmation();
const lifecycle = ref({ open: false, action: 'clone', save: null });
const openMenuId = ref('');

const closeMenuOnOutside = (event) => {
  if (!event.target.closest('[data-save-actions]')) openMenuId.value = '';
};
onMounted(() => document.addEventListener('pointerdown', closeMenuOnOutside));
onBeforeUnmount(() => document.removeEventListener('pointerdown', closeMenuOnOutside));

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
    gameStore.setActionSuggestions(data.action_suggestions);
    gameStore.syncState(data.state);
    configStore.applyStoryConfig(data);
    
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
    cancelDelete();
    
    // 如果粉碎的正是当前正在推演的世界，直接物理清屏！
    if (gameStore.currentSaveName === saveName) {
      gameStore.reset();
      configStore.resetStoryConfig();
      assetStore.fetchLocalAssets(null); // 清空局内专属
    }
    
    await assetStore.fetchAssets();
  } catch (err) {
    alert("档案粉碎失败，请检查后端运行状态。");
  }
};

const openLifecycle = (save, action) => {
  openMenuId.value = '';
  lifecycle.value = { open: true, action, save };
};

const requestSaveDelete = (saveName) => {
  openMenuId.value = '';
  requestDelete(saveName);
};

const confirmLifecycle = async (newName) => {
  const { save, action } = lifecycle.value;
  if (!save) return;
  try {
    const result = await assetApi.lifecycleSave(save.name, action, newName);
    if (action === 'rename' && gameStore.currentSaveName === save.name) {
      gameStore.currentSaveName = result.name;
    }
    lifecycle.value = { open: false, action: 'clone', save: null };
    await assetStore.fetchAssets();
    uiStore.showToast(`${action === 'clone' ? '克隆' : '重命名'}存档完成：${result.name}`);
  } catch (error) {
    uiStore.showToast(error.message || '存档操作失败', 'error');
  }
};
</script>

<template>
  <div class="flex flex-col flex-1 min-h-0 animate-[fadeIn_0.2s]">
    
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
    
    <!-- 只滚动存档卡片，搜索、收藏、新局和计数固定 -->
    <div class="flex-1 min-h-0 overflow-y-auto custom-scrollbar pr-1">
    <div class="space-y-3 pb-32">
      <div v-for="save in filteredSaves" :key="save.id" class="bg-aw_panel border rounded-xl p-3 transition group shadow" :class="gameStore.currentSaveName===save.name?'border-emerald-500 ring-1 ring-emerald-500/30':'border-slate-700 hover:border-indigo-500'">
        
        <div class="flex justify-between items-start mb-2">
          <h4 class="text-sm font-bold text-slate-200 group-hover:text-indigo-400">{{ save.name }} <span v-if="gameStore.currentSaveName===save.name" class="ml-1 rounded bg-emerald-950 px-1.5 py-0.5 text-[9px] text-emerald-300">当前游玩</span></h4>
          <span class="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded border border-slate-700">{{ save.type }}</span>
        </div>
        
        <p class="text-xs text-slate-500 mb-3 line-clamp-1">{{ save.desc }}</p>
        
        <!-- 操作按钮栏 -->
        <div class="flex gap-2 relative" data-save-actions>
          <button @click="loadSave(save.name)" class="flex-1 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white text-[10px] py-1.5 rounded font-bold transition">▶ 唤醒</button>
          <div v-if="confirmDeleteId !== save.name" class="relative" data-save-actions>
            <button @click.stop="openMenuId = openMenuId === save.name ? '' : save.name" class="h-full w-10 rounded border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700" aria-label="存档管理" :aria-expanded="openMenuId === save.name">•••</button>
            <div v-if="openMenuId === save.name" class="absolute right-0 top-full z-20 mt-2 w-32 overflow-hidden rounded-lg border border-slate-600 bg-slate-900 p-1 shadow-2xl">
              <button @click="openLifecycle(save, 'rename')" class="w-full rounded px-3 py-2 text-left text-[10px] text-slate-300 hover:bg-slate-800">✍️ 重命名</button>
              <button @click="openLifecycle(save, 'clone')" class="w-full rounded px-3 py-2 text-left text-[10px] text-cyan-300 hover:bg-slate-800">⎘ 克隆存档</button>
              <button @click="requestSaveDelete(save.name)" class="w-full rounded px-3 py-2 text-left text-[10px] text-rose-400 hover:bg-rose-950/50">🗑 删除存档</button>
            </div>
          </div>
          
          <!-- 展开后的防误触确认区 -->
          <div v-else :data-delete-confirm-id="save.name" class="flex gap-1">
            <button @click="executeDelete(save.name)" class="px-3 bg-rose-700 hover:bg-rose-600 text-white rounded transition text-[10px] font-bold shadow-lg border border-rose-500">确认粉碎</button>
            <button @click="cancelDelete" class="w-10 bg-slate-700 hover:bg-slate-600 text-slate-300 hover:text-white rounded transition text-xs flex items-center justify-center border border-slate-600">取消</button>
          </div>
        </div>

      </div>
    </div>
    </div>
    <AssetLifecycleModal :open="lifecycle.open" :action="lifecycle.action" :current-name="lifecycle.save?.name || ''" kind-label="存档" @cancel="lifecycle={ open:false, action:'clone', save:null }" @confirm="confirmLifecycle" />
  </div>
</template>
