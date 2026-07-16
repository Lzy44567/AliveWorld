<script setup>
import { onMounted, ref } from 'vue';
import { gameApi } from '../../api/gameApi';
import { gameStore } from '../../store/gameStore';

const status = ref(null);
const loading = ref(false);
const message = ref('');

async function refresh() {
  if (!gameStore.sessionId) return;
  loading.value = true;
  try {
    status.value = await gameApi.getStoryMemory(gameStore.sessionId);
    message.value = '';
  } catch (error) {
    message.value = error.message;
  } finally {
    loading.value = false;
  }
}

async function inspectNow() {
  if (!gameStore.sessionId) return;
  loading.value = true;
  message.value = '正在执行调试压缩检查…';
  try {
    const result = await gameApi.compactStoryMemory(gameStore.sessionId, true);
    status.value = result.status;
    message.value = result.completed ? `已归档回合 ${result.start_turn}–${result.end_turn}` : (result.reason || '当前没有可归档回合');
  } catch (error) {
    message.value = error.message;
  } finally {
    loading.value = false;
  }
}

onMounted(refresh);
</script>

<template>
  <div class="rounded-lg border border-slate-700 bg-slate-950/40 p-3 text-[10px] text-slate-400">
    <div v-if="status" class="grid grid-cols-2 gap-x-3 gap-y-1">
      <span>近期完整回合：{{ status.raw_turn_count }}</span>
      <span>估算 token：{{ status.raw_token_estimate }}</span>
      <span>已归档片段：{{ status.segment_count }}</span>
      <span>活动故事线程：{{ status.active_event_count }}</span>
      <span class="col-span-2">高水位 / 目标低水位：{{ status.budget?.history_high_water }} / {{ status.budget?.history_low_water }}</span>
      <span v-if="status.running" class="col-span-2 text-indigo-300">后台压缩正在运行</span>
      <span v-if="status.last_error" class="col-span-2 text-rose-300">最近失败：{{ status.last_error }}</span>
    </div>
    <div class="mt-2 flex gap-2">
      <button class="rounded border border-slate-600 px-2 py-1 hover:border-slate-400" :disabled="loading" @click="refresh">刷新状态</button>
      <button class="rounded border border-indigo-500/50 px-2 py-1 text-indigo-200 hover:border-indigo-400" :disabled="loading" @click="inspectNow">调试：立即压缩</button>
    </div>
    <p v-if="message" class="mt-2 text-slate-300">{{ message }}</p>
    <p class="mt-2 text-slate-600">“立即压缩”只用于测试；正常游玩由 token 水位自动触发。</p>
  </div>
</template>
