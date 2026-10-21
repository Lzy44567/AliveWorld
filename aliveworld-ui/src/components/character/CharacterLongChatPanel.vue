<script setup>
import { ref, watch, onUnmounted } from 'vue';
import { characterChatApi as api } from '../../api/characterChatApi.js';
const props = defineProps({ session: Object, active: Boolean });
const emit = defineEmits(['updated']);
const state = ref(null), error = ref(''), busy = ref(false), confirm = ref(''), sources = ref({});
let timer, generation = 0;
async function refresh() {
  const sid = props.session.session_id, token = generation;
  try { const value = await api.longChat(sid); if (token === generation) state.value = value; }
  catch (e) { if (token === generation) error.value = e.message; }
}
watch(() => [props.session.session_id, props.active], () => {
  ++generation; clearInterval(timer); state.value = null; error.value = ''; sources.value = {}; confirm.value = '';
  if (props.active && props.session.schema_version === 2) { void refresh(); timer = setInterval(refresh, 3000); }
}, { immediate: true });
onUnmounted(() => { ++generation; clearInterval(timer); });
async function update(enabled, rebuild = false) {
  const sid = props.session.session_id, token = generation;
  busy.value = true; error.value = '';
  try {
    const latest = await api.longChat(sid);
    const result = await api.updateLongChat(sid, { expected_revision: latest.revision, enabled, acknowledged: enabled, rebuild });
    if (token === generation) { emit('updated', result); confirm.value = ''; await refresh(); }
  } catch (e) { if (token === generation) error.value = e.message; }
  finally { busy.value = false; }
}
async function loadSources(seq) {
  const token = generation, sid = props.session.session_id;
  try { const value = await api.longChatSources(sid, seq); if (token === generation) sources.value[seq] = value.messages; }
  catch (e) { if (token === generation) error.value = e.message; }
}
</script>

<template>
  <section data-testid="character-long-chat" class="mb-4 rounded-lg border border-slate-700 p-3 text-sm">
    <h3 class="font-semibold text-slate-200">长聊整理</h3>
    <p v-if="session.schema_version!==2" class="mt-2 text-xs text-slate-400">此旧格式会话暂不支持长聊整理。</p>
    <template v-else>
      <p class="my-2 text-xs text-slate-400">整理较早聊天，帮助后续回复参考共同经历。原文不删除，摘要可能遗漏细节；主动联系暂不使用摘要。</p>
      <div v-if="state" class="flex flex-wrap items-center gap-3">
        <span>{{ state.enabled ? (state.running ? '正在后台整理…' : '已开启') : '已关闭' }}</span>
        <button :disabled="busy" class="text-indigo-300 disabled:opacity-40" @click="state.enabled ? update(false) : confirm='enable'">{{ state.enabled ? '关闭' : '开启长聊整理' }}</button>
        <button v-if="state.enabled" :disabled="busy || state.running" class="text-slate-400 disabled:opacity-40" @click="confirm='rebuild'">重新整理</button>
      </div>
      <div v-if="confirm" class="mt-3 rounded bg-slate-900 p-3">
        <p class="text-xs text-amber-200">仅授权当前会话。整理会额外调用当前角色接口并产生 token 费用；不是无限记忆。{{ confirm==='rebuild' ? '重新整理会清除旧摘要，本次最多处理一批较早聊天。' : '开启不会立即收费，之后在正常聊天结束且达到水位时低频整理。' }}</p>
        <div class="mt-2 flex gap-4"><button :disabled="busy" class="text-indigo-300" @click="update(true,confirm==='rebuild')">确认并{{ confirm==='rebuild'?'重新整理':'开启' }}</button><button @click="confirm=''">取消</button></div>
      </div>
      <p v-if="state?.failure" class="mt-2 text-xs text-amber-300">上次整理失败，已停止自动尝试。原文不受影响；可选择重新整理。</p>
      <p v-if="state && !state.enabled" class="mt-2 text-xs text-slate-500">关闭后不再整理或引用摘要，已有摘要保留在本地。</p>
      <details v-if="state?.segments.length" class="mt-3 text-xs">
        <summary class="cursor-pointer text-slate-400">已整理 {{ state.segments.length }} 段 · 查看摘要与来源</summary>
        <p class="my-2 text-slate-500">最多保留24段，回复最多参考最近8段，仍受上下文预算限制。更早的原文仍在聊天记录中。</p>
        <article v-for="segment in state.segments" :key="segment.through_seq" class="my-2 rounded bg-slate-950 p-2">
          <p class="whitespace-pre-wrap select-text">{{ segment.summary }}</p>
          <p class="mt-1 text-slate-500">覆盖至消息序号 {{ segment.through_seq }} · {{ segment.group_ids.length }} 组</p>
          <button class="mt-1 text-indigo-300" @click="loadSources(segment.through_seq)">查看关联原文</button>
          <p v-for="message in sources[segment.through_seq] || []" :key="message.message_id" class="mt-2 whitespace-pre-wrap select-text text-slate-400">{{ message.content }}</p>
        </article>
      </details>
      <p v-else-if="state" class="mt-2 text-xs text-slate-500">尚无摘要，近期聊天优先保留原文。</p>
      <p v-if="state?.invalid_count" class="mt-2 text-xs text-amber-200">{{ state.invalid_count }} 段来源已变化，已停止引用。</p>
      <p v-if="error" role="alert" class="mt-2 text-xs text-red-300">{{ error }}</p>
    </template>
  </section>
</template>
