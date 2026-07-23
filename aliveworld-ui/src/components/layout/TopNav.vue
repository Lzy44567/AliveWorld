<script setup>
import { onBeforeUnmount, onMounted } from 'vue';
import { uiStore } from '../../store/uiStore';
import { gameStore } from '../../store/gameStore';
import { preferenceStore } from '../../store/preferenceStore';
import { APP_VERSION } from '../../version';

const openPreferences = () => {
  uiStore.settingsSection = 'preferences';
  uiStore.modals.settings = true;
};
let preferenceRefreshTimer = null;
onMounted(() => {
  preferenceStore.refresh().catch(() => {});
  preferenceRefreshTimer = window.setInterval(() => preferenceStore.refresh().catch(() => {}), 15000);
});
onBeforeUnmount(() => {
  if (preferenceRefreshTimer) window.clearInterval(preferenceRefreshTimer);
});
</script>

<template>
  <header class="relative h-12 bg-slate-900 border-b border-slate-700 flex justify-between items-center px-4 z-50 shadow-md shrink-0 select-none">
    <div class="flex items-center gap-4">
      <button @click="uiStore.leftDrawerOpen = !uiStore.leftDrawerOpen" class="text-slate-400 hover:text-emerald-400 transition" title="局内雷达">
        <span class="text-xl">☷</span>
      </button>
      <span class="font-black text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-indigo-400 text-lg tracking-widest">ALIVEWORLD</span>
      <span class="rounded border border-slate-700 bg-slate-800/80 px-1.5 py-0.5 text-[9px] font-bold tracking-normal text-slate-400">{{ APP_VERSION }}</span>
    </div>

    <div class="absolute left-1/2 hidden -translate-x-1/2 items-center gap-2 md:flex">
      <div class="flex rounded-full border border-slate-700 bg-slate-950/80 p-0.5 text-xs shadow-inner">
        <button class="rounded-full px-4 py-1 transition" :class="uiStore.appMode==='game'?'bg-emerald-700 text-white':'text-slate-500 hover:text-slate-300'" @click="uiStore.appMode='game'">🎮 游戏</button>
        <button class="rounded-full px-4 py-1 transition" :class="uiStore.appMode==='workshop'?'bg-cyan-700 text-white':'text-slate-500 hover:text-slate-300'" @click="uiStore.appMode='workshop'">🧰 工坊</button>
      </div>
      <div v-if="gameStore.currentSaveName && uiStore.appMode==='game'" class="flex max-w-[22vw] items-center gap-1.5 rounded-full border border-indigo-800/70 bg-indigo-950/40 px-3 py-1 text-xs text-indigo-200" :title="`当前存档：${gameStore.currentSaveName}`"><span>📂</span><span class="truncate">{{ gameStore.currentSaveName }}</span><span v-if="gameStore.isProcessing" class="text-amber-400">推演中</span></div>
    </div>
    
    <div class="flex items-center gap-3">
      <button @click="openPreferences" class="relative text-slate-400 hover:text-fuchsia-300 flex items-center gap-1 text-sm font-bold transition" title="用户偏好卡">
        <span class="text-lg">🪞</span><span class="hidden xl:inline">偏好</span>
        <span v-if="preferenceStore.pendingCount" class="absolute -right-2 -top-2 min-w-4 rounded-full bg-rose-500 px-1 text-[9px] leading-4 text-white">{{ Math.min(preferenceStore.pendingCount, 99) }}</span>
      </button>
      <button @click="uiStore.modals.gallery = true" class="text-slate-400 hover:text-amber-400 flex items-center gap-1 text-sm font-bold transition">
        <span class="text-lg">🖼️</span> 画廊
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
