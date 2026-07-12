<!-- src/components/modals/AssetEditorModal.vue -->
<script setup>
import { computed, ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { assetApi } from '../../api/assetApi';
import { gameApi } from '../../api/gameApi';
import { gameStore } from '../../store/gameStore';
import { buildEntityPayload } from '../../utils/entityForm';
import SystemTagInput from '../common/SystemTagInput.vue';

const form = computed(() => uiStore.editorData.form);
const type = computed(() => uiStore.editorData.type);
const closeEditor = () => { uiStore.modals.assetEditor = false; };

const addWorldEntry = () => {
  if (!form.value.entries) form.value.entries = [];
  form.value.entries.push({ name: '', keys: '', content: '', tags: '', is_active: true });
};

const removeWorldEntry = (idx) => { form.value.entries.splice(idx, 1); };
const entryTags = (entry) => typeof entry.tags === 'string' ? entry.tags.split(/[,，]/).map(tag => tag.trim()).filter(Boolean) : (entry.tags || []);
const isPendingEntry = (entry) => entryTags(entry).includes('待确认');
const acceptPendingEntry = (entry) => {
  entry.tags = entryTags(entry).filter(tag => tag !== '待确认').join(', ');
  entry.is_active = true;
};
const rejectPendingEntry = (idx) => { form.value.entries.splice(idx, 1); };
const entrySearch = ref('');
const expandedEntries = ref({});
const filteredWorldEntries = computed(() => {
  const keyword = entrySearch.value.trim().toLowerCase();
  return (form.value.entries || []).map((entry, index) => ({ entry, index })).filter(({ entry }) => {
    if (!keyword) return true;
    const tags = typeof entry.tags === 'string' ? entry.tags : (entry.tags || []).join(' ');
    return [entry.name, entry.keys, tags, entry.content].some(value => String(value || '').toLowerCase().includes(keyword));
  });
});
const entryKey = (entry, index) => entry.id || `index_${index}`;
const toggleEntryExpanded = (entry, index) => { expandedEntries.value[entryKey(entry, index)] = !expandedEntries.value[entryKey(entry, index)]; };
const isEntryExpanded = (entry, index) => Boolean(expandedEntries.value[entryKey(entry, index)]);
const openWorkshop = () => {
  if (uiStore.editorData.isNew) return uiStore.showToast('请先保存世界书，再进入工坊', 'error');
  if (uiStore.assetScope !== 'global') return uiStore.showToast('当前工坊先用于局外世界书资产', 'error');
  uiStore.workshopWorldbookName = form.value.name;
  uiStore.modals.assetEditor = false;
  uiStore.modals.worldbookWorkshop = true;
};
const addEntityTrigger = () => { form.value.triggers.push({ condition: '', result: '' }); };
const removeEntityTrigger = (idx) => { form.value.triggers.splice(idx, 1); };
const addEntityRelationship = () => { form.value.relationships.push({ target: '', relation: '' }); };
const removeEntityRelationship = (idx) => { form.value.relationships.splice(idx, 1); };

const saveContent = async () => {
  try {
    if(!form.value.name.trim()) return uiStore.showToast("资产名称不能为空", "error");
    
    if (!uiStore.editorData.isNew && form.value.name !== uiStore.editorData.name) {
      if (uiStore.assetScope === 'local') await gameApi.deleteLocalAsset(gameStore.sessionId, type.value, uiStore.editorData.name);
      else await assetApi.deleteAsset(type.value, uiStore.editorData.name);
    }

    let payload = { name: form.value.name };
    if (typeof form.value.tags === 'string' && form.value.tags) payload.tags = form.value.tags.split(/[,，]/).map(t => t.trim()).filter(t => t);
    else if (Array.isArray(form.value.tags)) payload.tags = form.value.tags;

    if (type.value === 'worldbooks') {
      payload.overview = form.value.overview;
      payload.axioms = String(form.value.axiomsText || '').split(/\r?\n/).map(item => item.trim()).filter(Boolean);
      payload.starting_scene = form.value.starting_scene;
      payload.entries = form.value.entries.filter(e => e.name || e.keys || e.content).map(e => ({
        ...e,
        keys: e.keys ? e.keys.replace(/，/g, ',') : '',
        tags: typeof e.tags === 'string' ? e.tags.split(/[,，]/).map(t => t.trim()).filter(Boolean) : (e.tags || []),
      }));
    } else if (type.value === 'characters') {
      payload.description = form.value.desc;
      payload.starting_scene = form.value.starting_scene;
      payload.is_player = form.value.is_player;
    } else if (type.value === 'styles') { payload.content = form.value.desc; }
    else if (type.value === 'entities') { Object.assign(payload, buildEntityPayload(form.value)); }

    if (uiStore.assetScope === 'local') {
      payload.is_active = form.value.is_active; 
      await gameApi.updateLocalAsset(gameStore.sessionId, type.value, form.value.name, payload);
      await assetStore.fetchLocalAssets(gameStore.sessionId);
    } else {
      await assetApi.saveAsset(type.value, form.value.name, "", payload);
      await assetStore.fetchAssets(); 
    }
    
    uiStore.showToast("保存成功"); closeEditor();
  } catch(e) { uiStore.showToast("保存失败: " + e.message, "error"); }
};
</script>

<template>
  <div class="fixed inset-0 bg-black/80 z-[80] flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-[#1a1a1f] border border-slate-600 rounded-xl w-full max-w-4xl shadow-2xl flex flex-col slide-up overflow-hidden h-[85vh]">
      <div class="p-4 border-b border-slate-700 flex justify-between bg-slate-900/80">
        <h2 class="font-bold text-emerald-400 text-lg">✨ 编辑设定 <span class="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded">{{ type }}</span></h2>
        <div class="flex gap-2"><button v-if="type==='worldbooks'" @click="openWorkshop" class="px-4 py-2 bg-violet-800 text-violet-100 text-sm font-bold rounded shadow">🧭 进入工坊</button><button @click="saveContent" class="px-5 py-2 bg-emerald-600 text-white text-sm font-bold rounded shadow">保存</button><button @click="closeEditor" class="px-4 py-2 bg-slate-700 text-white text-sm font-bold rounded">取消</button></div>
      </div>
      <div class="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
        <div class="grid grid-cols-2 gap-6">
          <div><label class="text-xs text-slate-400 font-bold mb-1.5 block">资产名称 (Name)</label><input v-model="form.name" class="w-full bg-[#0d0d12] border border-slate-700 text-slate-200 px-4 py-2.5 rounded-lg text-sm" /></div>
          <div><label class="text-xs text-slate-400 font-bold mb-1.5 block">{{ type === 'worldbooks' ? '世界书分类标签（仅用于玩家检索管理）' : '标签 (逗号分隔)' }}</label><input v-model="form.tags" class="w-full bg-[#0d0d12] border border-slate-700 text-slate-200 px-4 py-2.5 rounded-lg text-sm" /></div>
        </div>

        <!-- 🚀 修复问题10：补回完整视图 -->
        <template v-if="type === 'worldbooks'">
          <div><label class="text-xs text-slate-400 font-bold block mb-1.5">世界概述</label><p class="mb-1.5 text-[10px] text-slate-500">介绍世界背景与总体印象，不视为不可违反的规则。</p><textarea v-model="form.overview" class="w-full h-24 bg-[#0d0d12] border border-slate-700 text-slate-300 p-3 rounded-lg text-sm"></textarea></div>
          <div><label class="text-xs text-amber-300 font-bold block mb-1.5">世界公理（每行一条）</label><p class="mb-1.5 text-[10px] text-slate-500">定义世界最基础的客观规则与基调，和口语化概述分开。</p><textarea v-model="form.axiomsText" class="w-full h-24 bg-[#0d0d12] border border-amber-900/70 text-slate-300 p-3 rounded-lg text-sm"></textarea></div>
          <div class="border-t border-slate-700 pt-4">
            <div class="flex justify-between items-center mb-3"><h3 class="text-sm font-bold text-slate-300">📚 世界书条目</h3><button @click="addWorldEntry" class="px-3 py-1 bg-indigo-900/50 text-indigo-400 border border-indigo-700/50 rounded text-xs font-bold">+ 新增条目</button></div>
            <input v-model="entrySearch" class="mb-3 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200" placeholder="搜索条目名称、触发词、标签或内容……" />
            <div class="space-y-4">
              <div v-for="({entry, index: idx}) in filteredWorldEntries" :key="entry.id || idx" class="bg-slate-800/50 p-3 rounded-lg border border-slate-700 relative group" :class="entry.is_active===false?'opacity-60':''">
                <div class="flex items-center gap-3">
                  <button type="button" @click="toggleEntryExpanded(entry, idx)" class="text-slate-400">{{ isEntryExpanded(entry, idx) ? '▼' : '▶' }}</button>
                  <div class="min-w-0 flex-1"><div class="truncate text-xs font-bold text-slate-200">{{ entry.name || '未命名条目' }}</div><div class="mt-1 flex flex-wrap gap-1 text-[9px] text-slate-500"><span v-if="entry.keys">触发：{{ entry.keys }}</span><span v-for="tag in entryTags(entry)" :key="tag" class="rounded bg-slate-900 px-1 text-indigo-300">{{ tag }}</span></div></div>
                  <button type="button" role="switch" :aria-checked="entry.is_active!==false" @click="entry.is_active=entry.is_active===false" class="rounded-full border px-2 py-1 text-[10px]" :class="entry.is_active===false?'border-slate-600 text-slate-500':'border-emerald-700 text-emerald-300'">{{ entry.is_active===false?'已关闭':'已启用' }}</button>
                  <button @click="removeWorldEntry(idx)" class="text-rose-500">✕</button>
                </div>
                <div v-if="isEntryExpanded(entry, idx)" class="mt-4 border-t border-slate-700 pt-3">
                <div class="grid grid-cols-2 gap-4 mb-3">
                  <div><label class="text-[10px] text-slate-500 block mb-1">词条名</label><input v-model="entry.name" class="w-full bg-slate-900 border border-slate-700 text-slate-200 px-3 py-1.5 rounded text-xs" /></div>
                  <div><label class="text-[10px] text-slate-500 block mb-1">触发关键词 (逗号分隔)</label><input v-model="entry.keys" class="w-full bg-slate-900 border border-slate-700 text-slate-200 px-3 py-1.5 rounded text-xs" /></div>
                </div>
                <div><label class="text-[10px] text-slate-500 block mb-1">词条内容</label><textarea v-model="entry.content" class="w-full h-20 bg-slate-900 border border-slate-700 text-slate-300 p-3 rounded text-xs"></textarea></div>
                <div class="mt-3"><SystemTagInput v-model="entry.tags"><template #label><span class="text-[10px] text-slate-500">词条标签</span></template></SystemTagInput></div>
                <div v-if="isPendingEntry(entry)" class="mt-3 flex items-center justify-between rounded-lg border border-amber-700/60 bg-amber-950/30 p-2">
                  <span class="text-[10px] text-amber-300">此AI候选尚未参与正文检索</span>
                  <div class="flex gap-2"><button type="button" @click="acceptPendingEntry(entry)" class="rounded bg-emerald-700 px-2 py-1 text-[10px] font-bold text-white">接受并启用</button><button type="button" @click="rejectPendingEntry(idx)" class="rounded bg-rose-800 px-2 py-1 text-[10px] font-bold text-white">拒绝并删除</button></div>
                </div>
                </div>
              </div>
            </div>
          </div>
        </template>
        
        <template v-else-if="type === 'characters'">
          <div class="flex items-center gap-3 p-3 bg-indigo-900/20 border border-indigo-900/50 rounded-lg"><input type="checkbox" v-model="form.is_player" class="w-5 h-5 rounded bg-slate-900 border-slate-700 text-indigo-500"><div><p class="text-sm font-bold text-indigo-300">将此角色设为主役 (Is Player)</p></div></div>
          <div><label class="text-xs text-slate-400 font-bold mb-1.5 block">背景与外观设定 (Description)</label><textarea v-model="form.desc" class="w-full h-40 bg-[#0d0d12] border border-slate-700 text-slate-300 p-4 rounded-lg text-sm"></textarea></div>
        </template>
        
        <template v-else-if="type === 'entities'">
          <div class="grid grid-cols-2 gap-4">
            <div><label class="text-xs text-slate-400 font-bold mb-1.5 block">动机 (Motive)</label><textarea v-model="form.motive" class="w-full h-24 bg-[#0d0d12] border border-slate-700 text-slate-300 p-3 rounded-lg text-sm"></textarea></div>
            <div><label class="text-xs text-slate-400 font-bold mb-1.5 block">当前状态 (Status)</label><textarea v-model="form.status" class="w-full h-24 bg-[#0d0d12] border border-slate-700 text-slate-300 p-3 rounded-lg text-sm"></textarea></div>
          </div>
          <div><label class="text-xs text-slate-400 font-bold mb-1.5 block">描述（供资产库浏览）</label><textarea v-model="form.desc" class="w-full h-20 bg-[#0d0d12] border border-slate-700 text-slate-300 p-3 rounded-lg text-sm"></textarea></div>
          <div class="grid grid-cols-3 gap-4">
            <div><label class="text-xs text-slate-400 font-bold mb-1.5 block">近期行动（每行一项）</label><textarea v-model="form.recentActionsText" class="w-full h-28 bg-[#0d0d12] border border-slate-700 text-slate-300 p-3 rounded-lg text-xs"></textarea></div>
            <div><label class="text-xs text-slate-400 font-bold mb-1.5 block">计划（每行一项）</label><textarea v-model="form.plansText" class="w-full h-28 bg-[#0d0d12] border border-slate-700 text-slate-300 p-3 rounded-lg text-xs"></textarea></div>
            <div><label class="text-xs text-slate-400 font-bold mb-1.5 block">机制（每行一项）</label><textarea v-model="form.mechanismsText" class="w-full h-28 bg-[#0d0d12] border border-slate-700 text-slate-300 p-3 rounded-lg text-xs"></textarea></div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="border border-slate-700 rounded-lg p-3 space-y-3"><div class="flex items-center justify-between"><label class="text-xs text-slate-400 font-bold">触发器</label><button @click="addEntityTrigger" class="px-2 py-1 rounded bg-indigo-900/50 text-indigo-300 text-[10px]">+ 添加</button></div><div v-if="!form.triggers.length" class="text-xs text-slate-500">暂无触发器</div><div v-for="(trigger, idx) in form.triggers" :key="idx" class="grid grid-cols-[1fr_1fr_auto] gap-2"><input v-model="trigger.condition" placeholder="触发条件" class="min-w-0 bg-[#0d0d12] border border-slate-700 text-slate-300 px-2 py-1.5 rounded text-xs"><input v-model="trigger.result" placeholder="触发后果" class="min-w-0 bg-[#0d0d12] border border-slate-700 text-slate-300 px-2 py-1.5 rounded text-xs"><button @click="removeEntityTrigger(idx)" class="text-rose-400 px-1">✕</button></div></div>
            <div class="border border-slate-700 rounded-lg p-3 space-y-3"><div class="flex items-center justify-between"><label class="text-xs text-slate-400 font-bold">关系</label><button @click="addEntityRelationship" class="px-2 py-1 rounded bg-indigo-900/50 text-indigo-300 text-[10px]">+ 添加</button></div><div v-if="!form.relationships.length" class="text-xs text-slate-500">暂无关系</div><div v-for="(relationship, idx) in form.relationships" :key="idx" class="grid grid-cols-[1fr_1fr_auto] gap-2"><input v-model="relationship.target" placeholder="对象名称" class="min-w-0 bg-[#0d0d12] border border-slate-700 text-slate-300 px-2 py-1.5 rounded text-xs"><input v-model="relationship.relation" placeholder="关系描述" class="min-w-0 bg-[#0d0d12] border border-slate-700 text-slate-300 px-2 py-1.5 rounded text-xs"><button @click="removeEntityRelationship(idx)" class="text-rose-400 px-1">✕</button></div></div>
          </div>
          <div class="max-w-xs"><label class="text-xs text-slate-400 font-bold mb-1.5 block">重要性（0 到 1）</label><input v-model="form.importance" type="number" min="0" max="1" step="0.1" class="w-full bg-[#0d0d12] border border-slate-700 text-slate-200 px-4 py-2.5 rounded-lg text-sm" /></div>
        </template>

        <template v-else>
           <div><label class="text-xs text-slate-400 font-bold mb-1.5 block">设定正文 (Content)</label><textarea v-model="form.desc" class="w-full h-64 bg-[#0d0d12] border border-slate-700 text-slate-300 p-4 rounded-lg text-sm"></textarea></div>
        </template>
      </div>
    </div>
  </div>
</template>
