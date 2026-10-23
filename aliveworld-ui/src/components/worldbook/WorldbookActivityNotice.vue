<script setup>
import { onBeforeUnmount, ref, watch } from 'vue';
import { gameStore } from '../../store/gameStore';
import { uiStore } from '../../store/uiStore';
import { fetchWorldbookActivity } from '../../api/worldbookActivityApi';
import { activityTracker } from '../../utils/worldbookActivity';

const count = ref(0);
let timer, hideTimer, disposed = false, generation = 0;
async function poll(id, epoch) {
  if (disposed || epoch !== generation) return;
  try {
    if (id && !document.hidden && uiStore.appMode === 'game') {
      const data = await fetchWorldbookActivity(id);
      if (disposed || epoch !== generation || id !== gameStore.sessionId) return;
      const added = activityTracker.observe(id, data.ids);
      if (added) {
        count.value += added;
        clearTimeout(hideTimer);
        hideTimer = setTimeout(() => { count.value = 0; }, 6500);
      }
    }
  } catch { /* Explicit history refresh shows errors; background checks stay quiet. */ }
  if (!disposed && epoch === generation) timer = setTimeout(() => poll(id, epoch), 5000);
}
watch(() => gameStore.sessionId, id => {
  clearTimeout(timer); clearTimeout(hideTimer); count.value = 0;
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
    <button v-if="count" data-testid="worldbook-activity-notice" class="absolute bottom-36 right-4 z-20 max-w-[85%] rounded-xl border border-cyan-700 bg-slate-900/95 px-4 py-3 text-left text-xs text-cyan-200 shadow-lg" @click="openHistory">
      世界书新增 {{ count }} 条修订记录 · 点击查看
    </button>
  </Transition>
</template>
