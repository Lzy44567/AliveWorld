<script setup>
import { computed, ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';

const searchKeyword = ref("");

// 根据当前选中的 Tab 和 Scope 动态计算要展示的列表
const currentList = computed(() => {
  const tab = uiStore.rightTab;
  const scope = uiStore.assetScope;
  if (tab === 'world') return assetStore.worlds[scope];
  if (tab === 'character') return assetStore.characters[scope];
  if (tab === 'style') return assetStore.styles[scope];
  if (tab === 'entity') return assetStore.entities[scope];
  return [];
});

const openInsertCharModal = (charName) => {
  assetStore.insertCharData.name = charName;
  assetStore.insertCharData.entrance = "";
  uiStore.modals.insertChar = true;
};
</script>

<template>
  <div class="flex flex-col h-full animate-[fadeIn_0.2s]">
    <!-- 局内/全局 切换 -->
    <div class="flex bg-slate-900 rounded-lg p-1 border border-slate-700 shadow-inner mb-4 shrink-0">
      <button @click="uiStore.assetScope = 'local'" :class="uiStore.assetScope==='local'?'bg-slate-700 text-white shadow':'text-slate-400 hover:text-slate-200'" class="flex-1 py-1.5 rounded text-xs font-bold transition">🛡️ 本局专属</button>
      <button @click="uiStore.assetScope = 'global'" :class="uiStore.assetScope==='global'?'bg-slate-700 text-white shadow':'text-slate-400 hover:text-slate-200'" class="flex-1 py-1.5 rounded text-xs font-bold transition">🌐 全局图鉴</button>
    </div>
    
    <!-- 搜索与工具栏 -->
    <div class="flex gap-2 mb-4 shrink-0">
      <div class="flex-1 relative">
        <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-xs">🔍</span>
        <input v-model="searchKeyword" class="w-full bg-slate-800 border border-slate-600 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 outline-none focus:border-indigo-500" placeholder="搜索名称或标签..." />
      </div>
      <button class="w-8 h-8 bg-slate-800 border border-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-amber-400 transition" title="收藏">⭐</button>
      <button class="w-8 h-8 bg-slate-800 border border-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-indigo-400 transition" title="标签过滤">🏷️</button>
      <button class="px-2 h-8 bg-emerald-600/20 text-emerald-400 border border-emerald-700/50 rounded-lg hover:bg-emerald-600 hover:text-white transition text-xs font-bold whitespace-nowrap">+ 新建</button>
    </div>
    
    <!-- 资产卡片列表 -->
    <div class="space-y-3 pb-8">
       <div v-for="item in currentList" :key="item.name" class="bg-aw_panel border border-slate-700 p-3 rounded-xl hover:border-indigo-500 transition group shadow flex flex-col gap-2 relative overflow-hidden">
         <div v-if="item.status" class="absolute right-0 top-0 bg-rose-900/80 text-rose-200 text-[9px] px-2 py-0.5 rounded-bl-lg">{{ item.status }}</div>
         <h4 class="text-sm font-bold text-slate-200 group-hover:text-indigo-400 transition">{{ item.name }}</h4>
         <div class="flex flex-wrap gap-1">
           <span v-for="t in item.tags" :key="t" class="bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded text-[9px] border border-slate-700">{{ t }}</span>
         </div>
         <p class="text-xs text-slate-500 line-clamp-2 mt-1 leading-relaxed">{{ item.desc }}</p>
         
         <div class="mt-2 flex gap-2 border-t border-slate-800 pt-2 opacity-0 group-hover:opacity-100 transition-opacity">
           <button class="flex-1 bg-slate-800 hover:bg-slate-700 text-[10px] py-1.5 rounded font-bold text-slate-300">✏️ 编辑</button>
           <button v-if="uiStore.assetScope==='global' && uiStore.rightTab==='character'" @click="openInsertCharModal(item.name)" class="flex-1 bg-indigo-900/50 hover:bg-indigo-600 text-[10px] py-1.5 rounded font-bold text-indigo-300 hover:text-white border border-indigo-700/50">⬇️ 安排登场</button>
           <button v-else-if="uiStore.assetScope==='global'" class="flex-1 bg-indigo-900/50 hover:bg-indigo-600 text-[10px] py-1.5 rounded font-bold text-indigo-300 hover:text-white border border-indigo-700/50">⬇️ 载入局内</button>
           <button v-if="uiStore.assetScope==='local'" class="flex-1 bg-emerald-900/50 hover:bg-emerald-600 text-[10px] py-1.5 rounded font-bold text-emerald-300 hover:text-white border border-emerald-700/50">⬆️ 提取全局</button>
         </div>
       </div>
    </div>
  </div>
</template>