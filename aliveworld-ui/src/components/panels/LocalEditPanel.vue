<!-- src/components/panels/LocalEditPanel.vue -->
<script setup>
import { gameStore } from '../../store/gameStore';
import { configStore } from '../../store/configStore';
</script>
<template>
  <div class="space-y-6 animate-[fadeIn_0.2s]">
    <div v-if="!gameStore.sessionId" class="text-center text-slate-500 text-xs mt-10">未连接时间线</div>
    <template v-else>
      <div class="bg-indigo-900/20 border border-indigo-800/50 p-4 rounded-xl shadow-inner">
        <h3 class="text-xs font-bold text-indigo-300 mb-2">🧭 主线剧情导向 (Plot Compass)</h3>
        <p class="text-[10px] text-slate-400 mb-3 leading-relaxed">此设定将被强行注入到 AI 系统最深处，实时干预剧本走向。</p>
        <textarea v-model="configStore.localSettings.plotCompass" class="w-full h-24 bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs text-slate-300 outline-none focus:border-indigo-500 resize-none shadow-inner" placeholder="例如：玩家被困在密室里，必须设法逃脱..."></textarea>
      </div>
      
      <!-- 🚀 修复问题11：在此处管理局内配置 -->
      <div class="border-t border-slate-700 pt-4 space-y-3">
        <h3 class="text-xs font-bold text-slate-400 mb-3">👁️ 局内雷达功能覆盖</h3>
        <label class="flex items-center justify-between text-xs text-slate-300 cursor-pointer bg-slate-800/50 px-3 py-2.5 rounded border border-slate-700 hover:border-slate-500 transition">
          <span>⏳ 顶部悬浮显示当前时间</span>
          <input type="checkbox" v-model="configStore.settings.showTime" class="w-4 h-4 rounded bg-slate-900 border-slate-600 text-amber-500">
        </label>
      </div>
    </template>
  </div>
</template>