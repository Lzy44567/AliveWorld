<script setup>
import { uiStore } from '../../store/uiStore';
import AssetPanel from '../panels/AssetPanel.vue';
import SavesPanel from '../panels/SavesPanel.vue';
import LocalEditPanel from '../panels/LocalEditPanel.vue';
import EntityRuntimeToggle from '../controls/EntityRuntimeToggle.vue';
</script>

<template>
  <aside :class="uiStore.rightDrawerOpen ? 'w-[400px]' : 'w-0'" class="bg-aw_panel border-l border-slate-700 flex flex-col transition-all duration-300 z-30 shadow-2xl overflow-hidden relative shrink-0">
    
    <!-- 顶级 Tab 导航栏 -->
    <div class="flex text-lg border-b border-slate-700 bg-slate-900 min-w-[400px] shrink-0">
      <button @click="uiStore.rightTab = 'saves'" :class="uiStore.rightTab==='saves'?'text-emerald-400 border-b-2 border-emerald-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 transition" title="故事线/存档">📂</button>
      <button @click="uiStore.rightTab = 'character'" :class="uiStore.rightTab==='character'?'text-indigo-400 border-b-2 border-indigo-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 transition" title="角色卡库">🎭</button>
      <button @click="uiStore.rightTab = 'world'" :class="uiStore.rightTab==='world'?'text-amber-400 border-b-2 border-amber-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 transition" title="世界法则">🌍</button>
      <button @click="uiStore.rightTab = 'style'" :class="uiStore.rightTab==='style'?'text-rose-400 border-b-2 border-rose-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 transition" title="文风卡">📜</button>
      <button @click="uiStore.rightTab = 'entity'" :class="uiStore.rightTab==='entity'?'text-purple-400 border-b-2 border-purple-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 transition" title="暗流实体">👾</button>
      <button @click="uiStore.rightTab = 'local_edit'" :class="uiStore.rightTab==='local_edit'?'text-cyan-400 border-b-2 border-cyan-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 transition" title="局内独立设定">⚙️</button>
    </div>

    <!-- 面板内容挂载区 -->
    <div class="flex-1 min-h-0 overflow-hidden bg-slate-900/30 min-w-[400px] p-4 relative flex flex-col">
      <div class="mb-3 flex min-h-7 items-center justify-between">
        <h2 class="text-sm font-bold text-slate-200 tracking-wider">{{ uiStore.tabTitles[uiStore.rightTab] || "数据面板" }}</h2>
        <EntityRuntimeToggle v-if="uiStore.rightTab === 'entity'" />
      </div>
      
      <!-- 动态呼叫组件 -->
      <AssetPanel v-if="['character', 'world', 'style', 'entity'].includes(uiStore.rightTab)" />
      <div v-else class="flex flex-1 min-h-0 flex-col overflow-hidden">
        <SavesPanel v-if="uiStore.rightTab === 'saves'" />
        <LocalEditPanel v-else-if="uiStore.rightTab === 'local_edit'" />
      </div>
    </div>
  </aside>
</template>
