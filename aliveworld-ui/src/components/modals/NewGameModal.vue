<!-- src/components/modals/NewGameModal.vue -->
<script setup>
import { ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { gameStore } from '../../store/gameStore';
import { gameApi } from '../../api/gameApi';
import { configStore } from '../../store/configStore';

const newSaveDesc = ref("");
const close = () => { uiStore.modals.newGame = false; };

const startNewGame = async () => {
  if (!assetStore.newSaveName.trim()) return uiStore.showToast("存档名不能为空！", "error"); 
  gameStore.isProcessing = true;
  try {
    const data = await gameApi.startGame({ save_name: assetStore.newSaveName, world_premise: newSaveDesc.value, story_settings: configStore.settings });
    gameStore.sessionId = data.session_id;
    gameStore.currentSaveName = assetStore.newSaveName;
    gameStore.chatLog = data.chat_messages;
    gameStore.setActionSuggestions(data.action_suggestions);
    gameStore.syncState(data.state);
    configStore.applyStoryConfig(data);
    
    close();
    await assetStore.fetchAssets();
    await assetStore.fetchLocalAssets(data.session_id);
    newSaveDesc.value = "";
    uiStore.showToast("新世界已降临");
  } catch (err) {
    uiStore.showToast("创世失败", "error");
  } finally { gameStore.isProcessing = false; }
};
</script>
<template>
  <div class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-aw_panel border border-emerald-900/50 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col slide-up">
      <div class="p-5 border-b border-slate-700 flex justify-between bg-slate-900/80">
        <h2 class="font-bold text-emerald-400 text-xl">✨ 创世协议</h2>
        <button @click="close" class="text-slate-400 hover:text-white text-2xl">✕</button>
      </div>
      <div class="p-6 space-y-5">
        <div><label class="text-xs font-bold text-slate-400 block mb-1">📝 时间线命名</label><input v-model="assetStore.newSaveName" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none focus:border-emerald-500" /></div>
        <div>
          <label class="text-xs font-bold text-slate-400 block mb-1">🌌 宇宙主导向简述 (选填)</label>
          <textarea v-model="newSaveDesc" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none focus:border-emerald-500 h-24 resize-none shadow-inner"></textarea>
        </div>
        <button @click="startNewGame" :disabled="gameStore.isProcessing" class="w-full py-4 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-bold shadow-lg disabled:opacity-50 transition text-lg mt-2">降临新世界</button>
      </div>
    </div>
  </div>
</template>
