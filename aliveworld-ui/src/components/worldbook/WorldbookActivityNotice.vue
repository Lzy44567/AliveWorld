<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { gameStore } from '../../store/gameStore';
import { uiStore } from '../../store/uiStore';
import { fetchWorldbookActivity } from '../../api/worldbookActivityApi';
import { activityTracker, notificationRows } from '../../utils/worldbookActivity';
import { effectiveStorySettings } from '../../store/configStore';

const count = ref(0);
const rows = ref([]);
const enabled = computed(() => effectiveStorySettings.value.worldbookNotices);
const detailed = computed(() => enabled.value && effectiveStorySettings.value.worldbookDetailedNotices);
const content = computed(() => detailed.value && effectiveStorySettings.value.worldbookNoticeContent);
let timer, hideTimer, disposed = false, generation = 0;
async function poll(id, epoch) {
  if (disposed || epoch !== generation) return;
  try {
    if (id && !document.hidden && uiStore.appMode === 'game') {
      const data = await fetchWorldbookActivity(id, { details: content.value });
      if (disposed || epoch !== generation || id !== gameStore.sessionId) return;
      const added = activityTracker.observeIds(id, data.ids);
      if (enabled.value && added.length) {
        count.value += added.length;
        rows.value = [...notificationRows(data.items, added, content.value), ...rows.value].slice(0, 3);
        clearTimeout(hideTimer);
        hideTimer = setTimeout(() => { count.value = 0; rows.value = []; }, detailed.value ? 12000 : 6500);
      }
    }
  } catch { /* Explicit history refresh shows errors; background checks stay quiet. */ }
  if (!disposed && epoch === generation) timer = setTimeout(() => poll(id, epoch), 5000);
}
watch(() => [gameStore.sessionId, enabled.value, detailed.value, content.value], ([id, active], previous) => {
  if (previous && previous[0] === id && !previous[1] && active) activityTracker.reset(id);
  clearTimeout(timer); clearTimeout(hideTimer); count.value = 0; rows.value = [];
  poll(id, ++generation);
}, { immediate: true });
onBeforeUnmount(() => { disposed = true; clearTimeout(timer); clearTimeout(hideTimer); });
function openHistory() {
  uiStore.rightDrawerOpen = true;
  uiStore.rightTab = 'world';
  uiStore.assetScope = 'local';
  uiStore.worldbookActivityOpen = true;
  uiStore.worldbookActivityRefresh++;
  count.value = 0;
}
</script>

<template>
  <Transition enter-active-class="transition duration-200" leave-active-class="transition duration-300" enter-from-class="opacity-0 translate-y-2" leave-to-class="opacity-0">
    <button v-if="enabled && count && uiStore.appMode === 'game'" data-testid="worldbook-activity-notice" class="absolute bottom-36 right-4 z-20 max-h-[40vh] w-80 max-w-[85%] overflow-y-auto rounded-xl border border-cyan-700 bg-slate-900/95 px-4 py-3 text-left text-xs text-cyan-200 shadow-lg" @click="openHistory">
      世界书新增 {{ count }} 条修订记录 · 点击查看
      <span v-if="detailed" class="mt-2 block space-y-2">
        <span v-for="row in rows" :key="row.id" class="block border-t border-slate-700 pt-2" data-testid="worldbook-notice-row">
          <span class="block break-words text-slate-200">{{ row.book }} · {{ row.summary }}</span>
          <span v-if="content && row.title" class="mt-1 block break-words">{{ row.title }}</span>
          <span v-if="content && row.excerpt" class="mt-1 block whitespace-pre-wrap break-words text-slate-400">{{ row.excerpt }} <span class="text-slate-500">（摘录）</span></span>
        </span>
        <span v-if="count > rows.length" class="block text-slate-400">其余 {{ count - rows.length }} 条请到修订记录查看</span>
      </span>
    </button>
  </Transition>
</template>
