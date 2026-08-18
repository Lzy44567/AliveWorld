<script setup>
import { computed, onMounted, ref } from 'vue';
import { worldPackageApi } from '../../api/worldPackageApi';
import { assetStore } from '../../store/assetStore';
import { configStore } from '../../store/configStore';
import { gameStore } from '../../store/gameStore';
import { uiStore } from '../../store/uiStore';
import WorldPackageManagerModal from '../modals/WorldPackageManagerModal.vue';

const packages = ref([]);
const preview = ref(null);
const pendingFile = ref(null);
const busy = ref(false);
const startTarget = ref(null);
const saveName = ref('');
const managerOpen = ref(false);

const previewStatus = computed(() => ({
  new: '新的世界包', update: '可安装的新版本', downgrade: '较旧版本', same: '已经安装',
  version_collision: '版本号相同但内容不同',
}[preview.value?.status] || '待检查'));

const refresh = async () => {
  const data = await worldPackageApi.list();
  packages.value = data.packages || [];
};

const chooseFile = async (event) => {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (!file) return;
  busy.value = true;
  try {
    preview.value = await worldPackageApi.inspect(file);
    pendingFile.value = file;
    saveName.value = preview.value.manifest.name;
  } catch (error) {
    preview.value = null;
    pendingFile.value = null;
    uiStore.showToast(error.message || '世界包检查失败', 'error');
  } finally { busy.value = false; }
};

const install = async () => {
  if (!pendingFile.value || ['same', 'version_collision'].includes(preview.value?.status)) return;
  busy.value = true;
  try {
    await worldPackageApi.install(pendingFile.value);
    uiStore.showToast(`世界包“${preview.value.manifest.name}”已安装`);
    pendingFile.value = null;
    preview.value = null;
    await refresh();
  } catch (error) { uiStore.showToast(error.message || '安装失败', 'error'); }
  finally { busy.value = false; }
};

const applyStartedStory = async (data, name) => {
  gameStore.sessionId = data.session_id;
  gameStore.currentSaveName = name;
  gameStore.chatLog = data.chat_messages || [];
  gameStore.setActionSuggestions(data.action_suggestions);
  gameStore.syncState(data.state);
  configStore.applyStoryConfig(data);
  await assetStore.fetchAssets();
  await assetStore.fetchLocalAssets(data.session_id);
  uiStore.rightTab = 'saves';
};

const installAndStart = async () => {
  if (!pendingFile.value || !saveName.value.trim() || preview.value?.status === 'version_collision') return;
  gameStore.isProcessing = true;
  try {
    const name = saveName.value.trim();
    const data = await worldPackageApi.installAndStart(pendingFile.value, name);
    await applyStartedStory(data, name);
    pendingFile.value = null;
    preview.value = null;
    await refresh();
    uiStore.showToast('世界包已安装，故事已建立');
  } catch (error) { uiStore.showToast(error.message || '安装并开始失败', 'error'); }
  finally { gameStore.isProcessing = false; }
};

const openStart = (item) => {
  startTarget.value = item;
  saveName.value = item.name;
};

const startStory = async () => {
  if (!startTarget.value || !saveName.value.trim()) return;
  gameStore.isProcessing = true;
  try {
    const data = await worldPackageApi.start(startTarget.value.package_id, startTarget.value.version, saveName.value.trim());
    await applyStartedStory(data, saveName.value.trim());
    startTarget.value = null;
    uiStore.rightTab = 'saves';
    uiStore.showToast('世界包故事已建立，可以直接开始游玩');
  } catch (error) { uiStore.showToast(error.message || '一键开始失败', 'error'); }
  finally { gameStore.isProcessing = false; }
};

onMounted(() => refresh().catch(error => uiStore.showToast(error.message, 'error')));
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col" data-testid="world-packages-panel">
    <div class="mb-3 flex items-center justify-between shrink-0">
      <div><h2 class="text-sm font-black text-slate-200">开始与世界包</h2><p class="mt-0.5 text-[10px] text-slate-500">选择完整世界，或从空白故事开始</p></div>
      <button data-testid="world-package-manage" class="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-300 hover:border-cyan-700 hover:text-cyan-300" @click="managerOpen=true">⚙ 管理</button>
    </div>
    <div class="mb-3 grid grid-cols-2 gap-2 shrink-0">
      <label class="cursor-pointer rounded-lg border border-cyan-700/60 bg-cyan-950/30 px-3 py-2 text-center text-xs font-bold text-cyan-300 hover:bg-cyan-900/50">
        {{ busy ? '处理中…' : '📦 导入并开始' }}
        <input data-testid="world-package-file" type="file" accept=".aliveworld" class="hidden" :disabled="busy" @change="chooseFile" />
      </label>
      <button class="rounded-lg border border-emerald-700/60 bg-emerald-950/30 px-3 py-2 text-xs font-bold text-emerald-300 hover:bg-emerald-900/50" @click="uiStore.modals.newGame=true">＋ 空白故事</button>
    </div>

    <section v-if="preview" class="mb-3 shrink-0 rounded-xl border p-3" :class="preview.status==='version_collision'?'border-rose-700 bg-rose-950/20':'border-cyan-700 bg-cyan-950/20'" data-testid="world-package-preview">
      <div class="flex items-start justify-between gap-2">
        <div>
          <p class="font-bold text-slate-100">{{ preview.manifest.name }}</p>
          <p class="mt-1 text-[10px] text-slate-400">{{ previewStatus }} · v{{ preview.manifest.version }} · {{ preview.manifest.assets.length }} 项内容</p>
        </div>
        <button class="text-slate-500 hover:text-white" @click="preview=null; pendingFile=null">✕</button>
      </div>
      <p v-if="preview.status==='version_collision'" class="mt-2 text-xs text-rose-300">相同版本号对应不同内容。请让作者提高版本号，AliveWorld 不会静默覆盖。</p>
      <p v-for="conflict in preview.conflicts" :key="`${conflict.kind}:${conflict.asset_id || conflict.package_id}`" class="mt-2 text-xs text-amber-300">{{ conflict.message || `资产“${conflict.name}”已有旧版本，安装时仍会保留版本边界。` }}</p>
      <label class="mt-3 block text-xs font-bold text-slate-300">故事线名称</label>
      <input v-model="saveName" class="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 p-2.5 text-sm outline-none focus:border-cyan-600" @keydown.enter="installAndStart">
      <div class="mt-3 flex gap-2">
        <button data-testid="world-package-install-start" class="flex-1 rounded bg-emerald-700 py-2 text-xs font-bold text-white disabled:opacity-40" :disabled="gameStore.isProcessing || !saveName.trim() || preview.status==='version_collision'" @click="installAndStart">安装并开始</button>
        <button data-testid="world-package-install" class="rounded bg-cyan-800 px-3 py-2 text-xs font-bold text-white disabled:opacity-40" :disabled="busy || ['same','version_collision'].includes(preview.status)" @click="install">仅安装</button>
        <button class="rounded bg-slate-700 px-3 py-2 text-xs" @click="preview=null; pendingFile=null">取消</button>
      </div>
    </section>

    <div v-if="!packages.length" class="flex flex-1 flex-col items-center justify-center px-6 text-center text-slate-500">
      <div class="mb-3 text-4xl">🌌</div>
      <p class="font-bold text-slate-300">还没有安装世界包</p>
      <p class="mt-2 text-xs leading-5">世界包会准备好世界、角色、文风与开场。你也可以先创建空白故事，继续使用原有自由创作流程。</p>
    </div>

    <div v-else class="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1 custom-scrollbar">
      <article v-for="item in packages" :key="`${item.package_id}:${item.version}`" class="rounded-xl border border-slate-700 bg-aw_panel p-4" :data-package-name="item.name">
        <div class="flex items-start justify-between gap-2">
          <div>
            <h3 class="font-bold text-slate-100">{{ item.name }}</h3>
            <p class="mt-1 text-[10px] text-slate-500">v{{ item.version }} · {{ item.author }}</p>
          </div>
          <span v-if="item.adult" class="rounded border border-rose-800 bg-rose-950/50 px-1.5 py-0.5 text-[9px] text-rose-300">成人内容</span>
        </div>
        <p class="mt-3 line-clamp-3 text-xs leading-5 text-slate-400">{{ item.description || '作者暂未填写体验简介。' }}</p>
        <div class="mt-2 flex flex-wrap gap-1">
          <span v-for="tag in item.tags" :key="tag" class="rounded border border-slate-700 bg-slate-900 px-1.5 py-0.5 text-[9px] text-slate-400">{{ tag }}</span>
        </div>
        <p v-if="!item.healthy" class="mt-2 text-[10px] text-amber-300">本地内容有 {{ item.modified_asset_ids.length }} 项修改、{{ item.missing_asset_ids.length }} 项丢失；开始前请检查。</p>
        <div class="mt-4"><button data-testid="world-package-start" class="w-full rounded bg-emerald-700 py-2 text-xs font-bold text-white hover:bg-emerald-600" @click="openStart(item)">▶ 创建新故事</button></div>
      </article>
    </div>

    <div v-if="startTarget" class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm" @click.self="startTarget=null">
      <section role="dialog" aria-label="从世界包开始" class="w-full max-w-md rounded-2xl border border-emerald-800 bg-slate-900 p-5 shadow-2xl">
        <h3 class="text-lg font-bold text-emerald-300">从“{{ startTarget.name }}”开始</h3>
        <p class="mt-2 text-xs leading-5 text-slate-400">系统会创建一份独立故事。以后修改或卸载世界包都不会删除这份故事。</p>
        <label class="mt-4 block text-xs font-bold text-slate-300">故事线名称</label>
        <input data-testid="world-package-save-name" v-model="saveName" class="mt-2 w-full rounded-lg border border-slate-600 bg-slate-950 p-3 text-sm outline-none focus:border-emerald-500" @keydown.enter="startStory" />
        <div class="mt-5 flex gap-2">
          <button class="flex-1 rounded bg-slate-700 py-2 text-sm" @click="startTarget=null">取消</button>
          <button data-testid="world-package-confirm-start" class="flex-1 rounded bg-emerald-700 py-2 text-sm font-bold text-white disabled:opacity-40" :disabled="gameStore.isProcessing || !saveName.trim()" @click="startStory">{{ gameStore.isProcessing ? '正在建立…' : '建立并进入故事' }}</button>
        </div>
      </section>
    </div>
    <WorldPackageManagerModal v-if="managerOpen" :packages="packages" @close="managerOpen=false" @refresh="refresh" />
  </div>
</template>
