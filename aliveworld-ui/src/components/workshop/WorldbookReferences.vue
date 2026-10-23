<script setup>
import { computed, ref, watch } from 'vue';
import { workshopStore } from '../../store/workshopStore';
import { worldbookWorkshopApi } from '../../api/worldbookWorkshopApi';
const items = ref([]), selected = ref([]), error = ref(''), search = ref(''), loading = ref(false);
let generation = 0;
const visible = computed(() => items.value.filter(item => item.name.includes(search.value) || item.source_id.includes(search.value)));
const focus = computed(() => workshopStore.draft?.entries?.find(e => e.id === workshopStore.context.focusEntryId));
async function load() {
  const id = workshopStore.workshopId, epoch = ++generation;
  if (!id || workshopStore.type !== 'worldbooks') return;
  loading.value = true;
  try {
    const data = await worldbookWorkshopApi.references(id);
    if (epoch !== generation || id !== workshopStore.workshopId) return;
    items.value = data.items; selected.value = workshopStore.context.references.map(r => r.source_id); error.value = '';
  } catch (e) { if (epoch === generation) error.value = e.message; }
  finally { if (epoch === generation) loading.value = false; }
}
watch(() => workshopStore.workshopId, () => { items.value = []; selected.value = []; search.value = ''; load(); }, { immediate: true });
async function save(ids) {
  const id = workshopStore.workshopId;
  if (await workshopStore.saveReauthoring({ reference_ids: ids }) && id === workshopStore.workshopId) selected.value = [...ids];
}
</script>

<template>
  <div v-if="workshopStore.type === 'worldbooks'" class="mt-2 text-xs" data-testid="worldbook-reauthoring">
    <div v-if="workshopStore.context.focusEntryId" class="flex items-center justify-between gap-2 rounded-lg border border-violet-800 bg-violet-950/40 p-2 text-violet-200">
      <span>定向重写：{{ focus?.name || '目标条目已移除，请清除目标' }} · 仅生成待审修改</span>
      <button :disabled="workshopStore.busy || workshopStore.published" @click="workshopStore.saveReauthoring({ focus_entry_id: '' })">清除定向</button>
    </div>
    <details class="mt-2 rounded-lg border border-slate-700 p-2">
      <summary class="cursor-pointer text-cyan-300">参考世界书 · 已保存 {{ workshopStore.context.references.length }} 本</summary>
      <p class="my-2 text-slate-400">同一{{ workshopStore.scope === 'local' ? '故事' : '全局目录' }}内选择最多3本。保存快照不会调用AI；后续发送会携带参考内容并增加token。只改当前目标书，不改参考书。</p>
      <p class="mb-2 text-amber-300/80">融合结果发布后，不要与互斥原书同时启用。需要保留目标原版时请先克隆。</p>
      <p v-for="item in workshopStore.context.references" :key="item.source_id" class="text-slate-400">已保存快照：{{ item.name }} · {{ item.entries }} 条 · {{ item.characters }} 字符</p>
      <div class="my-2 flex gap-2"><input v-model="search" placeholder="搜索参考世界书" class="min-w-0 flex-1 rounded bg-slate-900 px-2 py-1 text-slate-200" /><button :disabled="loading || workshopStore.busy" @click="load">刷新目录</button></div>
      <p v-if="error" role="alert" class="text-rose-300">{{ error }}</p>
      <div class="grid max-h-48 grid-cols-2 gap-2 overflow-y-auto">
        <label v-for="item in visible" :key="item.source_id" class="flex gap-2 rounded border border-slate-700 bg-slate-900 p-2 text-slate-300">
          <input v-model="selected" type="checkbox" :value="item.source_id" :aria-label="`参考 ${item.name}`" :disabled="workshopStore.busy || workshopStore.published || (!selected.includes(item.source_id) && selected.length >= 3)" />
          <span class="min-w-0 break-words">{{ item.name }}<small class="block text-slate-500">{{ item.source_id }} · {{ item.entries }} 条</small></span>
        </label>
      </div>
      <p v-if="!items.length && !loading" class="text-slate-500">当前范围没有其他世界书。</p>
      <div class="mt-2 flex gap-3 text-cyan-300"><button :disabled="workshopStore.busy || loading || workshopStore.published" @click="save(selected)">保存 / 更新参考快照</button><button :disabled="workshopStore.busy || workshopStore.published" @click="save([])">清空参考</button></div>
    </details>
  </div>
</template>
