import { reactive } from 'vue';
import { characterChatApi } from '../api/characterChatApi.js';
import { createConversationPreferences, detailReadMarker } from '../utils/characterConversationList.js';
import { createCharacterInteractionPreferences } from '../utils/characterInteraction.js';

const uuid = () => globalThis.crypto.randomUUID();
const terminal = status => ['committed', 'cancelled', 'failed', 'interrupted'].includes(status);
export function createCharacterChatStore(api = characterChatApi, delay = ms => new Promise(resolve => setTimeout(resolve, ms)), storage) {
  let listGeneration = 0, spoilerGeneration = 0;
  const state = reactive({
    sessions: [], contexts: {}, activeId: '', error: '', loading: false, nextCursor: null,
    listComplete: false, listWarning: '', visible: false, preferences: createConversationPreferences(storage), interaction: createCharacterInteractionPreferences(storage),
    get current() { return this.contexts[this.activeId] || null; },
    context(id) {
      if (!this.contexts[id]) this.contexts[id] = { session: null, draft: '', busy: false, settingsBusy: false, preview: '', inflight: null, failure: null, error: '', ...this.interaction.get(id), historyLoading: false, historyComplete: false, needsReload: false, spoiler: null };
      return this.contexts[id];
    },
    setInteraction(id, changes) {
      const ctx = this.context(id);
      if (ctx.busy || !this.interaction.set(id, changes)) return;
      Object.assign(ctx, this.interaction.get(id));
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
    setVisible(value) { this.visible = value; if (!value) this.clearSpoiler(); },
    markPresented(id) {
      const ctx = this.contexts[id];
      if (this.visible && this.activeId === id && ctx?.session && !ctx.needsReload && !ctx.session.schema_read_only) this.preferences.read(detailReadMarker(ctx.session));
    },
    async open(id) {
      this.clearSpoiler();
      this.activeId = id; const ctx = this.context(id);
      try {
        ctx.session = await api.get(id); ctx.error = ''; ctx.needsReload = false;
        const failed = ctx.session.last_failed_action;
        if (!ctx.busy && failed && failed.base_revision === ctx.session.revision && typeof failed.retry_input === 'string') {
          ctx.failure = { ...failed, content: failed.retry_input, retryable: !['PERSISTENCE_FAILED', 'SESSION_LIMIT'].includes(failed.error_code) };
          if (!ctx.draft && failed.operation === 'send') ctx.draft = failed.retry_input;
          ctx.error = failed.status === 'interrupted' ? '上次生成因程序中断未保存，可明确重试。' : '上次生成未完成，原记录保持不变。';
        }
        if (ctx.session.pending && !ctx.busy) {
          ctx.busy = true; ctx.inflight = { ...ctx.session.pending, lastSeq: 0, content: '' };
          void this.recover(id, ctx.inflight);
        }
      } catch (e) { ctx.error = e.message; }
    },
    async create(payload) {
      const session = await api.create({ client_creation_id: uuid(), ...payload });
      this.context(session.session_id).session = session; this.activeId = session.session_id;
      await this.refreshList(); return session;
    },
    async loadEarlier(id) {
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
      ctx.preview = '';
      // Never construct committed history from preview or supplier output.
      if (result.status === 'committed' || result.status === 'already_committed') {
        if (flight.operation === 'send' && ctx.draft === flight.content) ctx.draft = '';
        if (flight.operation === 'undo' && !ctx.draft) ctx.draft = flight.withdrawnInput || '';
        ctx.failure = null; ctx.error = '';
      } else {
        ctx.error = result.message || (result.status === 'cancelled' ? '已停止，临时内容未保存。' : '生成失败，原记录保持不变。');
        ctx.failure = { ...flight, request_id: result.request_id || flight.request_id, retryable: result.retryable !== false, status: result.status };
      }
      try { ctx.session = await api.get(id); ctx.needsReload = false; ctx.spoiler = null; } catch (e) { ctx.needsReload = true; ctx.error = '终态已返回，但载入记录失败：' + e.message; }
      ctx.busy = false; ctx.inflight = null; await this.refreshList();
    },
    async recover(id, flight) {
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
      const ctx = this.context(id); if (ctx.busy || ctx.settingsBusy || !ctx.session || ctx.needsReload || ctx.session.schema_read_only) return;
      this.preferences.ensure(detailReadMarker(ctx.session));
      const content = ctx.draft.trim(); if (operation === 'send' && !retry && !content) return;
      const failed = ctx.failure;
      const last = ctx.session.turns?.at(-1)?.user_message;
      const flight = { action_id: retry ? failed.action_id : uuid(), request_id: '', lastSeq: 0, operation, content: retry ? failed.content : ctx.draft, withdrawnInput: typeof last === 'string' ? last : last?.content || '', status: 'accepted' };
      ctx.inflight = flight; const active = ctx.inflight; ctx.busy = true; ctx.preview = ''; ctx.error = '';
      const payload = { client_action_id: flight.action_id, expected_revision: ctx.session.revision, operation, delivery: operation === 'undo' ? 'non_stream' : ctx.delivery };
      if (operation === 'send') payload.content = content;
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
        if (['INVALID_REQUEST', 'REVISION_CONFLICT', 'SESSION_BUSY', 'SCHEMA_READ_ONLY', 'SESSION_DELETED', 'SESSION_NOT_FOUND', 'INPUT_LIMIT', 'IDEMPOTENCY_MISMATCH', 'STALE_RETRY'].includes(e.code)) {
          ctx.preview = ''; ctx.error = e.message; ctx.busy = false; ctx.inflight = null;
          try { ctx.session = await api.get(id); } catch { ctx.needsReload = true; }
        } else await this.recover(id, active);
      }
    },
    async loadSpoiler(id) {
      const token = ++spoilerGeneration, ctx = this.context(id);
      try { const data = await api.ledger(id, 'spoiler'); if (token === spoilerGeneration && this.visible && this.activeId === id) ctx.spoiler = Array.isArray(data) ? data : data.ledger || []; }
      catch (e) { if (token === spoilerGeneration && this.visible && this.activeId === id) throw e; }
    },
    async stop(id) {
      const ctx = this.context(id), flight = ctx.inflight; if (!flight?.request_id) return;
      try { const result = await api.cancel(id, flight.request_id); if (terminal(result.status) || result.status === 'already_committed') await this.settle(id, flight, result); }
      catch (e) { ctx.error = '停止结果待确认：' + e.message; }
    },
    async update(id, changes) {
      const ctx = this.context(id);
      if (ctx.busy || ctx.settingsBusy || ctx.needsReload || ctx.session.schema_read_only) return;
      ctx.settingsBusy = true;
      try { ctx.session = await api.update(id, { expected_revision: ctx.session.revision, ...changes }); await this.refreshList(); }
      finally { ctx.settingsBusy = false; }
    },
    async remove(id) { const ctx = this.context(id); if (ctx.busy || ctx.settingsBusy || ctx.needsReload || ctx.session.schema_read_only) return; await api.remove(id, ctx.session.revision); this.preferences.remove(id); this.interaction.remove(id); delete this.contexts[id]; if (this.activeId === id) this.activeId = ''; await this.refreshList(); },
  });
  return state;
}
export const characterChatStore = createCharacterChatStore();
