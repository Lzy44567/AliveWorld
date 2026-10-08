import { reactive } from 'vue';
import { characterChatApi } from '../api/characterChatApi.js';
import { createConversationPreferences, detailReadMarker } from '../utils/characterConversationList.js';
import { createCharacterInteractionPreferences } from '../utils/characterInteraction.js';
import { characterWorldReport } from '../utils/characterWorldReport.js';
import { characterMemoryReport, correctionDraft, memorySourceMessages, automaticMemoryState, memoryNotice } from '../utils/characterMemory.js';
import { createMemoryNoticeCache } from '../utils/characterMemoryNotices.js';
import { characterCapacity, capacityWarning } from '../utils/characterCapacity.js';
import { characterCognition, sourceRecallReport } from '../utils/characterCognition.js';
import { oocText, oocError, restoreInputPair } from '../utils/characterOoc.js';
import { createCharacterGroupController } from './characterGroupController.js';

const uuid = () => globalThis.crypto.randomUUID();
const terminal = status => ['committed', 'cancelled', 'failed', 'interrupted'].includes(status);
export function createCharacterChatStore(api = characterChatApi, delay = ms => new Promise(resolve => setTimeout(resolve, ms)), storage) {
  let listGeneration = 0, spoilerGeneration = 0;
  const noticeCache = createMemoryNoticeCache(storage);
  let groups;
  const state = reactive({
    sessions: [], contexts: {}, activeId: '', error: '', loading: false, nextCursor: null,
    listComplete: false, listWarning: '', visible: false, creationPending: null, creationBusy: false, preferences: createConversationPreferences(storage), interaction: createCharacterInteractionPreferences(storage),
    get current() { return this.contexts[this.activeId] || null; },
    context(id) {
      if (!this.contexts[id]) this.contexts[id] = { session: null, draft: '', oocDraft: '', oocOpen: false, busy: false, settingsBusy: false, preview: '', inflight: null, failure: null, error: '', ...this.interaction.get(id), displayMode: this.interaction.display(id), commandPending: false, groupCommand: null, previewByRequestOrdinal: {}, subscriptionReady: false, subscriptionError: '', queuedCount: 0, historyLoading: false, historyComplete: false, needsReload: false, spoiler: null };
      return this.contexts[id];
    },
    setInteraction(id, changes) {
      const ctx = this.context(id);
      if ((ctx.busy && ctx.session?.schema_version !== 2) || !this.interaction.set(id, changes)) return;
      Object.assign(ctx, this.interaction.get(id), { displayMode: this.interaction.display(id) });
    },
    async refreshCapacity(id) {
      const ctx = this.contexts[id];
      if (!ctx?.session || ctx.session.schema_read_only) return;
      const seq = ctx.capacitySeq = (ctx.capacitySeq || 0) + 1;
      ctx.capacityLoading = true; ctx.capacityError = '';
      try {
        const report = characterCapacity(await api.capacity(id), id);
        if (this.contexts[id] !== ctx || seq !== ctx.capacitySeq) return;
        if (!report || report.revision < ctx.session.revision) throw Error('容量状态待重新核对');
        ctx.capacity = report;
      } catch (e) {
        if (this.contexts[id] === ctx && seq === ctx.capacitySeq) { ctx.capacity = null; ctx.capacityError = '暂时无法读取容量，请刷新状态。'; }
      } finally { if (this.contexts[id] === ctx && seq === ctx.capacitySeq) ctx.capacityLoading = false; }
    },
    async refreshCognition(id) {
      const ctx = this.contexts[id];
      if (!ctx?.session || ctx.session.schema_read_only) return;
      const seq = ctx.cognitionSeq = (ctx.cognitionSeq || 0) + 1;
      ctx.cognitionLoading = true; ctx.cognitionError = ''; ctx.cognition = null;
      const current = () => this.contexts[id] === ctx && seq === ctx.cognitionSeq;
      try {
        for (let attempt = 0; attempt < 2; attempt++) {
          const raw = await api.cognition(id);
          if (!current()) return;
          const report = characterCognition(raw,ctx.session);
          if (report) { ctx.cognition = report; return; }
          if (attempt || raw?.session_id !== id || !Number.isSafeInteger(raw.revision) || raw.revision === ctx.session.revision) throw Error('认知索引格式错误');
          const session = await api.get(id);
          if (!current()) return;
          if (session.session_id !== id || session.revision < ctx.session.revision) throw Error('会话修订待核对');
          ctx.session = session;
        }
      } catch { if (current()) { ctx.cognition = null; ctx.cognitionError = '暂时无法核对当前认知，请刷新。'; } }
      finally { if (current()) ctx.cognitionLoading = false; }
    },
    setCognitionOpen(id, open) {
      const ctx = this.context(id); ctx.cognitionOpen = open;
      if (open) void this.refreshCognition(id);
    },
    async refreshList() {
      const generation = ++listGeneration; this.loading = true;
      const rows = new Map(), cursors = new Set(); let cursor, complete = false;
      try {
        for (let page = 0; page < 40; page++) {
          const data = await api.list(cursor); if (generation !== listGeneration) return;
          if (!Array.isArray(data.sessions) || data.sessions.length > 50) throw Error('会话列表格式错误');
          for (const row of data.sessions) { if (!row?.session_id) throw Error('会话列表格式错误'); rows.set(row.session_id, row); }
          if (rows.size > 2000) throw Error('会话列表达到加载上限');
          if (!data.next_cursor) { complete = true; break; }
          if (cursors.has(data.next_cursor) || (cursor && data.next_cursor <= cursor)) break;
          cursors.add(data.next_cursor); cursor = data.next_cursor;
        }
        this.sessions = [...rows.values()]; this.listComplete = complete; this.nextCursor = null; this.error = '';
        this.listWarning = complete ? '' : '列表未完整加载；搜索和排序仅覆盖已加载会话。';
        for (const row of this.sessions) this.preferences.ensure(row, false);
        this.preferences.save();
      } catch (e) { if (generation === listGeneration) { this.error = e.message; this.listComplete = false; this.listWarning = '刷新失败，列表可能过期；搜索仅覆盖已加载会话。'; } }
      finally { if (generation === listGeneration) this.loading = false; }
    },
    clearSpoiler() { ++spoilerGeneration; for (const ctx of Object.values(this.contexts)) ctx.spoiler = null; },
    setVisible(value) { this.visible = value; groups.visibility(); if (!value) { this.clearSpoiler(); for (const ctx of Object.values(this.contexts)) ctx.memoryNotice = null; } },
    markPresented(id) {
      const ctx = this.contexts[id];
      if (ctx?.session?.schema_version === 2) return groups.markPresented(id);
      if (this.visible && this.activeId === id && ctx?.session && !ctx.needsReload && !ctx.session.schema_read_only) this.preferences.read(detailReadMarker(ctx.session));
    },
    async open(id) {
      this.clearSpoiler();
      if (this.activeId && this.activeId !== id) groups.detach(this.activeId);
      this.activeId = id; const ctx = this.context(id);
      ctx.memoryReport = null;
      ctx.sourceRecallReport = null; ctx.cognition = null; ctx.cognitionSeq = (ctx.cognitionSeq || 0) + 1;
      ctx.cognitionLoading = false; ctx.cognitionError = '';
      for (const item of Object.values(this.contexts)) item.memoryNotice = null;
      try {
        ctx.session = await api.get(id); ctx.error = ''; ctx.needsReload = false;
        if (ctx.session.schema_version === 2 && !ctx.session.schema_read_only) { await groups.open(id); void this.refreshCapacity(id); return; }
        void this.refreshCapacity(id);
        const failed = ctx.session.last_failed_action;
        if (!ctx.busy && failed && failed.base_revision === ctx.session.revision && typeof failed.retry_input === 'string') {
          ctx.failure = { ...failed, content: failed.retry_input, oocDraft: failed.retry_ooc_note || '', retryable: !['PERSISTENCE_FAILED', 'SESSION_LIMIT'].includes(failed.error_code) };
          if (failed.operation === 'send') restoreInputPair(ctx, failed.retry_input, failed.retry_ooc_note);
          ctx.error = failed.status === 'interrupted' ? '上次生成因程序中断未保存，可明确重试。' : '上次生成未完成，原记录保持不变。';
        }
        if (ctx.session.pending && !ctx.busy) {
          ctx.busy = true; ctx.inflight = { ...ctx.session.pending, lastSeq: 0, content: '', fromReload: true };
          void this.recover(id, ctx.inflight);
        }
      } catch (e) { ctx.error = e.message; }
    },
    async create(payload) {
      if (this.creationBusy) throw Error('正在核对创建结果，请稍候。');
      if (!this.creationPending) this.creationPending = JSON.parse(JSON.stringify({ client_creation_id: uuid(), ...payload }));
      else if (payload && JSON.stringify(payload) !== JSON.stringify(this.creationPending)) throw Error('上次创建结果待确认，请先核对／重试原请求。');
      this.creationBusy = true;
      try {
        const session = await api.create(JSON.parse(JSON.stringify(this.creationPending)));
        this.context(session.session_id).session = session; this.activeId = session.session_id;
        this.creationPending = null; void this.refreshCapacity(session.session_id);
        await this.refreshList(); return session;
      } catch (e) {
        if (['INVALID_REQUEST', 'INPUT_LIMIT', 'ROLE_FIELDS_INVALID', 'SESSION_DELETED', 'IDEMPOTENCY_MISMATCH', 'SCHEMA_READ_ONLY'].includes(e.code)) this.creationPending = null;
        throw e;
      } finally { this.creationBusy = false; }
    },
    async loadEarlier(id) {
      if (this.context(id).session?.schema_version === 2) return groups.loadEarlier(id);
      const ctx = this.context(id); if (ctx.historyLoading || ctx.historyComplete) return;
      ctx.historyLoading = true;
      try {
        const data = await api.turns(id, ctx.session.turns?.[0]?.turn_id);
        const old = data.turns || []; const existing = new Set(ctx.session.turns.map(t => t.turn_id));
        ctx.session.turns = [...old.filter(t => !existing.has(t.turn_id)), ...ctx.session.turns];
        ctx.historyComplete = old.length < 50;
      } catch (e) { ctx.error = e.message; } finally { ctx.historyLoading = false; }
    },
    event(id, flight, name, data) {
      const ctx = this.context(id);
      if (ctx.inflight !== flight || data.session_id !== id || data.action_id !== flight.action_id || data.v !== 1) return false;
      if (flight.request_id && data.request_id !== flight.request_id) return false;
      if (!Number.isInteger(data.seq) || data.seq <= flight.lastSeq || typeof data.request_id !== 'string') return false;
      flight.request_id = data.request_id; flight.lastSeq = data.seq;
      if (name === 'accepted') {
        ctx.contextNotice = Array.isArray(data.context_omissions) && data.context_omissions.some(item => item.field === 'dialogue_examples') ? '本次上下文预算不足，示例整段未发送。' : '';
        ctx.worldReport = characterWorldReport(data.world_context_report);
        ctx.memoryReport = characterMemoryReport(data.memory_context_report);
        ctx.sourceRecallReport = sourceRecallReport(data.source_recall_report);
      }
      if (name === 'reply_delta') {
        if (typeof data.text !== 'string' || ctx.preview.length + data.text.length > 8000) throw new Error('预览超出安全长度，状态待确认');
        ctx.preview += data.text;
      }
      if (name === 'validating') flight.status = 'validating';
      return true;
    },
    async settle(id, flight, result) {
      const ctx = this.context(id); if (ctx.inflight !== flight || flight.settled) return;
      flight.settled = true;
      if (Array.isArray(result.context_omissions)) ctx.contextNotice = result.context_omissions.some(item => item.field === 'dialogue_examples') ? '本次上下文预算不足，示例整段未发送。' : '';
      if ('world_context_report' in result) ctx.worldReport = characterWorldReport(result.world_context_report);
      if ('memory_context_report' in result) ctx.memoryReport = characterMemoryReport(result.memory_context_report);
      if ('source_recall_report' in result) ctx.sourceRecallReport = sourceRecallReport(result.source_recall_report);
      ctx.preview = '';
      // Never construct committed history from preview or supplier output.
      if (result.status === 'committed' || result.status === 'already_committed') {
        if (flight.operation === 'send' && ctx.draft === flight.content && ctx.oocDraft === (flight.oocDraft || '')) { ctx.draft = ''; ctx.oocDraft = ''; }
        if (flight.operation === 'undo') restoreInputPair(ctx, flight.withdrawnInput, flight.withdrawnOoc);
        ctx.failure = null; ctx.error = '';
      } else {
        ctx.error = result.message || (result.status === 'cancelled' ? '已停止，临时内容未保存。' : '生成失败，原记录保持不变。');
        ctx.failure = { ...flight, operation: result.operation || flight.operation,
          content: flight.fromReload && typeof result.retry_input === 'string' ? result.retry_input : flight.content,
          oocDraft: flight.fromReload && typeof result.retry_input === 'string' ? result.retry_ooc_note || '' : flight.oocDraft || '',
          request_id: result.request_id || flight.request_id, retryable: result.retryable !== false, status: result.status };
        if (flight.fromReload && ctx.failure.operation === 'send') restoreInputPair(ctx, ctx.failure.content, ctx.failure.oocDraft);
      }
      try { ctx.session = await api.get(id); ctx.needsReload = false; ctx.spoiler = null; } catch (e) { ctx.needsReload = true; ctx.error = '终态已返回，但载入记录失败：' + e.message; }
      ctx.busy = false; ctx.inflight = null; await this.refreshList();
      void this.refreshCapacity(id);
      ctx.cognition = null;
      if (ctx.cognitionOpen) void this.refreshCognition(id);
      if (result.status === 'committed' && flight.operation === 'send' && !flight.fromReload && !ctx.needsReload && this.visible && this.activeId === id) {
        const notice = memoryNotice(result.memory_notice);
        if (notice && notice.action_id === flight.action_id && notice.committed_revision <= ctx.session.revision && notice.committed_revision > (ctx.session.memory_settings?.notice_ack_revision || 0) && noticeCache.claim(id, notice.action_id)) {
          ctx.memoryNotice = notice;
          // Acknowledgement never retries a paid generation or guesses a revision.
          await this.acknowledgeMemoryNotice(id, notice);
        }
      }
    },
    async recover(id, flight) {
      if (this.context(id).session?.schema_version === 2) return groups.recover(id);
      const ctx = this.context(id); if (flight.recovering) return; flight.recovering = true; ctx.preview = ''; flight.status = 'unknown';
      try {
        for (let i = 0; i < 96; i++) {
          const result = await api.actionStatus(id, flight.action_id);
          if (ctx.inflight !== flight) return;
          if (terminal(result.status)) { await this.settle(id, flight, result); return; }
          flight.request_id = result.request_id || flight.request_id;
          await delay(2000);
        }
        ctx.error = '连接不可达，状态仍待确认。请点击核对状态，不会自动重发。';
      } catch (e) {
        if (e.code === 'ACTION_NOT_FOUND') {
          ctx.error = '服务器确认该动作不存在，草稿保留，可重新发送。'; ctx.busy = false; ctx.inflight = null;
        } else ctx.error = '状态待确认：' + e.message;
      } finally { flight.recovering = false; }
    },
    async run(id, operation = 'send', retry = false) {
      if (this.context(id).session?.schema_version === 2) return groups.run(id,operation,retry);
      const ctx = this.context(id); if (ctx.busy || ctx.settingsBusy || !ctx.session || ctx.needsReload || ctx.session.schema_read_only) return;
      this.preferences.ensure(detailReadMarker(ctx.session));
      const content = ctx.draft.trim(); if (operation === 'send' && !retry && !content) return;
      if (operation === 'send' && !retry && oocError(ctx.oocDraft)) { ctx.error = oocError(ctx.oocDraft); return; }
      const failed = ctx.failure;
      const lastTurn = ctx.session.turns?.at(-1), last = lastTurn?.user_message;
      const flight = { action_id: retry ? failed.action_id : uuid(), request_id: '', lastSeq: 0, operation, content: retry ? failed.content : ctx.draft, oocDraft: retry ? failed.oocDraft || '' : ctx.oocDraft, withdrawnInput: typeof last === 'string' ? last : last?.content || '', withdrawnOoc: lastTurn?.ooc_note || '', status: 'accepted' };
      ctx.inflight = flight; const active = ctx.inflight; ctx.busy = true; ctx.preview = ''; ctx.error = '';
      ctx.contextNotice = '';
      ctx.worldReport = null;
      ctx.memoryReport = null;
      ctx.sourceRecallReport = null;
      ctx.memoryNotice = null;
      const payload = { client_action_id: flight.action_id, expected_revision: ctx.session.revision, operation, delivery: operation === 'undo' ? 'non_stream' : ctx.delivery };
      if (operation === 'send') { payload.content = content; if (oocText(flight.oocDraft)) payload.ooc_note = oocText(flight.oocDraft); }
      else payload.target_turn_id = ctx.session.turns.at(-1)?.turn_id;
      try {
        const callback = (name, data) => this.event(id, active, name, data);
        const result = retry
          ? await api.retry(id, failed.action_id, { expected_revision: ctx.session.revision, retry_of: failed.request_id, retry_token: uuid(), delivery: ctx.delivery }, callback)
          : await api.action(id, payload, callback);
        const matches = (!result.session_id || result.session_id === id) && (!result.action_id || result.action_id === active.action_id) && (!active.request_id || !result.request_id || result.request_id === active.request_id);
        if (terminal(result.status) && matches) await this.settle(id, active, result);
        else await this.recover(id, active);
      } catch (e) {
        if (['INVALID_REQUEST', 'REVISION_CONFLICT', 'SESSION_BUSY', 'SCHEMA_READ_ONLY', 'SESSION_DELETED', 'SESSION_NOT_FOUND', 'INPUT_LIMIT', 'IDEMPOTENCY_MISMATCH', 'STALE_RETRY', 'CONTEXT_CONTRACT_UNSUPPORTED'].includes(e.code)) {
          ctx.preview = ''; ctx.error = e.message; ctx.busy = false; ctx.inflight = null;
          try { ctx.session = await api.get(id); } catch { ctx.needsReload = true; }
        } else await this.recover(id, active);
        if (!ctx.busy) void this.refreshCapacity(id);
      }
    },
    async loadSpoiler(id) {
      const token = ++spoilerGeneration, ctx = this.context(id);
      try { const data = await api.ledger(id, 'spoiler'); if (token === spoilerGeneration && this.visible && this.activeId === id) ctx.spoiler = Array.isArray(data) ? data : data.ledger || []; }
      catch (e) { if (token === spoilerGeneration && this.visible && this.activeId === id) throw e; }
    },
    async stop(id) {
      if (this.context(id).session?.schema_version === 2) return groups.stop(id);
      const ctx = this.context(id), flight = ctx.inflight; if (!flight?.request_id) return;
      try { const result = await api.cancel(id, flight.request_id); if (terminal(result.status) || result.status === 'already_committed') await this.settle(id, flight, result); }
      catch (e) { ctx.error = '停止结果待确认：' + e.message; }
    },
    async update(id, changes) {
      const ctx = this.context(id);
      if (ctx.busy || ctx.settingsBusy || ctx.needsReload || ctx.session.schema_read_only) return;
      ctx.settingsBusy = true;
      try { if (ctx.session.schema_version === 2) await groups.beforeMutation(id); ctx.session = await api.update(id, { expected_revision: ctx.session.revision, ...changes }); await this.refreshList(); }
      finally { ctx.settingsBusy = false; if (ctx.capacityOpen || capacityWarning(ctx.capacity)) void this.refreshCapacity(id); if (ctx.cognitionOpen) void this.refreshCognition(id); }
    },
    correctMemory(id, entry) {
      const ctx = this.context(id);
      const draft = correctionDraft(entry, ctx.draft);
      if (draft === null) { ctx.error = '输入框已有未发送内容，请先保存或发送，再创建纠正草稿。'; return; }
      ctx.draft = draft;
      ctx.error = '';
    },
    async memorySources(id, entry) { return memorySourceMessages(await api.memorySources(id, entry), entry); },
    async memoryMutation(id, method, changes, quiet = false) {
      const ctx = this.context(id);
      if ((ctx.busy && !(quiet && method === 'acknowledgeMemoryNotice' && ctx.session?.schema_version === 2)) || ctx.settingsBusy || ctx.needsReload || !ctx.session || ctx.session.schema_read_only) return false;
      ctx.settingsBusy = true;
      if (!quiet) { ctx.memoryReport = null; ctx.sourceRecallReport = null; }
      try {
        if (ctx.session.schema_version === 2) await groups.beforeMutation(id);
        const result = await api[method](id, { expected_revision: ctx.session.revision, ...changes });
        const settings = automaticMemoryState(result.memory_settings);
        if (result.session_id !== id || !Number.isSafeInteger(result.revision) || result.revision < ctx.session.revision || !settings || settings.notice_ack_revision > result.revision) throw Error('记忆设置响应格式错误');
        if (this.contexts[id] === ctx) { ctx.session = { ...ctx.session, revision: result.revision, memory_settings: settings }; if (!quiet) ctx.error = ''; }
        return true;
      } catch (e) {
        if (this.contexts[id] === ctx) {
          if (!quiet) ctx.error = '记忆设置结果需核对：' + e.message;
          try { ctx.session = await api.get(id); ctx.needsReload = false; } catch { ctx.needsReload = true; }
        }
        return false;
      } finally { ctx.settingsBusy = false; if (ctx.capacityOpen || capacityWarning(ctx.capacity)) void this.refreshCapacity(id); if (ctx.cognitionOpen) void this.refreshCognition(id); }
    },
    async enableAutomaticMemory(id) { return this.memoryMutation(id, 'enableAutomaticMemory', { enabled: true }); },
    async acknowledgeMemoryNotice(id, notice) {
      // Only this idempotent acknowledgement can be supplemented after an
      // authoritative reload. A failed selection or generation is never retried.
      for (let attempt = 0; attempt < 2; attempt++) {
        const ctx = this.contexts[id];
        if (!ctx?.session || (ctx.busy && ctx.session.schema_version !== 2) || ctx.settingsBusy || ctx.needsReload || ctx.session.schema_read_only) return false;
        if ((ctx.session.memory_settings?.notice_ack_revision || 0) >= notice.committed_revision) return true;
        if (await this.memoryMutation(id, 'acknowledgeMemoryNotice', { action_id: notice.action_id }, true)) return true;
      }
      return false;
    },
    async selectAutomaticMemory(id, entry, dismissed) { return this.memoryMutation(id, 'selectAutomaticMemory', { entry_id: entry, dismissed }); },
    async releaseAutomaticMemory(id, root) { return this.memoryMutation(id, 'releaseAutomaticMemory', { root_entry_id: root }); },
    closeMemoryNotice(id) { this.context(id).memoryNotice = null; },
    async markMemory(id, entry, important) {
      const ctx = this.context(id);
      if (ctx.busy || ctx.settingsBusy || ctx.needsReload || !ctx.session || ctx.session.schema_read_only) return;
      ctx.settingsBusy = true;
      ctx.memoryReport = null;
      ctx.sourceRecallReport = null; ctx.cognition = null;
      try {
        if (ctx.session.schema_version === 2) await groups.beforeMutation(id);
        const result = await api.markMemory(id, { expected_revision: ctx.session.revision, entry_id: entry, important });
        if (this.contexts[id] === ctx) { ctx.session = result; ctx.memoryReport = null; ctx.error = ''; }
      } catch (e) {
        if (this.contexts[id] === ctx) {
          ctx.error = '标记结果需核对：' + e.message;
          try { ctx.session = await api.get(id); ctx.needsReload = false; } catch { ctx.needsReload = true; }
        }
      } finally { ctx.settingsBusy = false; if (ctx.capacityOpen || capacityWarning(ctx.capacity)) void this.refreshCapacity(id); if (ctx.cognitionOpen) void this.refreshCognition(id); }
    },
    async remove(id) { const ctx = this.context(id); if (ctx.busy || ctx.settingsBusy || ctx.needsReload || ctx.session.schema_read_only) return; await api.remove(id, ctx.session.revision); groups.detach(id); this.preferences.remove(id); this.interaction.remove(id); noticeCache.removeSession(id); delete this.contexts[id]; if (this.activeId === id) this.activeId = ''; await this.refreshList(); },
  });
  groups = createCharacterGroupController(state,api,noticeCache);
  return state;
}
export const characterChatStore = createCharacterChatStore();
