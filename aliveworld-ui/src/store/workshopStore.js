import { reactive } from 'vue';
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
    {
      id: 'create',
      label: '从一句话创建',
      description: '根据一句核心想法、题材与偏好，协作建立概述、公理和首批条目。',
    },
    {
      id: 'expand',
      label: '拓展新领域',
      description: '横向补充尚未覆盖的地区、制度、文化、职业或生活细节。',
    },
    {
      id: 'evolve',
      label: '演化已有设定',
      description: '从已有公理与规则推导逻辑后果，检查关联、缺口和冲突。',
    },
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

export const workshopStore = reactive({
  type: 'worldbooks',
  scope: 'global',
  assetName: '',
  workshopId: '',
  draft: null,
  messages: [],
  suggestions: [],
  proposed: [],
  pending: [],
  dirty: false,
  published: false,
  busy: false,
  activity: '',
  input: '',
  commitChanges: false,
  mode: 'expand',
  search: '',
  initialized: false,

  get typeInfo() {
    return WORKSHOP_TYPES.find(item => item.id === this.type) || WORKSHOP_TYPES[0];
  },

  get modes() {
    return MODE_MAP[this.type] || MODE_MAP.asset;
  },

  get activeMode() {
    return this.modes.find(item => item.id === this.mode) || this.modes[0];
  },

  get assets() {
    if (this.type === 'preferences') return [];
    const list = assetStore[this.typeInfo.store]?.[this.scope] || [];
    const keyword = this.search.trim().toLowerCase();
    return keyword
      ? list.filter(item => [item.name, ...(item.tags || [])].join(' ').toLowerCase().includes(keyword))
      : list;
  },

  get hasSession() {
    return Boolean(gameStore.sessionId);
  },

  sync(data) {
    this.workshopId = data.workshop_id || this.workshopId;
    this.draft = data.draft ?? this.draft;
    this.messages = data.messages || this.messages;
    this.suggestions = data.suggested_actions || [];
    this.proposed = data.proposed || [];
    this.pending = data.pending || [];
    this.dirty = Boolean(data.dirty);
    this.published = Boolean(data.published);
  },

  async initialize() {
    if (this.initialized) return;
    await assetStore.fetchAssets();
    if (gameStore.sessionId) await assetStore.fetchLocalAssets(gameStore.sessionId);
    this.initialized = true;
  },

  async selectType(type) {
    if (this.busy || this.type === type) return;
    this.type = type;
    this.search = '';
    this.assetName = '';
    this.resetSession();
    this.mode = this.modes[0].id;
    if (type === 'preferences') await this.start('', 'global');
  },

  async setScope(scope) {
    if (scope === 'local' && !gameStore.sessionId) return;
    this.scope = scope;
    this.assetName = '';
    this.resetSession();
    if (scope === 'local') await assetStore.fetchLocalAssets(gameStore.sessionId);
  },

  resetSession() {
    this.workshopId = '';
    this.draft = null;
    this.messages = [];
    this.suggestions = [];
    this.proposed = [];
    this.pending = [];
    this.dirty = false;
    this.published = false;
    this.input = '';
  },

  async start(name = '', scope = this.scope) {
    if (this.busy) return;
    this.scope = scope;
    this.assetName = name;
    this.resetSession();
    this.busy = true;
    this.activity = 'loading';
    try {
      const sessionId = scope === 'local' ? gameStore.sessionId : '';
      let data;
      if (this.type === 'worldbooks') data = await worldbookWorkshopApi.start(name, sessionId || null);
      else if (this.type === 'preferences') data = await preferenceWorkshopApi.start(gameStore.sessionId || '');
      else data = await assetWorkshopApi.start(this.type, name, sessionId);
      this.sync(data);
      if (data.resumed) uiStore.showToast('已恢复尚未发布的工坊草稿');
      if (data.rebased) uiStore.showToast('草稿已安全合并到最新正式偏好卡');
    } catch (error) {
      uiStore.showToast(error.message, 'error');
    } finally {
      this.busy = false;
      this.activity = '';
    }
  },

  async send(text = this.input) {
    const message = String(text || '').trim();
    if (!message || this.busy || !this.workshopId) return;
    this.input = '';
    this.messages = [...this.messages, { role: 'user', content: message, optimistic: true }];
    this.busy = true;
    this.activity = 'chat';
    try {
      let data;
      if (this.type === 'worldbooks') data = await worldbookWorkshopApi.chat(this.workshopId, message, this.mode, this.commitChanges);
      else if (this.type === 'preferences') data = await preferenceWorkshopApi.chat(this.workshopId, message, this.mode, this.commitChanges);
      else data = await assetWorkshopApi.chat(this.workshopId, message, this.mode, this.commitChanges);
      this.sync(data);
    } catch (error) {
      this.messages = this.messages.map(item => item.optimistic ? { ...item, failed: true } : item);
      uiStore.showToast(error.message, 'error');
    } finally {
      this.busy = false;
      this.activity = '';
    }
  },

  async applyOperations(operations, confirmHighRisk = false) {
    if (!this.workshopId || this.busy) return false;
    this.busy = true;
    try {
      let data;
      if (this.type === 'worldbooks') data = await worldbookWorkshopApi.operations(this.workshopId, operations, confirmHighRisk);
      else if (this.type === 'preferences') data = await preferenceWorkshopApi.operations(this.workshopId, operations, confirmHighRisk);
      else data = await assetWorkshopApi.operations(this.workshopId, operations);
      this.sync(data);
      return true;
    } catch (error) {
      uiStore.showToast(error.message, 'error');
      return false;
    } finally {
      this.busy = false;
    }
  },

  async submitProposal() {
    if (this.proposed.length) await this.applyOperations(this.proposed, false);
  },

  async decide(operationId, approve) {
    try {
      let data;
      const api = this.type === 'worldbooks' ? worldbookWorkshopApi : preferenceWorkshopApi;
      data = approve ? await api.approve(this.workshopId, operationId) : await api.reject(this.workshopId, operationId);
      this.sync(data);
    } catch (error) { uiStore.showToast(error.message, 'error'); }
  },

  async undo() {
    if (!this.workshopId) return;
    try {
      const api = this.type === 'worldbooks'
        ? worldbookWorkshopApi : this.type === 'preferences'
          ? preferenceWorkshopApi : assetWorkshopApi;
      this.sync(await api.undo(this.workshopId));
    } catch (error) { uiStore.showToast(error.message, 'error'); }
  },

  async publish() {
    if (!this.workshopId || this.pending.length) {
      if (this.pending.length) uiStore.showToast('请先处理待确认修改', 'error');
      return;
    }
    this.busy = true;
    try {
      let data;
      if (this.type === 'worldbooks') data = await worldbookWorkshopApi.publish(this.workshopId, this.assetName || null);
      else if (this.type === 'preferences') data = await preferenceWorkshopApi.publish(this.workshopId);
      else data = await assetWorkshopApi.publish(this.workshopId);
      this.sync(data);
      await assetStore.fetchAssets();
      if (this.type === 'preferences') await preferenceStore.refresh();
      if (gameStore.sessionId) await assetStore.fetchLocalAssets(gameStore.sessionId);
      uiStore.showToast('工坊草稿已发布');
    } catch (error) { uiStore.showToast(error.message, 'error'); }
    finally { this.busy = false; }
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

  prepareWorldbookEntryPrompt(entry) {
    if (this.type !== 'worldbooks' || !entry) return;
    this.mode = 'evolve';
    this.input = `请和我讨论并修改指定条目“${entry.name}”（entry_id: ${entry.id}）。先说明它与世界概述、公理及其他条目的关系和修改取舍；未达成一致前不要写入。我的要求是：`;
  },

  prepareWorldbookAxiomPrompt(axiom, index) {
    if (this.type !== 'worldbooks') return;
    this.mode = 'evolve';
    this.input = `请和我讨论并修改第 ${index + 1} 条世界公理“${axiom}”。先说明它与其他公理、概述及条目的关系和修改取舍；未达成一致前不要写入。我的要求是：`;
  },
});
