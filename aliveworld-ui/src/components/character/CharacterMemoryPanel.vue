<script setup>
import { computed, ref, watch } from 'vue';
import { automaticMemoryState, memoryReasonLabels } from '../../utils/characterMemory.js';
import CharacterCognitionPanel from './CharacterCognitionPanel.vue';
import CharacterSourceRecallReport from './CharacterSourceRecallReport.vue';
const props = defineProps({ session: Object, report: Object, disabled: Boolean, sourceLoader: Function, cognition:Object, cognitionLoading:Boolean, cognitionError:String, recallReport:Object });
const emit = defineEmits(['mark', 'correct', 'enable-automatic', 'select-automatic', 'release-automatic', 'cognition-open']);
const panel = ref(null);
const sources = ref({}), error = ref(''), loading = ref('');
let generation = 0;
watch(() => [props.session?.session_id, props.session?.revision], () => { ++generation; sources.value = {}; error.value = ''; loading.value = ''; });
const protectedIds = computed(() => new Set((props.session.memory_settings?.protected_entries || []).map(e => e.entry_id)));
const inactive = computed(() => props.session.memory_settings?.inactive_root_ids || []);
const automatic = computed(() => automaticMemoryState(props.session.memory_settings));
const automaticById = computed(() => new Map((automatic.value?.automatic_entries || []).map(e => [e.entry_id, e])));
const labels = { important: '玩家重要', auto_important: '自动重要', auto_highlight: '自动高光', related: '话题相关', recent: '近期补充', sent: '已送入本次请求', budget: '预算不足未发送', not_selected: '本次未取用' };
function description(id) { return props.session.ledger?.find(e => e.entry_id === id)?.content?.slice(0, 60) || '公开记忆（本轮可能已被更新）'; }
async function load(entry) {
  const token = ++generation, sid = props.session.session_id;
  loading.value = entry.entry_id; error.value = '';
  try {
    const messages = await props.sourceLoader(sid, entry.entry_id);
    if (generation === token && props.session.session_id === sid) sources.value = { ...sources.value, [entry.entry_id]: messages };
  } catch (e) { if (generation === token) error.value = e.message; }
  finally { if (generation === token) loading.value = ''; }
}
async function revealSource(id) {
  const entry = props.session.ledger?.find(e => e.entry_id === id);
  if (!entry) return;
  const element = panel.value?.querySelector(`[data-source-entry="${id}"]`);
  if (element) { element.open = true; element.scrollIntoView({ block:'nearest' }); }
  if (!sources.value[id]) await load(entry);
}
</script>

<template>
  <section ref="panel" data-testid="character-memory-panel" class="mt-6 text-sm">
    <h4 class="mb-2">共同经历与记忆</h4>
    <div v-if="!automatic && session.memory_settings?.version!==2" class="mb-3 rounded bg-slate-800 p-2 text-xs text-slate-400">
      <p>旧会话尚未启用自动重要记忆。启用后只分析以后的回复，不扫描历史；不增加独立模型调用。</p>
      <button data-testid="character-memory-enable" class="mt-2 text-indigo-300 disabled:opacity-40" :disabled="disabled" @click="emit('enable-automatic')">启用自动重要记忆</button>
    </div>
    <p v-else-if="automatic" data-testid="character-memory-automatic" class="mb-3 text-xs text-slate-400">已启用自动重要记忆。重要性不是事实确认，也不代表真实用户偏好；可逐条取消自动选取。</p>
    <p class="text-xs text-slate-500 mb-3">重要标记只提高取材优先级，不代表事实已确认。最多8条；预算不足仍可能省略。</p>
    <CharacterCognitionPanel :session="session" :report="cognition" :loading="cognitionLoading" :error="cognitionError" :disabled="disabled" @open="emit('cognition-open',$event)" @source="revealSource" @correct="emit('correct',$event)" />
    <CharacterSourceRecallReport :session="session" :report="recallReport" :disabled="disabled" @source="revealSource" />
    <details data-testid="character-memory-report" class="mb-3 text-xs text-slate-400">
      <summary class="cursor-pointer">本次记忆取材</summary>
      <p class="mt-2">只显示公开记录，不表示模型已记住；未取用不等于删除。</p>
      <p v-if="!report" class="mt-2">尚无本次取材信息</p>
      <p v-else-if="!report.entries.length" class="mt-2">本次没有可说明的公开记录</p>
      <ul v-else class="space-y-2 mt-2"><li v-for="item in report.entries" :key="item.entry_id" class="break-words"><p>{{ description(item.entry_id) }}</p><p :class="item.state==='budget'?'text-amber-300':''">{{ labels[item.reason] }} · {{ labels[item.state] }}</p></li></ul>
    </details>
    <div data-testid="character-public-ledger" class="space-y-2">
      <p v-if="!session.ledger?.length" class="text-xs text-slate-500">暂无公开记录</p>
      <article v-for="entry in session.ledger" :key="entry.entry_id" :data-entry-id="entry.entry_id" class="rounded bg-slate-950 p-2">
        <p class="whitespace-pre-wrap break-words select-text">{{ entry.content }}</p>
        <p class="text-xs text-slate-500 mt-1">{{ entry.kind }} · {{ entry.source?.type==='player_statement'?'用户陈述':entry.source?.type==='model_inference'?'角色推断':'共同对话' }}</p>
        <div v-if="automaticById.has(entry.entry_id)" data-testid="character-memory-auto-entry" class="mt-2 text-xs text-indigo-200">
          <p>{{ labels['auto_'+automaticById.get(entry.entry_id).level] }} · {{ memoryReasonLabels[automaticById.get(entry.entry_id).reason] }}{{ automaticById.get(entry.entry_id).dismissed?' · 已取消自动优先':'' }}</p>
          <button data-testid="character-memory-auto-select" class="mt-1 text-slate-400 disabled:opacity-40" :disabled="disabled" :aria-pressed="!automaticById.get(entry.entry_id).dismissed" @click="emit('select-automatic',entry.entry_id,!automaticById.get(entry.entry_id).dismissed)">{{ automaticById.get(entry.entry_id).dismissed?'恢复自动选取':'取消自动选取' }}</button>
        </div>
        <div class="mt-2 flex flex-wrap gap-3 text-xs"><button data-testid="character-memory-mark" class="text-indigo-300 disabled:opacity-40" :disabled="disabled" :aria-pressed="protectedIds.has(entry.entry_id)" @click="emit('mark', entry.entry_id, !protectedIds.has(entry.entry_id))">{{ protectedIds.has(entry.entry_id)?'★ 取消重要':'☆ 标为重要' }}</button><button class="text-slate-400 disabled:opacity-40" :disabled="disabled" @click="emit('correct',entry)">纠正记忆</button></div>
        <details v-if="entry.source" :data-source-entry="entry.entry_id" class="text-xs text-slate-400 mt-2"><summary class="cursor-pointer">来源证据</summary><p v-for="(item,index) in entry.source.evidence || []" :key="index" class="whitespace-pre-wrap break-words select-text mt-1">{{ item.quote }}</p><p class="break-all select-text mt-1">{{ (entry.source.message_ids || []).join('、') }}</p><button v-if="!sources[entry.entry_id]" class="underline mt-2" :disabled="Boolean(loading)" @click="load(entry)">{{ loading===entry.entry_id?'载入中…':'查看关联原文' }}</button><p v-for="message in sources[entry.entry_id] || []" :key="message.message_id" class="whitespace-pre-wrap break-words select-text mt-2">{{ message.content }}</p></details>
      </article>
    </div>
    <p v-if="error" class="mt-2 text-xs text-rose-300">{{ error }}</p>
    <details v-if="inactive.length" class="text-xs text-slate-400 mt-3"><summary>已失效的重要标记 · 可释放名额</summary><p class="mt-2">无当前公开有效条目；不会召回旧内容。</p><div v-for="root in inactive" :key="root" class="mt-2 flex justify-between gap-2"><span>{{ root.slice(0,8) }}</span><button :disabled="disabled" @click="emit('mark',root,false)">取消标记</button></div></details>
    <details v-if="automatic?.inactive_dismissed_root_ids.length" class="text-xs text-slate-400 mt-3"><summary>已失效的自动取消项 · 可释放名额</summary><p class="mt-2">仅清理已失效设置，不恢复当前有效记忆的自动优先。</p><div v-for="root in automatic.inactive_dismissed_root_ids" :key="root" class="mt-2 flex justify-between gap-2"><span>{{ root.slice(0,8) }}</span><button data-testid="character-memory-auto-release" :disabled="disabled" @click="emit('release-automatic',root)">清理失效项</button></div></details>
    <p class="mt-3 text-xs text-slate-500">纠正只创建可编辑草稿，需你发送；模型实际更新记录后才生效。</p>
  </section>
</template>
