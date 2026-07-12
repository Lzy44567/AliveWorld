<script setup>
import { onMounted, ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { worldbookWorkshopApi } from '../../api/worldbookWorkshopApi';

const workshopId = ref('');
const draft = ref({ entries: [] });
const pending = ref([]);
const messages = ref([]);
const suggestions = ref([]);
const input = ref('');
const mode = ref('expand');
const busy = ref(false);

const close = () => { uiStore.modals.worldbookWorkshop = false; };
const sync = (data) => {
  workshopId.value = data.workshop_id || workshopId.value;
  draft.value = data.draft || draft.value;
  pending.value = data.pending || [];
  if (data.messages) messages.value = data.messages;
  if (data.suggested_actions) suggestions.value = data.suggested_actions;
};

onMounted(async () => {
  busy.value = true;
  try { sync(await worldbookWorkshopApi.start(uiStore.workshopWorldbookName)); }
  catch (e) { uiStore.showToast(e.message, 'error'); close(); }
  finally { busy.value = false; }
});

const send = async (text = input.value) => {
  const message = text.trim();
  if (!message || busy.value) return;
  input.value = '';
  busy.value = true;
  try { sync(await worldbookWorkshopApi.chat(workshopId.value, message, mode.value)); }
  catch (e) { uiStore.showToast(e.message, 'error'); }
  finally { busy.value = false; }
};

const decide = async (operationId, approve) => {
  try { sync(approve ? await worldbookWorkshopApi.approve(workshopId.value, operationId) : await worldbookWorkshopApi.reject(workshopId.value, operationId)); }
  catch (e) { uiStore.showToast(e.message, 'error'); }
};

const undo = async () => {
  try { sync(await worldbookWorkshopApi.undo(workshopId.value)); }
  catch (e) { uiStore.showToast(e.message, 'error'); }
};

const publish = async () => {
  try {
    const isTemplate = draft.value.is_template === true || (draft.value.tags || []).includes('模板');
    const publishName = isTemplate ? window.prompt('模板不能被覆盖，请输入个人世界书名称：', `${draft.value.name || '新世界书'}_个人版`) : null;
    if (isTemplate && !publishName) return;
    sync(await worldbookWorkshopApi.publish(workshopId.value, publishName));
    await assetStore.fetchAssets();
    uiStore.showToast('世界书草稿已发布');
  } catch (e) { uiStore.showToast(e.message, 'error'); }
};
</script>

<template>
  <div class="fixed inset-0 z-[90] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
    <div class="flex h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-indigo-700/60 bg-slate-950 shadow-2xl">
      <header class="flex items-center justify-between border-b border-slate-800 px-5 py-3">
        <div><h2 class="font-bold text-indigo-300">🧭 世界书工坊 · {{ uiStore.workshopWorldbookName }}</h2><p class="text-[10px] text-slate-500">独立草稿会话，不推进故事正文与世界时间</p></div>
        <div class="flex gap-2"><button @click="undo" class="rounded bg-slate-800 px-3 py-1.5 text-xs text-slate-300">撤销</button><button @click="publish" class="rounded bg-emerald-700 px-3 py-1.5 text-xs font-bold text-white">发布草稿</button><button @click="close" class="px-2 text-slate-400">✕</button></div>
      </header>
      <div class="grid min-h-0 flex-1 grid-cols-[1fr_360px]">
        <section class="flex min-h-0 flex-col border-r border-slate-800">
          <div class="flex gap-2 border-b border-slate-800 p-3">
            <button v-for="item in [['create','从一句话创建'],['expand','拓展新领域'],['evolve','演化已有设定']]" :key="item[0]" @click="mode=item[0]" class="rounded px-3 py-1.5 text-xs" :class="mode===item[0]?'bg-indigo-700 text-white':'bg-slate-900 text-slate-400'">{{ item[1] }}</button>
          </div>
          <div class="flex-1 space-y-3 overflow-y-auto p-4">
            <div v-if="busy && !messages.length" class="text-sm text-slate-500">正在建立工坊草稿……</div>
            <div v-for="(msg, index) in messages" :key="index" class="max-w-[85%] rounded-xl p-3 text-sm" :class="msg.role==='user'?'ml-auto bg-indigo-700 text-white':'bg-slate-800 text-slate-200'">{{ msg.content }}</div>
            <div v-if="pending.length" class="rounded-xl border border-amber-700/60 bg-amber-950/30 p-3">
              <div class="mb-2 text-xs font-bold text-amber-300">需要确认的高影响修改</div>
              <div v-for="op in pending" :key="op.operation_id" class="mb-2 rounded bg-black/30 p-2 text-xs text-slate-300"><div>{{ op.op }} · {{ op.entry?.name || op.entry_id }}</div><div class="mt-2 flex gap-2"><button @click="decide(op.operation_id,true)" class="rounded bg-emerald-700 px-2 py-1">接受</button><button @click="decide(op.operation_id,false)" class="rounded bg-rose-800 px-2 py-1">拒绝</button></div></div>
            </div>
          </div>
          <div class="border-t border-slate-800 p-3">
            <div v-if="suggestions.length" class="mb-2 flex flex-wrap gap-1"><button v-for="item in suggestions" :key="item" @click="send(item)" class="rounded-full border border-indigo-800 px-2 py-1 text-[10px] text-indigo-300">{{ item }}</button></div>
            <div class="flex gap-2"><textarea v-model="input" @keydown.ctrl.enter.prevent="send()" class="h-20 flex-1 rounded-lg border border-slate-700 bg-slate-900 p-3 text-sm text-slate-200" placeholder="描述你希望怎样创建、拓展或演化世界书；Ctrl+Enter发送"></textarea><button @click="send()" :disabled="busy" class="w-20 rounded-lg bg-indigo-700 text-sm font-bold text-white disabled:opacity-50">{{ busy ? '处理中' : '发送' }}</button></div>
          </div>
        </section>
        <aside class="overflow-y-auto p-4"><h3 class="font-bold text-slate-200">当前草稿</h3><p class="mt-1 text-xs text-slate-500">{{ draft.global_setting }}</p><div class="mt-4 space-y-2"><div v-for="entry in draft.entries" :key="entry.id" class="rounded-lg border border-slate-800 bg-slate-900 p-2" :class="entry.is_active===false?'opacity-50':''"><div class="text-xs font-bold text-slate-300">{{ entry.name }}</div><div class="mt-1 line-clamp-3 text-[10px] text-slate-500">{{ entry.content }}</div><div class="mt-1 flex flex-wrap gap-1"><span v-for="tag in entry.tags" :key="tag" class="rounded bg-slate-800 px-1 text-[9px] text-indigo-300">{{ tag }}</span></div></div></div></aside>
      </div>
    </div>
  </div>
</template>
