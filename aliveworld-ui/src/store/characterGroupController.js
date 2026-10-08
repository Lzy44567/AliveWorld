import { groupDetail, mergeGroupPage, presentedAiSeq } from '../utils/characterGroupState.js';
import { oocText, oocError, restoreInputPair } from '../utils/characterOoc.js';
import { characterWorldReport } from '../utils/characterWorldReport.js';
import { characterMemoryReport, memoryNotice } from '../utils/characterMemory.js';
import { sourceRecallReport } from '../utils/characterCognition.js';

const ended = status => ['committed','already_committed','failed','cancelled','interrupted'].includes(status);
const rejected = code => ['INVALID_REQUEST','REVISION_CONFLICT','SESSION_BUSY','SCHEMA_READ_ONLY','SESSION_DELETED','SESSION_NOT_FOUND','INPUT_LIMIT','IDEMPOTENCY_MISMATCH','STALE_RETRY','SESSION_LIMIT'].includes(code);
// Owns subscriptions and quick command lifetimes, never the server worker.
export function createCharacterGroupController(state, api, noticeCache) {
  const links = new Map(), refreshes = new Map(), reads = new Map();
  function detach(id) { const link = links.get(id); if (link) { links.delete(id); link.abort.abort(); } }
  function acceptCommand(ctx, actionId) {
    const command = ctx.groupCommand;
    if (!command || command.action_id !== actionId || command.accepted) return;
    command.accepted = true;
    if (command.clearsDraft && ctx.draft === command.content && ctx.oocDraft === command.oocDraft) { ctx.draft = ''; ctx.oocDraft = ''; }
  }
  async function refresh(id) {
    const ctx = state.contexts[id]; if (!ctx) return;
    const current = refreshes.get(id);
    if (current) { current.again = true; return current.promise; }
    const task = { again: false };
    task.promise = (async () => {
      let passes = 0;
      do {
        if (++passes > 8) throw Error('状态连续变化，请稍后重新核对');
        task.again = false;
        let session = groupDetail(await api.get(id),id);
        if (state.contexts[id] !== ctx) return;
        if (session.revision < (ctx.session?.revision || 0)) { task.again = true; continue; }
        // Revalidate already loaded pages, not blindly retain withdrawn/replaced rows.
        const previousFirst = ctx.session?.messages?.[0]?.message.seq;
        for (let page = 0; previousFirst && session.next_cursor && session.messages[0]?.message.seq > previousFirst && page < 26; page++) {
          session = mergeGroupPage(session,await api.groups(id,session.next_cursor));
        }
        // Atomic authoritative replacement: keep previews until matching formal IDs exist.
        ctx.session = session; ctx.busy = Boolean(session.busy_group); ctx.queuedCount = session.queued_count;
        ctx.historyComplete = !session.next_cursor; ctx.needsReload = false;
        ctx.failure = session.last_failed_action || null;
        for (const [rid,preview] of Object.entries(ctx.previewByRequestOrdinal)) {
          const group = session.groups.find(g => g.request_id === rid);
          if (group && group.status !== 'generating' || preview.terminal) delete ctx.previewByRequestOrdinal[rid];
        }
      } while (task.again);
    })().catch(e => { if (state.contexts[id] === ctx) { ctx.error = '会话状态待核对：' + e.message; ctx.needsReload = true; } })
      .finally(() => { if (refreshes.get(id) === task) refreshes.delete(id); });
    refreshes.set(id,task); return task.promise;
  }
  async function notice(id, raw) {
    const ctx = state.contexts[id], value = memoryNotice(raw);
    if (!ctx?.session || !value || !state.visible || state.activeId !== id ||
        value.committed_revision > ctx.session.revision || value.committed_revision <= (ctx.session.memory_settings?.notice_ack_revision || 0) || !noticeCache.claim(id,value.action_id)) return;
    ctx.memoryNotice = value;
    await state.acknowledgeMemoryNotice(id,value);
  }
  async function event(id, link, name, data) {
    if (links.get(id) !== link || data.session_id !== id) return;
    const ctx = state.contexts[id]; if (!ctx) return;
    if (name === 'ready') { ctx.subscriptionReady = true; ctx.subscriptionError = ''; ctx.previewByRequestOrdinal = {}; await refresh(id); return; }
    if (name === 'input_saved') { acceptCommand(ctx,data.action_id); await refresh(id); void state.refreshList(); return; }
    if (name === 'accepted') {
      ctx.previewByRequestOrdinal[data.request_id] = { action_id: data.action_id, group_id: data.group_id, display_mode: data.display_mode,
        reserved: [...data.reserved_ai_ids], bubbles: [], lastSeq: data.seq };
      ctx.contextNotice = data.context_omissions?.some(item => item.field === 'dialogue_examples') ? '本次上下文预算不足，示例整段未发送。' : '';
      ctx.worldReport = characterWorldReport(data.world_context_report); ctx.memoryReport = characterMemoryReport(data.memory_context_report);
      ctx.sourceRecallReport = sourceRecallReport(data.source_recall_report); ctx.busy = true;
      return;
    }
    const preview = ctx.previewByRequestOrdinal[data.request_id];
    if (name.startsWith('preview_')) {
      if (!preview || preview.display_mode !== 'stream' || preview.group_id !== data.group_id || preview.action_id !== data.action_id || data.seq <= preview.lastSeq) return;
      preview.lastSeq = data.seq;
      const ordinal = data.ordinal;
      if (ordinal >= preview.reserved.length) throw Error('预览气泡身份待核对');
      if (name === 'preview_start') {
        if (preview.bubbles[ordinal] || ordinal !== preview.bubbles.length) throw Error('预览气泡顺序待核对');
        preview.bubbles.push({ message_id: preview.reserved[ordinal], group_id: preview.group_id,
          speaker_instance_id: ctx.session.participants.find(p => p.controller === 'ai').instance_id, text: '', ended: false });
      } else {
        const bubble = preview.bubbles[ordinal]; if (!bubble || bubble.ended) throw Error('预览气泡状态待核对');
        if (name === 'preview_delta') {
          if (preview.bubbles.reduce((n,b) => n + [...b.text].length,0) + [...data.text].length > 8000) throw Error('预览超出安全长度');
          bubble.text += data.text;
        } else bubble.ended = true;
      }
      return;
    }
    if (['group_saved','failed','cancelled','interrupted','state_changed'].includes(name)) {
      if (preview && name !== 'state_changed') preview.terminal = true;
      await refresh(id); void state.refreshList();
      if (name === 'group_saved' && data.group?.status === 'complete') { await notice(id,data.group.memory_notice); void state.refreshCapacity(id); if (ctx.cognitionOpen) void state.refreshCognition(id); }
      if (['failed','cancelled','interrupted'].includes(name)) ctx.error = name === 'cancelled' ? '生成已取消；已发送消息保留。' : '生成未完成；已发送消息保留，请核对后重试。';
    }
  }
  function attach(id) {
    if (!state.visible || state.activeId !== id || state.contexts[id]?.session?.schema_version !== 2 || links.has(id)) return;
    for (const other of links.keys()) detach(other);
    const ctx = state.contexts[id], link = { abort: new AbortController() };
    links.set(id,link); ctx.subscriptionReady = false;
    // Stream parser dispatch is synchronous; asynchronous state refresh failures are contained here.
    void api.subscribe(id,(name,data) => { void event(id,link,name,data).catch(e => {
      if (links.get(id) === link) { ctx.subscriptionError = e.message; detach(id); void refresh(id); }
    }); },{ signal: link.abort.signal }).catch(e => {
      if (links.get(id) === link) { ctx.subscriptionError = e.message; void refresh(id); }
    }).finally(() => { if (links.get(id) === link) { links.delete(id); ctx.subscriptionReady = false; } });
  }
  async function open(id) { for (const other of links.keys()) if (other !== id) detach(other); await refresh(id); attach(id); }
  function visibility() { for (const id of links.keys()) if (!state.visible || state.activeId !== id) detach(id); if (state.visible) { attach(state.activeId); void state.refreshList(); } }
  async function recover(id) {
    const ctx = state.contexts[id], command = ctx?.groupCommand; if (!command || command.checking) return;
    command.checking = true;
    try {
      const result = await api.actionStatus(id,command.action_id);
      acceptCommand(ctx,command.action_id); ctx.commandPending = false;
      if (command.operation === 'undo' && ended(result.status)) restoreInputPair(ctx,command.withdrawnInput,command.withdrawnOoc);
      await refresh(id); ctx.groupCommand = null; attach(id);
    } catch (e) {
      if (e.code === 'ACTION_NOT_FOUND') { ctx.commandPending = false; ctx.groupCommand = null; ctx.error = '服务器确认消息未保存，草稿保留，可重新发送。'; }
      else ctx.error = '发送结果待核对：' + e.message + '；不会自动重发。';
    } finally { command.checking = false; }
  }
  async function run(id, operation = 'send', retry = false) {
    const ctx = state.context(id);
    if (!ctx.session || ctx.session.schema_version !== 2 || ctx.commandPending || ctx.settingsBusy || ctx.needsReload) return;
    if ((retry || operation !== 'send') && (ctx.busy || ctx.queuedCount)) return;
    if (!retry && operation === 'send' && (!ctx.draft.trim() || oocError(ctx.oocDraft))) { ctx.error = oocError(ctx.oocDraft); return; }
    const failed = ctx.failure; if (retry && !failed?.retryable) return;
    const target = ctx.session.groups.at(-1);
    const input = ctx.session.messages.find(row => row.message.message_id === target?.input_ids?.[0]);
    const command = { action_id: retry ? failed.action_id : crypto.randomUUID(), operation, clearsDraft: !retry && operation === 'send', content: ctx.draft, oocDraft: ctx.oocDraft,
      withdrawnInput: target?.input_ids?.length === 1 ? input?.message.content || '' : '', withdrawnOoc: target?.input_ids?.length === 1 ? input?.ooc_note || '' : '' };
    ctx.groupCommand = command; ctx.commandPending = true; ctx.error = '';
    const mode = state.interaction.display(id), delivery = mode === 'stream' ? 'stream' : 'non_stream';
    const payload = retry ? { expected_revision: ctx.session.revision, retry_of: failed.request_id, retry_token: crypto.randomUUID(), display_mode: mode, delivery }
      : { client_action_id: command.action_id, expected_revision: ctx.session.revision, operation, display_mode: mode, delivery,
        ...(operation === 'send' ? { content: command.content.trim(), ...(oocText(command.oocDraft) ? { ooc_note: oocText(command.oocDraft) } : {}) } : { target_group_id: target?.group_id }) };
    command.payload = payload;
    try {
      const result = retry ? await api.groupRetry(id,failed.action_id,payload) : await api.groupAction(id,payload);
      if (result.session_id !== id || result.action_id !== command.action_id) throw Error('发送身份待核对');
      acceptCommand(ctx,command.action_id); ctx.commandPending = false;
      if (operation === 'undo' && ended(result.status)) restoreInputPair(ctx,command.withdrawnInput,command.withdrawnOoc);
      ctx.groupCommand = null; await refresh(id); void state.refreshList(); attach(id);
    } catch (e) {
      if (rejected(e.code)) { ctx.commandPending = false; ctx.groupCommand = null; ctx.error = e.message; await refresh(id); }
      else { ctx.error = '发送结果待核对；不会自动重发。'; await recover(id); }
    }
  }
  async function markPresented(id) {
    const ctx = state.contexts[id];
    if (!ctx?.session || !state.visible || state.activeId !== id || ctx.needsReload || reads.has(id)) return;
    const seq = presentedAiSeq(ctx.session); if (seq <= ctx.session.read_ai_seq) return;
    reads.set(id,true);
    try {
      const result = await api.read(id,seq);
      if (result.session_id !== id || !Number.isSafeInteger(result.read_ai_seq) || result.read_ai_seq < seq || !Number.isSafeInteger(result.revision)) throw Error('已读状态待核对');
      // Never advance detail revision without loading the corresponding message state.
      await refresh(id); void state.refreshList();
    } catch (e) { ctx.subscriptionError = '已读状态待核对：' + e.message; }
    finally { reads.delete(id); }
  }
  async function loadEarlier(id) {
    const ctx = state.context(id); if (ctx.historyLoading || ctx.historyComplete) return;
    ctx.historyLoading = true;
    try { ctx.session = mergeGroupPage(ctx.session,await api.groups(id,ctx.session.next_cursor)); ctx.historyComplete = !ctx.session.next_cursor; }
    catch (e) { ctx.error = e.message; await refresh(id); }
    finally { ctx.historyLoading = false; }
  }
  async function stop(id) { const ctx = state.context(id), group = ctx.session?.busy_group; if (group?.status !== 'generating') return;
    try { await api.cancel(id,group.request_id); await refresh(id); } catch (e) { ctx.error = '取消结果待核对：' + e.message; } }
  return { open, attach, detach, visibility, refresh, recover, run, markPresented, loadEarlier, stop };
}
