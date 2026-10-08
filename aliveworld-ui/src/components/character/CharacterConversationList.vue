<script setup>
import { computed, ref } from 'vue';
import { conversationRows } from '../../utils/characterConversationList.js';
const props = defineProps({ store: Object });
defineEmits(['open']);
const query = ref('');
const rows = computed(() => conversationRows(props.store.sessions, query.value, props.store.preferences));
const preview = item => (item.last_message_kind === 'author_opening' ? '预设 · ' : '') + (item.last_message_preview || '尚未开始对话');
const unread = item => item.schema_version === 2 ? item.unread_count > 0 : props.store.preferences.unread(item);
const typing = item => item.schema_version === 2 ? Boolean(item.busy_group || (props.store.activeId===item.session_id && props.store.visible && props.store.contexts[item.session_id]?.busy)) : Boolean(props.store.contexts[item.session_id]?.busy || item.pending);
const stamp = value => { const date = new Date(value); if (!Number.isFinite(date.getTime())) return ''; const today = new Date(); return date.toDateString() === today.toDateString() ? date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : date.toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' }); };
</script>

<template>
  <input v-model="query" data-testid="character-session-search" aria-label="搜索角色对话" maxlength="80" placeholder="搜索对话或角色" class="min-w-0 w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm">
  <p v-if="store.loading" class="text-xs text-slate-400">正在刷新对话…</p>
  <p v-if="store.listWarning" data-testid="character-list-warning" class="text-xs text-amber-300">{{ store.listWarning }}</p>
  <div class="flex-1 overflow-y-auto custom-scrollbar space-y-1">
    <div v-for="item in rows" :key="item.session_id" class="group relative flex items-center rounded-md" :class="store.activeId===item.session_id?'bg-indigo-800/40':'hover:bg-slate-800'">
      <button :data-testid="`character-session-${item.session_id}`" class="flex min-w-0 flex-1 items-center gap-3 px-2 py-3 text-left" @click="$emit('open',item.session_id)">
        <span class="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-900 text-indigo-100">{{ Array.from(item.ai_name || item.title || '?')[0] }}<span v-if="unread(item)" :data-testid="`character-unread-${item.session_id}`" role="status" aria-label="有新的回复" class="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-rose-500"></span></span>
<span class="min-w-0 flex-1"><span class="flex items-center gap-2"><span class="min-w-0 flex-1 truncate text-sm">{{ item.title }}</span><time class="shrink-0 text-[10px] text-slate-500">{{ stamp(item.last_activity_at) }}</time></span><span class="mt-1 block truncate text-xs text-slate-400">{{ typing(item) ? '对方正在输入中…' : preview(item) }}</span><span v-if="item.schema_read_only || item.read_error" class="text-[10px] text-amber-300">只读或无法读取</span></span>
      </button>
      <button type="button" :data-testid="`character-pin-${item.session_id}`" :aria-label="`${store.preferences.entries[item.session_id]?.pinned?'取消置顶':'置顶'} ${item.title}`" :aria-pressed="Boolean(store.preferences.entries[item.session_id]?.pinned)" class="shrink-0 p-1 text-xs" :class="store.preferences.entries[item.session_id]?.pinned?'text-amber-300':'text-slate-500 md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100'" @click="store.preferences.pin(item)">⌖</button>
    </div>
    <p v-if="!rows.length && !store.loading" class="p-2 text-sm text-slate-500">{{ query ? (store.listComplete ? '没有匹配的对话' : '已加载的对话中没有匹配结果') : store.listComplete ? '选择一张角色卡，开始独立对话。' : '暂无已加载对话，请刷新列表。' }}</p>
  </div>
  <p v-if="store.preferences.warning" class="text-xs text-amber-300">{{ store.preferences.warning }}</p>
  <p class="text-[9px] text-slate-500">置顶保存在此浏览器；新会话的未读随会话保存</p>
</template>
