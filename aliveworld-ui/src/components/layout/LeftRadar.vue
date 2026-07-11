<!-- src/components/layout/LeftRadar.vue -->
<script setup>
import { computed } from 'vue';
import { uiStore } from '../../store/uiStore';
import { gameStore } from '../../store/gameStore';
import { effectiveStorySettings } from '../../store/configStore';
import RadarBars from './RadarBars.vue';
import RadarNpcs from './RadarNpcs.vue';

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
        <!-- 时间悬浮置顶展示 -->
        <div v-if="effectiveStorySettings.showTime && currentTime !== '未知纪元'" class="bg-indigo-950/60 border border-indigo-800/50 p-3 rounded-lg flex items-center justify-center gap-2 shadow-inner">
          <span class="text-xl">⏳</span>
          <span class="font-bold text-indigo-200 tracking-wide">{{ currentTime }}</span>
        </div>

        <!-- 组装：动态进度条与Buff -->
        <RadarBars />

        <div v-if="Object.keys(otherProperties).length > 0 || Object.keys(gameStore.npcs).length > 0">
          <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase">📡 场景与实体感知</h3>
          
          <!-- 场景文本属性 -->
          <div class="space-y-2 mb-2">
            <div v-for="(val, key) in otherProperties" :key="key" class="bg-slate-800/80 px-2 py-1.5 rounded text-[11px] flex justify-between shadow-sm border border-slate-700/50">
              <span class="text-slate-400">{{ key }}</span>
              <span class="text-emerald-300 font-bold">{{ val }}</span>
            </div>
          </div>
          
          <!-- 组装：NPC卡片渲染 -->
          <RadarNpcs />
        </div>
      </template>
    </div>
  </aside>
</template>
