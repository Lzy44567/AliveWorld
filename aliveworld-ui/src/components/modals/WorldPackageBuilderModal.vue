<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { worldPackageApi } from '../../api/worldPackageApi';
import { assetStore } from '../../store/assetStore';
import { uiStore } from '../../store/uiStore';

const DRAFT_KEY = 'aliveworld.world-package-builder.v1';
const TYPE_META = {
  worldbooks: { label: '世界书', icon: '🌍' },
  characters: { label: '角色卡', icon: '🎭' },
  styles: { label: '文风卡', icon: '📜' },
  entities: { label: '暗流实体', icon: '👾' },
};

const assets = ref([]);
const selected = ref([]);
const busy = ref(false);
const loading = ref(true);
const form = reactive({
  package_id: '', version: '1.0.0', name: '', author: '', description: '', tags: '',
  adult: false, license: 'unspecified', world_premise: '', opening: '',
});

const groups = computed(() => Object.entries(TYPE_META).map(([type, meta]) => ({
  type, ...meta, items: assets.value.filter(item => item.type === type),
})));
const keyOf = item => `${item.type}\u0000${item.name}`;
const isSelected = item => selected.value.includes(keyOf(item));
function toggle(item) {
  const key = keyOf(item);
  selected.value = isSelected(item) ? selected.value.filter(value => value !== key) : [...selected.value, key];
}
function close() { if (!busy.value) uiStore.modals.worldPackageBuilder = false; }

function persistDraft() {
  localStorage.setItem(DRAFT_KEY, JSON.stringify({ form: { ...form }, selected: selected.value }));
}
watch([form, selected], persistDraft, { deep: true });

async function exportPackage() {
  if (!form.name.trim() || !form.author.trim() || !selected.value.length || busy.value) return;
  busy.value = true;
  try {
    const chosen = assets.value.filter(item => selected.value.includes(keyOf(item)));
    const result = await worldPackageApi.exportPackage({
      ...form,
      tags: form.tags.split(/[,，]/).map(item => item.trim()).filter(Boolean),
      assets: chosen.map(item => ({ type: item.type, name: item.name })),
    });
    form.package_id = result.manifest.package_id;
    persistDraft();
    const link = document.createElement('a');
    link.href = result.download_url;
    link.download = result.filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    uiStore.showToast(`世界包“${form.name}”已通过隐私检查并导出`);
  } catch (error) {
    uiStore.showToast(error.message || '导出世界包失败', 'error');
  } finally { busy.value = false; }
}

onMounted(async () => {
  try {
    const saved = JSON.parse(localStorage.getItem(DRAFT_KEY) || '{}');
    if (saved.form && typeof saved.form === 'object') Object.assign(form, saved.form);
    if (Array.isArray(saved.selected)) selected.value = saved.selected;
  } catch (_) { /* 损坏的浏览器草稿不阻止重新制作 */ }
  try {
    const data = await worldPackageApi.authoringAssets();
    assets.value = data.assets || [];
    const valid = new Set(assets.value.map(keyOf));
    selected.value = selected.value.filter(key => valid.has(key));
  } catch (error) {
    uiStore.showToast(error.message || '读取可打包资产失败', 'error');
  } finally { loading.value = false; }
});
</script>

<template>
  <div class="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm" @click.self="close">
    <section role="dialog" aria-label="创建世界包" class="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-cyan-700 bg-slate-950 shadow-2xl">
      <header class="flex items-start justify-between border-b border-slate-800 px-6 py-4">
        <div><h2 class="text-lg font-black text-cyan-200">📦 创建世界包</h2><p class="mt-1 text-xs text-slate-500">选择正式资产，生成可分享的本地文件；此操作不会上传或公开任何内容。</p></div>
        <button class="text-2xl text-slate-500 hover:text-white" @click="close">×</button>
      </header>
      <div class="grid min-h-0 flex-1 grid-cols-[minmax(0,0.95fr)_minmax(0,1.25fr)] overflow-hidden">
        <div class="overflow-y-auto border-r border-slate-800 p-5 custom-scrollbar">
          <div class="grid grid-cols-2 gap-3">
            <label class="col-span-2 text-xs font-bold text-slate-300">世界包名称<input v-model="form.name" data-testid="package-builder-name" class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 p-2.5 text-sm" placeholder="玩家会看到的作品名称" /></label>
            <label class="text-xs font-bold text-slate-300">作者<input v-model="form.author" class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 p-2.5 text-sm" placeholder="创作者名称" /></label>
            <label class="text-xs font-bold text-slate-300">版本<input v-model="form.version" class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 p-2.5 text-sm" placeholder="1.0.0" /></label>
          </div>
          <label class="mt-3 block text-xs font-bold text-slate-300">体验简介<textarea v-model="form.description" class="mt-1 h-24 w-full rounded-lg border border-slate-700 bg-slate-900 p-2.5 text-sm" placeholder="告诉玩家会获得什么体验，不要堆内部技术术语。"></textarea></label>
          <label class="mt-3 block text-xs font-bold text-slate-300">世界与故事梗概<textarea v-model="form.world_premise" class="mt-1 h-24 w-full rounded-lg border border-slate-700 bg-slate-900 p-2.5 text-sm" placeholder="新建故事时交给正文 AI 的背景；留空则使用体验简介。"></textarea></label>
          <label class="mt-3 block text-xs font-bold text-slate-300">开场文本<textarea v-model="form.opening" class="mt-1 h-24 w-full rounded-lg border border-slate-700 bg-slate-900 p-2.5 text-sm" placeholder="玩家进入新故事后首先看到的开场。"></textarea></label>
          <label class="mt-3 block text-xs font-bold text-slate-300">分类标签<input v-model="form.tags" class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 p-2.5 text-sm" placeholder="奇幻，悬疑，短篇" /></label>
          <div class="mt-3 grid grid-cols-2 gap-3">
            <label class="text-xs font-bold text-slate-300">许可证<input v-model="form.license" class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 p-2.5 text-sm" placeholder="unspecified" /></label>
            <label class="flex items-center gap-2 self-end rounded-lg border border-slate-700 bg-slate-900 p-2.5 text-xs text-slate-300"><input v-model="form.adult" type="checkbox" /> 包含成人内容</label>
          </div>
          <details class="mt-4 rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-xs text-slate-500">
            <summary class="cursor-pointer font-bold text-slate-300">作品身份（高级）</summary>
            <p class="mt-2 leading-5">首次导出后自动生成。更新同一个世界包时保留该 ID 并提高版本号；新作品请清空。</p>
            <input v-model="form.package_id" class="mt-2 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-[10px]" placeholder="首次导出自动生成" />
          </details>
        </div>
        <div class="flex min-h-0 flex-col p-5">
          <div class="mb-3 flex items-center justify-between"><div><h3 class="font-bold text-slate-200">选择包内资产</h3><p class="mt-1 text-[10px] text-slate-500">只读取全局正式资产；不打包存档、日志、密钥、偏好或工坊草稿。</p></div><span class="rounded bg-cyan-950 px-2 py-1 text-xs text-cyan-300">已选 {{ selected.length }}</span></div>
          <div v-if="loading" class="flex flex-1 items-center justify-center text-sm text-slate-500">正在读取资产……</div>
          <div v-else class="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1 custom-scrollbar">
            <details v-for="group in groups" :key="group.type" open class="rounded-xl border border-slate-800 bg-slate-900/45 p-3">
              <summary class="cursor-pointer text-sm font-bold text-slate-200">{{ group.icon }} {{ group.label }} · {{ group.items.length }}</summary>
              <div class="mt-2 space-y-2">
                <button v-for="item in group.items" :key="keyOf(item)" type="button" class="flex w-full items-start gap-3 rounded-lg border p-3 text-left" :class="isSelected(item)?'border-cyan-600 bg-cyan-950/35':'border-slate-700 bg-slate-950/40 hover:border-slate-500'" @click="toggle(item)">
                  <input type="checkbox" class="mt-0.5" :checked="isSelected(item)" tabindex="-1" />
                  <span class="min-w-0"><strong class="block truncate text-xs text-slate-200">{{ item.name }}</strong><span class="mt-1 line-clamp-2 block text-[10px] leading-4 text-slate-500">{{ item.description || '未填写简介' }}</span><span v-if="item.is_template" class="mt-1 inline-block rounded bg-indigo-950 px-1.5 py-0.5 text-[9px] text-indigo-300">模板</span></span>
                </button>
                <p v-if="!group.items.length" class="py-3 text-center text-xs text-slate-600">暂无可选资产</p>
              </div>
            </details>
          </div>
        </div>
      </div>
      <footer class="flex items-center justify-between gap-4 border-t border-slate-800 px-6 py-4">
        <p class="text-[10px] text-slate-500">导出前会执行路径、隐私、哈希与格式检查。下载不等于发布。</p>
        <div class="flex gap-2"><button class="rounded bg-slate-800 px-4 py-2 text-sm" @click="close">取消</button><button data-testid="package-builder-export" class="rounded bg-emerald-700 px-5 py-2 text-sm font-bold text-white disabled:opacity-35" :disabled="busy || !form.name.trim() || !form.author.trim() || !selected.length" @click="exportPackage">{{ busy ? '正在检查并导出…' : '导出世界包' }}</button></div>
      </footer>
    </section>
  </div>
</template>
