<script setup>
import { computed, ref, watch } from 'vue';
import { workshopStore } from '../../store/workshopStore';
import { uiStore } from '../../store/uiStore';

const edit = ref({});
const entryEditor = ref(null);
const preferenceEditor = ref(null);
watch(() => workshopStore.draft, value => {
  edit.value = JSON.parse(JSON.stringify(value || {}));
}, { immediate: true, deep: true });
const type = computed(() => workshopStore.type);
const tagsText = computed({
  get: () => (edit.value.tags || []).join(', '),
  set: value => { edit.value.tags = value.split(/[,，]/).map(item => item.trim()).filter(Boolean); },
});
const lines = field => Array.isArray(edit.value[field]) ? edit.value[field].join('\n') : String(edit.value[field] || '');
const setLines = (field, value) => { edit.value[field] = value.split(/\r?\n/).map(item => item.trim()).filter(Boolean); };

async function save() {
  if (type.value === 'worldbooks') {
    await workshopStore.saveFields({
      overview: edit.value.overview || '',
      axioms: Array.isArray(edit.value.axioms) ? edit.value.axioms : [],
    });
    return;
  }
  if (type.value === 'preferences') return;
  const fields = type.value === 'characters'
    ? ['tags', 'description', 'starting_scene', 'is_player']
    : type.value === 'styles'
      ? ['tags', 'content']
      : ['tags', 'description', 'motive', 'status', 'mechanisms', 'plans', 'recent_actions', 'triggers', 'relationships', 'importance', 'is_active'];
  const changes = {};
  for (const field of fields) changes[field] = edit.value[field];
  await workshopStore.saveFields(changes);
}

function startEntry(entry = null) {
  entryEditor.value = entry
    ? { ...JSON.parse(JSON.stringify(entry)), tagsText: (entry.tags || []).join(', ') }
    : { id: '', name: '', keys: '', content: '', tagsText: '', is_active: true, isNew: true };
}
async function saveEntry() {
  const item = entryEditor.value;
  if (!item?.name?.trim() || !item?.content?.trim()) return;
  const entry = {
    name: item.name.trim(), keys: item.keys || '', content: item.content.trim(),
    tags: item.tagsText.split(/[,，]/).map(value => value.trim()).filter(Boolean),
    is_active: item.is_active !== false,
  };
  const operation = item.isNew
    ? { op: 'add_entry', entry }
    : { op: 'update_entry', entry_id: item.id, changes: entry };
  if (await workshopStore.applyOperations([operation], true)) entryEditor.value = null;
}
const toggleEntry = entry => workshopStore.applyOperations([{
  op: 'update_entry', entry_id: entry.id, changes: { is_active: entry.is_active === false }
}], true);
const deleteEntry = entry => workshopStore.applyOperations([{
  op: 'delete_entry', entry_id: entry.id
}], false);

function startPreference(item = null) {
  preferenceEditor.value = item
    ? { ...JSON.parse(JSON.stringify(item)), isNew: false }
    : { statement: '', category: 'story', polarity: 'prefer', status: 'candidate', sensitive: false, isNew: true };
}
async function savePreference() {
  const item = preferenceEditor.value;
  if (!item?.statement?.trim()) return;
  const editable = {
    statement: item.statement.trim(), category: item.category, polarity: item.polarity,
    status: item.status, sensitive: Boolean(item.sensitive),
  };
  const operation = item.isNew
    ? { op: 'add_preference', preference: editable }
    : { op: 'update_preference', preference_id: item.id, changes: editable };
  if (await workshopStore.applyOperations([operation], true)) preferenceEditor.value = null;
}
const setPreferenceStatus = (item, status) => workshopStore.applyOperations([{
  op: 'set_status', preference_id: item.id, status
}], status !== 'active');
const deletePreference = item => workshopStore.applyOperations([{
  op: 'delete_preference', preference_id: item.id
}], false);
const addTrigger = () => { (edit.value.triggers ||= []).push({ condition: '', result: '' }); };
const addRelationship = () => { (edit.value.relationships ||= []).push({ target: '', relation: '' }); };
</script>

<template>
  <aside :class="uiStore.leftDrawerOpen ? 'w-[340px]' : 'w-0'" class="relative z-20 flex shrink-0 flex-col overflow-hidden border-r border-cyan-950 bg-aw_panel shadow-xl transition-all duration-300">
    <div class="min-w-[340px] border-b border-slate-800 bg-slate-900 px-4 py-3"><h2 class="text-sm font-bold text-cyan-200">🗂️ 工坊草稿</h2><p class="mt-1 text-[10px] text-slate-500">结构导航与直接编辑</p></div>
    <div class="min-h-0 min-w-[340px] flex-1 overflow-y-auto p-4 custom-scrollbar">
      <p v-if="!workshopStore.draft" class="rounded-lg border border-dashed border-slate-700 p-6 text-center text-xs text-slate-500">从右侧选择资产后，这里显示草稿结构。</p>
      <template v-else>
        <div class="mb-4 flex items-center justify-between"><div><div class="text-sm font-bold text-slate-200">{{ workshopStore.assetName || '用户偏好卡' }}</div><div class="mt-1 text-[10px]" :class="workshopStore.dirty?'text-amber-400':'text-emerald-500'">{{ workshopStore.dirty?'未发布修改已保存':'与正式资产一致' }}</div></div><button v-if="type!=='preferences'" class="rounded bg-cyan-800 px-2 py-1 text-[10px] text-white" @click="save">保存到草稿</button></div>
        <label v-if="!['preferences','worldbooks'].includes(type)" class="block"><span class="field-label">标签</span><input v-model="tagsText" class="field"></label>

        <template v-if="type==='worldbooks'">
          <label class="block"><span class="field-label">世界概述</span><textarea v-model="edit.overview" class="field h-32"></textarea></label>
          <label class="mt-3 block"><span class="field-label">世界公理（每行一条）</span><textarea :value="lines('axioms')" class="field h-32" @input="setLines('axioms',$event.target.value)"></textarea></label>
          <section class="mt-4">
            <div class="flex items-center justify-between"><h3 class="text-xs font-bold text-amber-300">世界书条目 · {{ (edit.entries||[]).length }}</h3><button class="rounded bg-indigo-900 px-2 py-1 text-[9px] text-indigo-300" @click="startEntry()">＋ 新增</button></div>
            <div v-if="entryEditor" class="mt-2 space-y-2 rounded-xl border border-indigo-700 bg-slate-950 p-2"><input v-model="entryEditor.name" class="field" placeholder="条目名称"><input v-model="entryEditor.keys" class="field" placeholder="触发词，逗号分隔"><textarea v-model="entryEditor.content" class="field h-32" placeholder="条目内容"></textarea><input v-model="entryEditor.tagsText" class="field" placeholder="标签，逗号分隔"><label class="flex items-center gap-2 text-[10px] text-slate-400"><input v-model="entryEditor.is_active" type="checkbox">启用条目</label><div class="flex justify-end gap-1"><button class="rounded bg-slate-800 px-2 py-1 text-[9px]" @click="entryEditor=null">取消</button><button class="rounded bg-indigo-700 px-2 py-1 text-[9px] text-white" @click="saveEntry">保存到草稿</button></div></div>
            <article v-for="entry in edit.entries||[]" :key="entry.id" class="mt-2 rounded-lg border border-slate-700 bg-slate-900/60 p-2"><div class="flex items-center justify-between gap-2"><button class="min-w-0 truncate text-left text-xs font-bold text-slate-300 hover:text-indigo-300" @click="startEntry(entry)">{{ entry.name }}</button><button class="text-[9px]" :class="entry.is_active===false?'text-slate-600':'text-emerald-400'" @click="toggleEntry(entry)">{{ entry.is_active===false?'关闭':'启用' }}</button></div><p class="mt-1 line-clamp-3 text-[10px] leading-relaxed text-slate-500">{{ entry.content }}</p><div class="mt-2 flex justify-end"><button class="text-[9px] text-rose-400" @click="deleteEntry(entry)">删除</button></div></article>
          </section>
        </template>
        <template v-else-if="type==='characters'">
          <label class="mb-3 flex items-center gap-2 rounded border border-slate-700 p-2 text-xs text-slate-300"><input v-model="edit.is_player" type="checkbox">玩家扮演角色</label>
          <label class="block"><span class="field-label">人物设定</span><textarea v-model="edit.description" class="field h-64"></textarea></label>
          <label class="mt-3 block"><span class="field-label">登场情境</span><textarea v-model="edit.starting_scene" class="field h-24"></textarea></label>
        </template>
        <template v-else-if="type==='styles'">
          <label class="block"><span class="field-label">文风规范</span><textarea v-model="edit.content" class="field h-[60vh]"></textarea></label>
        </template>
        <template v-else-if="type==='entities'">
          <label class="block"><span class="field-label">描述</span><textarea v-model="edit.description" class="field h-20"></textarea></label>
          <label class="mt-3 block"><span class="field-label">动机</span><textarea v-model="edit.motive" class="field h-24"></textarea></label>
          <label class="mt-3 block"><span class="field-label">状态</span><textarea v-model="edit.status" class="field h-24"></textarea></label>
          <label v-for="field in ['mechanisms','plans','recent_actions']" :key="field" class="mt-3 block"><span class="field-label">{{ {mechanisms:'机制',plans:'计划',recent_actions:'近期行动'}[field] }}（每行一项）</span><textarea :value="lines(field)" class="field h-24" @input="setLines(field,$event.target.value)"></textarea></label>
          <section class="mt-3 rounded border border-slate-700 p-2"><div class="flex justify-between text-[10px] font-bold text-slate-400"><span>触发器</span><button class="text-cyan-300" @click="addTrigger">＋添加</button></div><div v-for="(item,index) in edit.triggers||[]" :key="index" class="mt-2 grid grid-cols-[1fr_1fr_auto] gap-1"><input v-model="item.condition" class="field" placeholder="条件"><input v-model="item.result" class="field" placeholder="结果"><button class="text-rose-400" @click="edit.triggers.splice(index,1)">✕</button></div></section>
          <section class="mt-3 rounded border border-slate-700 p-2"><div class="flex justify-between text-[10px] font-bold text-slate-400"><span>关系</span><button class="text-cyan-300" @click="addRelationship">＋添加</button></div><div v-for="(item,index) in edit.relationships||[]" :key="index" class="mt-2 grid grid-cols-[1fr_1fr_auto] gap-1"><input v-model="item.target" class="field" placeholder="对象"><input v-model="item.relation" class="field" placeholder="关系"><button class="text-rose-400" @click="edit.relationships.splice(index,1)">✕</button></div></section>
          <label class="mt-3 block"><span class="field-label">重要性（0-1）</span><input v-model.number="edit.importance" type="number" min="0" max="1" step="0.1" class="field"></label>
        </template>
        <template v-else>
          <div class="mb-3 flex justify-end"><button class="rounded bg-fuchsia-900 px-2 py-1 text-[9px] text-fuchsia-200" @click="startPreference()">＋ 新增偏好</button></div>
          <div v-if="preferenceEditor" class="mb-3 space-y-2 rounded-xl border border-fuchsia-700 bg-slate-950 p-2"><textarea v-model="preferenceEditor.statement" class="field h-24" placeholder="偏好表述"></textarea><div class="grid grid-cols-2 gap-1"><select v-model="preferenceEditor.category" class="field"><option v-for="item in ['story','adult','action','character','relationship','visual','boundary','other']" :key="item">{{ item }}</option></select><select v-model="preferenceEditor.polarity" class="field"><option value="prefer">希望出现</option><option value="avoid">希望回避</option></select></div><div class="flex justify-end gap-1"><button class="rounded bg-slate-800 px-2 py-1 text-[9px]" @click="preferenceEditor=null">取消</button><button class="rounded bg-fuchsia-700 px-2 py-1 text-[9px] text-white" @click="savePreference">保存到草稿</button></div></div>
          <section v-for="item in edit" :key="item.id" class="mb-2 rounded-xl border border-slate-700 bg-slate-900/65 p-3"><div class="flex justify-between gap-2"><button class="text-left text-xs leading-relaxed text-slate-300 hover:text-fuchsia-300" @click="startPreference(item)">{{ item.statement }}</button><span class="shrink-0 text-[9px]" :class="item.status==='active'?'text-emerald-400':item.status==='candidate'?'text-amber-400':'text-slate-600'">{{ item.status==='active'?'生效':item.status==='candidate'?'候选':'停用' }}</span></div><div class="mt-2 text-[9px] text-slate-600">{{ item.category }} · 后验 {{ Math.round((item.posterior||item.confidence||0)*100) }}%</div><div class="mt-2 flex gap-2 text-[9px]"><button v-if="item.status!=='active'" class="text-emerald-400" @click="setPreferenceStatus(item,'active')">启用</button><button v-else class="text-slate-400" @click="setPreferenceStatus(item,'disabled')">停用</button><button class="text-rose-400" @click="deletePreference(item)">删除</button></div></section>
        </template>
      </template>
    </div>
  </aside>
</template>

<style scoped>
.field-label { display: block; margin-bottom: .3rem; font-size: .68rem; color: rgb(148 163 184); }
.field { width: 100%; border: 1px solid rgb(51 65 85); border-radius: .45rem; background: rgb(15 23 42); padding: .5rem .6rem; font-size: .72rem; color: rgb(226 232 240); }
</style>
