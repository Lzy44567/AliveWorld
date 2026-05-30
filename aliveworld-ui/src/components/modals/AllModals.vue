<!-- src/components/modals/AllModals.vue -->
<!-- 100% 完整底稿 (请直接覆盖原文件) -->

<script setup>
import { ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { configStore } from '../../store/configStore';
import { gameStore } from '../../store/gameStore';
import { gameApi } from '../../api/gameApi';
import TerminalModal from './TerminalModal.vue';
import AssetEditorModal from './AssetEditorModal.vue';

const newSaveDesc = ref("");

const startNewGame = async () => {
  if (!assetStore.newSaveName.trim()) { 
    uiStore.showToast("⚠️ 命运必须有一个名字 (存档名为空)！", "error"); 
    return; 
  }
  gameStore.isProcessing = true;
  try {
    const payload = { 
      save_name: assetStore.newSaveName,
      description: newSaveDesc.value
    };
    const data = await gameApi.startGame(payload);
    
    gameStore.sessionId = data.session_id;
    gameStore.currentSaveName = assetStore.newSaveName;
    gameStore.chatLog = data.chat_messages;
    gameStore.syncState(data.state);
    
    uiStore.modals.newGame = false;
    await assetStore.fetchAssets();
    await assetStore.fetchLocalAssets(data.session_id);
    
    newSaveDesc.value = "";
    uiStore.showToast("新世界已降临");
  } catch (err) {
    uiStore.showToast("创世失败，请检查后端运行状态", "error");
  } finally {
    gameStore.isProcessing = false;
  }
};
</script>

<template>
  <!-- ⚙️ 设置弹窗 -->
  <div v-if="uiStore.modals.settings" class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-aw_panel border border-slate-600 rounded-2xl w-full max-w-3xl shadow-2xl flex flex-col slide-up overflow-hidden h-[80vh]">
      <div class="p-5 border-b border-slate-700 flex justify-between bg-slate-900/80">
        <h2 class="font-bold text-slate-200 text-xl">⚙️ 系统设置与模型核心</h2>
        <button @click="uiStore.modals.settings=false" class="text-slate-400 hover:text-white text-xl">✕</button>
      </div>
      <div class="flex flex-1 overflow-hidden">
        
        <!-- 左侧菜单 -->
        <div class="w-48 bg-slate-900/50 border-r border-slate-700 p-3 space-y-1">
          <button class="w-full text-left px-3 py-2 text-sm font-bold bg-slate-800 text-emerald-400 rounded">🔌 API 配置</button>
          <button class="w-full text-left px-3 py-2 text-sm font-bold text-slate-400 hover:bg-slate-800 rounded">🎛️ 调试与推演</button>
          <button class="w-full text-left px-3 py-2 text-sm font-bold text-slate-400 hover:bg-slate-800 rounded">🖼️ 生图与多模态</button>
        </div>
        
        <!-- 右侧内容区 -->
        <div class="flex-1 p-6 overflow-y-auto space-y-8 bg-slate-800/20 custom-scrollbar">
          
          <section>
            <h3 class="text-sm font-bold text-emerald-400 mb-3 border-b border-slate-700 pb-2">大语言模型配置 (LLM)</h3>
            <div class="space-y-3">
              <div>
                <label class="text-xs text-slate-400 block mb-1">API Base URL</label>
                <input v-model="configStore.globalSettings.apiBaseUrl" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" placeholder="https://api.openai.com/v1" />
              </div>
              <div>
                <label class="text-xs text-slate-400 block mb-1">API Key (密钥)</label>
                <input type="password" v-model="configStore.globalSettings.apiKey" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" placeholder="sk-..." />
              </div>
              <div>
                <label class="text-xs text-slate-400 block mb-1">请求模型 (Model)</label>
                <input v-model="configStore.globalSettings.model" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" placeholder="gpt-4o / deepseek-chat" />
              </div>
            </div>
          </section>
          
          <section>
            <h3 class="text-sm font-bold text-rose-400 mb-4 border-b border-slate-700 pb-2">推演与调试选项</h3>
            <div class="grid grid-cols-2 gap-4">
              <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
                <input type="checkbox" v-model="configStore.settings.showFutures" class="rounded bg-slate-800 border-slate-600 text-rose-500">
                <span>显示未来可能性包 (N*n)</span>
              </label>
              <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
                <input type="checkbox" v-model="configStore.settings.showDice" class="rounded bg-slate-800 border-slate-600 text-rose-500">
                <span>显示命运掷骰结果</span>
              </label>
              <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
                <input type="checkbox" v-model="configStore.settings.allowReroll" class="rounded bg-slate-800 border-slate-600 text-rose-500">
                <span>开启“重掷未来”允许反悔</span>
              </label>
              <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
                <input type="checkbox" v-model="configStore.settings.aiSuggestions" class="rounded bg-slate-800 border-slate-600 text-rose-500">
                <span>开启 AI 行动灵感建议</span>
              </label>
              <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
                <input type="checkbox" v-model="configStore.settings.showEntityDebug" class="rounded bg-slate-800 border-slate-600 text-amber-500">
                <span>显示暗流实体演算推导 (调试)</span>
              </label>
              <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
                <input type="checkbox" v-model="configStore.settings.autoCompressMemory" class="rounded bg-slate-800 border-slate-600 text-indigo-500">
                <span>智能记忆压缩 (避免炸上下文)</span>
              </label>
            </div>
          </section>
          
          <section>
            <h3 class="text-sm font-bold text-amber-400 mb-3 border-b border-slate-700 pb-2">环境感知与 UI</h3>
            <div class="grid grid-cols-2 gap-4">
              <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
                <input type="checkbox" v-model="configStore.settings.showTime" class="rounded bg-slate-800 border-slate-600 text-amber-500">
                <span>雷达显示世界时间流逝</span>
              </label>
            </div>
          </section>

        </div>
      </div>
    </div>
  </div>

  <!-- ✨ 创世弹窗 (极简版) -->
  <div v-if="uiStore.modals.newGame" class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-aw_panel border border-emerald-900/50 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col slide-up">
      <div class="p-5 border-b border-slate-700 flex justify-between bg-slate-900/80">
        <h2 class="font-bold text-emerald-400 text-xl">✨ 创世协议</h2>
        <button @click="uiStore.modals.newGame=false" class="text-slate-400 hover:text-white text-2xl">✕</button>
      </div>
      <div class="p-6 space-y-5">
        <div>
          <label class="text-xs font-bold text-slate-400 block mb-1">📝 时间线命名</label>
          <input v-model="assetStore.newSaveName" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none focus:border-emerald-500" placeholder="例如：废土远征纪" />
        </div>
        <div>
          <label class="text-xs font-bold text-slate-400 block mb-1">🌌 宇宙主导向简述 (选填)</label>
          <textarea v-model="newSaveDesc" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none focus:border-emerald-500 h-24 resize-none shadow-inner" placeholder="一句话描述这个世界的基础逻辑，例如：这是一个赛博朋克与修仙混合的世界..."></textarea>
          <p class="text-[10px] text-slate-500 mt-1">进入游戏后，您可以随时从右侧万象资产面板将世界书、文风或角色载入本局沙盒。</p>
        </div>
        <button @click="startNewGame" :disabled="gameStore.isProcessing" class="w-full py-4 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-bold shadow-lg disabled:opacity-50 transition text-lg mt-2">降临新世界</button>
      </div>
    </div>
  </div>

  <!-- ⬇️ 插入角色弹窗 -->
  <div v-if="uiStore.modals.insertChar" class="fixed inset-0 bg-black/80 z-[60] flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-aw_panel border border-indigo-900/50 rounded-2xl w-[500px] shadow-2xl flex flex-col slide-up overflow-hidden">
      <div class="p-4 border-b border-slate-700 flex justify-between bg-slate-900/80"><h2 class="font-bold text-indigo-400 text-lg">⬇️ 引入局内: {{ assetStore.insertCharData.name }}</h2><button @click="uiStore.modals.insertChar=false" class="text-slate-400 hover:text-white text-xl">✕</button></div>
      <div class="p-6 space-y-4">
        <p class="text-xs text-slate-400">AI 会根据你的描述自动安排他/她的出场方式。</p>
        <textarea v-model="assetStore.insertCharData.entrance" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none h-28 resize-none shadow-inner" placeholder="例如：突然踹开酒馆的大门，向玩家求救..."></textarea>
        <div class="flex justify-end gap-3 mt-4">
          <button @click="uiStore.modals.insertChar=false" class="px-4 py-2 bg-slate-800 text-slate-300 rounded font-bold hover:bg-slate-700">取消</button>
          <button class="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded font-bold shadow-lg">发送指令</button>
        </div>
      </div>
    </div>
  </div>

  <div v-if="uiStore.modals.gallery" class="fixed inset-0 bg-black/80 z-[70] flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-aw_panel border border-slate-600 rounded-xl w-full max-w-5xl shadow-2xl flex flex-col slide-up overflow-hidden h-[80vh]">
      <div class="p-4 border-b border-slate-700 flex justify-between bg-slate-900/80">
        <h2 class="font-bold text-amber-400 text-lg flex items-center gap-2">🖼️ 回忆画廊</h2>
        <button @click="uiStore.modals.gallery=false" class="text-slate-400 hover:text-white text-xl">✕</button>
      </div>
      <div class="flex-1 p-6 overflow-y-auto bg-slate-900/30">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="aspect-square bg-slate-800 rounded-lg border border-slate-700 overflow-hidden group cursor-pointer relative">
            <img src="https://images.unsplash.com/photo-1542204625-236b284e366d?q=80&w=400&auto=format&fit=crop" class="w-full h-full object-cover opacity-70 group-hover:opacity-100 group-hover:scale-110 transition duration-500">
          </div>
        </div>
      </div>
    </div>
  </div>

  <TerminalModal v-if="uiStore.modals.terminal" />
  <AssetEditorModal v-if="uiStore.modals.assetEditor" />
</template>