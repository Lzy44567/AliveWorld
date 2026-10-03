<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { gameStore } from '../../store/gameStore';
import { preferenceStore } from '../../store/preferenceStore';
import { APP_VERSION } from '../../version';

const runtimeVersion = ref(APP_VERSION);

async function refreshRuntimeVersion() {
  try {
    const response = await fetch('/api/health', { cache: 'no-store' });
    if (!response.ok) return;
    const payload = await response.json();
    const value = String(payload?.version || '').trim();
    if (value) runtimeVersion.value = value.startsWith('v') ? value : `v${value}`;
  } catch {
    // The build-time version remains a safe fallback while the backend starts.
  }
}

const openPreferences = () => {
  uiStore.settingsSection = 'preferences';
  uiStore.modals.settings = true;
};
let preferenceRefreshTimer = null;
onMounted(() => {
  refreshRuntimeVersion();
  preferenceStore.refresh().catch(() => {});
  preferenceRefreshTimer = window.setInterval(() => preferenceStore.refresh().catch(() => {}), 15000);
});
onBeforeUnmount(() => {
  if (preferenceRefreshTimer) window.clearInterval(preferenceRefreshTimer);
});
</script>

<template>
  <header class="relative min-h-12 bg-slate-900 border-b border-slate-700 flex flex-wrap justify-between items-center px-2 md:px-4 z-50 shadow-md shrink-0 select-none">
    <div class="flex items-center gap-4">
      <button @click="uiStore.leftDrawerOpen = !uiStore.leftDrawerOpen" class="text-slate-400 hover:text-emerald-400 transition" title="局内雷达">
        <span class="text-xl">☷</span>
      </button>
      <span class="hidden sm:inline font-black text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-indigo-400 text-lg tracking-widest">ALIVEWORLD</span>
      <span data-testid="runtime-version" class="rounded border border-slate-700 bg-slate-800/80 px-1.5 py-0.5 text-[9px] font-bold tracking-normal text-slate-400">{{ runtimeVersion }}</span>
    </div>

    <div class="order-last w-full flex justify-center py-1 md:py-0 md:order-none md:w-auto md:absolute md:left-1/2 md:-translate-x-1/2 items-center gap-2">
      <div class="flex rounded-full border border-slate-700 bg-slate-950/80 p-0.5 text-xs shadow-inner">
        <button data-testid="mode-story" class="rounded-full px-4 py-1 transition" :class="uiStore.appMode==='game'?'bg-emerald-700 text-white':'text-slate-500 hover:text-slate-300'" @click="uiStore.appMode='game'">🎮 故事</button>
        <button data-testid="mode-character" class="rounded-full px-4 py-1 transition" :class="uiStore.appMode==='character'?'bg-indigo-700 text-white':'text-slate-500 hover:text-slate-300'" @click="uiStore.appMode='character'">🎭 角色</button>
        <button class="rounded-full px-4 py-1 transition" :class="uiStore.appMode==='workshop'?'bg-cyan-700 text-white':'text-slate-500 hover:text-slate-300'" @click="uiStore.appMode='workshop'">🧰 工坊</button>
      </div>
      <div v-if="gameStore.currentSaveName && uiStore.appMode==='game'" class="hidden lg:flex max-w-[22vw] items-center gap-1.5 rounded-full border border-indigo-800/70 bg-indigo-950/40 px-3 py-1 text-xs text-indigo-200" :title="`当前存档：${gameStore.currentSaveName}`"><span>📂</span><span class="truncate">{{ gameStore.currentSaveName }}</span><span v-if="gameStore.isProcessing" class="text-amber-400">推演中</span><span v-if="gameStore.runningCount>1" class="text-cyan-300">另有 {{ gameStore.runningCount-1 }} 项</span></div>
    </div>
    
    <div class="flex items-center gap-3">
      <button @click="openPreferences" class="relative text-slate-400 hover:text-fuchsia-300 flex items-center gap-1 text-sm font-bold transition" title="用户偏好卡">
        <span class="text-lg">🪞</span><span class="hidden xl:inline">偏好</span>
        <span v-if="preferenceStore.pendingCount" class="absolute -right-2 -top-2 min-w-4 rounded-full bg-rose-500 px-1 text-[9px] leading-4 text-white">{{ Math.min(preferenceStore.pendingCount, 99) }}</span>
      </button>
      <button data-testid="open-resource-library" @click="uiStore.resourceLibrarySection='images'; uiStore.modals.gallery = true" class="text-slate-400 hover:text-amber-400 flex items-center gap-1 text-sm font-bold transition" title="统一管理图片、卡片资产与世界包">
        <span class="text-lg">🗂️</span> 资源库
      </button>
      <button @click="uiStore.modals.terminal = true" class="text-slate-400 hover:text-rose-400 flex items-center gap-1 text-sm font-bold transition">
        <span class="text-lg">💻</span> 日志
      </button>
      <button @click="uiStore.modals.settings = true" class="text-slate-400 hover:text-indigo-400 flex items-center gap-1 text-sm font-bold transition">
        <span class="text-lg">⚙️</span> 设置
      </button>
      <div class="w-px h-6 bg-slate-700 mx-2"></div>
      <button @click="uiStore.rightDrawerOpen = !uiStore.rightDrawerOpen" class="text-slate-400 hover:text-emerald-400 transition" title="万象资产">
        <span class="text-xl">☰</span>
      </button>
    </div>
  </header>
</template>
