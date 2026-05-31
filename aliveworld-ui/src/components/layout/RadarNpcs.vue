<!-- src/components/layout/RadarNpcs.vue -->
<script setup>
import { gameStore } from '../../store/gameStore';

const parseNpcStatus = (statusStr) => {
  const parts = String(statusStr).split(',').map(s => s.trim());
  const tags = [];
  let hp = null, max_hp = null;
  let colorTheme = 'border-slate-700/50 bg-slate-800/60 text-slate-300';
  let barColor = 'bg-slate-600';
  
  const colorMap = {
    red: { theme: 'border-rose-900/50 bg-rose-950/40 text-rose-300', bar: 'bg-rose-600' },
    pink: { theme: 'border-pink-900/50 bg-pink-950/40 text-pink-300', bar: 'bg-pink-600' },
    orange: { theme: 'border-orange-900/50 bg-orange-950/40 text-orange-300', bar: 'bg-orange-600' },
    amber: { theme: 'border-amber-900/50 bg-amber-950/40 text-amber-300', bar: 'bg-amber-600' },
    emerald: { theme: 'border-emerald-900/50 bg-emerald-950/40 text-emerald-300', bar: 'bg-emerald-600' },
    cyan: { theme: 'border-cyan-900/50 bg-cyan-950/40 text-cyan-300', bar: 'bg-cyan-600' },
    indigo: { theme: 'border-indigo-900/50 bg-indigo-950/40 text-indigo-300', bar: 'bg-indigo-600' },
    purple: { theme: 'border-purple-900/50 bg-purple-950/40 text-purple-300', bar: 'bg-purple-600' },
    slate: { theme: 'border-slate-700/50 bg-slate-800/60 text-slate-300', bar: 'bg-slate-600' }
  };
  
  const cnMap = { "红色": "red", "粉色": "pink", "橙色": "orange", "黄色": "amber", "绿色": "emerald", "青色": "cyan", "蓝色": "indigo", "紫色": "purple", "灰色": "slate" };

  parts.forEach(p => {
    if (p.startsWith('hp:')) hp = parseInt(p.replace('hp:', ''));
    else if (p.startsWith('max_hp:')) max_hp = parseInt(p.replace('max_hp:', ''));
    else if (p.startsWith('theme:')) {
       let c = p.replace('theme:', '').trim().toLowerCase();
       if (cnMap[c]) c = cnMap[c];
       if (colorMap[c]) { colorTheme = colorMap[c].theme; barColor = colorMap[c].bar; }
    }
    else if (p.startsWith('description:')) tags.push(p.replace('description:', ''));
    else tags.push(p);
  });
  
  if (hp !== null && max_hp === null) max_hp = hp; 
  return { tags, hp, max_hp, colorTheme, barColor };
};
</script>

<template>
  <div v-if="Object.keys(gameStore.npcs).length > 0">
    <div class="space-y-2">
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