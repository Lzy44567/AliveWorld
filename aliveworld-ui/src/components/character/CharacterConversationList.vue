<script setup>
import { computed, ref } from 'vue';
import { conversationRows } from '../../utils/characterConversationList.js';
const props = defineProps({ store: Object });
defineEmits(['open']);
const query = ref('');
const rows = computed(() => conversationRows(props.store.sessions, query.value, props.store.preferences));
const stamp = value => { const date = new Date(value); return Number.isFinite(date.getTime()) ? date.toLocaleString(undefined, { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''; };
</script>

<template>
  <input v-model="query" data-testid="character-session-search" aria-label="搜索角色对话" maxlength="80" placeholder="搜索对话或角色" class="min-w-0 w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm">
  <p v-if="store.loading" class="text-xs text-slate-400">正在刷新对话…</p>
  <p v-if="store.listWarning" data-testid="character-list-warning" class="text-xs text-amber-300">{{ store.listWarning }}</p>
  <div class="flex-1 overflow-y-auto custom-scrollbar space-y-1">
    <div v-for="item in rows" :key="item.session_id" class="flex items-center rounded-lg border" :class="store.activeId===item.session_id?'border-indigo-600 bg-indigo-950/60':'border-transparent hover:bg-slate-800'">
      <button :data-testid="`character-session-${item.session_id}`" class="flex min-w-0 flex-1 items-center gap-2 p-2 text-left" @click="$emit('open',item.session_id)">
        <span class="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-900 text-indigo-100">{{ Array.from(item.ai_name || item.title || '?')[0] }}<span v-if="store.preferences.unread(item)" :data-testid="`character-unread-${item.session_id}`" role="status" aria-label="有新的回复" class="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-rose-500"></span></span>
<span class="min-w-0 flex-1"><span class="block truncate text-sm">{{ item.title }}</span><span class="mt-1 block truncate text-xs text-slate-400">{{ item.last_message_preview || '尚未开始对话' }}</span><time class="mt-1 block text-[9px] text-slate-500">{{ stamp(item.last_activity_at) }}</time><span v-if="store.contexts[item.session_id]?.busy || item.pending" class="text-[10px] text-amber-300">正在回复</span><span v-if="item.schema_read_only || item.read_error" class="text-[10px] text-amber-300">只读或无法读取</span></span>
      </button>
      <button type="button" :data-testid="`character-pin-${item.session_id}`" :aria-label="`${store.preferences.entries[item.session_id]?.pinned?'取消置顶':'置顶'} ${item.title}`" :aria-pressed="Boolean(store.preferences.entries[item.session_id]?.pinned)" class="shrink-0 p-2 text-xs" :class="store.preferences.entries[item.session_id]?.pinned?'text-amber-300':'text-slate-500'" @click="store.preferences.pin(item)">⌖</button>
    </div>
    <p v-if="!rows.length && !store.loading" class="p-2 text-sm text-slate-500">{{ query ? (store.listComplete ? '没有匹配的对话' : '已加载的对话中没有匹配结果') : store.listComplete ? '选择一张角色卡，开始独立对话。' : '暂无已加载对话，请刷新列表。' }}</p>
  </div>
  <p v-if="store.preferences.warning" class="text-xs text-amber-300">{{ store.preferences.warning }}</p>
  <p class="text-[9px] text-slate-500">置顶与未读仅保存在此浏览器</p>
</template>
