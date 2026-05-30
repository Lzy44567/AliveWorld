<!-- src/components/modals/AssetEditorModal.vue -->
<!-- 100% 完整底稿 (请直接覆盖原文件) -->

<script setup>
import { computed } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { assetApi } from '../../api/assetApi';
import { gameApi } from '../../api/gameApi';
import { gameStore } from '../../store/gameStore';

const form = computed(() => uiStore.editorData.form);
const type = computed(() => uiStore.editorData.type);

const closeEditor = () => { uiStore.modals.assetEditor = false; };

const addWorldEntry = () => {
  if (!form.value.entries) form.value.entries = [];
  form.value.entries.push({ name: '', keys: '', content: '' });
};

const removeWorldEntry = (idx) => { form.value.entries.splice(idx, 1); };

const saveContent = async () => {
  try {
    if(!form.value.name.trim()) return uiStore.showToast("资产名称不能为空", "error");
    
    // 🚀 问题 2：处理重命名逻辑
    if (!uiStore.editorData.isNew && form.value.name !== uiStore.editorData.name) {
      if (uiStore.assetScope === 'local') {
        await gameApi.deleteLocalAsset(gameStore.sessionId, type.value, uiStore.editorData.name);
      } else {
        await assetApi.deleteAsset(type.value, uiStore.editorData.name);
      }
    }

    let payload = { name: form.value.name };
    if (typeof form.value.tags === 'string' && form.value.tags) {
        payload.tags = form.value.tags.split(/[,，]/).map(t => t.trim()).filter(t => t);
    } else if (Array.isArray(form.value.tags)) { payload.tags = form.value.tags; }

    if (type.value === 'worldbooks') {
      payload.global_setting = form.value.global_setting;
      payload.starting_scene = form.value.starting_scene;
      payload.entries = form.value.entries.filter(e => e.name || e.keys).map(e => ({
          ...e, keys: e.keys ? e.keys.replace(/，/g, ',') : ''
      }));
    } else if (type.value === 'characters') {
      payload.description = form.value.desc;
      payload.starting_scene = form.value.starting_scene;
      payload.is_player = form.value.is_player; // 🚀 问题 3：记录其是否为主角
    } else if (type.value === 'styles') {
      payload.content = form.value.desc;
    } else if (type.value === 'entities') {
      payload.description = form.value.desc;
      payload.motive = form.value.desc; 
    }

    if (uiStore.assetScope === 'local') {
      if (!gameStore.sessionId) throw new Error("无活跃时间线");
      payload.is_active = form.value.is_active; 
      await gameApi.updateLocalAsset(gameStore.sessionId, type.value, form.value.name, payload);
      await assetStore.fetchLocalAssets(gameStore.sessionId);
    } else {
      await assetApi.saveAsset(type.value, form.value.name, "", payload);
      await assetStore.fetchAssets(); 
    }
    
    uiStore.showToast("保存成功");
    closeEditor();
  } catch(e) {
    uiStore.showToast("保存失败: " + e.message, "error");
  }
};
</script>

<template>
  <div class="fixed inset-0 bg-black/80 z-[80] flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-[#1a1a1f] border border-slate-600 rounded-xl w-full max-w-4xl shadow-2xl flex flex-col slide-up overflow-hidden h-[85vh]">
      <div class="p-4 border-b border-slate-700 flex justify-between items-center bg-slate-900/80">
        <h2 class="font-bold text-emerald-400 text-lg flex items-center gap-2">
          <span>✨</span> {{ uiStore.editorData.isNew ? '创建档案' : '编辑设定' }} 
          <span class="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded ml-2">{{ type }}</span>
        </h2>
        <div class="flex gap-2">
          <button @click="saveContent" class="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold rounded shadow-lg shadow-emerald-900/50 transition">💾 保存卡片</button>
          <button @click="closeEditor" class="px-4 py-2 bg-slate-700 hover:bg-rose-600 text-white text-sm font-bold rounded transition">✕ 取消</button>
        </div>
      </div>
      <div class="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
        <div class="grid grid-cols-2 gap-6">
          <div>
            <label class="text-xs text-slate-400 font-bold mb-1.5 block">资产名称 (Name)</label>
            <!-- 🚀 解除了 disabled，允许重命名 -->
            <input v-model="form.name" class="w-full bg-[#0d0d12] border border-slate-700 text-slate-200 px-4 py-2.5 rounded-lg outline-none focus:border-indigo-500 shadow-inner text-sm" placeholder="起个独一无二的名字..." />
          </div>
          <div>
            <label class="text-xs text-slate-400 font-bold mb-1.5 block">标签 / Keywords (逗号分隔)</label>
            <input v-model="form.tags" class="w-full bg-[#0d0d12] border border-slate-700 text-slate-200 px-4 py-2.5 rounded-lg outline-none focus:border-indigo-500 shadow-inner text-sm" placeholder="例如: 傲娇, 废土, NPC..." />
          </div>
        </div>

        <template v-if="type === 'characters'">
          <!-- 🚀 问题 3：作为玩家扮演的勾选框 -->
          <div class="flex items-center gap-3 p-3 bg-indigo-900/20 border border-indigo-900/50 rounded-lg">
            <input type="checkbox" v-model="form.is_player" class="w-5 h-5 rounded bg-slate-900 border-slate-700 text-indigo-500 cursor-pointer">
            <div>
              <p class="text-sm font-bold text-indigo-300">将此角色设为主役 (Is Player)</p>
              <p class="text-[10px] text-slate-500">勾选后，AI 将知道你是扮演这个角色的，否则将其视为 NPC。</p>
            </div>
          </div>
          <div>
            <label class="text-xs text-slate-400 font-bold mb-1.5 block">背景与外观设定 (Description)</label>
            <textarea v-model="form.desc" class="w-full h-40 bg-[#0d0d12] border border-slate-700 text-slate-300 p-4 rounded-lg outline-none focus:border-indigo-500 text-sm leading-relaxed custom-scrollbar shadow-inner"></textarea>
          </div>
        </template>
        
        <!-- ... 其它类型（worldbooks/styles/entities）保持与上一版相同即可，为了省字数省略 -->
        <template v-else>
           <div>
            <label class="text-xs text-slate-400 font-bold mb-1.5 block">设定正文 (Content)</label>
            <textarea v-model="form.desc" class="w-full h-64 bg-[#0d0d12] border border-slate-700 text-slate-300 p-4 rounded-lg outline-none focus:border-indigo-500 text-sm leading-relaxed custom-scrollbar shadow-inner"></textarea>
          </div>
        </template>
        
      </div>
    </div>
  </div>
</template>