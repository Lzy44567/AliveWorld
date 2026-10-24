import { reactive } from 'vue';
import { stopGeneration } from '../api/generationApi';
import { assetWorkshopApi } from '../api/assetWorkshopApi';
import { preferenceWorkshopApi } from '../api/preferenceWorkshopApi';
import { worldbookWorkshopApi } from '../api/worldbookWorkshopApi';
import { assetStore } from './assetStore';
import { gameStore } from './gameStore';
import { preferenceStore } from './preferenceStore';
import { uiStore } from './uiStore';

export const WORKSHOP_TYPES = [
  { id: 'worldbooks', icon: '🌍', label: '世界书', store: 'worlds' },
  { id: 'characters', icon: '🎭', label: '角色卡', store: 'characters' },
  { id: 'styles', icon: '📜', label: '文风卡', store: 'styles' },
  { id: 'entities', icon: '👾', label: '实体卡', store: 'entities' },
  { id: 'preferences', icon: '🪞', label: '偏好卡', store: '' },
];

const MODE_MAP = {
  worldbooks: [
    { id: 'create', label: '从一句话创建', description: '根据一句核心想法、题材与偏好，协作建立概述、公理和首批条目。' },
    { id: 'expand', label: '拓展新领域', description: '横向补充尚未覆盖的地区、制度、文化、职业或生活细节。' },
    { id: 'evolve', label: '演化已有设定', description: '从已有公理与规则推导逻辑后果，检查关联、缺口和冲突。' },
    { id: 'adapt', label: '参考与融合', description: '选择参考书，比较差异并为当前目标书设计适配方案；参考原书不会改变。' },
  ],
  preferences: [
    { id: 'discover', label: '探索偏好', description: '讨论玩家行为背后的多种可能动机，形成可验证假设。' },
    { id: 'refine', label: '修正表述', description: '修正已有偏好的边界、措辞和替代解释。' },
    { id: 'balance', label: '平衡去重复', description: '合并重复项，避免某类偏好在故事中被机械重复。' },
  ],
  asset: [
    { id: 'create', label: '从核心想法创建', description: '从核心想法建立一份可以继续讨论和修改的初稿。' },
    { id: 'refine', label: '细化与修改', description: '围绕指定字段继续补充细节、关系和表现方式。' },
    { id: 'review', label: '审阅去俗套', description: '检查自相矛盾、模板化表达和缺少辨识度的问题。' },
  ],
};

function newContext(mode = 'expand') {
  return {
    workshopId: '', draft: null, messages: [], history: [], suggestions: [], creativeBrief: '',
    references: [], focusEntryId: '',
    proposed: [], pending: [], dirty: false, published: false, useHistory: true, contextInfo: null,
    busy: false, activity: '', input: '', commitChanges: false, mode, preview: '', pendingMessage: '',
    task: { status: 'idle', kind: '', error: '', startedAt: '', finishedAt: '' },
  };
}

const idle = newContext();

export const workshopStore = reactive({
  type: 'worldbooks', scope: 'global', assetName: '', search: '', initialized: false,
  localSessionId: '', contexts: {}, activeContextKey: '', streamingEnabled: true,

  get context() { return this.contexts[this.activeContextKey] || idle; },
  get workshopId() { return this.context.workshopId; }, set workshopId(value) { this.context.workshopId = value || ''; },
  get draft() { return this.context.draft; }, set draft(value) { this.context.draft = value; },
  get messages() { return this.context.messages; }, set messages(value) { this.context.messages = value || []; },
  get history() { return this.context.history; }, set history(value) { this.context.history = value || []; },
  get suggestions() { return this.context.suggestions; }, set suggestions(value) { this.context.suggestions = value || []; },
  get proposed() { return this.context.proposed; }, set proposed(value) { this.context.proposed = value || []; },
  get pending() { return this.context.pending; }, set pending(value) { this.context.pending = value || []; },
  get dirty() { return this.context.dirty; }, set dirty(value) { this.context.dirty = Boolean(value); },
  get published() { return this.context.published; }, set published(value) { this.context.published = Boolean(value); },
  get busy() { return this.context.busy; }, set busy(value) { this.context.busy = Boolean(value); },
  get activity() { return this.context.activity; }, set activity(value) { this.context.activity = value || ''; },
  get input() { return this.context.input; }, set input(value) { this.context.input = value || ''; },
  get commitChanges() { return this.context.commitChanges; }, set commitChanges(value) { this.context.commitChanges = Boolean(value); },
  get mode() { return this.context.mode; }, set mode(value) { this.context.mode = value || this.modes[0].id; },

  get typeInfo() { return WORKSHOP_TYPES.find(item => item.id === this.type) || WORKSHOP_TYPES[0]; },
  get modes() { return MODE_MAP[this.type] || MODE_MAP.asset; },
  get activeMode() { return this.modes.find(item => item.id === this.mode) || this.modes[0]; },
  get assets() {
    if (this.type === 'preferences') return [];
    const list = assetStore[this.typeInfo.store]?.[this.scope] || [];
    const keyword = this.search.trim().toLowerCase();
    return keyword ? list.filter(item => [item.name, ...(item.tags || [])].join(' ').toLowerCase().includes(keyword)) : list;
  },
  get hasSession() { return Boolean(gameStore.sessionId); },
  get localScopeLabel() { return gameStore.currentSaveName || gameStore.sessionId || '未载入故事'; },
  get runningCount() { return Object.values(this.contexts).filter(item => item.busy).length; },

  identity(type = this.type, scope = this.scope, name = this.assetName, sessionId = gameStore.sessionId || '') {
    return [type, scope, scope === 'local' ? sessionId : 'global', name || (type === 'preferences' ? 'profile' : '')].join('::');
  },
  taskForAsset(type, scope, name, sessionId = gameStore.sessionId || '') {
    return this.contexts[this.identity(type, scope, name, sessionId)]?.task || { status: 'idle' };
  },
  runningForType(type) {
    return Object.entries(this.contexts).filter(([key, value]) => key.startsWith(`${type}::`) && value.busy).length;
  },
  activateContext(name = this.assetName, scope = this.scope, force = false) {
    this.assetName = name;
    this.scope = scope;
    const key = this.identity();
    if (force || !this.contexts[key]) {
      const previous = this.contexts[key];
      this.contexts[key] = newContext(previous?.mode || this.modes[0].id);
      this.contexts[key].useHistory = previous?.useHistory ?? this.type !== 'preferences';
      this.contexts[key].input = previous?.input || '';
      this.contexts[key].commitChanges = previous?.commitChanges || false;
      if (previous) {
        for (const field of ['workshopId', 'draft', 'messages', 'history', 'published', 'creativeBrief']) {
          this.contexts[key][field] = previous[field];
        }
      }
    }
    this.activeContextKey = key;
    return this.contexts[key];
  },
  markTask(context, status, kind = context.task.kind, error = '') {
    context.task = {
      ...context.task, status, kind, error,
      startedAt: status === 'running' ? new Date().toISOString() : context.task.startedAt,
      finishedAt: ['completed', 'failed'].includes(status) ? new Date().toISOString() : '',
    };
  },
  syncInto(context, data) {
    context.workshopId = data.workshop_id || context.workshopId;
    context.draft = data.draft ?? context.draft;
    if (Object.prototype.hasOwnProperty.call(data, 'creative_brief')) context.creativeBrief = data.creative_brief;
    if (Object.prototype.hasOwnProperty.call(data, 'references')) context.references = data.references;
    if (Object.prototype.hasOwnProperty.call(data, 'focus_entry_id')) context.focusEntryId = data.focus_entry_id;
    context.messages = data.messages || context.messages;
    if (Object.prototype.hasOwnProperty.call(data, 'history')) context.history = data.history || [];
    context.suggestions = data.suggested_actions || [];
    context.proposed = data.proposed || [];
    context.pending = data.pending || [];
    context.dirty = Boolean(data.dirty);
    context.published = Boolean(data.published);
    if (data.context_info) context.contextInfo = data.context_info;
  },
  sync(data) { this.syncInto(this.context, data); },

  async initialize() {
    if (!this.initialized) await assetStore.fetchAssets();
    await this.syncStoryScope();
    this.initialized = true;
  },
  async syncStoryScope() {
    const sessionId = gameStore.sessionId || '';
    if (sessionId === this.localSessionId) return;
    this.localSessionId = sessionId;
    if (this.scope === 'local') { this.assetName = ''; this.activeContextKey = ''; }
    await assetStore.fetchLocalAssets(sessionId);
    if (!sessionId && this.scope === 'local') this.scope = 'global';
  },
  async selectType(type) {
    if (this.type === type) return;
    this.type = type; this.search = ''; this.assetName = ''; this.activeContextKey = '';
    if (type === 'preferences') await this.start('', 'global');
  },
  async setScope(scope) {
    if (scope === 'local' && !gameStore.sessionId) return;
    this.scope = scope; this.assetName = ''; this.activeContextKey = '';
    if (scope === 'local') {
      this.localSessionId = gameStore.sessionId;
      await assetStore.fetchLocalAssets(gameStore.sessionId);
    }
  },
  resetSession() { this.activeContextKey = ''; },

  async start(name = '', scope = this.scope, force = false) {
    this.scope = scope; this.assetName = name;
    const key = this.identity();
    const existing = this.contexts[key];
    if (existing?.busy && force) return;
    if (existing && !force) { this.activeContextKey = key; return; }
    const context = this.activateContext(name, scope, force);
    if (context.busy) return;
    context.busy = true; context.activity = 'loading'; this.markTask(context, 'running', 'load');
    const type = this.type;
    const sessionId = scope === 'local' ? gameStore.sessionId : '';
    try {
      let data;
      if (type === 'worldbooks') data = await worldbookWorkshopApi.start(name, sessionId || null);
      else if (type === 'preferences') data = await preferenceWorkshopApi.start(gameStore.sessionId || '');
      else data = await assetWorkshopApi.start(type, name, sessionId);
      this.syncInto(context, data); context.preview = ''; this.markTask(context, 'completed');
      if (data.resumed) uiStore.showToast('已恢复尚未发布的工坊草稿');
      if (data.rebased) uiStore.showToast('草稿已安全合并到最新正式偏好卡');
    } catch (error) {
      this.markTask(context, 'failed', 'load', error.message); uiStore.showToast(error.message, 'error');
    } finally { context.busy = false; context.activity = ''; }
  },
  async startNewRound() { await this.start(this.assetName, this.scope, true); },

  async send(text = this.input) {
    const message = String(text || '').trim();
    let context = this.context;
    if (!message || context.busy || !context.workshopId) return;
    const continuing = context.published;
    if (continuing) {
      const key = this.activeContextKey;
      context.input = '';
      await this.startNewRound();
      context = this.contexts[key];
      if (!context.workshopId || context.published || context.task.status === 'failed') {
        context.input ||= message;
        return;
      }
      // Selection may change during the request that opens the new draft.
      if (this.activeContextKey !== key) { context.input ||= message; return; }
    }
    if (!continuing) context.input = '';
    context.pendingMessage = message;
    context.failedMessage = '';
    context.generationId = crypto.randomUUID();
    context.stopping = false;
    context.preview = '';
    context.busy = true; context.activity = 'chat'; this.markTask(context, 'running', 'chat');
    const type = this.type, mode = context.mode, commitChanges = context.commitChanges, workshopId = context.workshopId;
    try {
      let data;
      const api = type === 'worldbooks' ? worldbookWorkshopApi : type === 'preferences' ? preferenceWorkshopApi : assetWorkshopApi;
      data = this.streamingEnabled
        ? await api.chatStream(workshopId, message, mode, commitChanges, text => { context.preview += text; }, context.generationId, context.useHistory)
        : await api.chat(workshopId, message, mode, commitChanges, context.generationId, context.useHistory);
      this.syncInto(context, data); this.markTask(context, 'completed');
    } catch (error) {
      context.input = context.input || message;
      context.failedMessage = message;
      if (context.stopping || /content_filter|服务商过滤/.test(error.message)) context.preview = '';
      this.markTask(context, 'failed', 'chat', error.message); uiStore.showToast(error.message, 'error');
    } finally { context.pendingMessage = ''; context.busy = false; context.activity = ''; context.generationId = ''; context.stopping = false; }
  },

  async stop() {
    const context = this.context;
    if (!context.generationId || context.stopping) return;
    context.stopping = true;
    try {
      const result = await stopGeneration('workshop', context.workshopId, context.generationId);
      if (result.status !== 'cancelling') {
        context.stopping = false;
        uiStore.showToast(result.status === 'committing' ? '结果已开始保存，不能再停止' : '任务尚未确认或已经结束，请稍后核对');
      }
    } catch (error) { context.stopping = false; uiStore.showToast(error.message, 'error'); }
  },

  editFailedMessage() {
    const context = this.context;
    if (context.input && context.input !== context.failedMessage) {
      uiStore.showToast('输入框中已有新草稿，请先保存或清空，再编辑这条请求');
      return;
    }
    context.input = context.failedMessage || '';
  },

  async applyOperations(operations, confirmHighRisk = false) {
    const context = this.context;
    if (!context.workshopId || context.busy) return false;
    context.busy = true; this.markTask(context, 'running', 'apply');
    const type = this.type, workshopId = context.workshopId;
    try {
      let data;
      if (type === 'worldbooks') data = await worldbookWorkshopApi.operations(workshopId, operations, confirmHighRisk);
      else if (type === 'preferences') data = await preferenceWorkshopApi.operations(workshopId, operations, confirmHighRisk);
      else data = await assetWorkshopApi.operations(workshopId, operations);
      this.syncInto(context, data); this.markTask(context, 'completed'); return true;
    } catch (error) {
      this.markTask(context, 'failed', 'apply', error.message); uiStore.showToast(error.message, 'error'); return false;
    } finally { context.busy = false; }
  },
  async submitProposal() { if (this.proposed.length) await this.applyOperations(this.proposed, false); },
  async reviewSelection(source, operationIds, accept) {
    const context = this.context;
    if (!context.workshopId || context.busy) return;
    const api = this.type === 'worldbooks' ? worldbookWorkshopApi : this.type === 'preferences' ? preferenceWorkshopApi : assetWorkshopApi;
    context.busy = true; this.markTask(context, 'running', 'review');
    try {
      this.syncInto(context, await api.review(context.workshopId, source, operationIds, accept));
      this.markTask(context, 'completed');
    } catch (error) {
      this.markTask(context, 'failed', 'review', error.message); uiStore.showToast(error.message, 'error');
    } finally { context.busy = false; }
  },
  async saveCreativeBrief(text) {
    const context = this.context;
    if (!context.workshopId || context.busy) return false;
    const api = this.type === 'worldbooks' ? worldbookWorkshopApi : this.type === 'preferences' ? preferenceWorkshopApi : assetWorkshopApi;
    context.busy = true;
    try {
      this.syncInto(context, await api.saveBrief(context.workshopId, text));
      uiStore.showToast('创作目标已保存'); return true;
    } catch (error) { uiStore.showToast(error.message, 'error'); return false; }
    finally { context.busy = false; }
  },
  async decide(operationId, approve) {
    const context = this.context, type = this.type, workshopId = context.workshopId;
    if (!workshopId || context.busy) return;
    context.busy = true; this.markTask(context, 'running', 'review');
    try {
      const api = type === 'worldbooks' ? worldbookWorkshopApi : preferenceWorkshopApi;
      const data = approve ? await api.approve(workshopId, operationId) : await api.reject(workshopId, operationId);
      this.syncInto(context, data); this.markTask(context, 'completed');
    } catch (error) { this.markTask(context, 'failed', 'review', error.message); uiStore.showToast(error.message, 'error'); }
    finally { context.busy = false; }
  },
  async undo() {
    const context = this.context, type = this.type, workshopId = context.workshopId;
    if (!workshopId || context.busy) return;
    context.busy = true; this.markTask(context, 'running', 'undo');
    try {
      const api = type === 'worldbooks' ? worldbookWorkshopApi : type === 'preferences' ? preferenceWorkshopApi : assetWorkshopApi;
      this.syncInto(context, await api.undo(workshopId)); this.markTask(context, 'completed');
    } catch (error) { this.markTask(context, 'failed', 'undo', error.message); uiStore.showToast(error.message, 'error'); }
    finally { context.busy = false; }
  },
  async publish() {
    const context = this.context, type = this.type, workshopId = context.workshopId, assetName = this.assetName;
    if (!workshopId || context.pending.length || context.busy) {
      if (context.pending.length) uiStore.showToast('请先处理待确认修改', 'error');
      return;
    }
    context.busy = true; this.markTask(context, 'running', 'publish');
    try {
      let data;
      if (type === 'worldbooks') data = await worldbookWorkshopApi.publish(workshopId, assetName || null);
      else if (type === 'preferences') data = await preferenceWorkshopApi.publish(workshopId);
      else data = await assetWorkshopApi.publish(workshopId);
      this.syncInto(context, data); this.markTask(context, 'completed');
      await assetStore.fetchAssets();
      if (type === 'preferences') await preferenceStore.refresh();
      if (gameStore.sessionId) await assetStore.fetchLocalAssets(gameStore.sessionId);
      uiStore.showToast('工坊草稿已发布');
    } catch (error) { this.markTask(context, 'failed', 'publish', error.message); uiStore.showToast(error.message, 'error'); }
    finally { context.busy = false; }
  },
  async saveFields(changes) {
    if (this.type === 'worldbooks') {
      const operations = [];
      if ('overview' in changes) operations.push({ op: 'update_overview', overview: changes.overview });
      if ('axioms' in changes) operations.push({ op: 'set_axioms', axioms: changes.axioms });
      return this.applyOperations(operations, true);
    }
    if (this.type === 'preferences') return false;
    return this.applyOperations([{ op: 'update_fields', changes, reason: '玩家在工坊左栏直接编辑' }], true);
  },
  async saveReauthoring(change) {
    const context = this.context;
    if (this.type !== 'worldbooks' || !context.workshopId || context.busy || context.published) return false;
    context.busy = true;
    try { this.syncInto(context, await worldbookWorkshopApi.reauthoring(context.workshopId, change)); return true; }
    catch (error) { uiStore.showToast(error.message, 'error'); return false; }
    finally { context.busy = false; }
  },
  async prepareWorldbookEntryPrompt(entry) {
    if (this.type !== 'worldbooks' || !entry) return;
    const key = this.activeContextKey;
    if (!await this.saveReauthoring({ focus_entry_id: entry.id }) || this.activeContextKey !== key) return;
    this.mode = 'evolve';
    if (!this.input.trim()) this.input = `请重写指定条目“${entry.name}”，先讨论取舍并形成待审方案。我的要求是：`;
  },
  async prepareWorldbookAxiomPrompt(axiom, index) {
    if (this.type !== 'worldbooks') return;
    const key = this.activeContextKey;
    if (this.context.focusEntryId && !await this.saveReauthoring({ focus_entry_id: '' })) return;
    if (this.activeContextKey !== key) return;
    this.mode = 'evolve';
    this.input = `请和我讨论并修改第 ${index + 1} 条世界公理“${axiom}”。先说明它与其他公理、概述及条目的关系和修改取舍；未达成一致前不要写入。我的要求是：`;
  },
});
