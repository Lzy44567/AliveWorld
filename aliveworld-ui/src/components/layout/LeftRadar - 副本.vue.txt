<script setup>
import { uiStore } from '../../store/uiStore';
import { gameStore } from '../../store/gameStore';
import { configStore } from '../../store/configStore';

// 【修复核心】将后端传来的代码格式字符串，解析成漂亮的血条和标签
const parseNpcStatus = (statusStr) => {
  const parts = String(statusStr).split(',').map(s => s.trim());
  const tags = [];
  let hp = null, max_hp = null;
  
  parts.forEach(p => {
    if (p.startsWith('hp:')) hp = parseInt(p.replace('hp:', ''));
    else if (p.startsWith('max_hp:')) max_hp = parseInt(p.replace('max_hp:', ''));
    else if (p.startsWith('description:')) tags.push(p.replace('description:', ''));
    else tags.push(p);
  });
  
  // 如果没有 max_hp 但有 hp，默认为 hp 的值（防止进度条报错）
  if (hp !== null && max_hp === null) max_hp = hp; 
  return { tags, hp, max_hp };
};
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
               <div class="bg-gradient-to-r from-red-600 to-red-400 h-1.5 rounded-full transition-all duration-500" :style="{ width: (gameStore.playerState.hp / gameStore.playerState.maxHp * 100) + '%' }"></div>
             </div>
             
             <!-- 动态条 -->
             <div v-for="(bar, name) in gameStore.dynamicBars" :key="name" class="mb-2">
               <div class="flex justify-between text-[10px] mb-1 text-slate-400"><span>{{ name }}</span><span class="font-mono">{{ bar.current }}/{{ bar.max }}</span></div>
               <div class="w-full bg-slate-950 rounded-full h-1">
                 <div class="bg-indigo-500 h-1 rounded-full transition-all duration-500" :style="{ width: Math.max(0, Math.min(100, (bar.current / bar.max * 100))) + '%' }"></div>
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
            <!-- 场景文字状态 -->
            <div v-for="(val, key) in gameStore.properties" :key="key" v-show="configStore.localSettings.showTime || !key.includes('时间')" class="bg-slate-800/80 px-2 py-1.5 rounded text-[11px] flex justify-between shadow-sm border border-slate-700/50">
              <span class="text-slate-400">{{ key }}</span><span class="text-emerald-300 font-bold">{{ val }}</span>
            </div>
            
            <!-- NPC 解析渲染 -->
            <div v-for="(statusStr, name) in gameStore.npcs" :key="name" class="bg-slate-800/60 p-2.5 rounded border border-rose-900/50 shadow-sm relative overflow-hidden">
              <div class="absolute left-0 top-0 bottom-0 w-1 bg-rose-500"></div>
              <div class="ml-2">
                <div class="flex justify-between items-center mb-1.5">
                  <span class="text-rose-300 font-bold text-sm">{{ name }}</span>
                  <!-- 如果解析出了血量，就渲染血量数值 -->
                  <span v-if="parseNpcStatus(statusStr).hp !== null" class="text-[10px] font-mono text-rose-400">
                    {{ parseNpcStatus(statusStr).hp }}/{{ parseNpcStatus(statusStr).max_hp }}
                  </span>
                </div>
                <!-- 如果解析出了血量，就渲染真实血条 -->
                <div v-if="parseNpcStatus(statusStr).hp !== null" class="w-full bg-slate-950 rounded-full h-1 mb-2">
                  <div class="bg-rose-600 h-1 rounded-full transition-all" :style="{ width: (parseNpcStatus(statusStr).hp / parseNpcStatus(statusStr).max_hp * 100) + '%' }"></div>
                </div>
                <!-- 渲染其他文本标签 -->
                <div class="flex flex-wrap gap-1">
                  <span v-for="(tag, idx) in parseNpcStatus(statusStr).tags" :key="idx" class="px-1.5 py-0.5 bg-rose-950/80 border border-rose-700/30 rounded text-[10px] text-rose-200">
                    {{ tag }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </aside>
</template>