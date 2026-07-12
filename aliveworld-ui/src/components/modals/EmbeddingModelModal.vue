<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { worldbookWorkshopApi } from '../../api/worldbookWorkshopApi';

const status = ref({ state: 'disabled', progress: 0, downloaded_bytes: 0, estimated_bytes: 0 });
const busy = ref(false);
let timer = null;
const formatBytes = (value) => {
  const mb = Number(value || 0) / 1024 / 1024;
  return `${mb.toFixed(mb >= 100 ? 0 : 1)} MB`;
};
const refresh = async () => {
  try { status.value = await worldbookWorkshopApi.embeddingStatus(); } catch (e) { status.value.error = e.message; }
};
onMounted(async () => { await refresh(); timer = window.setInterval(refresh, 1500); });
onBeforeUnmount(() => { if (timer) window.clearInterval(timer); });
const run = async (action) => {
  if (busy.value) return;
  busy.value = true;
  try { status.value = await action(); } catch (e) { uiStore.showToast(e.message, 'error'); }
  finally { busy.value = false; }
};
const download = () => run(() => worldbookWorkshopApi.downloadEmbeddings());
const pause = () => run(() => worldbookWorkshopApi.pauseEmbeddings());
const toggle = () => run(() => worldbookWorkshopApi.toggleEmbeddings(!status.value.enabled));
const uninstall = () => {
  if (window.confirm('卸载会删除本地语义模型和世界书向量缓存，之后自动退回关键词检索。确定卸载吗？')) run(() => worldbookWorkshopApi.uninstallEmbeddings());
};
</script>

<template>
  <div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
    <div class="w-full max-w-2xl rounded-2xl border border-cyan-800 bg-slate-950 p-5 shadow-2xl">
      <div class="flex items-start justify-between"><div><h2 class="font-bold text-cyan-300">🧠 世界书语义模型</h2><p class="mt-1 text-xs text-slate-500">用于本地向量检索；不可用时游戏自动使用关键词检索。</p></div><button @click="uiStore.modals.embeddingModel=false" class="text-slate-400">✕</button></div>
      <div class="mt-5 grid grid-cols-[110px_1fr] gap-x-3 gap-y-2 rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-xs"><span class="text-slate-500">模型</span><span class="break-all text-slate-300">{{ status.model_name }}</span><span class="text-slate-500">来源</span><a :href="status.source_url" target="_blank" class="break-all text-cyan-400 underline">Hugging Face 官方模型页</a><span class="text-slate-500">预计下载</span><span class="text-slate-300">{{ formatBytes(status.estimated_bytes) }}（权重约471MB，另含分词与配置）</span><span class="text-slate-500">保存位置</span><span class="break-all font-mono text-[10px] text-slate-400">{{ status.model_dir }}</span><span class="text-slate-500">运行要求</span><span class="text-slate-300">{{ status.runtime_note }}</span></div>
      <div class="mt-4"><div class="mb-1 flex justify-between text-xs"><span class="text-slate-400">状态：{{ status.state }}</span><span class="text-slate-500">{{ formatBytes(status.downloaded_bytes) }} / {{ formatBytes(status.estimated_bytes) }}</span></div><div class="h-3 overflow-hidden rounded-full bg-slate-800"><div class="h-full bg-cyan-500 transition-all" :style="{width:`${status.progress||0}%`}" /></div><p class="mt-2 text-[10px] text-slate-500">“停止并保留断点”会终止当前下载进程；再次继续时由模型仓库客户端复用已下载文件。暂不提供进程级暂停。</p></div>
      <div v-if="status.error" class="mt-3 rounded border border-rose-800 bg-rose-950/30 p-2 text-xs text-rose-300">{{ status.error }}</div>
      <div class="mt-5 flex flex-wrap gap-2"><button v-if="status.state!=='downloading' && !status.downloaded" @click="download" :disabled="busy" class="rounded bg-cyan-700 px-3 py-2 text-xs font-bold text-white">{{ status.state==='paused'?'继续下载':'开始下载' }}</button><button v-if="status.state==='downloading'" @click="pause" class="rounded bg-amber-700 px-3 py-2 text-xs font-bold text-white">停止并保留断点</button><button v-if="status.downloaded" @click="toggle" class="rounded px-3 py-2 text-xs font-bold text-white" :class="status.enabled?'bg-slate-700':'bg-emerald-700'">{{ status.enabled?'关闭语义检索':'启用语义检索' }}</button><button v-if="status.downloaded || status.downloaded_bytes" @click="uninstall" class="rounded bg-rose-900 px-3 py-2 text-xs font-bold text-rose-200">卸载模型</button></div>
    </div>
  </div>
</template>
