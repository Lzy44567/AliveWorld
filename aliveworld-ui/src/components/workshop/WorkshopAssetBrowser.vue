<script setup>
import { onMounted, watch } from 'vue';
import { createEntityEditorForm } from '../../utils/entityForm';
import { WORKSHOP_TYPES, workshopStore } from '../../store/workshopStore';
import { uiStore } from '../../store/uiStore';
import { gameStore } from '../../store/gameStore';

onMounted(() => workshopStore.initialize());
watch(() => gameStore.sessionId, () => workshopStore.syncStoryScope());

function createAsset() {
  if (workshopStore.scope !== 'global' || workshopStore.type === 'preferences') return;
  const type = workshopStore.type;
  uiStore.editorData = {
    type, name: '', isNew: true,
    form: {
      name: '', tags: '', desc: '', overview: '', axiomsText: '', starting_scene: '',
      entries: [], is_active: true, is_player: false, portrait: null,
      ...(type === 'entities' ? createEntityEditorForm() : {})
    }
  };
  uiStore.modals.assetEditor = true;
}
</script>

<template>
  <aside :class="uiStore.rightDrawerOpen ? 'w-[400px]' : 'w-0'" class="relative z-30 flex shrink-0 flex-col overflow-hidden border-l border-cyan-950 bg-aw_panel shadow-2xl transition-all duration-300">
    <div class="min-w-[400px] border-b border-slate-800 bg-slate-900 p-2">
      <div class="grid grid-cols-5 gap-1">
        <button v-for="item in WORKSHOP_TYPES" :key="item.id" class="rounded-lg px-2 py-2 text-center transition" :class="workshopStore.type===item.id?'bg-cyan-900/60 text-cyan-200':'text-slate-500 hover:bg-slate-800'" :title="item.label" @click="workshopStore.selectType(item.id)">
          <span class="block text-lg">{{ item.icon }}</span><span class="text-[9px]">{{ item.label }}</span>
        </button>
      </div>
    </div>
    <div class="flex min-h-0 min-w-[400px] flex-1 flex-col p-4">
      <div class="mb-3 flex items-center justify-between">
        <div><h2 class="text-sm font-bold text-cyan-200">{{ workshopStore.typeInfo.label }}资产</h2><p class="mt-1 text-[10px] text-slate-500">选择创作对象，不会载入正文</p></div>
        <div class="flex gap-1">
          <button data-testid="open-world-package-builder" class="rounded border border-cyan-800 bg-cyan-950/40 px-2 py-1 text-[10px] font-bold text-cyan-200" title="选择已完成的资产并导出本地世界包" @click="uiStore.modals.worldPackageBuilder=true">📦 打包</button>
          <button v-if="workshopStore.type!=='preferences' && workshopStore.scope==='global'" class="rounded bg-emerald-800 px-2 py-1 text-[10px] font-bold text-white" @click="createAsset">＋ 新建</button>
        </div>
      </div>
      <template v-if="workshopStore.type==='preferences'">
        <button class="rounded-xl border p-4 text-left" :class="workshopStore.workshopId?'border-fuchsia-700 bg-fuchsia-950/25':'border-slate-700 bg-slate-900/50 hover:border-fuchsia-800'" @click="workshopStore.start('', 'global')">
          <div class="font-bold text-fuchsia-200">🪞 我的用户偏好卡</div>
          <p class="mt-2 text-[10px] leading-relaxed text-slate-500">结合自述和已采集证据探索、修正与平衡偏好；正式偏好只在发布后变化。</p>
        </button>
      </template>
      <template v-else>
        <div class="mb-3 flex rounded-lg border border-slate-700 bg-slate-900 p-1 text-xs">
          <button class="flex-1 rounded py-1.5" :class="workshopStore.scope==='global'?'bg-cyan-800 text-white':'text-slate-500'" @click="workshopStore.setScope('global')">全局资产</button>
          <button class="flex-1 rounded py-1.5 disabled:opacity-30" :disabled="!workshopStore.hasSession" :class="workshopStore.scope==='local'?'bg-cyan-800 text-white':'text-slate-500'" :title="workshopStore.hasSession ? `只编辑故事线“${workshopStore.localScopeLabel}”的资产副本` : '请先载入故事线'" @click="workshopStore.setScope('local')">当前故事</button>
        </div>
        <div v-if="workshopStore.scope==='local'" class="mb-3 rounded-lg border border-cyan-900/60 bg-cyan-950/20 px-3 py-2 text-[10px] text-cyan-200">
          故事线：<strong>{{ workshopStore.localScopeLabel }}</strong>
          <span class="ml-1 text-slate-500">· 下列资产只属于这条故事线</span>
        </div>
        <input v-model="workshopStore.search" class="mb-3 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200" placeholder="搜索名称或标签……" />
        <div class="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1 custom-scrollbar">
          <button v-for="item in workshopStore.assets" :key="item.name" :data-workshop-asset-name="item.name" class="w-full rounded-xl border p-3 text-left transition" :class="workshopStore.assetName===item.name?'border-cyan-600 bg-cyan-950/30':'border-slate-700 bg-slate-900/55 hover:border-cyan-900'" @click="workshopStore.start(item.name)">
            <div class="truncate text-xs font-bold text-slate-200">{{ item.name }}</div>
            <div v-if="workshopStore.scope==='local'" class="mt-1 text-[9px] text-cyan-400/80">📂 {{ workshopStore.localScopeLabel }}</div>
            <div class="mt-2 flex flex-wrap gap-1"><span v-for="tag in item.tags" :key="tag" class="rounded bg-slate-800 px-1 text-[9px] text-slate-500">{{ tag }}</span></div>
            <p class="mt-2 line-clamp-2 text-[10px] text-slate-500">{{ item.desc }}</p>
          </button>
          <p v-if="!workshopStore.assets.length" class="rounded-lg border border-dashed border-slate-700 p-6 text-center text-xs text-slate-500">当前范围没有可用资产</p>
        </div>
      </template>
    </div>
  </aside>
</template>
