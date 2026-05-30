<script setup>
import { uiStore } from '../../store/uiStore';
import { gameStore } from '../../store/gameStore';
import { configStore } from '../../store/configStore';
</script>

<template>
  <aside :class="uiStore.leftDrawerOpen ? 'w-[320px]' : 'w-0'" class="bg-aw_panel border-r border-slate-700 flex flex-col transition-all duration-300 z-20 shadow-xl overflow-hidden relative shrink-0">
    <div class="flex-1 overflow-y-auto p-4 space-y-6 min-w-[320px] custom-scrollbar">
      
      <div v-if="!gameStore.sessionId" class="h-full flex items-center justify-center text-slate-500 text-sm italic">等待唤醒故事线...</div>
      
      <template v-else>
        <!-- 玩家状态 -->
        <div>
          <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase">👤 玩家 (Player)</h3>
          <div class="bg-slate-800/80 p-3 rounded-lg border border-slate-700 shadow-inner">
             <div class="flex justify-between text-xs mb-1 text-slate-300 font-bold">
               <span>HP</span><span class="font-mono text-emerald-400">{{ gameStore.playerState.hp }}/{{ gameStore.playerState.maxHp }}</span>
             </div>
             <div class="w-full bg-slate-950 rounded-full h-1.5 mb-3">
               <div class="bg-gradient-to-r from-red-600 to-red-400 h-1.5 rounded-full transition-all" :style="{ width: (gameStore.playerState.hp / gameStore.playerState.maxHp * 100) + '%' }"></div>
             </div>
             
             <!-- 动态条 -->
             <div v-for="(bar, name) in gameStore.dynamicBars" :key="name" class="mb-2">
               <div class="flex justify-between text-[10px] mb-1 text-slate-400"><span>{{ name }}</span><span class="font-mono">{{ bar.current }}/{{ bar.max }}</span></div>
               <div class="w-full bg-slate-950 rounded-full h-1">
                 <div class="bg-indigo-500 h-1 rounded-full" :style="{ width: Math.max(0, Math.min(100, (bar.current / bar.max * 100))) + '%' }"></div>
               </div>
             </div>
          </div>
        </div>

        <!-- 编队系统 -->
        <div v-if="gameStore.companions && gameStore.companions.length > 0">
          <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase">👥 同行者 (Party)</h3>
          <div class="flex flex-col gap-2">
            <div v-for="(comp, idx) in gameStore.companions" :key="idx" class="bg-slate-800/60 p-2.5 rounded-lg border border-slate-700 flex gap-3 hover:border-indigo-500 cursor-pointer transition shadow-sm">
              <div class="w-10 h-10 rounded bg-slate-700 flex items-center justify-center text-xl shadow-inner shrink-0">{{ comp.avatar }}</div>
              <div class="flex-1 min-w-0 flex flex-col justify-center">
                <div class="flex justify-between items-center mb-1">
                  <span class="text-xs font-bold text-slate-200">{{ comp.name }}</span>
                  <div class="w-12 bg-slate-900 rounded-full h-1">
                    <div class="bg-emerald-500 h-1 rounded-full" :style="{ width: (comp.hp / comp.maxHp * 100) + '%' }"></div>
                  </div>
                </div>
                <div class="text-[10px] text-slate-400 leading-snug whitespace-pre-wrap">{{ comp.status }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 环境与 NPC -->
        <div v-if="Object.keys(gameStore.properties).length > 0 || Object.keys(gameStore.npcs).length > 0">
          <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase">📡 场景与实体感知</h3>
          <div class="space-y-2">
            <div v-for="(val, key) in gameStore.properties" :key="key" v-show="configStore.localSettings.showTime || !key.includes('时间')" class="bg-slate-800/80 px-2 py-1.5 rounded text-[11px] flex justify-between shadow-sm border border-slate-700/50">
              <span class="text-slate-400">{{ key }}</span><span class="text-emerald-300 font-bold">{{ val }}</span>
            </div>
            <div v-for="(statusStr, name) in gameStore.npcs" :key="name" class="bg-slate-800/60 p-2 rounded border border-rose-900/50 shadow-sm relative">
              <div class="absolute left-0 top-0 bottom-0 w-1 bg-rose-500"></div><span class="text-rose-300 font-bold text-xs ml-2">{{ name }}</span>
              <div class="flex flex-wrap gap-1 mt-1 ml-2">
                <span v-for="(tag, idx) in String(statusStr).split(',')" :key="idx" class="px-1.5 py-0.5 bg-rose-950 border border-rose-700/50 rounded text-[9px] text-rose-200">{{ tag.trim() }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 场景地图 -->
        <div v-if="configStore.localSettings.showMap" class="border-t border-slate-700 pt-4 pb-6">
          <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase flex justify-between items-center">
            <span>🗺️ 区域地图</span><button class="text-indigo-400 hover:text-white text-[10px]">全屏</button>
          </h3>
          <div class="h-28 bg-slate-900 rounded-lg border border-slate-700 overflow-hidden relative group mb-3 shadow-lg">
            <img :src="gameStore.currentScene.img" class="w-full h-full object-cover opacity-60 group-hover:opacity-100 transition duration-500">
            <div class="absolute bottom-0 w-full bg-gradient-to-t from-black via-black/80 to-transparent p-2 text-xs font-bold text-white">{{ gameStore.currentScene.name }}</div>
          </div>
        </div>
      </template>
    </div>
  </aside>
</template>