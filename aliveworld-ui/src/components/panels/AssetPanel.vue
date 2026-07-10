<!-- src/components/panels/AssetPanel.vue -->
<!-- 100% 完整底稿 (请直接覆盖原文件) -->

<script setup>
import { computed, ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { configStore } from '../../store/configStore';
import { assetApi } from '../../api/assetApi';
import { gameApi } from '../../api/gameApi';
import { gameStore } from '../../store/gameStore';
import { ENTITY_VISIBILITIES, normalizeEntityVisibility, projectLocalEntity } from '../../utils/entityVisibility';

const searchKeyword = ref("");
const confirmDeleteId = ref(null);
const entityVisibility = computed(() => normalizeEntityVisibility(configStore.settings.entityVisibility));
const canManageLocalEntity = computed(() => entityVisibility.value === ENTITY_VISIBILITIES.full);

const currentList = computed(() => {
  const tab = uiStore.rightTab;
  const scope = uiStore.assetScope;
  let list = [];
  if (tab === 'world') list = assetStore.worlds[scope] || [];
  if (tab === 'character') list = assetStore.characters[scope] || [];
  if (tab === 'style') list = assetStore.styles[scope] || [];
  if (tab === 'entity') list = assetStore.entities[scope] || [];
  if (tab === 'entity' && scope === 'local') {
    list = list.map(item => projectLocalEntity(item, entityVisibility.value)).filter(Boolean);
  }
  
  if (!searchKeyword.value) return list;
  return list.filter(item => item.name.toLowerCase().includes(searchKeyword.value.toLowerCase()));
});

const getApiType = () => {
  const map = { world: 'worldbooks', character: 'characters', style: 'styles', entity: 'entities' };
  return map[uiStore.rightTab];
};

const openNewAsset = () => {
  uiStore.editorData = { 
    type: getApiType(), name: '', isNew: true,
    form: { name: '', tags: '', desc: '', global_setting: '', starting_scene: '', entries: [], is_active: true, is_player: false }
  };
  uiStore.modals.assetEditor = true;
};

const openEditAsset = async (name) => {
  try {
    let p = {};
    if (uiStore.assetScope === 'local') {
      const item = currentList.value.find(i => i.name === name);
      if (item) p = JSON.parse(JSON.stringify(item));
      p.tags = (p.tags || []).filter(t => t !== '本局独有');
    } else {
      const res = await assetApi.getAssetDetail(getApiType(), name);
      p = res.parsed || {};
    }

    uiStore.editorData = { 
      type: getApiType(), name: name, isNew: false,
      form: {
        name: p.name || name,
        tags: Array.isArray(p.tags) ? p.tags.join(', ') : (p.tags || ''),
        desc: p.description || p.content || p.motive || '',
        global_setting: p.global_setting || '',
        starting_scene: p.starting_scene || '',
        entries: p.entries || [],
        is_active: p.is_active !== false,
        is_player: p.is_player || false // 🚀 问题 3
      }
    };
    uiStore.modals.assetEditor = true;
  } catch(e) { uiStore.showToast("读取资产详情失败", "error"); }
};

const executeDelete = async (name) => {
  try {
    if (uiStore.assetScope === 'local') {
      if (!gameStore.sessionId) return uiStore.showToast("当前无激活的时间线", "error");
      await gameApi.deleteLocalAsset(gameStore.sessionId, getApiType(), name);
      await assetStore.fetchLocalAssets(gameStore.sessionId);
    } else {
      await assetApi.deleteAsset(getApiType(), name);
      await assetStore.fetchAssets();
    }
    confirmDeleteId.value = null;
    uiStore.showToast("资产已移除");
  } catch(e) { uiStore.showToast("操作失败：" + e.message, "error"); }
};

const pullAssetToLocal = async (name) => {
  if (!gameStore.sessionId) return uiStore.showToast("⚠️ 请先开启或载入一个命运时间线！", "error");
  try {
    await gameApi.pullAsset(gameStore.sessionId, { asset_type: getApiType(), asset_name: name });
    await assetStore.fetchLocalAssets(gameStore.sessionId);
    uiStore.showToast(`[${name}] 已成功载入本局`);
  } catch(e) { uiStore.showToast("拉取失败：" + e.message, "error"); }
};

// 🚀 问题 1：另存为逻辑
const pushToGlobal = async (item) => {
  const defaultName = `${item.name}_${gameStore.currentSaveName}`;
  const newName = window.prompt("推送至全局图鉴：\n请输入保存名称（覆盖同名或另存为）", defaultName);
  
  if (!newName) return; 

  try {
    const payload = JSON.parse(JSON.stringify(item));
    payload.name = newName;
    payload.tags = (payload.tags || []).filter(t => t !== '本局独有');
    delete payload.is_active; 
    
    await assetApi.saveAsset(getApiType(), newName, "", payload);
    await assetStore.fetchAssets();
    uiStore.showToast(`[${newName}] 已安全记录至全局图鉴`);
  } catch(e) {
    uiStore.showToast("推送失败: " + e.message, "error");
  }
};

const toggleActive = async (item) => {
  if (!gameStore.sessionId) return;
  try {
    const payload = JSON.parse(JSON.stringify(item));
    payload.is_active = payload.is_active === false ? true : false;
    payload.tags = (payload.tags || []).filter(t => t !== '本局独有');
    
    await gameApi.updateLocalAsset(gameStore.sessionId, getApiType(), item.name, payload);
    await assetStore.fetchLocalAssets(gameStore.sessionId);
  } catch(e) { uiStore.showToast("切换失败", "error"); }
};

const openInsertCharModal = (charName) => {
  assetStore.insertCharData.name = charName;
  assetStore.insertCharData.entrance = "";
  uiStore.modals.insertChar = true;
};
</script>

<template>
  <div class="flex flex-col h-full animate-[fadeIn_0.2s]">
    <div class="flex bg-slate-900 rounded-lg p-1 border border-slate-700 shadow-inner mb-4 shrink-0">
      <button @click="uiStore.assetScope = 'local'" :class="uiStore.assetScope==='local'?'bg-slate-700 text-white shadow':'text-slate-400 hover:text-slate-200'" class="flex-1 py-1.5 rounded text-xs font-bold transition">🛡️ 本局专属</button>
      <button @click="uiStore.assetScope = 'global'" :class="uiStore.assetScope==='global'?'bg-slate-700 text-white shadow':'text-slate-400 hover:text-slate-200'" class="flex-1 py-1.5 rounded text-xs font-bold transition">🌐 全局图鉴</button>
    </div>
    
    <div class="flex gap-2 mb-4 shrink-0">
      <div class="flex-1 relative">
        <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-xs">🔍</span>
        <input v-model="searchKeyword" class="w-full bg-slate-800 border border-slate-600 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 outline-none focus:border-indigo-500" placeholder="搜索名称或标签..." />
      </div>
      <button v-if="uiStore.assetScope==='global'" @click="openNewAsset" class="px-2 h-8 bg-emerald-600/20 text-emerald-400 border border-emerald-700/50 rounded-lg hover:bg-emerald-600 hover:text-white transition text-xs font-bold whitespace-nowrap">+ 新建</button>
    </div>
    
    <div v-if="currentList.length === 0" class="text-center text-slate-500 text-xs mt-10">当前区域暂无资产记录</div>

    <div class="space-y-3 pb-8">
       <div v-for="item in currentList" :key="item.name" class="bg-aw_panel border border-slate-700 p-3 rounded-xl hover:border-indigo-500 transition group shadow flex flex-col gap-2 relative overflow-hidden" :class="item.is_active === false ? 'opacity-60 grayscale' : ''">
         
         <div class="flex justify-between items-start">
            <h4 class="text-sm font-bold text-slate-200 group-hover:text-indigo-400 transition flex items-center gap-2">
              <span v-if="item.is_player" class="text-amber-400" title="玩家化身">👑</span>
              {{ item.name }}
              <button v-if="uiStore.assetScope==='local'" @click.stop="toggleActive(item)" class="text-xs hover:scale-110 transition" :title="item.is_active === false ? '点击启用' : '点击封存'">
                {{ item.is_active === false ? '🔴' : '🟢' }}
              </button>
            </h4>
         </div>
         
         <div class="flex flex-wrap gap-1">
           <span v-for="t in item.tags" :key="t" class="bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded text-[9px] border border-slate-700">{{ t }}</span>
         </div>
         <p class="text-xs text-slate-500 line-clamp-2 mt-1 leading-relaxed">{{ item.desc }}</p>
         
         <div class="mt-2 flex gap-2 border-t border-slate-800 pt-2 opacity-0 group-hover:opacity-100 transition-opacity">
           <button v-if="uiStore.assetScope === 'global' || canManageLocalEntity" @click="openEditAsset(item.name)" class="flex-1 bg-slate-800 hover:bg-slate-700 text-[10px] py-1.5 rounded font-bold text-slate-300">✏️ {{ uiStore.assetScope === 'local' ? '微调' : '编辑' }}</button>
           <button v-if="uiStore.assetScope==='global'" @click="pullAssetToLocal(item.name)" class="flex-1 bg-indigo-900/50 hover:bg-indigo-600 text-[10px] py-1.5 rounded font-bold text-indigo-300 hover:text-white border border-indigo-700/50">⬇️ 载入局内</button>
           <button v-if="uiStore.assetScope==='local' && canManageLocalEntity" @click="pushToGlobal(item)" class="flex-1 bg-emerald-900/50 hover:bg-emerald-600 text-[10px] py-1.5 rounded font-bold text-emerald-300 hover:text-white border border-emerald-700/50">⬆️ 推送全局</button>

           <button v-if="(uiStore.assetScope === 'global' || canManageLocalEntity) && confirmDeleteId !== item.name" @click="confirmDeleteId = item.name" class="px-2 bg-rose-900/30 hover:bg-rose-600 text-rose-400 hover:text-white rounded text-xs border border-rose-900/50">🗑</button>
           <div v-else-if="uiStore.assetScope === 'global' || canManageLocalEntity" class="flex gap-1">
             <button @click="executeDelete(item.name)" class="px-2 bg-rose-700 hover:bg-rose-600 text-white rounded text-[10px] font-bold border border-rose-500">{{ uiStore.assetScope==='local' ? '移除' : '粉碎' }}</button>
             <button @click="confirmDeleteId = null" class="px-2 bg-slate-700 hover:bg-slate-600 text-slate-300 hover:text-white rounded text-[10px] border border-slate-600">取消</button>
           </div>
         </div>
       </div>
    </div>
  </div>
</template>
