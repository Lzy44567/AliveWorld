<script setup>
import { ref } from 'vue';
import { worldPackageApi } from '../../api/worldPackageApi';
import { assetStore } from '../../store/assetStore';
import { configStore } from '../../store/configStore';
import { uiStore } from '../../store/uiStore';
import ExternalAssetImportModal from './ExternalAssetImportModal.vue';

const props = defineProps({ packages: { type: Array, default: () => [] } });
const emit = defineEmits(['close', 'refresh']);
const busy = ref(false);
const preview = ref(null);
const pendingFile = ref(null);
const uninstallTarget = ref(null);
const selectedStoryPaths = ref([]);
const externalImportKind = ref('');

const chooseFile = async (event) => {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (!file) return;
  busy.value = true;
  try {
    preview.value = await worldPackageApi.inspect(file);
    pendingFile.value = file;
  } catch (error) {
    uiStore.showToast(error.message || '世界包检查失败', 'error');
  } finally { busy.value = false; }
};

const installOnly = async () => {
  if (!pendingFile.value || ['same', 'version_collision'].includes(preview.value?.status)) return;
  busy.value = true;
  try {
    await worldPackageApi.install(pendingFile.value);
    uiStore.showToast(`世界包“${preview.value.manifest.name}”已安装`);
    preview.value = null;
    pendingFile.value = null;
    emit('refresh');
  } catch (error) { uiStore.showToast(error.message || '安装失败', 'error'); }
  finally { busy.value = false; }
};

const openUninstall = (item) => {
  uninstallTarget.value = item;
  selectedStoryPaths.value = configStore.uiPreferences.deleteWorldPackageStoriesByDefault
    ? (item.related_stories || []).map(story => story.path)
    : [];
};

const closeUninstall = () => {
  uninstallTarget.value = null;
  selectedStoryPaths.value = [];
};

const uninstall = async () => {
  if (!uninstallTarget.value) return;
  busy.value = true;
  try {
    const item = uninstallTarget.value;
    const result = await worldPackageApi.uninstall(
      item.package_id, item.version, 'safe', false, selectedStoryPaths.value,
    );
    const notes = [];
    if (result.preserved_paths?.length) notes.push(`保留 ${result.preserved_paths.length} 个修改资产`);
    if (result.deleted_story_paths?.length) notes.push(`删除 ${result.deleted_story_paths.length} 个故事`);
    uiStore.showToast(`世界包已安全卸载${notes.length ? `；${notes.join('，')}` : ''}`);
    closeUninstall();
    emit('refresh');
    await assetStore.fetchAssets();
  } catch (error) { uiStore.showToast(error.message || '卸载失败', 'error'); }
  finally { busy.value = false; }
};
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm" @click.self="emit('close')">
    <section role="dialog" aria-label="世界包管理" class="flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-cyan-800 bg-slate-950 shadow-2xl">
      <header class="flex items-center justify-between border-b border-slate-800 px-5 py-4">
        <div>
          <h2 class="text-lg font-black text-cyan-300">📦 世界包管理</h2>
          <p class="mt-1 text-xs text-slate-500">管理安装源、版本、来源和关联故事；不会按名称猜测资产归属。</p>
        </div>
        <button class="text-xl text-slate-500 hover:text-white" @click="emit('close')">✕</button>
      </header>

      <div class="min-h-0 flex-1 overflow-y-auto p-5 custom-scrollbar">
        <div class="flex flex-wrap items-center gap-3 rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <label class="cursor-pointer rounded-lg bg-cyan-700 px-4 py-2 text-xs font-bold text-white hover:bg-cyan-600">
            {{ busy ? '处理中…' : '＋ 仅安装世界包' }}
            <input type="file" accept=".aliveworld" class="hidden" :disabled="busy" @change="chooseFile">
          </label>
          <label class="ml-auto flex cursor-pointer items-center gap-2 text-xs text-slate-400">
            <input v-model="configStore.uiPreferences.deleteWorldPackageStoriesByDefault" type="checkbox" class="accent-rose-500">
            卸载时默认勾选关联故事
          </label>
          <p class="w-full text-[10px] text-slate-600">默认关闭。它只改变复选框初态；删除前仍会显示故事并要求确认。</p>
        </div>

        <section class="mt-3 rounded-xl border border-indigo-900/70 bg-indigo-950/20 p-3">
          <div><h3 class="text-sm font-bold text-indigo-200">外部资产兼容导入</h3><p class="mt-1 text-[10px] leading-4 text-slate-500">支持 Character Card V2/V3 JSON、PNG 角色卡与常见 Lorebook JSON。导入前会显示降级和未支持字段。</p></div>
          <div class="mt-3 flex flex-wrap gap-2">
            <button data-testid="import-external-character" class="rounded-lg border border-indigo-700 bg-indigo-900/40 px-3 py-2 text-xs text-indigo-200 hover:bg-indigo-800" @click="externalImportKind='character'">⇩ 导入角色卡</button>
            <button data-testid="import-external-lorebook" class="rounded-lg border border-cyan-700 bg-cyan-900/30 px-3 py-2 text-xs text-cyan-200 hover:bg-cyan-800" @click="externalImportKind='lorebook'">⇩ 导入世界书</button>
          </div>
        </section>

        <section v-if="preview" class="mt-3 rounded-xl border border-cyan-800 bg-cyan-950/20 p-3">
          <div class="flex justify-between gap-3">
            <div>
              <p class="font-bold text-slate-100">{{ preview.manifest.name }}</p>
              <p class="mt-1 text-[10px] text-slate-500">v{{ preview.manifest.version }} · {{ preview.manifest.author }} · {{ preview.manifest.assets.length }} 项资产</p>
            </div>
            <button class="text-slate-500" @click="preview=null; pendingFile=null">✕</button>
          </div>
          <p v-if="preview.status==='version_collision'" class="mt-2 text-xs text-rose-300">同一包 ID 与版本对应不同内容，已阻止覆盖。</p>
          <p v-for="conflict in preview.conflicts" :key="`${conflict.kind}:${conflict.asset_id || conflict.package_id}`" class="mt-2 text-xs text-amber-300">{{ conflict.message || `资产“${conflict.name}”存在版本变化。` }}</p>
          <button class="mt-3 rounded bg-cyan-700 px-4 py-2 text-xs font-bold text-white disabled:opacity-40" :disabled="busy || ['same','version_collision'].includes(preview.status)" @click="installOnly">确认仅安装</button>
        </section>

        <div v-if="!props.packages.length" class="py-12 text-center text-sm text-slate-500">当前没有已安装世界包。</div>
        <div v-else class="mt-4 space-y-3">
          <article v-for="item in props.packages" :key="`${item.package_id}:${item.version}`" class="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <h3 class="font-bold text-slate-100">{{ item.name }}</h3>
                <p class="mt-1 text-[10px] text-slate-500">v{{ item.version }} · {{ item.author }} · {{ item.assets.length }} 项资产</p>
                <div class="mt-2 flex flex-wrap gap-1">
                  <span v-for="tag in item.system_tags" :key="tag" class="rounded bg-slate-800 px-1.5 py-0.5 text-[9px] text-slate-500" title="系统来源标签不可修改">🔒 {{ tag }}</span>
                </div>
                <p class="mt-2 text-[10px] text-slate-500">关联故事 {{ item.related_stories?.length || 0 }} 个</p>
              </div>
              <button class="rounded border border-rose-900 px-3 py-2 text-xs text-rose-300 hover:bg-rose-950/50" @click="openUninstall(item)">卸载</button>
            </div>
          </article>
        </div>
      </div>
    </section>

    <div v-if="uninstallTarget" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 p-4" @click.self="closeUninstall">
      <section class="w-full max-w-lg rounded-2xl border border-rose-900 bg-slate-950 p-5 shadow-2xl">
        <h3 class="text-lg font-bold text-rose-300">卸载“{{ uninstallTarget.name }}”</h3>
        <p class="mt-2 text-xs leading-5 text-slate-400">安装源将移入恢复区。下面的故事默认全部保留；只有你明确勾选的故事才会一同删除。</p>
        <div v-if="uninstallTarget.related_stories?.length" class="mt-4 max-h-56 space-y-2 overflow-y-auto rounded-xl border border-slate-800 p-3 custom-scrollbar">
          <label v-for="story in uninstallTarget.related_stories" :key="story.path" class="flex cursor-pointer items-center gap-3 rounded-lg bg-slate-900 p-3 text-sm text-slate-200">
            <input v-model="selectedStoryPaths" :value="story.path" type="checkbox" class="accent-rose-600">
            <span class="min-w-0"><span class="block font-bold">{{ story.save_name }}</span><span class="block truncate text-[10px] text-slate-600">由 v{{ story.package_version }} 创建</span></span>
          </label>
        </div>
        <p v-else class="mt-4 rounded-lg bg-slate-900 p-3 text-xs text-slate-500">没有找到由该版本创建的故事。</p>
        <p v-if="selectedStoryPaths.length" class="mt-3 text-xs font-bold text-rose-300">将永久删除 {{ selectedStoryPaths.length }} 个已勾选故事，此操作不进入世界包恢复区。</p>
        <div class="mt-5 flex gap-2">
          <button class="flex-1 rounded bg-slate-700 py-2 text-sm" @click="closeUninstall">取消</button>
          <button class="flex-1 rounded bg-rose-700 py-2 text-sm font-bold text-white disabled:opacity-40" :disabled="busy" @click="uninstall">确认卸载</button>
        </div>
      </section>
    </div>
    <ExternalAssetImportModal v-if="externalImportKind" :kind="externalImportKind" @close="externalImportKind=''" @imported="emit('refresh')" />
  </div>
</template>
