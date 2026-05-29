<!-- src/components/TopNav.vue -->
<script setup>
import { store } from '../store.js'
</script>

<template>
  <header class="h-12 bg-slate-900 border-b border-slate-700 flex justify-between items-center px-2 z-50 select-none shadow-md">
    <!-- 左侧区域 -->
    <div class="flex items-center gap-2">
      <button @click="store.leftDrawerOpen = !store.leftDrawerOpen" class="w-10 h-10 flex justify-center items-center text-slate-400 hover:text-emerald-400 hover:bg-slate-800 rounded transition" title="开关雷达">
        <span class="text-xl">☷</span>
      </button>
      <div class="flex items-center gap-2 ml-2">
        <span class="font-black text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-indigo-400 text-lg tracking-widest">ALIVEWORLD</span>
        <span class="text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded border border-slate-700">v2.1</span>
      </div>
    </div>

    <!-- 中间区域 (当前故事信息) -->
    <div class="hidden md:flex items-center text-xs text-slate-400 bg-slate-800 px-4 py-1 rounded-full border border-slate-700">
      <span class="mr-2">当前界域:</span>
      <span class="text-indigo-300 font-bold">{{ store.sessionId ? "冒险进行中" : "未连接" }}</span>
    </div>

    <!-- 右侧工具栏 -->
    <div class="flex items-center gap-1">
      <button @click="store.modals.newGame = true" class="px-3 h-8 flex items-center gap-1 bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600 hover:text-white rounded text-xs font-bold transition mr-2 border border-emerald-700">
        <span>✨</span> 创世
      </button>
      
      <button @click="store.modals.workshop = true" class="w-10 h-10 flex justify-center items-center text-slate-400 hover:text-indigo-400 hover:bg-slate-800 rounded transition" title="万象工坊 (角色/世界书/文风/实体)">
        <span class="text-lg">🗃️</span>
      </button>
      <button @click="store.modals.settings = true" class="w-10 h-10 flex justify-center items-center text-slate-400 hover:text-amber-400 hover:bg-slate-800 rounded transition" title="全局设置 (API/生图/日志)">
        <span class="text-lg">⚙️</span>
      </button>
      <button @click="store.rightDrawerOpen = !store.rightDrawerOpen" class="w-10 h-10 flex justify-center items-center text-slate-400 hover:text-indigo-400 hover:bg-slate-800 rounded transition" title="开关侧栏">
        <span class="text-xl">☰</span>
      </button>
    </div>
  </header>
</template>