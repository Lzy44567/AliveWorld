<script setup>
import { computed } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { assetApi } from '../../api/assetApi';

const form = computed(() => uiStore.editorData.form);
const type = computed(() => uiStore.editorData.type);

const closeEditor = () => { uiStore.modals.assetEditor = false; };

const addWorldEntry = () => {
  if (!form.value.entries) form.value.entries = [];
  form.value.entries.push({ name: '', keys: '', content: '' });
};

const removeWorldEntry = (idx) => {
  form.value.entries.splice(idx, 1);
};

const saveContent = async () => {
  try {
    if(!form.value.name.trim()) return alert("资产名称不能为空");
    
    let payload = { name: form.value.name };
    
    // 【修复核心】支持中英文逗号混合输入，全部切分
    if (typeof form.value.tags === 'string' && form.value.tags) {
        payload.tags = form.value.tags.split(/[,，]/).map(t => t.trim()).filter(t => t);
    } else if (Array.isArray(form.value.tags)) {
        payload.tags = form.value.tags;
    }

    if (type.value === 'worldbooks') {
      payload.global_setting = form.value.global_setting;
      payload.starting_scene = form.value.starting_scene;
      
      // 【修复核心】强制把词条 keys 里的中文逗号转成英文逗号，以适应 Python 后端死板的 split(',')
      payload.entries = form.value.entries.filter(e => e.name || e.keys).map(e => ({
          ...e,
          keys: e.keys ? e.keys.replace(/，/g, ',') : ''
      }));
    } else if (type.value === 'characters') {
      payload.description = form.value.desc;
      payload.starting_scene = form.value.starting_scene;
    } else if (type.value === 'styles') {
      payload.content = form.value.desc;
    } else if (type.value === 'entities') {
      payload.motive = form.value.motive;
      payload.status = form.value.status;
      payload.description = form.value.desc;
    }

    await assetApi.saveAsset(type.value, form.value.name, "", payload);
    await assetStore.fetchAssets(); 
    closeEditor();
  } catch(e) {
    alert("保存失败: " + e.message);
  }
};
</script>

<!-- template 模板部分与上一版完全一致，此处略去重复以保证核心逻辑清晰，你直接覆盖整个文件，模板就是上一次发你的模板 -->
<template>
  <div class="fixed inset-0 bg-black/80 z-[80] flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-[#1a1a1f] border border-slate-600 rounded-xl w-full max-w-4xl shadow-2xl flex flex-col slide-up overflow-hidden h-[85vh]">
      <div class="p-4 border-b border-slate-700 flex justify-between items-center bg-slate-900/80">
        <h2 class="font-bold text-emerald-400 text-lg flex items-center gap-2">
          <span>✨</span> {{ uiStore.editorData.isNew ? '创建新档案' : '编辑设定' }} 
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
            <input v-model="form.name" class="w-full bg-[#0d0d12] border border-slate-700 text-slate-200 px-4 py-2.5 rounded-lg outline-none focus:border-indigo-500 shadow-inner text-sm" placeholder="起个独一无二的名字..." />
          </div>
          <div>
            <label class="text-xs text-slate-400 font-bold mb-1.5 block">标签 / Keywords (逗号分隔)</label>
            <input v-model="form.tags" class="w-full bg-[#0d0d12] border border-slate-700 text-slate-200 px-4 py-2.5 rounded-lg outline-none focus:border-indigo-500 shadow-inner text-sm" placeholder="例如: 傲娇, 废土, NPC..." />
          </div>
        </div>

        <template v-if="type === 'worldbooks'">
          <div>
            <label class="text-xs text-slate-400 font-bold mb-1.5 block">常驻世界法则 (Global Setting)</label>
            <textarea v-model="form.global_setting" class="w-full h-32 bg-[#0d0d12] border border-slate-700 text-slate-300 p-4 rounded-lg outline-none focus:border-indigo-500 text-sm leading-relaxed custom-scrollbar shadow-inner" placeholder="描述世界的根本运行逻辑..."></textarea>
          </div>
          <div>
            <label class="text-xs text-slate-400 font-bold mb-1.5 block">世界开场白 (Starting Scene)</label>
            <textarea v-model="form.starting_scene" class="w-full h-24 bg-[#0d0d12] border border-slate-700 text-slate-300 p-4 rounded-lg outline-none focus:border-indigo-500 text-sm leading-relaxed custom-scrollbar shadow-inner" placeholder="DM(系统)说出的第一段话..."></textarea>
          </div>
          <div class="border-t border-slate-800 pt-6">
            <div class="flex justify-between items-center mb-4">
              <div>
                <h3 class="text-sm font-bold text-indigo-400">词条矩阵 (Lore Entries)</h3>
                <p class="text-[10px] text-slate-500 mt-1">当对话上下文中出现对应的【触发关键词】时注入给大模型。</p>
              </div>
              <button @click="addWorldEntry" class="px-3 py-1.5 bg-indigo-900/40 text-indigo-300 hover:bg-indigo-600 hover:text-white border border-indigo-800/50 rounded text-xs font-bold transition">+ 新增词条</button>
            </div>
            <div class="space-y-4">
              <div v-for="(entry, idx) in form.entries" :key="idx" class="bg-[#121217] border border-slate-700 p-4 rounded-xl flex gap-4 relative group">
                <button @click="removeWorldEntry(idx)" class="absolute -right-2 -top-2 bg-rose-600 text-white w-6 h-6 rounded-full text-xs opacity-0 group-hover:opacity-100 transition flex items-center justify-center shadow-lg">✕</button>
                <div class="w-1/3 space-y-3">
                  <div><label class="text-[10px] text-slate-500 font-bold">词条名</label><input v-model="entry.name" class="w-full bg-[#0d0d12] border border-slate-700 text-slate-300 px-3 py-1.5 rounded outline-none text-xs" /></div>
                  <div><label class="text-[10px] text-slate-500 font-bold">触发关键词(逗号分隔)</label><input v-model="entry.keys" class="w-full bg-[#0d0d12] border border-slate-700 text-slate-300 px-3 py-1.5 rounded outline-none text-xs" /></div>
                </div>
                <div class="w-2/3 flex flex-col">
                  <label class="text-[10px] text-slate-500 font-bold">设定内容 (Content)</label>
                  <textarea v-model="entry.content" class="flex-1 w-full bg-[#0d0d12] border border-slate-700 text-slate-300 p-3 rounded outline-none text-xs leading-relaxed custom-scrollbar"></textarea>
                </div>
              </div>
              <div v-if="!form.entries || form.entries.length === 0" class="text-center py-6 border-2 border-dashed border-slate-700/50 rounded-xl text-slate-500 text-xs">暂无词条，点击右上角添加。</div>
            </div>
          </div>
        </template>
        <template v-else-if="type === 'characters'">
          <div>
            <label class="text-xs text-slate-400 font-bold mb-1.5 block">背景与外观设定 (Description & Persona)</label>
            <textarea v-model="form.desc" class="w-full h-40 bg-[#0d0d12] border border-slate-700 text-slate-300 p-4 rounded-lg outline-none focus:border-indigo-500 text-sm leading-relaxed custom-scrollbar shadow-inner"></textarea>
          </div>
          <div>
            <label class="text-xs text-slate-400 font-bold mb-1.5 block">默认出场表现 (Starting Scene)</label>
            <textarea v-model="form.starting_scene" class="w-full h-24 bg-[#0d0d12] border border-slate-700 text-slate-300 p-4 rounded-lg outline-none focus:border-indigo-500 text-sm leading-relaxed custom-scrollbar shadow-inner"></textarea>
          </div>
        </template>
        <template v-else>
          <div>
            <label class="text-xs text-slate-400 font-bold mb-1.5 block">核心指令 / 描述</label>
            <textarea v-model="form.desc" class="w-full h-48 bg-[#0d0d12] border border-slate-700 text-slate-300 p-4 rounded-lg outline-none focus:border-indigo-500 text-sm leading-relaxed custom-scrollbar shadow-inner"></textarea>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>