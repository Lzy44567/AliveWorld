<script setup>
import { uiStore } from '../../store/uiStore';
import { gameStore } from '../../store/gameStore';
</script>

<template>
  <header class="relative h-12 bg-slate-900 border-b border-slate-700 flex justify-between items-center px-4 z-50 shadow-md shrink-0 select-none">
    <div class="flex items-center gap-4">
      <button @click="uiStore.leftDrawerOpen = !uiStore.leftDrawerOpen" class="text-slate-400 hover:text-emerald-400 transition" title="局内雷达">
        <span class="text-xl">☷</span>
      </button>
      <span class="font-black text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-indigo-400 text-lg tracking-widest">ALIVEWORLD</span>
    </div>

    <div v-if="gameStore.currentSaveName" class="absolute left-1/2 hidden max-w-[36vw] -translate-x-1/2 items-center gap-1.5 rounded-full border border-indigo-800/70 bg-indigo-950/40 px-3 py-1 text-xs text-indigo-200 md:flex" :title="`当前存档：${gameStore.currentSaveName}`"><span>📂</span><span class="truncate">{{ gameStore.currentSaveName }}</span><span v-if="gameStore.isProcessing" class="text-amber-400">推演中</span></div>
    
    <div class="flex items-center gap-3">
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
