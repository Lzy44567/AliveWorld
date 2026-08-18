<script setup>
import { uiStore } from '../../store/uiStore';
import SavesPanel from '../panels/SavesPanel.vue';
import LocalEditPanel from '../panels/LocalEditPanel.vue';
</script>

<template>
  <aside :class="uiStore.rightDrawerOpen ? 'w-[400px]' : 'w-0'" class="bg-aw_panel border-l border-slate-700 flex flex-col transition-all duration-300 z-30 shadow-2xl overflow-hidden relative shrink-0">
    
    <!-- 顶级 Tab 导航栏 -->
    <div class="flex text-lg border-b border-slate-700 bg-slate-900 min-w-[400px] shrink-0">
      <button data-testid="tab-saves" @click="uiStore.rightTab = 'saves'" :class="uiStore.rightTab==='saves'?'text-emerald-400 border-b-2 border-emerald-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 text-xs font-bold transition" title="故事线/存档">📂 故事线</button>
      <button @click="uiStore.rightTab = 'local_edit'" :class="uiStore.rightTab==='local_edit'?'text-cyan-400 border-b-2 border-cyan-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 text-xs font-bold transition" title="局内独立设定">⚙️ 本局设置</button>
    </div>

    <!-- 面板内容挂载区 -->
    <div class="flex-1 min-h-0 overflow-hidden bg-slate-900/30 min-w-[400px] p-4 relative flex flex-col">
      <div class="mb-3 flex min-h-7 items-center justify-between">
        <h2 class="text-sm font-bold text-slate-200 tracking-wider">{{ uiStore.tabTitles[uiStore.rightTab] || "数据面板" }}</h2>
      </div>
      
      <!-- 动态呼叫组件 -->
      <div class="flex flex-1 min-h-0 flex-col overflow-hidden">
        <SavesPanel v-if="uiStore.rightTab === 'saves'" />
        <LocalEditPanel v-else-if="uiStore.rightTab === 'local_edit'" />
      </div>
    </div>
  </aside>
</template>
