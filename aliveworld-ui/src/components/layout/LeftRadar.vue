<!-- src/components/layout/LeftRadar.vue -->
<script setup>
import { computed } from 'vue';
import { uiStore } from '../../store/uiStore';
import { gameStore } from '../../store/gameStore';
import { configStore } from '../../store/configStore';

const parseNpcStatus = (statusStr) => {
  const parts = String(statusStr).split(',').map(s => s.trim());
  const tags = [];
  let hp = null, max_hp = null;
  
  // 默认冷灰色调
  let colorTheme = 'border-slate-700/50 bg-slate-800/60 text-slate-300';
  let barColor = 'bg-slate-600';
  
  // 🚀 我们支持这五种预设高亮色，AI 可以在标签里直接写 "theme:red" 等
  const colorMap = {
    red: { theme: 'border-rose-900/50 bg-rose-950/40 text-rose-300', bar: 'bg-rose-600' },
    emerald: { theme: 'border-emerald-900/50 bg-emerald-950/40 text-emerald-300', bar: 'bg-emerald-600' },
    amber: { theme: 'border-amber-900/50 bg-amber-950/40 text-amber-300', bar: 'bg-amber-600' },
    indigo: { theme: 'border-indigo-900/50 bg-indigo-950/40 text-indigo-300', bar: 'bg-indigo-600' },
    slate: { theme: 'border-slate-700/50 bg-slate-800/60 text-slate-300', bar: 'bg-slate-600' }
  };

  parts.forEach(p => {
    if (p.startsWith('hp:')) hp = parseInt(p.replace('hp:', ''));
    else if (p.startsWith('max_hp:')) max_hp = parseInt(p.replace('max_hp:', ''));
    else if (p.startsWith('theme:')) {
       // 提取颜色，并不把这一条塞入 UI 显示的 tags 里！
       const c = p.replace('theme:', '').trim().toLowerCase();
       if (colorMap[c]) {
         colorTheme = colorMap[c].theme;
         barColor = colorMap[c].bar;
       }
    }
    else if (p.startsWith('description:')) tags.push(p.replace('description:', ''));
    else tags.push(p);
  });
  
  if (hp !== null && max_hp === null) max_hp = hp; 
  return { tags, hp, max_hp, colorTheme, barColor };
};

// 提取当前时间用于置顶高亮
const currentTime = computed(() => gameStore.properties['当前时间'] || "未知纪元");
const otherProperties = computed(() => {
  const props = { ...gameStore.properties };
  delete props['当前时间'];
  return props;
});
</script>

<template>
  <aside :class="uiStore.leftDrawerOpen ? 'w-[320px]' : 'w-0'" class="bg-aw_panel border-r border-slate-700 flex flex-col transition-all duration-300 z-20 shadow-xl overflow-hidden relative shrink-0">
    <div class="flex-1 overflow-y-auto p-4 space-y-6 min-w-[320px] custom-scrollbar">
      
      <div v-if="!gameStore.sessionId" class="h-full flex items-center justify-center text-slate-500 text-sm italic">等待唤醒故事线...</div>
      
      <template v-else>
        <!-- 🚀 时间开关：绑定了 configStore.settings.showTime -->
        <div v-if="configStore.settings.showTime && currentTime !== '未知纪元'" class="bg-indigo-950/60 border border-indigo-800/50 p-3 rounded-lg flex items-center justify-center gap-2 shadow-inner">
          <span class="text-xl">⏳</span>
          <span class="font-bold text-indigo-200 tracking-wide">{{ currentTime }}</span>
        </div>

        <div>
          <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase">👤 玩家状态</h3>
          <div class="bg-slate-800/80 p-3 rounded-lg border border-slate-700 shadow-inner">
             <div class="flex justify-between text-xs mb-1 text-slate-300 font-bold">
               <span>HP</span><span class="font-mono text-emerald-400">{{ gameStore.playerState.hp }}/{{ gameStore.playerState.maxHp }}</span>
             </div>
             <div class="w-full bg-slate-950 rounded-full h-1.5 mb-3">
               <div class="bg-gradient-to-r from-red-600 to-red-400 h-1.5 rounded-full transition-all duration-500" :style="{ width: (gameStore.playerState.hp / gameStore.playerState.maxHp * 100) + '%' }"></div>
             </div>
             
             <div v-for="(bar, name) in gameStore.dynamicBars" :key="name" class="mb-2">
               <div class="flex justify-between text-[10px] mb-1 text-slate-400"><span>{{ name }}</span><span class="font-mono">{{ bar.current }}/{{ bar.max }}</span></div>
               <div class="w-full bg-slate-950 rounded-full h-1">
                 <div class="bg-indigo-500 h-1 rounded-full transition-all duration-500" :style="{ width: Math.max(0, Math.min(100, (bar.current / bar.max * 100))) + '%' }"></div>
               </div>
             </div>
          </div>
        </div>

        <div v-if="Object.keys(otherProperties).length > 0 || Object.keys(gameStore.npcs).length > 0">
          <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase">📡 场景与实体</h3>
          <div class="space-y-2">
            
            <div v-for="(val, key) in otherProperties" :key="key" class="bg-slate-800/80 px-2 py-1.5 rounded text-[11px] flex justify-between shadow-sm border border-slate-700/50">
              <span class="text-slate-400">{{ key }}</span><span class="text-emerald-300 font-bold">{{ val }}</span>
            </div>
            
            <!-- 🚀 高度自由色卡渲染 -->
            <div v-for="(statusStr, name) in gameStore.npcs" :key="name" :class="parseNpcStatus(statusStr).colorTheme" class="p-2.5 rounded border shadow-sm relative overflow-hidden transition-colors duration-300">
              <div class="flex justify-between items-center mb-1.5">
                <span class="font-bold text-sm">{{ name }}</span>
                <span v-if="parseNpcStatus(statusStr).hp !== null" class="text-[10px] font-mono opacity-80">
                  {{ parseNpcStatus(statusStr).hp }}/{{ parseNpcStatus(statusStr).max_hp }}
                </span>
              </div>
              
              <div v-if="parseNpcStatus(statusStr).hp !== null" class="w-full bg-slate-950/50 rounded-full h-1 mb-2">
                <div :class="parseNpcStatus(statusStr).barColor" class="h-1 rounded-full transition-all" :style="{ width: (parseNpcStatus(statusStr).hp / parseNpcStatus(statusStr).max_hp * 100) + '%' }"></div>
              </div>
              
              <div class="flex flex-wrap gap-1">
                <span v-for="(tag, idx) in parseNpcStatus(statusStr).tags" :key="idx" class="px-1.5 py-0.5 bg-black/30 rounded text-[10px] opacity-90 border border-white/5">
                  {{ tag }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </aside>
</template>