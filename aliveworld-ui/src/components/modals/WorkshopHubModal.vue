<script setup>
import { computed, onMounted, ref } from 'vue';
import { assetStore } from '../../store/assetStore';
import { gameStore } from '../../store/gameStore';
import { uiStore } from '../../store/uiStore';
import { createEntityEditorForm } from '../../utils/entityForm';

const type = ref('worldbooks');
const scope = ref(gameStore.sessionId ? 'local' : 'global');
const search = ref('');
const types = [
  { id: 'worldbooks', icon: '🌍', label: '世界书', note: '讨论、拓展和演化世界设定' },
  { id: 'characters', icon: '🎭', label: '角色卡', note: '共同设计人物与登场方式' },
  { id: 'styles', icon: '📜', label: '文风卡', note: '整理可执行的写作规范' },
  { id: 'entities', icon: '👾', label: '实体卡', note: '设计长期动机、机制与计划' },
  { id: 'preferences', icon: '🪞', label: '偏好卡', note: '探索、修正和平衡体验偏好' },
];
const storeKey = { worldbooks: 'worlds', characters: 'characters', styles: 'styles', entities: 'entities' };
const assets = computed(() => {
  if (type.value === 'preferences') return [];
  const items = assetStore[storeKey[type.value]]?.[scope.value] || [];
  const keyword = search.value.trim().toLowerCase();
  return keyword
    ? items.filter(item => [item.name, ...(item.tags || [])].join(' ').toLowerCase().includes(keyword))
    : items;
});
const activeType = computed(() => types.find(item => item.id === type.value));

onMounted(async () => {
  await assetStore.fetchAssets();
  if (gameStore.sessionId) await assetStore.fetchLocalAssets(gameStore.sessionId);
});

function close() {
  uiStore.modals.workshopHub = false;
}

function openPreference() {
  close();
  uiStore.modals.preferenceWorkshop = true;
}

function openAsset(item) {
  const sessionId = scope.value === 'local' ? gameStore.sessionId : '';
  if (type.value === 'worldbooks') {
    uiStore.workshopWorldbookName = item.name;
    uiStore.workshopSessionId = sessionId;
    close();
    uiStore.modals.worldbookWorkshop = true;
    return;
  }
  uiStore.workshopAssetType = type.value;
  uiStore.workshopAssetName = item.name;
  uiStore.workshopAssetSessionId = sessionId;
  close();
  uiStore.modals.assetWorkshop = true;
}

function createAsset() {
  if (type.value === 'preferences') return;
  if (scope.value !== 'global') return uiStore.showToast('局内资产来自当前存档，请先创建全局资产再载入本局', 'error');
  const assetType = type.value;
  uiStore.editorData = {
    type: assetType, name: '', isNew: true,
    form: {
      name: '', tags: '', desc: '', overview: '', axiomsText: '', starting_scene: '',
      entries: [], is_active: true, is_player: false, portrait: null,
      ...(assetType === 'entities' ? createEntityEditorForm() : {})
    }
  };
  close();
  uiStore.modals.assetEditor = true;
}
</script>

<template>
  <div class="fixed inset-0 z-[92] flex items-center justify-center bg-black/85 p-4 backdrop-blur-sm">
    <div class="flex h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-cyan-800/70 bg-slate-950 shadow-2xl">
      <header class="flex items-center justify-between border-b border-slate-800 px-5 py-4">
        <div><h2 class="font-bold text-cyan-300">🧰 AliveWorld 总工坊</h2><p class="mt-1 text-[10px] text-slate-500">选择创作对象；所有工坊对话和草稿独立于正文，不推进故事时间</p></div>
        <button class="text-xl text-slate-500 hover:text-white" @click="close">✕</button>
      </header>
      <div class="grid min-h-0 flex-1 grid-cols-[220px_1fr]">
        <nav class="space-y-2 border-r border-slate-800 bg-slate-900/50 p-3">
          <button v-for="item in types" :key="item.id" class="w-full rounded-xl border p-3 text-left transition" :class="type===item.id?'border-cyan-700 bg-cyan-950/35':'border-transparent text-slate-400 hover:bg-slate-800'" @click="type=item.id; search=''">
            <div class="text-sm font-bold"><span class="mr-2">{{ item.icon }}</span>{{ item.label }}</div>
            <p class="mt-1 text-[10px] leading-relaxed text-slate-500">{{ item.note }}</p>
          </button>
        </nav>
        <main class="flex min-h-0 flex-col p-5">
          <div class="mb-4 flex items-center justify-between gap-4">
            <div><h3 class="font-bold text-slate-200">{{ activeType.icon }} {{ activeType.label }}工坊</h3><p class="mt-1 text-xs text-slate-500">{{ activeType.note }}</p></div>
            <div v-if="type!=='preferences'" class="flex items-center gap-2">
              <div class="flex rounded-lg border border-slate-700 bg-slate-900 p-1 text-xs">
                <button class="rounded px-3 py-1.5" :class="scope==='global'?'bg-cyan-800 text-white':'text-slate-500'" @click="scope='global'">全局资产</button>
                <button class="rounded px-3 py-1.5 disabled:opacity-30" :disabled="!gameStore.sessionId" :class="scope==='local'?'bg-cyan-800 text-white':'text-slate-500'" @click="scope='local'">本局专属</button>
              </div>
              <button v-if="scope==='global'" class="rounded-lg bg-emerald-800 px-3 py-2 text-xs font-bold text-white" @click="createAsset">＋ 新建</button>
            </div>
          </div>

          <template v-if="type==='preferences'">
            <div class="flex flex-1 items-center justify-center">
              <div class="max-w-lg rounded-2xl border border-fuchsia-800/60 bg-fuchsia-950/20 p-8 text-center">
                <div class="text-4xl">🪞</div><h4 class="mt-3 font-bold text-fuchsia-200">用户偏好协作工坊</h4>
                <p class="mt-2 text-xs leading-relaxed text-slate-400">结合玩家自述和已采集证据探索偏好，保留竞争解释；正式偏好卡只在发布草稿后改变。</p>
                <button class="mt-5 rounded-lg bg-fuchsia-700 px-5 py-2 text-sm font-bold text-white" @click="openPreference">进入偏好工坊</button>
              </div>
            </div>
          </template>
          <template v-else>
            <input v-model="search" class="mb-4 rounded-xl border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm text-slate-200" placeholder="搜索名称或标签……" />
            <div class="grid min-h-0 flex-1 auto-rows-max grid-cols-2 gap-3 overflow-y-auto pr-2 custom-scrollbar xl:grid-cols-3">
              <button v-for="item in assets" :key="item.name" class="rounded-xl border border-slate-700 bg-slate-900/60 p-4 text-left hover:border-cyan-700 hover:bg-cyan-950/20" @click="openAsset(item)">
                <div class="truncate text-sm font-bold text-slate-200">{{ item.name }}</div>
                <div class="mt-2 flex flex-wrap gap-1"><span v-for="tag in item.tags" :key="tag" class="rounded bg-slate-800 px-1.5 py-0.5 text-[9px] text-slate-400">{{ tag }}</span></div>
                <p class="mt-3 line-clamp-3 text-[10px] leading-relaxed text-slate-500">{{ item.desc || '进入工坊，与 AI 共同设计此资产。' }}</p>
              </button>
              <p v-if="!assets.length" class="col-span-full rounded-xl border border-dashed border-slate-700 p-10 text-center text-xs text-slate-500">{{ scope==='local'?'本局尚无此类资产':'没有可用资产，请先在资产栏创建一张卡片' }}</p>
            </div>
          </template>
        </main>
      </div>
    </div>
  </div>
</template>
