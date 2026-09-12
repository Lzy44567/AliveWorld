<script setup>
import { uiStore } from '../../store/uiStore';
import SavesPanel from '../panels/SavesPanel.vue';
import LocalEditPanel from '../panels/LocalEditPanel.vue';
import AssetPanel from '../panels/AssetPanel.vue';
import EntityRuntimeToggle from '../controls/EntityRuntimeToggle.vue';

const tabs = [
  { id: 'saves', icon: '📂', label: '故事线' },
  { id: 'world', icon: '🌍', label: '世界书' },
  { id: 'character', icon: '🎭', label: '角色' },
  { id: 'style', icon: '📜', label: '文风' },
  { id: 'entity', icon: '👾', label: '暗流' },
  { id: 'local_edit', icon: '⚙️', label: '本局' },
];
</script>

<template>
  <aside :class="uiStore.rightDrawerOpen ? 'w-[400px]' : 'w-0'" class="bg-aw_panel border-l border-slate-700 flex flex-col transition-all duration-300 z-30 shadow-2xl overflow-hidden relative shrink-0">
    
    <!-- 顶级 Tab 导航栏 -->
    <div class="grid grid-cols-6 border-b border-slate-700 bg-slate-900 min-w-[400px] shrink-0">
      <button v-for="tab in tabs" :key="tab.id" :data-testid="`tab-${tab.id}`" @click="uiStore.rightTab = tab.id" :class="uiStore.rightTab===tab.id?'text-cyan-300 border-b-2 border-cyan-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex min-w-0 flex-col items-center gap-1 px-1 py-2 text-[9px] font-bold transition" :title="uiStore.tabTitles[tab.id]">
        <span class="text-base leading-none">{{ tab.icon }}</span><span class="truncate">{{ tab.label }}</span>
      </button>
    </div>

    <!-- 面板内容挂载区 -->
    <div class="flex-1 min-h-0 overflow-hidden bg-slate-900/30 min-w-[400px] p-4 relative flex flex-col">
      <div class="mb-3 flex min-h-7 items-center justify-between gap-2">
        <h2 class="text-sm font-bold text-slate-200 tracking-wider">{{ uiStore.tabTitles[uiStore.rightTab] || "数据面板" }}</h2>
        <div v-if="uiStore.rightTab==='entity'" class="flex items-center gap-2">
          <button v-if="uiStore.assetScope==='local'" @click="uiStore.ledgerSourceFilter=''; uiStore.modals.causalLedger=true" class="rounded border border-fuchsia-800 bg-fuchsia-950/40 px-2 py-1 text-[9px] text-fuchsia-300">因果账本</button>
          <EntityRuntimeToggle />
        </div>
      </div>
      
      <!-- 动态呼叫组件 -->
      <div class="flex flex-1 min-h-0 flex-col overflow-hidden">
        <SavesPanel v-if="uiStore.rightTab === 'saves'" />
        <LocalEditPanel v-else-if="uiStore.rightTab === 'local_edit'" />
        <AssetPanel v-else-if="['world','character','style','entity'].includes(uiStore.rightTab)" />
      </div>
    </div>
  </aside>
</template>
