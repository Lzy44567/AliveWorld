<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { characterChatStore as store } from '../../store/characterChatStore.js';
import { assetStore } from '../../store/assetStore';
import { uiStore } from '../../store/uiStore';
import AssetCardPicker from '../assets/AssetCardPicker.vue';
import CharacterConversationList from './CharacterConversationList.vue';
import CharacterProfileDetails from './CharacterProfileDetails.vue';
import CharacterPresentationPicker from './CharacterPresentationPicker.vue';
import CharacterMessagePair from './CharacterMessagePair.vue';
import CharacterOpeningEditor from './CharacterOpeningEditor.vue';
import CharacterOpeningMessage from './CharacterOpeningMessage.vue';
import CharacterWorldContextReport from './CharacterWorldContextReport.vue';
import CharacterPreferenceSettings from './CharacterPreferenceSettings.vue';
import CharacterMemoryPanel from './CharacterMemoryPanel.vue';
import CharacterMemoryNotice from './CharacterMemoryNotice.vue';
import CharacterCapacityPanel from './CharacterCapacityPanel.vue';
import { capacityWarning } from '../../utils/characterCapacity.js';
import { shouldSendCharacterKey } from '../../utils/characterInteraction.js';

const creating = ref(false), aiCard = ref(''), userCard = ref(''), worldCard = ref(''), title = ref(''), mode = ref('messenger'), createBusy = ref(false), createError = ref('');
const creationId = ref(globalThis.crypto.randomUUID());
const openingText = ref('');
const details = ref(false), listOpen = ref(false), messagePane = ref(null);
const listToggle = ref(null), detailsToggle = ref(null);
const picker = ref('');
let mounted = false;
const pickerValue = computed({ get: () => picker.value === 'ai' ? aiCard.value : picker.value === 'user' ? userCard.value : worldCard.value, set: value => { if (picker.value === 'ai') aiCard.value=value; else if (picker.value === 'user') userCard.value=value; else worldCard.value=value; } });
const ctx = computed(() => store.current);
const session = computed(() => ctx.value?.session);
const turns = computed(() => session.value?.turns || []);
const readonly = computed(() => Boolean(session.value?.schema_read_only || ctx.value?.needsReload));
const capacityAlert = computed(() => capacityWarning(ctx.value?.capacity));
function showCapacity() { details.value = true; ctx.value.capacityOpen = true; void store.refreshCapacity(session.value.session_id); }
function capacityToggle(value) { if (ctx.value.capacityOpen === value) return; ctx.value.capacityOpen = value; if (value) void store.refreshCapacity(session.value.session_id); }
const composing = ref(false);
const participant = controller => session.value?.participants?.find(p => p.controller === controller);
const run = (operation, retry = false) => store.run(store.activeId, operation, retry);
async function create() {
  if ((!aiCard.value && !store.creationPending) || createBusy.value) return;
  createBusy.value = true; createError.value = '';
  try {
    await store.create(store.creationPending ? undefined : { client_creation_id: creationId.value, title: title.value || undefined, ai_asset_ref: { kind: 'character', key: aiCard.value }, opening_text: openingText.value,
      ...(userCard.value ? { user_asset_ref: { kind: 'character', key: userCard.value } } : {}),
      ...(worldCard.value ? { world_asset_ref: { kind: 'worldbook', key: worldCard.value } } : {}), presentation_mode: mode.value });
    creating.value = false; listOpen.value = false; creationId.value = globalThis.crypto.randomUUID(); openingText.value = '';
  } catch (e) { createError.value = e.message; } finally { createBusy.value = false; }
}
async function open(id) { creating.value = false; listOpen.value = false; await store.open(id); await nextTick(); store.markPresented(id); }
async function updateMode(value) {
  const id = store.activeId;
  try { await store.update(id, { presentation_mode: value }); }
  catch (e) { store.context(id).error = e.message; }
}
async function updatePreferences(value) {
  const id = store.activeId;
  try { await store.update(id, { preference_settings: value }); }
  catch (e) { store.context(id).error = e.message; }
}
function keydown(event) {
  if (shouldSendCharacterKey(event, ctx.value?.sendKey, composing.value)) { event.preventDefault(); run('send'); }
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
    <aside :class="listOpen ? 'flex absolute inset-y-0 left-0 z-20 w-72 shadow-xl' : 'hidden md:flex w-72'" class="shrink-0 flex-col bg-slate-900 border-r border-slate-700 p-3 gap-3">
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
        <fieldset :disabled="createBusy || Boolean(store.creationPending)" class="space-y-4">
        <p class="text-sm text-slate-400">卡片作为此会话的独立快照，不会修改原卡。</p>
        <label class="block text-sm">AI 扮演的角色
          <button type="button" data-testid="character-ai-card" class="field text-left" :disabled="createBusy" @click="picker='ai'">{{ aiCard || '＋ 选择角色卡' }}</button>
        </label>
        <p v-if="!assetStore.characters.global.length" class="text-sm text-amber-200">暂无角色卡。<button type="button" class="underline" @click="uiStore.appMode='workshop'">前往工坊制卡</button>，或在资源库导入。</p>
        <label class="block text-sm">对话名称（可选）<input v-model="title" data-testid="character-title" class="field" maxlength="80" placeholder="默认使用角色名字"></label>
        <CharacterPresentationPicker v-model="mode" test-id="character-create-mode" :disabled="createBusy" />
        <label class="block text-sm">世界书（可选）<button type="button" data-testid="character-world-card" class="field text-left" :disabled="createBusy" @click="picker='world'">{{ worldCard || '＋ 载入世界书' }}</button></label>
        <p class="text-xs text-slate-400">世界书作为本会话的独立快照；公开常驻规则及相关条目提供给角色，不改写原世界书。</p>
        <label class="block text-sm">我的身份（可选）<button type="button" data-testid="character-user-card" class="field text-left" :disabled="createBusy" @click="picker='user'">{{ userCard || '我（不加载玩家卡）' }}</button></label>
        <CharacterOpeningEditor v-model="openingText" :card="aiCard" :disabled="createBusy || Boolean(store.creationPending)" />
        </fieldset>
        <p v-if="store.creationPending" class="text-xs text-amber-300">创建结果待确认；再次点击将核对／重试原请求，不会新建第二份。原请求：{{ store.creationPending.title || store.creationPending.ai_asset_ref?.key }}</p>
        <p v-if="createError" class="text-sm text-rose-300">{{ createError }}</p>
        <div class="flex gap-2"><button data-testid="character-create" class="rounded-lg bg-indigo-700 px-4 py-2 disabled:opacity-40" :disabled="(!aiCard && !store.creationPending) || createBusy || Array.from(openingText).length>8000">{{ createBusy?'建立中…':store.creationPending?'核对／重试创建':'开始对话' }}</button><button type="button" class="text-slate-400 px-3" @click="creating=false">取消</button></div>
      </form>

      <div v-else-if="session?.schema_read_only" class="p-5 text-amber-200">此会话由更高版本创建，当前版本仅保留原文件。请升级后查看与继续对话。</div>
      <template v-else-if="session">
        <CharacterMemoryNotice :notice="ctx.memoryNotice" @close="store.closeMemoryNotice(session.session_id)" />
        <div v-if="capacityAlert" data-testid="character-capacity-warning" role="status" class="text-xs text-amber-200 px-4 py-2">{{ capacityAlert }} <button class="underline" @click="showCapacity">查看容量</button></div>
        <div ref="messagePane" data-testid="character-history" class="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 md:p-6 space-y-5">
          <button v-if="turns.length && !ctx.historyComplete" class="text-xs text-slate-400 block mx-auto" :disabled="ctx.historyLoading" @click="store.loadEarlier(store.activeId)">{{ ctx.historyLoading?'载入中…':'载入更早的对话' }}</button>
          <CharacterOpeningMessage v-if="session.opening" :opening="session.opening" :name="participant('ai')?.display_name" />
          <div v-if="!turns.length && !session.opening" class="text-slate-500 text-center py-10">和 {{ participant('ai')?.display_name || '角色' }} 说点什么吧。</div>
          <CharacterMessagePair v-for="turn in turns" :key="turn.turn_id" :turn="turn" :user-name="participant('user')?.display_name" :ai-name="participant('ai')?.display_name" />
          <div v-if="ctx.busy" data-testid="character-preview" class="max-w-[90%] md:max-w-[72%] rounded-xl border border-amber-700/40 bg-slate-900 p-3">
            <div class="text-xs text-amber-300 mb-2">{{ ctx.inflight?.status==='unknown'?'状态待确认':ctx.inflight?.status==='validating'?'正在验证与保存':ctx.preview?'生成中 · 未保存':'对方正在输入中' }}</div>
            <p class="whitespace-pre-wrap break-words select-text">{{ ctx.preview }}</p>
          </div>
        </div>
        <div class="shrink-0 border-t border-slate-800 p-3 space-y-2">
          <p v-if="ctx.contextNotice" data-testid="character-context-notice" class="text-xs text-amber-300">{{ ctx.contextNotice }}</p>
          <div v-if="ctx.error" data-testid="character-error" class="text-sm text-rose-300 flex flex-wrap items-center gap-2"><span>{{ ctx.error }}</span><button v-if="ctx.failure?.retryable && !ctx.busy" data-testid="character-retry" class="underline" @click="run(ctx.failure.operation,true)">重试本次生成</button><button v-if="ctx.busy && ctx.inflight?.status==='unknown'" class="underline" @click="store.recover(store.activeId,ctx.inflight)">核对状态</button></div>
          <button v-if="ctx.needsReload" class="text-xs underline text-amber-300" @click="store.open(store.activeId)">重新载入记录</button>
          <div v-if="turns.length" class="flex justify-end gap-3 text-xs text-slate-500"><button data-testid="character-regenerate" :disabled="ctx.busy || ctx.settingsBusy || readonly" @click="regenerate">重新生成末轮</button><button data-testid="character-undo" :disabled="ctx.busy || ctx.settingsBusy || readonly" @click="undo">撤回末轮</button></div>
          <form class="space-y-2" @submit.prevent="run('send')"><textarea v-model="ctx.draft" data-testid="character-composer" rows="3" maxlength="4000" class="field !mt-0 resize-none" :placeholder="ctx.sendKey==='ctrl_enter'?'输入消息；Enter 换行，Ctrl+Enter 发送':'输入消息；Enter 发送，Shift+Enter 换行'" @compositionstart="composing=true" @compositionend="composing=false" @keydown="keydown"></textarea><div class="flex justify-end items-center gap-3"><span class="text-[11px] text-slate-500">{{ ctx.sendKey==='ctrl_enter'?'Ctrl+Enter 发送':'Enter 发送 · Shift+Enter 换行' }}</span><button v-if="ctx.busy" data-testid="character-stop" type="button" class="rounded-lg bg-amber-900 px-5 py-2 disabled:opacity-40" :disabled="!ctx.inflight?.request_id" @click="store.stop(store.activeId)">停止</button><button v-else data-testid="character-send" class="rounded-lg bg-indigo-700 px-5 py-2 disabled:opacity-40" :disabled="!ctx.draft.trim() || ctx.needsReload || ctx.settingsBusy">发送</button></div></form>
        </div>
      </template>
      <div v-else class="flex-1 flex flex-col items-center justify-center gap-4 text-slate-400"><p>独立的一对一角色对话，保存后可随时继续。</p><button class="bg-indigo-700 rounded-lg px-5 py-2 text-white" @click="creating=true">新对话</button></div>
    </main>

    <aside v-if="details && session && !creating" class="absolute md:static md:shrink-0 right-0 inset-y-0 w-72 z-10 bg-slate-900 border-l border-slate-700 p-4 overflow-y-auto shadow-xl">
      <div class="flex justify-between"><h3 class="font-bold">当前对话</h3><button @click="details=false" aria-label="关闭资料">✕</button></div>
      <h4 class="mt-5 text-sm font-bold text-indigo-200">资料</h4>
      <details v-if="session.opening" class="mt-4 text-sm"><summary>本会话预设开场</summary><p class="mt-2 whitespace-pre-wrap break-words select-text text-slate-400">{{ session.opening.content }}</p><p class="mt-2 text-xs text-slate-500">创建后冻结，不是正式回合或玩家行动证据。</p></details>
      <details v-for="p in session.participants" :key="p.instance_id" class="mt-5 text-sm"><summary class="cursor-pointer">{{ p.display_name }} · {{ p.controller==='ai'?'AI扮演':'用户扮演' }}</summary><CharacterProfileDetails v-if="p.profile_snapshot?.semantics==='role_fields_v1'" :profile="p.profile_snapshot" /><template v-else><p class="mt-2 whitespace-pre-wrap text-slate-400 select-text">{{ p.profile_snapshot?.description }}</p><details v-if="p.profile_snapshot?.starting_scene" class="mt-2"><summary>角色场景资料</summary><p class="whitespace-pre-wrap select-text">{{ p.profile_snapshot.starting_scene }}</p></details></template></details>
      <div class="mt-5 text-sm" data-testid="character-world-details"><p>世界书 · {{ session.world_binding?.name || '未载入' }}</p><template v-if="session.world_binding"><p class="mt-2 text-xs text-slate-500">创建时快照，不随源资产自动变化。关键词参考本次输入与最近4回合的双方公开聊天，历史文本有长度限制；不扫描全部历史。</p><p class="mt-2 text-xs text-slate-500">世界设定不是角色已知的一切；本版本尚无条目级秘密权限。</p><CharacterWorldContextReport :report="ctx.worldReport" /></template></div>
      <CharacterMemoryPanel :session="session" :report="ctx.memoryReport" :cognition="ctx.cognition" :cognition-loading="ctx.cognitionLoading" :cognition-error="ctx.cognitionError" :recall-report="ctx.sourceRecallReport" :disabled="ctx.busy || ctx.settingsBusy || readonly" :source-loader="(id,entry)=>store.memorySources(id,entry)" @cognition-open="store.setCognitionOpen(session.session_id,$event)" @mark="(entry,important)=>store.markMemory(session.session_id,entry,important)" @correct="entry=>store.correctMemory(session.session_id,entry)" @enable-automatic="store.enableAutomaticMemory(session.session_id)" @select-automatic="(entry,dismissed)=>store.selectAutomaticMemory(session.session_id,entry,dismissed)" @release-automatic="root=>store.releaseAutomaticMemory(session.session_id,root)" />
      <button data-testid="character-spoiler" class="text-xs text-amber-300 mt-4" @click="ctx.spoiler ? store.clearSpoiler() : store.loadSpoiler(store.activeId).catch(e=>ctx.error=e.message)">{{ ctx.spoiler ? '隐藏内部记录' : '查看角色内部记录（剧透）' }}</button>
      <div v-if="ctx.spoiler" data-testid="character-private-ledger" class="space-y-2 mt-2"><div v-for="entry in ctx.spoiler" :key="entry.entry_id" class="text-sm rounded bg-amber-950/40 p-2 whitespace-pre-wrap select-text">{{ entry.content || entry.text || entry.summary }}</div></div>
      <h4 class="mt-6 text-sm font-bold text-indigo-200">会话设置</h4>
      <CharacterCapacityPanel :report="ctx.capacity" :loading="ctx.capacityLoading" :error="ctx.capacityError" :open="ctx.capacityOpen" @toggle="capacityToggle" @refresh="store.refreshCapacity(session.session_id)" />
      <CharacterPreferenceSettings :settings="session.preference_settings" :disabled="ctx.busy || ctx.settingsBusy || readonly" @update="updatePreferences" />
      <div class="mt-3"><CharacterPresentationPicker :model-value="session.presentation_mode" test-id="character-mode" :disabled="ctx.busy || ctx.settingsBusy || readonly" @update:model-value="updateMode" /></div>
      <label class="mt-5 flex items-center justify-between gap-3 text-sm">流式输出<input data-testid="character-delivery" type="checkbox" role="switch" :checked="ctx.delivery==='stream'" :disabled="ctx.busy" @change="store.setInteraction(store.activeId,{delivery:$event.target.checked?'stream':'non_stream'})"></label>
      <p class="mt-1 text-xs text-slate-500">{{ ctx.delivery==='stream'?'收到内容时逐步显示；验证保存后才成为正式消息。':'等待完整回复后显示。' }}</p>
      <label class="mt-4 flex items-center justify-between gap-3 text-sm">Enter 发送<input data-testid="character-send-key" type="checkbox" role="switch" :checked="ctx.sendKey==='enter'" :disabled="ctx.busy" @change="store.setInteraction(store.activeId,{sendKey:$event.target.checked?'enter':'ctrl_enter'})"></label>
      <p class="mt-1 text-xs text-slate-500">{{ ctx.sendKey==='enter'?'Shift+Enter 换行；Ctrl+Enter 也可发送。':'Enter 换行，Ctrl+Enter 发送，适合长文本。' }}</p>
      <p v-if="store.interaction.warning" class="mt-3 text-xs text-amber-300">{{ store.interaction.warning }}</p>
      <p class="mt-3 text-[10px] text-slate-500">流式和键位仅保存在此浏览器，按对话分别设置。</p>
      <button data-testid="character-delete" class="text-rose-400 text-sm mt-4 disabled:opacity-40" :disabled="ctx.busy || readonly" @click="remove">删除此对话</button>
    </aside>
  </section>
  <AssetCardPicker v-if="picker" v-model="pickerValue" :items="picker==='world' ? assetStore.worlds.global : assetStore.characters.global" :title="picker==='world' ? '选择世界书' : picker==='ai' ? '选择AI角色' : '选择我的角色'" :empty-label="picker==='world' ? '不加载世界书' : picker==='user' ? '我（不加载玩家卡）' : ''" @close="picker=''" />
</template>

<style scoped>
.field { display:block; width:100%; margin-top:0.5rem; padding:0.6rem; background:#020617; border:1px solid #334155; border-radius:0.5rem; color:#e2e8f0; }
button:disabled { opacity:.4; cursor:not-allowed; }
</style>
