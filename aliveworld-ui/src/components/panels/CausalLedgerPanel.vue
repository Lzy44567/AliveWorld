<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { gameApi } from '../../api/gameApi';
import { gameStore } from '../../store/gameStore';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { consumePolicyLabel, influenceStatusLabel, influenceTypeLabel, sourceDeathLabel } from '../../utils/causalLedgerLabels';

const props = defineProps({ initialSource: { type: String, default: '' } });

const influences = ref([]);
const turnCount = ref(0);
const editingId = ref(null);
const emptyForm = () => ({ summary: '', type: 'one_shot', condition: '', effect: '', sources: '', strength: 0.5, death: 'keep', consume: 'on_success', maxTriggers: '', worldTime: '', tags: '', forceNextTurn: false });
const form = ref(emptyForm());
const keyword = ref('');
const statusFilter = ref('all');
const sourceFilter = ref(props.initialSource);
watch(() => props.initialSource, value => { sourceFilter.value = value || ''; });
const visibleInfluences = computed(() => influences.value.filter(item => {
  const text = `${item.id} ${item.summary} ${item.condition} ${item.effect} ${(item.tags || []).join(' ')}`.toLowerCase();
  return (!keyword.value || text.includes(keyword.value.toLowerCase()))
    && (statusFilter.value === 'all' || item.status === statusFilter.value)
    && (!sourceFilter.value || (item.source_links || []).some(link => link.entity === sourceFilter.value));
}));

const refresh = async () => {
  try { const data = await gameApi.getCausalLedger(gameStore.sessionId); influences.value = data.influences || []; turnCount.value = data.turn_count || 0; }
  catch { uiStore.showToast('读取暗流因果账本失败', 'error'); }
};
const startNew = () => { editingId.value = 'new'; form.value = emptyForm(); };
const cancel = () => { editingId.value = null; form.value = emptyForm(); };
const edit = item => {
  const link = item.source_links?.[0] || {};
  editingId.value = item.id;
  form.value = { summary: item.summary, type: item.type, condition: item.condition, effect: item.effect, sources: (item.source_links || []).map(x => x.entity).join(', '), strength: link.life_link_strength ?? 0.5, death: link.on_source_death || 'keep', consume: item.consume_policy?.mode || 'never', maxTriggers: item.consume_policy?.max_triggers ?? '', worldTime: item.created_world_time || '', tags: (item.tags || []).join(', '), forceNextTurn: Boolean(item.force_next_turn) };
};
const makePayload = () => ({
  summary: form.value.summary.trim(), type: form.value.type, condition: form.value.condition.trim(), effect: form.value.effect.trim(),
  source_links: form.value.sources.split(',').map(x => x.trim()).filter(Boolean).map(entity => ({ entity, life_link_strength: Number(form.value.strength), on_source_death: form.value.death })),
  consume_policy: { mode: form.value.consume, max_triggers: form.value.maxTriggers === '' ? null : Number(form.value.maxTriggers) },
  created_world_time: form.value.worldTime.trim(), tags: form.value.tags.split(',').map(x => x.trim()).filter(Boolean), force_next_turn: form.value.forceNextTurn
});
const save = async () => {
  if (!form.value.summary.trim()) return uiStore.showToast('影响摘要不能为空', 'error');
  try {
    if (editingId.value === 'new') await gameApi.createInfluence(gameStore.sessionId, makePayload());
    else await gameApi.updateInfluence(gameStore.sessionId, editingId.value, makePayload());
    cancel(); await refresh(); await assetStore.fetchLocalAssets(gameStore.sessionId); uiStore.showToast('暗流影响已保存');
  } catch (error) { uiStore.showToast(error.message, 'error'); }
};
const cancelInfluence = async item => { try { await gameApi.deleteInfluence(gameStore.sessionId, item.id); await refresh(); await assetStore.fetchLocalAssets(gameStore.sessionId); } catch (error) { uiStore.showToast(error.message, 'error'); } };
onMounted(refresh);
</script>

<template>
  <div class="h-full overflow-y-auto custom-scrollbar pr-1 pb-8">
    <div class="mb-3 flex items-center justify-between"><p class="text-[10px] text-slate-500">世界回合 {{ turnCount }} · {{ influences.length }} 条记录</p><button @click="startNew" class="rounded border border-fuchsia-700/60 px-2 py-1 text-[10px] font-bold text-fuchsia-300">+ 新建影响</button></div>
    <div class="mb-3 grid grid-cols-2 gap-2">
      <input v-model="keyword" class="ledger-input" placeholder="搜索摘要、条件、标签">
      <select v-model="statusFilter" class="ledger-input"><option value="all">全部状态</option><option value="active">生效中</option><option value="consumed">已消失</option><option value="cancelled">已取消</option></select>
      <div v-if="sourceFilter" class="col-span-2 flex justify-between rounded border border-fuchsia-900/50 bg-fuchsia-950/20 px-2 py-1 text-[10px] text-fuchsia-300"><span>来源筛选：{{ sourceFilter }}</span><button @click="sourceFilter = ''">清除</button></div>
    </div>
    <div v-if="editingId" class="mb-4 grid grid-cols-2 gap-2 rounded-xl border border-fuchsia-800/60 bg-slate-900/80 p-3">
      <input v-model="form.summary" class="ledger-input col-span-2" placeholder="影响摘要">
      <select v-model="form.type" class="ledger-input"><option value="one_shot">一次性</option><option value="persistent">持续性</option><option value="evolving">可演化</option></select>
      <select v-model="form.consume" class="ledger-input"><option value="on_success">触发后消失</option><option value="on_attempt">判断后消失</option><option value="after_n">触发 N 次后消失</option><option value="never">持续保留</option></select>
      <textarea v-model="form.condition" class="ledger-input col-span-2 h-14" placeholder="触发条件" />
      <textarea v-model="form.effect" class="ledger-input col-span-2 h-14" placeholder="兑现后果" />
      <input v-model="form.sources" class="ledger-input col-span-2" placeholder="来源实体，逗号分隔">
      <label class="text-[10px] text-slate-400">生命关联 {{ form.strength }}<input type="range" min="0" max="1" step="0.1" v-model="form.strength" class="w-full"></label>
      <select v-model="form.death" class="ledger-input"><option value="remove">来源死亡时移除</option><option value="release">来源死亡时释放</option><option value="keep">来源死亡后保留</option></select>
      <input v-if="form.consume === 'after_n'" v-model="form.maxTriggers" type="number" min="1" class="ledger-input" placeholder="最大触发次数">
      <input v-model="form.worldTime" class="ledger-input" placeholder="创建时世界时间（文本）">
      <input v-model="form.tags" class="ledger-input col-span-2" placeholder="标签，逗号分隔">
      <label class="col-span-2 flex items-center justify-between rounded border border-amber-900/50 bg-amber-950/20 px-2 py-1.5 text-[10px] text-amber-300"><span>调试：下回合强制兑现</span><input type="checkbox" v-model="form.forceNextTurn"></label>
      <button @click="cancel" class="rounded bg-slate-700 py-1.5 text-xs">取消</button><button @click="save" class="rounded bg-fuchsia-700 py-1.5 text-xs font-bold">保存</button>
    </div>
    <div class="space-y-3">
      <article v-for="item in visibleInfluences" :key="item.id" class="rounded-xl border border-slate-700 bg-aw_panel p-3" :class="item.status !== 'active' ? 'opacity-55' : ''">
        <div class="flex justify-between gap-2"><div><h4 class="text-sm font-bold text-slate-200">{{ item.summary }}</h4><code class="text-[9px] text-slate-500">{{ item.id }}</code></div><span class="text-[9px] text-fuchsia-300">{{ influenceTypeLabel(item.type) }} · {{ influenceStatusLabel(item.status) }}</span></div>
        <p class="mt-2 text-[11px] text-slate-400">条件：{{ item.condition || '未设置' }}</p><p class="mt-1 text-[11px] text-slate-400">后果：{{ item.effect || '未设置' }}</p>
        <p class="mt-2 text-[9px] text-slate-500">创建于第 {{ item.created_tick }} 回合 · 存在 {{ item.age_ticks }} 回合 · 判断 {{ item.attempt_count }} 次 · 触发 {{ item.trigger_count }} 次</p>
        <p v-if="item.force_next_turn" class="mt-1 text-[9px] font-bold text-amber-300">⚠ 下回合强制兑现</p>
        <p class="mt-1 text-[9px] text-slate-500">消失规则：{{ consumePolicyLabel(item.consume_policy?.mode) }}</p>
        <p class="mt-1 text-[9px] text-slate-500">来源：{{ (item.source_links || []).map(x => `${x.entity}（${sourceDeathLabel(x.on_source_death)} / 关联 ${x.life_link_strength}）`).join('、') || '无' }}</p>
        <div class="mt-3 flex gap-2"><button @click="edit(item)" class="flex-1 rounded bg-slate-800 py-1 text-[10px]">编辑</button><button v-if="item.status === 'active'" @click="cancelInfluence(item)" class="rounded bg-rose-950/50 px-3 text-[10px] text-rose-400">取消影响</button></div>
      </article>
    </div>
  </div>
</template>

<style scoped>.ledger-input{min-width:0;border:1px solid #334155;border-radius:.4rem;background:#0f172a;padding:.5rem;font-size:.7rem;color:#cbd5e1;outline:none}.ledger-input:focus{border-color:#c026d3}textarea.ledger-input{resize:none}</style>
