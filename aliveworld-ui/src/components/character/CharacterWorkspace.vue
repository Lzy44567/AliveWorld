<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { characterChatStore as store } from '../../store/characterChatStore.js';
import { assetStore } from '../../store/assetStore';
import { uiStore } from '../../store/uiStore';
import AssetCardPicker from '../assets/AssetCardPicker.vue';
import CharacterConversationList from './CharacterConversationList.vue';

const creating = ref(false), aiCard = ref(''), userCard = ref(''), worldCard = ref(''), title = ref(''), mode = ref('messenger'), createBusy = ref(false), createError = ref('');
const creationId = ref(globalThis.crypto.randomUUID());
const details = ref(false), listOpen = ref(false), messagePane = ref(null);
const listToggle = ref(null), detailsToggle = ref(null);
const picker = ref('');
let mounted = false;
const pickerValue = computed({ get: () => picker.value === 'ai' ? aiCard.value : picker.value === 'user' ? userCard.value : worldCard.value, set: value => { if (picker.value === 'ai') aiCard.value=value; else if (picker.value === 'user') userCard.value=value; else worldCard.value=value; } });
const ctx = computed(() => store.current);
const session = computed(() => ctx.value?.session);
const turns = computed(() => session.value?.turns || []);
const readonly = computed(() => Boolean(session.value?.schema_read_only || ctx.value?.needsReload));
const modeName = value => value === 'roleplay' ? '情景扮演' : '即时聊天';
const text = message => typeof message === 'string' ? message : message?.content || '';
const participant = controller => session.value?.participants?.find(p => p.controller === controller);
const run = (operation, retry = false) => store.run(store.activeId, operation, retry);
async function create() {
  if (!aiCard.value || createBusy.value) return;
  createBusy.value = true; createError.value = '';
  try {
    await store.create({ client_creation_id: creationId.value, title: title.value || undefined, ai_asset_ref: { kind: 'character', key: aiCard.value },
      ...(userCard.value ? { user_asset_ref: { kind: 'character', key: userCard.value } } : {}),
      ...(worldCard.value ? { world_asset_ref: { kind: 'worldbook', key: worldCard.value } } : {}), presentation_mode: mode.value });
    creating.value = false; listOpen.value = false; creationId.value = globalThis.crypto.randomUUID();
  } catch (e) { createError.value = e.message; } finally { createBusy.value = false; }
}
async function open(id) { creating.value = false; listOpen.value = false; await store.open(id); await nextTick(); store.markPresented(id); }
async function updateMode(event) {
  try { await store.update(store.activeId, { presentation_mode: event.target.value }); }
  catch (e) { ctx.value.error = e.message; event.target.value = session.value.presentation_mode; }
}
async function remove() {
  if (!window.confirm('仅删除此对话与局内记录，不删除角色卡；保留无内容删除ID，防止旧请求恢复。确定删除？')) return;
  try { await store.remove(store.activeId); } catch (e) { ctx.value.error = e.message; }
}
function undo() { if (window.confirm('撤回最后一轮对话及其局内记录？')) run('undo'); }
function regenerate() { if (window.confirm('重新生成最后一轮回复？失败时保留原回复。')) run('regenerate'); }
watch(() => [store.activeId, turns.value.length, ctx.value?.preview, ctx.value?.busy], async () => {
  if (ctx.value?.historyLoading) return;
  await nextTick(); if (messagePane.value) messagePane.value.scrollTop = messagePane.value.scrollHeight;
  if (!creating.value) store.markPresented(store.activeId);
});
watch(details, value => { if (!value) { store.clearSpoiler(); nextTick(() => { if (!listOpen.value) detailsToggle.value?.focus(); }); } else listOpen.value = false; });
watch(listOpen, value => { if (value) details.value = false; else nextTick(() => { if (!details.value) listToggle.value?.focus(); }); });
function syncVisibility() { store.setVisible(!document.hidden); if (!document.hidden && !creating.value) nextTick(() => store.markPresented(store.activeId)); }
onMounted(async () => {
  mounted = true;
  syncVisibility(); document.addEventListener('visibilitychange', syncVisibility);
  await store.refreshList(); if (!mounted) return; if (store.activeId) await store.open(store.activeId);
  if (!mounted) return;
  await nextTick(); if (messagePane.value) messagePane.value.scrollTop = messagePane.value.scrollHeight;
  if (!creating.value) store.markPresented(store.activeId);
});
onUnmounted(() => { mounted = false; document.removeEventListener('visibilitychange', syncVisibility); store.setVisible(false); });
</script>

<template>
  <section data-testid="character-workspace" class="flex flex-1 min-h-0 overflow-hidden bg-slate-950 relative">
    <aside :class="listOpen ? 'flex absolute inset-y-0 left-0 z-20 w-64 shadow-xl' : 'hidden md:flex w-60'" class="shrink-0 flex-col bg-slate-900 border-r border-slate-700 p-3 gap-3">
      <div class="flex justify-between items-center"><h1 class="font-bold">角色对话</h1><button class="md:hidden" @click="listOpen=false" aria-label="关闭会话列表">✕</button></div>
      <button data-testid="character-new" class="rounded-lg bg-indigo-700 p-2 hover:bg-indigo-600" @click="creating=true; listOpen=false">＋ 新对话</button>
      <p v-if="store.error" class="text-xs text-rose-300">{{ store.error }}</p>
      <CharacterConversationList :store="store" @open="open" />
      <button class="text-xs text-slate-400" @click="store.refreshList()">刷新列表</button>
    </aside>

    <main class="flex flex-1 flex-col min-w-0 min-h-0">
      <div class="flex items-center gap-3 p-3 border-b border-slate-800 shrink-0">
        <button ref="listToggle" class="md:hidden text-slate-300" @click="listOpen=!listOpen" aria-label="会话列表">☷</button>
        <h2 class="font-bold flex-1 truncate">{{ creating ? '建立新对话' : session?.title || '独立角色对话' }}</h2>
        <button class="md:hidden text-sm" @click="creating=true">＋ 新对话</button>
        <button ref="detailsToggle" v-if="session && !creating" class="text-sm text-slate-400" @click="details=!details">{{ details ? '收起资料' : '会话资料' }}</button>
      </div>

      <form v-if="creating" class="p-5 max-w-lg w-full mx-auto space-y-4 overflow-y-auto" @submit.prevent="create">
        <p class="text-sm text-slate-400">卡片作为此会话的独立快照，不会修改原卡。</p>
        <label class="block text-sm">AI 扮演的角色
          <button type="button" data-testid="character-ai-card" class="field text-left" :disabled="createBusy" @click="picker='ai'">{{ aiCard || '＋ 选择角色卡' }}</button>
        </label>
        <p v-if="!assetStore.characters.global.length" class="text-sm text-amber-200">暂无角色卡。<button type="button" class="underline" @click="uiStore.appMode='workshop'">前往工坊制卡</button>，或在资源库导入。</p>
        <label class="block text-sm">对话名称（可选）<input v-model="title" data-testid="character-title" class="field" maxlength="80" placeholder="默认使用角色名字"></label>
        <label class="block text-sm">表现方式<select v-model="mode" data-testid="character-create-mode" class="field"><option value="messenger">即时聊天</option><option value="roleplay">情景扮演</option></select></label>
        <label class="block text-sm">世界书（可选）<button type="button" data-testid="character-world-card" class="field text-left" :disabled="createBusy" @click="picker='world'">{{ worldCard || '＋ 载入世界书' }}</button></label>
        <p class="text-xs text-slate-400">世界书作为本会话的独立快照；公开常驻规则及相关条目提供给角色，不改写原世界书。</p>
        <label class="block text-sm">我的身份（可选）<button type="button" data-testid="character-user-card" class="field text-left" :disabled="createBusy" @click="picker='user'">{{ userCard || '我（不加载玩家卡）' }}</button></label>
        <p v-if="createError" class="text-sm text-rose-300">{{ createError }}</p>
        <div class="flex gap-2"><button data-testid="character-create" class="rounded-lg bg-indigo-700 px-4 py-2 disabled:opacity-40" :disabled="!aiCard || createBusy">{{ createBusy?'建立中…':'开始对话' }}</button><button type="button" class="text-slate-400 px-3" @click="creating=false">取消</button></div>
      </form>

      <div v-else-if="session?.schema_read_only" class="p-5 text-amber-200">此会话由更高版本创建，当前版本仅保留原文件。请升级后查看与继续对话。</div>
      <template v-else-if="session">
        <div ref="messagePane" data-testid="character-history" class="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 md:p-6 space-y-5">
          <button v-if="turns.length && !ctx.historyComplete" class="text-xs text-slate-400 block mx-auto" :disabled="ctx.historyLoading" @click="store.loadEarlier(store.activeId)">{{ ctx.historyLoading?'载入中…':'载入更早的对话' }}</button>
          <div v-if="!turns.length" class="text-slate-500 text-center py-10">和 {{ participant('ai')?.display_name || '角色' }} 说点什么吧。</div>
          <div v-for="turn in turns" :key="turn.turn_id" class="space-y-3 max-w-4xl mx-auto">
            <div class="flex justify-end"><div class="max-w-[90%] md:max-w-[80%] rounded-xl bg-indigo-950 border border-indigo-800/50 p-3"><div class="text-xs text-indigo-300 mb-2">{{ participant('user')?.display_name || '我' }} · {{ modeName(turn.mode_at_generation) }}</div><p class="whitespace-pre-wrap break-words select-text" data-testid="character-user-message">{{ text(turn.user_message) }}</p></div></div>
            <div class="max-w-[90%] md:max-w-[80%] rounded-xl bg-slate-900 border border-slate-800 p-3"><div class="text-xs text-emerald-300 mb-2">{{ participant('ai')?.display_name || '角色' }}</div><p class="whitespace-pre-wrap break-words select-text" data-testid="character-ai-message">{{ text(turn.ai_message) }}</p></div>
          </div>
          <div v-if="ctx.busy" data-testid="character-preview" class="max-w-4xl mx-auto rounded-xl border border-amber-700/40 bg-slate-900 p-3">
            <div class="text-xs text-amber-300 mb-2">{{ ctx.inflight?.status==='unknown'?'状态待确认':ctx.inflight?.status==='validating'?'正在验证与保存':ctx.preview?'生成中 · 未保存':'对方正在输入中' }}</div>
            <p class="whitespace-pre-wrap break-words select-text">{{ ctx.preview }}</p>
          </div>
        </div>
        <div class="shrink-0 border-t border-slate-800 p-3 space-y-2">
          <div v-if="ctx.error" data-testid="character-error" class="text-sm text-rose-300 flex flex-wrap items-center gap-2"><span>{{ ctx.error }}</span><button v-if="ctx.failure?.retryable && !ctx.busy" data-testid="character-retry" class="underline" @click="run(ctx.failure.operation,true)">重试本次生成</button><button v-if="ctx.busy && ctx.inflight?.status==='unknown'" class="underline" @click="store.recover(store.activeId,ctx.inflight)">核对状态</button></div>
          <button v-if="ctx.needsReload" class="text-xs underline text-amber-300" @click="store.open(store.activeId)">重新载入记录</button>
          <div class="flex items-center gap-3 text-xs text-slate-400"><label>回应方式 <select v-model="ctx.delivery" data-testid="character-delivery" :disabled="ctx.busy" class="bg-slate-900 border border-slate-700 rounded p-1"><option value="stream">流式</option><option value="non_stream">非流式</option></select></label><span class="flex-1"></span><button v-if="turns.length" data-testid="character-regenerate" :disabled="ctx.busy || readonly" @click="regenerate">重新生成末轮</button><button v-if="turns.length" data-testid="character-undo" :disabled="ctx.busy || readonly" @click="undo">撤回末轮</button></div>
          <form class="flex gap-2" @submit.prevent="run('send')"><textarea v-model="ctx.draft" data-testid="character-composer" rows="2" maxlength="4000" class="field !mt-0 resize-none flex-1" placeholder="输入消息；Enter 换行，Ctrl+Enter 发送" @keydown.ctrl.enter.prevent="run('send')"></textarea><button v-if="ctx.busy" data-testid="character-stop" type="button" class="rounded-lg bg-amber-900 px-4 disabled:opacity-40" :disabled="!ctx.inflight?.request_id" @click="store.stop(store.activeId)">停止</button><button v-else data-testid="character-send" class="rounded-lg bg-indigo-700 px-4 disabled:opacity-40" :disabled="!ctx.draft.trim() || ctx.needsReload">发送</button></form>
        </div>
      </template>
      <div v-else class="flex-1 flex flex-col items-center justify-center gap-4 text-slate-400"><p>独立的一对一角色对话，保存后可随时继续。</p><button class="bg-indigo-700 rounded-lg px-5 py-2 text-white" @click="creating=true">新对话</button></div>
    </main>

    <aside v-if="details && session && !creating" class="absolute md:static md:shrink-0 right-0 inset-y-0 w-72 z-10 bg-slate-900 border-l border-slate-700 p-4 overflow-y-auto shadow-xl">
      <div class="flex justify-between"><h3 class="font-bold">当前对话</h3><button @click="details=false" aria-label="关闭资料">✕</button></div>
      <h4 class="mt-5 text-sm font-bold text-indigo-200">资料</h4>
      <details v-for="p in session.participants" :key="p.instance_id" class="mt-5 text-sm"><summary class="cursor-pointer">{{ p.display_name }} · {{ p.controller==='ai'?'AI扮演':'用户扮演' }}</summary><p class="mt-2 whitespace-pre-wrap text-slate-400 select-text">{{ p.profile_snapshot?.description }}</p><details v-if="p.profile_snapshot?.starting_scene" class="mt-2"><summary>角色场景资料</summary><p class="whitespace-pre-wrap select-text">{{ p.profile_snapshot.starting_scene }}</p></details></details>
      <div class="mt-5 text-sm" data-testid="character-world-details"><p>世界书 · {{ session.world_binding?.name || '未载入' }}</p><p v-if="session.world_binding" class="mt-2 text-xs text-slate-500">创建时快照，不随源资产自动变化。</p></div>
<h4 class="text-sm mt-6 mb-2">共同经历</h4><div data-testid="character-public-ledger" class="space-y-2"><p v-if="!session.ledger?.length" class="text-xs text-slate-500">暂无公开记录</p><div v-for="entry in session.ledger" :key="entry.entry_id" class="text-sm rounded bg-slate-950 p-2"><p class="whitespace-pre-wrap select-text">{{ entry.content || entry.text || entry.summary }}</p><p class="text-xs text-slate-500 mt-1">{{ entry.knowledge_type || entry.kind }} · {{ entry.source?.type==='player_statement'?'用户陈述':entry.source?.type==='model_inference'?'角色推断':'共同对话' }}</p><details v-if="entry.source" class="text-xs text-slate-400 mt-1"><summary class="cursor-pointer">来源证据</summary><p v-for="(item,index) in entry.source.evidence || []" :key="index" class="whitespace-pre-wrap select-text mt-1">{{ item.quote }}</p><p class="break-all select-text mt-1">{{ (entry.source.message_ids || []).join('、') }}</p></details></div></div>
      <button data-testid="character-spoiler" class="text-xs text-amber-300 mt-4" @click="ctx.spoiler ? store.clearSpoiler() : store.loadSpoiler(store.activeId).catch(e=>ctx.error=e.message)">{{ ctx.spoiler ? '隐藏内部记录' : '查看角色内部记录（剧透）' }}</button>
      <div v-if="ctx.spoiler" data-testid="character-private-ledger" class="space-y-2 mt-2"><div v-for="entry in ctx.spoiler" :key="entry.entry_id" class="text-sm rounded bg-amber-950/40 p-2 whitespace-pre-wrap select-text">{{ entry.content || entry.text || entry.summary }}</div></div>
      <h4 class="mt-6 text-sm font-bold text-indigo-200">会话设置</h4>
      <label class="block text-sm mt-3">表现方式<select :value="session.presentation_mode" data-testid="character-mode" :disabled="ctx.busy || readonly" class="field" @change="updateMode"><option value="messenger">即时聊天</option><option value="roleplay">情景扮演</option></select></label>
      <button data-testid="character-delete" class="text-rose-400 text-sm mt-4 disabled:opacity-40" :disabled="ctx.busy || readonly" @click="remove">删除此对话</button>
    </aside>
  </section>
  <AssetCardPicker v-if="picker" v-model="pickerValue" :items="picker==='world' ? assetStore.worlds.global : assetStore.characters.global" :title="picker==='world' ? '选择世界书' : picker==='ai' ? '选择AI角色' : '选择我的角色'" :empty-label="picker==='world' ? '不加载世界书' : picker==='user' ? '我（不加载玩家卡）' : ''" @close="picker=''" />
</template>

<style scoped>
.field { display:block; width:100%; margin-top:0.5rem; padding:0.6rem; background:#020617; border:1px solid #334155; border-radius:0.5rem; color:#e2e8f0; }
button:disabled { opacity:.4; cursor:not-allowed; }
</style>
