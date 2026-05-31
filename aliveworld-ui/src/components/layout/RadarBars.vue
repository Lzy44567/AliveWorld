<!-- src/components/layout/RadarBars.vue -->
<script setup>
import { gameStore } from '../../store/gameStore';

const colorMap = {
  red: { bg: 'bg-rose-600', text: 'text-rose-400' },
  pink: { bg: 'bg-pink-600', text: 'text-pink-400' },
  orange: { bg: 'bg-orange-600', text: 'text-orange-400' },
  amber: { bg: 'bg-amber-600', text: 'text-amber-400' },
  emerald: { bg: 'bg-emerald-600', text: 'text-emerald-400' },
  cyan: { bg: 'bg-cyan-600', text: 'text-cyan-400' },
  indigo: { bg: 'bg-indigo-600', text: 'text-indigo-400' },
  purple: { bg: 'bg-purple-600', text: 'text-purple-400' },
  slate: { bg: 'bg-slate-600', text: 'text-slate-400' }
};

const cnMap = { "红色": "red", "粉色": "pink", "橙色": "orange", "黄色": "amber", "绿色": "emerald", "青色": "cyan", "蓝色": "indigo", "紫色": "purple", "灰色": "slate" };

const getTheme = (colorRaw) => {
  let c = (colorRaw || 'indigo').trim().toLowerCase();
  if (cnMap[c]) c = cnMap[c];
  return colorMap[c] || colorMap['indigo'];
};
</script>

<template>
  <div v-if="Object.keys(gameStore.dynamicBars).length > 0 || Object.keys(gameStore.buffs).length > 0">
    <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase">👤 状态与刻度</h3>
    <div class="bg-slate-800/80 p-3 rounded-lg border border-slate-700 shadow-inner">
      
      <!-- 动态进度条 -->
      <div v-for="(bar, name) in gameStore.dynamicBars" :key="name" class="mb-3 last:mb-0">
        <!-- 整个顶部的文字都继承该状态条的主题色 -->
        <div class="flex justify-between text-xs mb-1 font-bold" :class="getTheme(bar.color).text">
          <span>{{ name }}</span>
          <span class="font-mono">
            {{ bar.current }}/{{ bar.max }}
            <!-- 🚀 变化量不再写死红绿，直接继承父级颜色，用 opacity-70 区分层级 -->
            <span v-if="bar.change !== undefined && bar.change !== 0" class="opacity-70 ml-1">
              ({{ bar.change > 0 ? '+' : '' }}{{ bar.change }})
            </span>
          </span>
        </div>
        <div class="w-full bg-slate-950 rounded-full h-1.5">
          <div :class="getTheme(bar.color).bg" class="h-1.5 rounded-full transition-all duration-500" :style="{ width: Math.max(0, Math.min(100, (bar.current / bar.max * 100))) + '%' }"></div>
        </div>
      </div>

      <!-- Buff 展示区 -->
      <div v-if="Object.keys(gameStore.buffs).length > 0" class="mt-3 pt-3 border-t border-slate-700/50 flex flex-wrap gap-1">
        <div v-for="(buff, name) in gameStore.buffs" :key="name" class="px-2 py-1 bg-indigo-900/40 border border-indigo-700/50 rounded text-[10px] text-indigo-300 flex items-center gap-1" :title="buff.description">
          <span>{{ name }}</span>
          <span v-if="buff.duration > 0" class="bg-indigo-950 px-1 rounded">{{ buff.duration }}t</span>
        </div>
      </div>
      
    </div>
  </div>
</template>