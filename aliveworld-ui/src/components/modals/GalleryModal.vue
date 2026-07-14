<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { gameStore } from '../../store/gameStore';
import { imageApi } from '../../api/imageApi';
import { assetStore } from '../../store/assetStore';

const close = () => { uiStore.modals.gallery = false; };
const filter = ref('all');
const scopeFilter = ref('all');
const selectedUrl = ref('');
const deleteConfirmId = ref('');
const libraryTasks = ref([]);
const loading = ref(false);
let refreshHandle = null;
const scopes = computed(() => {
  const map = new Map(libraryTasks.value.map(task => [task.scope_id, task.scope_name]));
  return [...map].map(([id, name]) => ({ id, name }));
});
const completed = computed(() => libraryTasks.value.filter(task =>
  task.status === 'succeeded' && task.output_images?.length &&
  (filter.value === 'all' || (filter.value === 'test' ? task.context_snapshot?.test_task : task.intent === filter.value)) &&
  (scopeFilter.value === 'all' || task.scope_id === scopeFilter.value)
));
const loadLibrary = async ({ silent = false } = {}) => {
  loading.value = true;
  try { libraryTasks.value = await imageApi.listLibrary(); }
  catch (error) { if (!silent) uiStore.showToast(error.message, 'error'); }
  finally { loading.value = false; }
};
onMounted(() => { loadLibrary(); refreshHandle = window.setInterval(() => loadLibrary({ silent: true }), 3000); });
onBeforeUnmount(() => { if (refreshHandle) window.clearInterval(refreshHandle); });

const canSetPortrait = task => Boolean(gameStore.sessionId && task.scope_kind === 'save' && task.scope_name === gameStore.currentSaveName && task.intent === 'character_portrait');
const setPortrait = async task => {
  const characterName = task.character_ids?.[0];
  if (!characterName) return uiStore.showToast('该立绘没有关联角色', 'error');
  try {
    await imageApi.setPortrait(gameStore.sessionId, task.id, characterName, 0, 'local');
    await assetStore.fetchLocalAssets(gameStore.sessionId);
    uiStore.showToast(`已设为 ${characterName} 的本局立绘`);
  } catch (error) { uiStore.showToast(error.message, 'error'); }
};
const regenerate = async task => {
  try { await imageApi.regenerateLibraryTask(task.scope_id, task.id); await loadLibrary(); uiStore.showToast('已创建新的重生成任务'); }
  catch (error) { uiStore.showToast(error.message, 'error'); }
};
const removeTask = async task => {
  try { await imageApi.deleteLibraryTask(task.scope_id, task.id); deleteConfirmId.value = ''; await loadLibrary(); uiStore.showToast('图片与任务记录已删除'); }
  catch (error) { uiStore.showToast(error.message, 'error'); }
};
</script>

<template>
  <div class="fixed inset-0 z-[70] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
    <div class="flex h-[82vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-slate-600 bg-aw_panel shadow-2xl slide-up">
      <div class="flex justify-between border-b border-slate-700 bg-slate-900/80 p-4">
        <div><h2 class="flex items-center gap-2 text-lg font-bold text-amber-400">🖼️ 统一图片资源库</h2><p class="text-[10px] text-slate-500">集中管理全局测试图与所有故事存档生成的图片；删除仍会检查角色立绘引用</p></div><button @click="close" class="text-xl text-slate-400 hover:text-white">✕</button>
      </div>
      <div class="flex flex-wrap gap-2 border-b border-slate-800 px-6 py-3">
        <button v-for="item in [{id:'all',name:'全部类型'},{id:'test',name:'测试图'},{id:'character_portrait',name:'角色立绘'},{id:'character_cg',name:'角色 CG'},{id:'scene_cg',name:'场景 CG'}]" :key="item.id" @click="filter=item.id" class="rounded-full border px-3 py-1 text-xs" :class="filter===item.id?'border-amber-500 bg-amber-950/50 text-amber-300':'border-slate-700 text-slate-400'">{{ item.name }}</button>
        <select v-model="scopeFilter" class="ml-auto rounded border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300"><option value="all">全部来源</option><option v-for="scope in scopes" :key="scope.id" :value="scope.id">{{ scope.name }}</option></select>
      </div>
      <div class="custom-scrollbar flex-1 overflow-y-auto bg-slate-900/30 p-6">
        <div v-if="loading && !libraryTasks.length" class="flex h-full items-center justify-center text-sm text-slate-500">正在读取图片资源……</div>
        <div v-else-if="!completed.length" class="flex h-full items-center justify-center text-sm text-slate-500">当前筛选条件下没有图片</div>
        <div v-else class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          <article v-for="task in completed" :key="`${task.scope_id}:${task.id}`" class="group overflow-hidden rounded-lg border border-slate-700 bg-slate-900">
            <div class="grid gap-1" :class="task.output_images.length > 1 ? 'grid-cols-2' : 'grid-cols-1'"><img v-for="url in task.output_images" :key="url" :src="imageApi.absoluteImageUrl(url)" @click="selectedUrl=imageApi.absoluteImageUrl(url)" class="aspect-square w-full cursor-zoom-in object-cover opacity-90 transition group-hover:opacity-100"></div>
            <div class="p-2"><div class="flex items-center justify-between gap-2 text-[10px]"><span class="text-amber-300">{{ task.context_snapshot?.test_task ? '接口测试图' : {character_portrait:'角色立绘',character_cg:'角色 CG',scene_cg:'场景 CG'}[task.intent] }}</span><span class="truncate text-slate-500">{{ task.scope_name }}</span></div><div class="mt-1 truncate text-[9px] text-slate-500">{{ task.character_ids?.join('、') || task.context_snapshot?.story_text || task.id }}</div><button v-if="canSetPortrait(task)" @click="setPortrait(task)" class="mt-2 w-full rounded bg-fuchsia-900/50 py-1 text-[10px] text-fuchsia-200 hover:bg-fuchsia-700">设为本局立绘</button><div class="mt-2 flex justify-end gap-1 text-[10px]"><button @click="regenerate(task)" class="rounded bg-fuchsia-900/50 px-2 py-1 text-fuchsia-200">重新生成</button><template v-if="deleteConfirmId===`${task.scope_id}:${task.id}`"><button @click="removeTask(task)" class="rounded bg-rose-700 px-2 py-1 text-white">确认删除</button><button @click="deleteConfirmId=''" class="rounded bg-slate-700 px-2 py-1">取消</button></template><button v-else @click="deleteConfirmId=`${task.scope_id}:${task.id}`" class="rounded bg-rose-950/50 px-2 py-1 text-rose-300">删除</button></div></div>
          </article>
        </div>
      </div>
    </div>
    <div v-if="selectedUrl" @click="selectedUrl=''" class="fixed inset-0 z-[90] flex cursor-zoom-out items-center justify-center bg-black/90 p-8"><img :src="selectedUrl" class="max-h-full max-w-full rounded-lg object-contain" /></div>
  </div>
</template>
