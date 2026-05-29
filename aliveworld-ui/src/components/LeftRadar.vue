<!-- src/components/LeftRadar.vue -->
<script setup>
import { store } from '../store.js'
</script>

<template>
  <aside :class="store.leftDrawerOpen ? 'w-72' : 'w-0'" class="bg-aw_panel border-r border-slate-700 flex flex-col transition-all duration-300 z-20 shadow-xl overflow-hidden relative shrink-0">
    <div class="p-4 flex-1 overflow-y-auto space-y-6 min-w-[18rem] custom-scrollbar">
      
      <div v-if="!store.sessionId" class="h-full flex items-center justify-center text-slate-600 text-sm italic">等待降临界域...</div>
      
      <template v-else>
        <!-- 1. 玩家自身状态 -->
        <div>
          <div class="flex justify-between text-xs mb-1"><span class="text-emerald-400 font-bold">👤 玩家 (Player)</span></div>
          <div class="bg-slate-800/80 p-3 rounded-lg border border-slate-700">
             <div class="flex justify-between text-[10px] mb-1 text-slate-400"><span>HP</span><span>{{ store.playerState.hp }}/{{ store.playerState.maxHp }}</span></div>
             <div class="w-full bg-slate-900 rounded-full h-1.5 mb-3"><div class="bg-gradient-to-r from-red-600 to-red-400 h-1.5 rounded-full" :style="{ width: (store.playerState.hp / store.playerState.maxHp * 100) + '%' }"></div></div>
             <!-- 动态条 -->
             <div v-for="(bar, name) in store.dynamicBars" :key="name" class="mb-2">
               <div class="flex justify-between text-[10px] mb-1 text-slate-400"><span>{{ name }}</span><span>{{ bar.current }}/{{ bar.max }}</span></div>
               <div class="w-full bg-slate-900 rounded-full h-1"><div class="bg-gradient-to-r from-indigo-600 to-indigo-400 h-1 rounded-full" :style="{ width: Math.max(0, Math.min(100, (bar.current / bar.max * 100))) + '%' }"></div></div>
             </div>
          </div>
        </div>

        <!-- 2. 🚀 编队系统 (Party) -->
        <div>
          <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase">👥 队伍 (Party)</h3>
          <div class="flex flex-col gap-2">
            <div v-for="(comp, idx) in store.companions" :key="idx" class="bg-slate-800/60 p-2 rounded-lg border border-slate-700 flex items-center gap-3">
              <div class="w-8 h-8 rounded bg-slate-700 flex items-center justify-center text-lg shadow-inner">{{ comp.avatar }}</div>
              <div class="flex-1">
                <div class="flex justify-between text-xs font-bold text-slate-200"><span>{{ comp.name }}</span><span class="text-[10px] text-emerald-400">{{ comp.status }}</span></div>
                <div class="w-full bg-slate-900 rounded-full h-1 mt-1"><div class="bg-emerald-500 h-1 rounded-full" :style="{ width: (comp.hp / comp.maxHp * 100) + '%' }"></div></div>
              </div>
            </div>
          </div>
        </div>

        <!-- 3. 环境与实体雷达 -->
        <div v-if="Object.keys(store.properties).length > 0 || Object.keys(store.npcs).length > 0">
          <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase">📡 环境雷达</h3>
          <div class="space-y-2">
            <div v-for="(val, key) in store.properties" :key="key" v-show="store.shouldShowTime || !key.includes('时间')" class="bg-slate-800/80 px-2 py-1.5 rounded text-[11px] flex justify-between shadow-sm border border-slate-700/50"><span class="text-slate-400">{{ key }}</span><span class="text-emerald-300 font-bold">{{ val }}</span></div>
            <div v-for="(statusStr, name) in store.npcs" :key="name" class="bg-slate-800/60 p-2 rounded border border-indigo-900/50 shadow-sm relative"><div class="absolute left-0 top-0 bottom-0 w-1 bg-indigo-500"></div><span class="text-indigo-300 font-bold text-xs ml-2">{{ name }}</span><div class="flex flex-wrap gap-1 mt-1 ml-2"><span v-for="(tag, idx) in String(statusStr).split(',')" :key="idx" class="px-1.5 py-0.5 bg-indigo-950 border border-indigo-700/50 rounded text-[9px] text-indigo-200">{{ tag.trim() }}</span></div></div>
          </div>
        </div>

        <!-- 4. 🚀 场景插图与地图 (ReadreamAI 风格) -->
        <div class="border-t border-slate-700 pt-4 mt-6 pb-6">
          <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase">🗺️ 当前场景</h3>
          <!-- 场景缩略图 -->
          <div class="h-24 bg-slate-900 rounded-lg border border-slate-700 overflow-hidden relative group mb-3 shadow-lg">
            <img :src="store.currentScene.img" class="w-full h-full object-cover opacity-60 group-hover:opacity-100 transition duration-500" alt="scene">
            <div class="absolute bottom-0 w-full bg-gradient-to-t from-black via-black/70 to-transparent p-2 text-xs font-bold text-white">{{ store.currentScene.name }}</div>
          </div>
          <!-- 节点地图 -->
          <div class="bg-slate-900/50 rounded-lg border border-slate-700 p-3">
            <div class="flex items-center justify-between relative">
              <div class="absolute top-1/2 left-0 w-full h-0.5 bg-slate-700 -z-10 -translate-y-1/2"></div>
              <div v-for="node in store.mapNodes" :key="node.id" class="flex flex-col items-center gap-1 z-10 cursor-pointer group">
                <div class="w-4 h-4 rounded-full border-2 transition" :class="node.status === 'current' ? 'border-emerald-400 bg-emerald-900 shadow-[0_0_10px_#34d399]' : node.status === 'visited' ? 'border-indigo-500 bg-indigo-900' : 'border-slate-600 bg-slate-800'"></div>
                <span class="text-[9px] font-bold" :class="node.status === 'current' ? 'text-emerald-400' : 'text-slate-500 group-hover:text-slate-300'">{{ node.name }}</span>
              </div>
            </div>
            <div class="text-center mt-3"><button class="text-[10px] bg-slate-700 hover:bg-slate-600 text-white px-3 py-1 rounded transition">探索周边</button></div>
          </div>
        </div>

      </template>
    </div>
  </aside>
</template>