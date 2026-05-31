<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetApi } from '../../api/assetApi';

const logs = ref([]);
let pollTimer = null;

const fetchRealLogs = async () => {
  try {
    const el = document.getElementById('terminal-log-container');
    // 【修复核心】判断拉取数据前，滚动条是否在最底部（容差 50px）
    const isAtBottom = el ? (el.scrollHeight - el.scrollTop <= el.clientHeight + 50) : true;
    
    const res = await assetApi.getSystemLogs();
    logs.value = res.logs || [];
    
    // 只有在用户原本就在底部时，拉取完新数据才自动滚下去
    if (isAtBottom) {
      setTimeout(() => {
        if (el) el.scrollTop = el.scrollHeight;
      }, 50);
    }
  } catch (err) {
    console.error("无法拉取后端日志", err);
  }
};

onMounted(() => {
  fetchRealLogs();
  pollTimer = setInterval(fetchRealLogs, 2000);
});

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
});
</script>

<template>
  <div class="fixed inset-0 bg-black/80 z-[70] flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-[#0c0c0c] border border-slate-600 rounded-xl w-full max-w-4xl shadow-2xl flex flex-col slide-up overflow-hidden h-[70vh]">
      <div class="p-3 border-b border-slate-700 flex justify-between bg-slate-900">
        <h2 class="font-bold text-slate-300 text-sm flex items-center gap-2">
          <span class="text-rose-500">💻</span> 系统统御终端 (Live Log)
        </h2>
        <button @click="uiStore.modals.terminal=false" class="text-slate-500 hover:text-white">✕</button>
      </div>
      
      <div class="flex-1 p-4 font-mono text-xs overflow-y-auto custom-scrollbar relative" id="terminal-log-container">
        <div class="text-emerald-500 mb-4 border-b border-slate-800 pb-2">AliveWorld OS v1.0.0 [Connection Established]</div>
        
        <div v-for="(log, idx) in logs" :key="idx" class="mb-1.5 leading-relaxed flex gap-2">
          <span class="text-slate-500 shrink-0">[{{ log.time }}]</span>
          <span class="shrink-0">{{ log.icon }}</span>
          <span class="text-indigo-400 shrink-0">[{{ log.module }}]</span>
          <span class="text-slate-300 whitespace-pre-wrap">{{ log.message }}</span>
        </div>
        
        <div class="text-slate-500 mt-4 animate-pulse">_</div>
      </div>
    </div>
  </div>
</template>