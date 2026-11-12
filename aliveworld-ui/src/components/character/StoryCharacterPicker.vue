<script setup>
import { onMounted, ref } from 'vue';
const props = defineProps({ sessionId: String });
const emit = defineEmits(['close', 'select']);
const npcs = ref([]), error = ref(''), loading = ref(true);
onMounted(async () => {
  try {
    const response = await fetch(`/api/v1/game/${encodeURIComponent(props.sessionId)}/character-material`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '人物读取失败');
    npcs.value = data.npcs;
  } catch (e) { error.value = e.message; }
  finally { loading.value = false; }
});
</script>
<template>
  <Teleport to="body"><div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4">
    <section role="dialog" aria-label="选择故事人物" class="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-xl border border-slate-700 bg-slate-950 p-5 text-slate-200">
      <header class="mb-4 flex justify-between"><h2>选择故事人物</h2><button aria-label="关闭人物选择" @click="emit('close')">×</button></header>
      <p class="mb-4 text-sm text-slate-400">包括已离场人物，无需预先创建角色卡。选择后自行勾选相关公开回合供 AI 整理。</p>
      <p v-if="error" role="alert">{{ error }}</p><p v-else-if="loading">正在读取……</p>
      <p v-else-if="!npcs.length">故事尚未记录场景人物。</p>
      <div class="grid min-h-0 grid-cols-2 gap-3 overflow-y-auto">
        <button v-for="npc in npcs" :key="npc.id" class="rounded-lg border border-slate-700 bg-slate-900 p-4 text-left hover:border-indigo-400" @click="emit('select', `npc:${npc.id}`)">
          <strong>{{ npc.name }}</strong><p class="mt-2 text-xs text-slate-400">{{ npc.aliases.join(' · ') }}</p><p class="text-xs text-slate-500">{{ npc.status }}</p>
        </button>
      </div>
    </section>
  </div></Teleport>
</template>
