<script setup>
import { ref, watch } from 'vue';
import { gameStore } from '../../store/gameStore';
import { uiStore } from '../../store/uiStore';
import { fetchWorldbookActivity } from '../../api/worldbookActivityApi';
import { activityStatus, activityOperation } from '../../utils/worldbookActivity';

defineEmits(['open-book']);
const data = ref(null), error = ref(''), details = ref(false), offset = ref(0), busy = ref(false);
let generation = 0;
async function refresh() {
  const id = gameStore.sessionId, epoch = ++generation;
  if (!id || !uiStore.worldbookActivityOpen) return;
  busy.value = true;
  try {
    const next = await fetchWorldbookActivity(id, { offset: offset.value, details: details.value });
    if (epoch === generation && id === gameStore.sessionId) { data.value = next; error.value = ''; }
  } catch (e) { if (epoch === generation) error.value = e.message; }
  finally { if (epoch === generation) busy.value = false; }
}
watch(() => gameStore.sessionId, () => {
  ++generation; data.value = null; details.value = false; offset.value = 0; error.value = '';
});
watch(() => [gameStore.sessionId, uiStore.worldbookActivityOpen, uiStore.worldbookActivityRefresh, details.value, offset.value], refresh, { immediate: true });
</script>

<template>
  <section class="mb-3 rounded-xl border border-slate-700 bg-slate-900/70 p-3 text-xs" aria-label="世界书修订记录">
    <button class="text-cyan-300" :aria-expanded="uiStore.worldbookActivityOpen" @click="uiStore.worldbookActivityOpen = !uiStore.worldbookActivityOpen">{{ uiStore.worldbookActivityOpen ? '收起' : '查看' }}修订记录</button>
    <div v-if="uiStore.worldbookActivityOpen" class="mt-3 space-y-3">
      <div class="flex items-center justify-between gap-2"><span class="text-slate-400">{{ data?.total || 0 }} 条记录 · {{ data?.pending || 0 }} 条待审</span><button class="text-cyan-300 disabled:opacity-50" :disabled="busy" @click="refresh">刷新记录</button></div>
      <label class="flex items-start gap-2 text-slate-400"><input type="checkbox" v-model="details" />显示条目详情（可能包含隐藏设定）</label>
      <p v-if="error" role="alert" class="text-rose-300">{{ error }}</p>
      <p v-if="data && !data.total" class="text-slate-500">尚无后台捕获记录。旧书没有历史的手动编辑不会补造记录。</p>
      <div class="max-h-[55vh] space-y-3 overflow-y-auto pr-1">
        <article v-for="item in data?.items || []" :key="item.id" class="rounded-lg border border-slate-700 p-2" data-testid="worldbook-activity-row">
          <div class="flex flex-wrap justify-between gap-1"><span class="break-all text-slate-200">{{ item.book_name }}</span><span class="text-cyan-300">{{ activityStatus[item.status] || item.status }}</span></div>
          <p class="mt-1 text-slate-400">回合 #{{ item.turn ?? '—' }} · {{ activityOperation[item.operation] || item.operation }}</p>
          <details v-if="details" class="mt-2 text-slate-300"><summary class="cursor-pointer break-words">{{ item.name || '查看变更' }}</summary>
            <p class="mt-2 text-[10px] text-slate-500">历史快照，不代表当前条目仍与此一致。</p>
            <p class="mt-2 text-slate-500">修改前</p><p class="whitespace-pre-wrap break-words">{{ item.before?.content || '无' }}</p>
            <p class="mt-2 text-slate-500">修改后</p><p class="whitespace-pre-wrap break-words">{{ item.after?.content || '无' }}</p>
          </details>
          <button class="mt-2 text-cyan-300" @click="$emit('open-book', item.book_id)">打开原书{{ item.status === 'pending' ? '审阅' : '' }}</button>
        </article>
      </div>
      <div v-if="data" class="flex justify-between text-cyan-300"><button :disabled="busy || offset === 0" class="disabled:opacity-30" @click="offset = Math.max(0, offset - 30)">上一页</button><button :disabled="busy || data.next_offset === null" class="disabled:opacity-30" @click="offset = data.next_offset">下一页</button></div>
    </div>
  </section>
</template>
