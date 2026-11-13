<script setup>
import { onMounted, ref } from 'vue';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';
import ManuscriptFields from './ManuscriptFields.vue';
import { assetStore } from '../../store/assetStore';
import { uiStore } from '../../store/uiStore';
const emit = defineEmits(['close']);
const projects = ref([]), project = ref(null), title = ref(''), source = ref(''), selectedText = ref('');
const busy = ref(false), error = ref(''), consent = ref(false), instruction = ref(''), checked = ref([]), results = ref([]);
const kinds = {worldbooks:'世界书',characters:'角色',styles:'文风',entities:'实体',starter:'开局',future_notes:'未来剧情（仅资料）'};
const origins = {original:'原稿已有',suggested:'推导建议',missing:'缺失待补'};
const statuses = {pending:'待审阅',accepted:'已接受',rejected:'已拒绝',published:'已发布'};
async function api(path='', body) {
  const response = await fetch(`/api/v1/manuscripts${path}`, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '请求失败，请检查输入');
  return data;
}
async function run(action) {
  busy.value=true; error.value='';
  try { await action(); } catch(e) { error.value=e.message; } finally { busy.value=false; }
}
async function refresh() { projects.value=(await api()).projects; }
onMounted(() => run(refresh));
function open(id) { run(async () => { project.value=await api(`/${id}`); selectedText.value=project.value.selected_text || ''; checked.value=[]; results.value=[]; consent.value=false; }); }
function create() { run(async () => { project.value=await api('',{title:title.value,source_text:source.value}); selectedText.value=source.value; await refresh(); }); }
function readFile(event) { run(async () => {
  const file=event.target.files[0]; if (!file) return;
  if (!/\.(txt|md|markdown)$/i.test(file.name)) throw new Error('请选择 TXT 或 Markdown 文件');
  source.value=await file.text(); if (!title.value) title.value=file.name.replace(/\.[^.]+$/,'');
}); }
function analyze() { run(async () => {
  project.value=await api(`/${project.value.id}/analyze`,{expected_revision:project.value.revision,selected_text:selectedText.value,instruction:instruction.value,acknowledged:consent.value});
}); }
function review(status, ids=checked.value) { run(async () => {
  const changes=project.value.candidates.filter(c=>ids.includes(c.id)).map(c=>({id:c.id,name:c.name,content:c.content,status:status || c.status}));
  project.value=await api(`/${project.value.id}/review`,{expected_revision:project.value.revision,changes});
}); }
function publish() { run(async () => {
  const response=await api(`/${project.value.id}/publish`,{expected_revision:project.value.revision,candidate_ids:checked.value});
  project.value=response.project; results.value=response.results; await assetStore.fetchAssets();
}); }
function exportPackage() {
  const assets=project.value.candidates.filter(c=>c.status==='published');
  const starters=project.value.candidates.filter(c=>c.kind==='starter' && c.status==='accepted');
  if (starters.length>1) { error.value='有多个已接受开局，请只保留一个后再打包。'; return; }
  const starter=starters[0]?.content || {};
  localStorage.setItem('aliveworld.world-package-builder.v1',JSON.stringify({form:{name:project.value.title,version:'1.0.0',world_premise:starter.world_premise||'',opening:starter.opening||''},selected:assets.map(c=>`${c.kind}\u0000${c.name}`)}));
  uiStore.modals.worldPackageBuilder=true;
}
</script>
<template>
  <section class="absolute inset-0 z-40 flex flex-col bg-slate-950 text-slate-200" aria-label="手稿创作">
    <header class="flex shrink-0 items-center justify-between border-b border-slate-800 p-3"><h2>手稿创作<span v-if="project"> · {{ project.title }}</span></h2><button :disabled="busy" @click="emit('close')">返回单卡工坊</button></header>
    <div v-if="!project" class="min-h-0 overflow-y-auto p-5 space-y-4">
      <p class="text-sm text-slate-400">导入设定，整理为多种卡片。文件先保留本地，只有点击 AI 整理才发送选取内容。</p>
      <label class="block">项目名称<input v-model="title" class="ml-3 rounded bg-slate-800 p-2" /></label>
      <input type="file" accept=".txt,.md,.markdown" :disabled="busy" @change="readFile" />
      <ExpandableTextarea v-model="source" label="手稿原文" :rows="8" textarea-class="bg-slate-900 p-3 rounded" />
      <button :disabled="busy || !title.trim() || !source.trim()" class="rounded bg-cyan-800 p-2 disabled:opacity-40" @click="create">创建手稿项目</button>
      <h3>继续已有项目</h3><div class="grid grid-cols-2 gap-3"><button v-for="item in projects" :key="item.id" :disabled="busy" class="rounded border border-slate-700 p-3 text-left" @click="open(item.id)">{{ item.title }}</button></div>
    </div>
    <div v-else class="min-h-0 flex-1 overflow-y-auto p-4 space-y-4">
      <button :disabled="busy" class="text-sm text-cyan-300" @click="project=null; run(refresh)">返回项目列表</button>
      <details :open="!project.candidates.length" class="rounded border border-slate-700 p-3"><summary class="cursor-pointer">原稿与 AI 取材</summary>
        <details class="my-3"><summary>查看完整原稿（不会自动发送）</summary><p class="whitespace-pre-wrap">{{ project.source_text }}</p></details>
        <ExpandableTextarea v-model="selectedText" label="本次发送的原文（可删减为连续片段）" :rows="7" textarea-class="bg-slate-900 p-3 rounded" />
        <ExpandableTextarea v-model="instruction" label="整理要求（可选）" :rows="2" textarea-class="bg-slate-900 p-3 rounded" />
        <label class="block my-3 text-sm"><input v-model="consent" type="checkbox" /> 确认发送以上选取内容和要求到工坊接口，产生模型费用</label>
        <button :disabled="busy || !consent || !selectedText.trim()" class="rounded bg-cyan-800 p-2 disabled:opacity-40" @click="analyze">AI 整理手稿</button>
      </details>
      <p v-if="project.notes" class="whitespace-pre-wrap rounded bg-amber-950/30 p-3 text-amber-200">{{ project.notes }}</p>
      <div class="flex flex-wrap gap-3 text-sm"><button :disabled="busy" @click="checked=project.candidates.filter(c=>c.status!=='published').map(c=>c.id)">选择全部未发布</button><button @click="checked=[]">清空选择</button><button :disabled="busy || !checked.length" @click="review('accepted')">接受所选</button><button :disabled="busy || !checked.length" @click="review('rejected')">拒绝所选</button><button :disabled="busy || !checked.length" @click="publish">发布所选资产</button><button :disabled="busy || !project.candidates.some(c=>c.status==='published')" @click="exportPackage">制作世界包</button></div>
      <p class="text-xs text-slate-400">发布前请核对跨卡依赖；未接受的相关设定不会自动补齐。开局与未来剧情留在项目，只有已接受开局进入打包预填；未来剧情不会执行。</p>
      <article v-for="item in project.candidates" :key="item.id" class="rounded-xl border border-slate-700 p-4">
        <div class="flex items-center gap-3"><input v-model="checked" type="checkbox" :value="item.id" :aria-label="`选择${item.name}`" /><strong>{{ kinds[item.kind] }} · {{ item.name }}</strong><span class="text-xs text-slate-400">{{ origins[item.origin] }} · {{ statuses[item.status] }}</span></div>
        <details class="mt-3"><summary class="cursor-pointer text-cyan-300">查看、编辑与审阅</summary>
          <fieldset :disabled="busy || item.status==='published'" class="space-y-3 mt-3">
            <label class="block">名称<input v-model="item.name" class="ml-3 rounded bg-slate-800 p-2" /></label>
            <ManuscriptFields v-model="item.content" />
            <p class="whitespace-pre-wrap text-xs text-slate-500">原文依据：{{ item.source_quote || '无直接引用，请核对' }}</p>
            <div class="flex gap-4"><button @click="review(null,[item.id])">保存编辑</button><button @click="review('accepted',[item.id])">接受</button><button @click="review('rejected',[item.id])">拒绝</button></div>
          </fieldset>
        </details>
      </article>
      <p v-for="result in results" :key="result.id" class="text-sm">{{ project.candidates.find(c=>c.id===result.id)?.name }}：{{ result.message || '已发布' }}</p>
    </div>
    <footer v-if="busy || error" class="shrink-0 border-t border-slate-800 p-3"><p v-if="busy">正在处理，请勿重复提交……</p><p v-if="error" role="alert" class="text-rose-300">{{ error }}</p></footer>
  </section>
</template>
