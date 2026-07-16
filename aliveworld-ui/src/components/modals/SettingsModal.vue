<script setup>
import { ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import InferenceSettings from '../settings/InferenceSettings.vue';
import ApiSettings from '../settings/ApiSettings.vue';
import ImageSettings from '../settings/ImageSettings.vue';
import MemorySettings from '../settings/MemorySettings.vue';

const activeSection = ref('inference');
const close = () => { uiStore.modals.settings = false; };
</script>

<template>
  <div class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-aw_panel border border-slate-600 rounded-2xl w-full max-w-3xl shadow-2xl flex flex-col slide-up overflow-hidden h-[80vh]">
      <div class="p-5 border-b border-slate-700 flex justify-between bg-slate-900/80">
        <h2 class="font-bold text-slate-200 text-xl">⚙️ 系统设置与模型核心</h2>
        <button @click="close" class="text-slate-400 hover:text-white text-xl">✕</button>
      </div>
      <div class="flex flex-1 min-h-0 overflow-hidden">
        <nav class="w-48 shrink-0 bg-slate-900/50 border-r border-slate-700 p-3 space-y-1">
          <button @click="activeSection = 'inference'" :class="activeSection === 'inference' ? 'bg-slate-800 text-rose-400' : 'text-slate-400 hover:bg-slate-800'" class="w-full text-left px-3 py-2 text-sm font-bold rounded transition">🎛️ 调试与推演</button>
          <button @click="activeSection = 'api'" :class="activeSection === 'api' ? 'bg-slate-800 text-emerald-400' : 'text-slate-400 hover:bg-slate-800'" class="w-full text-left px-3 py-2 text-sm font-bold rounded transition">🔌 API 配置</button>
          <button @click="activeSection = 'memory'" :class="activeSection === 'memory' ? 'bg-slate-800 text-indigo-300' : 'text-slate-400 hover:bg-slate-800'" class="w-full text-left px-3 py-2 text-sm font-bold rounded transition">🧠 记忆模型</button>
          <button @click="activeSection = 'image'" :class="activeSection === 'image' ? 'bg-slate-800 text-fuchsia-300' : 'text-slate-400 hover:bg-slate-800'" class="w-full text-left px-3 py-2 text-sm font-bold rounded transition">🎨 生图配置</button>
        </nav>
        <div class="flex-1 min-w-0 p-6 overflow-y-auto bg-slate-800/20 custom-scrollbar">
          <InferenceSettings v-if="activeSection === 'inference'" />
          <ApiSettings v-else-if="activeSection === 'api'" />
          <MemorySettings v-else-if="activeSection === 'memory'" />
          <ImageSettings v-else />
        </div>
      </div>
    </div>
  </div>
</template>
