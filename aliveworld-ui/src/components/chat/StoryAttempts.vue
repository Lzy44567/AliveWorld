<script setup>
import { ref, watch } from 'vue';
import { listStoryAttempts, deleteStoryAttempt } from '../../api/storyAttemptsApi';
const props = defineProps({ sessionId: String, busy: Boolean });
const open = ref(false), attempts = ref([]), error = ref(''), loading = ref(false);
let revision = 0;
watch(() => props.sessionId, () => { revision++; open.value = false; attempts.value = []; error.value = ''; loading.value = false; });
async function show() {
  open.value = true;
  const current = ++revision;
  loading.value = true;
  error.value = '';
  try {
    const result = await listStoryAttempts(props.sessionId);
    if (current === revision) attempts.value = result.attempts;
  } catch (e) { if (current === revision) error.value = e.message; }
  finally { if (current === revision) loading.value = false; }
}
async function remove(id) {
  if (!window.confirm('永久删除这条旧尝试？不会改变当前故事。')) return;
  const current = revision;
  loading.value = true;
  error.value = '';
  try {
    await deleteStoryAttempt(props.sessionId, id);
    if (current === revision) attempts.value = attempts.value.filter(item => item.id !== id);
  } catch (e) { if (current === revision) error.value = e.message; }
  finally { if (current === revision) loading.value = false; }
}
</script>

<template>
  <button data-testid="story-attempts" @click="show" :disabled="busy || !sessionId" class="text-xs text-slate-400 hover:text-cyan-300 disabled:opacity-40">旧尝试</button>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-[100] bg-black/70 flex items-center justify-center p-4" @click.self="open = false">
      <section role="dialog" aria-modal="true" aria-label="旧尝试" class="w-full max-w-4xl max-h-[85vh] flex flex-col rounded-xl border border-slate-600 bg-slate-900 text-slate-200">
        <header class="p-4 border-b border-slate-700 flex justify-between items-center"><h2>旧尝试</h2><button aria-label="关闭旧尝试" @click="open = false">✕</button></header>
        <div class="p-4 overflow-auto select-text">
          <p class="text-sm text-slate-400 mb-4">撤回和重试前的结果，不属于当前历史，也不会自动发送给模型。删除后无法恢复。</p>
          <p v-if="error" role="alert" class="text-red-300">{{ error }}</p>
          <p v-if="loading">正在读取或保存…</p>
          <p v-else-if="!attempts.length && !error">暂无旧尝试。</p>
          <details v-for="item in [...attempts].reverse()" :key="item.id" class="border border-slate-700 rounded-lg p-3 mb-3">
            <summary class="cursor-pointer">回合 {{ item.turns.map(turn => turn.turn_id).join('、') }} · {{ new Date(item.created_at).toLocaleString() }}</summary>
            <div v-for="(turn, index) in item.turns" :key="index" class="whitespace-pre-wrap leading-relaxed mt-4">
              <p class="text-cyan-200">行动：{{ turn.player }}</p><p class="mt-3">{{ turn.story }}</p>
            </div>
            <button @click="remove(item.id)" :disabled="loading || busy" class="mt-4 text-xs text-red-300 disabled:opacity-40">删除这条旧尝试</button>
          </details>
        </div>
      </section>
    </div>
  </Teleport>
</template>
