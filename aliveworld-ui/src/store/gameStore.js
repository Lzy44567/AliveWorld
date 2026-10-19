import { reactive } from 'vue';
import { stopGeneration } from '../api/generationApi';

function emptyContext(sessionId = null, saveName = null) {
  return {
    sessionId, saveName, isProcessing: false, chatLog: [],
    dynamicBars: {}, properties: {}, npcs: {}, buffs: {}, aiSuggestions: [],
    lastAction: '', draftInput: '', storyConfig: null, preview: '', pendingAction: '',
    generationId: '', stopping: false, failedAction: '',
    task: { status: 'idle', kind: '', startedAt: '', finishedAt: '', error: '' },
  };
}

const idle = emptyContext();

export const gameStore = reactive({
  contexts: {}, saveSessions: {}, activeSessionId: null, loadingSaves: {}, streamingEnabled: true,
  currentScene: {
    name: '未知界域',
    img: 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=400&auto=format&fit=crop',
  },
  mapNodes: [], companions: [], currentSpeakerSprite: '', isSpeakerActive: false,

  get currentContext() { return this.contexts[this.activeSessionId] || idle; },
  get sessionId() { return this.activeSessionId; },
  set sessionId(value) { this.activeSessionId = value || null; },
  get currentSaveName() { return this.currentContext.saveName; },
  set currentSaveName(value) { this.currentContext.saveName = value || null; },
  get isProcessing() { return this.currentContext.isProcessing; },
  set isProcessing(value) { this.currentContext.isProcessing = Boolean(value); },
  get chatLog() { return this.currentContext.chatLog; },
  set chatLog(value) { this.currentContext.chatLog = Array.isArray(value) ? value : []; },
  get dynamicBars() { return this.currentContext.dynamicBars; },
  set dynamicBars(value) { this.currentContext.dynamicBars = value || {}; },
  get properties() { return this.currentContext.properties; },
  set properties(value) { this.currentContext.properties = value || {}; },
  get npcs() { return this.currentContext.npcs; },
  set npcs(value) { this.currentContext.npcs = value || {}; },
  get buffs() { return this.currentContext.buffs; },
  set buffs(value) { this.currentContext.buffs = value || {}; },
  get aiSuggestions() { return this.currentContext.aiSuggestions; },
  set aiSuggestions(value) { this.currentContext.aiSuggestions = value || []; },
  get lastAction() { return this.currentContext.lastAction; },
  set lastAction(value) { this.currentContext.lastAction = value || ''; },
  get draftInput() { return this.currentContext.draftInput; },
  set draftInput(value) { this.currentContext.draftInput = value || ''; },
  get runningCount() { return Object.values(this.contexts).filter(item => item.isProcessing).length; },

  formatContent(content) {
    if (!content) return '';
    if (Array.isArray(content)) return content;
    if (typeof content !== 'string') return JSON.stringify(content);
    return content.replace(/\\n/g, '\n');
  },

  registerSession(data, saveName, { activate = true } = {}) {
    const sessionId = data.session_id;
    if (!sessionId) throw new Error('后端未返回故事会话 ID');
    const previousId = this.saveSessions[saveName];
    const previous = this.contexts[previousId];
    const context = previous && previousId === sessionId ? previous : emptyContext(sessionId, saveName);
    context.sessionId = sessionId;
    context.saveName = saveName;
    context.chatLog = data.chat_messages || context.chatLog;
    context.aiSuggestions = this.normalizeSuggestions(data.action_suggestions);
    context.storyConfig = data;
    this.contexts[sessionId] = context;
    this.saveSessions[saveName] = sessionId;
    if (activate) this.activeSessionId = sessionId;
    this.syncState(data.state, sessionId);
    return context;
  },

  activateSave(saveName) {
    const sessionId = this.saveSessions[saveName];
    if (!sessionId || !this.contexts[sessionId]) return null;
    this.activeSessionId = sessionId;
    return this.contexts[sessionId];
  },

  contextFor(sessionId) { return this.contexts[sessionId] || null; },
  taskForSave(saveName) {
    if (this.loadingSaves[saveName]) return { status: 'loading', kind: 'load' };
    return this.contexts[this.saveSessions[saveName]]?.task || { status: 'idle' };
  },

  beginTask(sessionId, kind) {
    const context = this.contextFor(sessionId);
    if (!context || context.isProcessing) return null;
    context.isProcessing = true;
    context.preview = '';
    context.task = { status: 'running', kind, startedAt: new Date().toISOString(), finishedAt: '', error: '' };
    context.generationId = ['turn', 'retry', 'reroll'].includes(kind) ? crypto.randomUUID() : '';
    context.stopping = false;
    context.failedAction = '';
    return context;
  },

  async stopTask(sessionId = this.sessionId) {
    const context = this.contextFor(sessionId);
    if (!context?.generationId || context.stopping) return;
    context.stopping = true;
    try {
      const result = await stopGeneration('story', sessionId, context.generationId);
      if (result.status !== 'cancelling') {
        throw new Error(result.status === 'committing' ? '结果正在保存，不能再停止' : '请求尚未确认运行或已经结束，请稍后核对');
      }
    } catch (error) {
      context.stopping = false;
      throw error;
    }
  },

  finishTask(sessionId, update) {
    const context = this.contextFor(sessionId);
    if (!context) return;
    if (typeof update === 'function') update(context);
    context.preview = '';
    context.isProcessing = false;
    context.task = { ...context.task, status: 'completed', finishedAt: new Date().toISOString(), error: '' };
    context.generationId = '';
    context.stopping = false;
  },

  failTask(sessionId, error) {
    const context = this.contextFor(sessionId);
    if (!context) return;
    context.preview = '';
    context.isProcessing = false;
    context.task = { ...context.task, status: 'failed', finishedAt: new Date().toISOString(), error: String(error?.message || error || '操作失败') };
    context.generationId = '';
    context.stopping = false;
  },

  normalizeSuggestions(items) {
    return Array.isArray(items) ? items.filter(item => typeof item === 'string' && item.trim()).slice(0, 4) : [];
  },
  setActionSuggestions(items, sessionId = this.sessionId) {
    const context = this.contextFor(sessionId);
    if (context) context.aiSuggestions = this.normalizeSuggestions(items);
  },
  syncState(newState, sessionId = this.sessionId) {
    const context = this.contextFor(sessionId);
    if (!newState || !context) return;
    if (newState.bars) context.dynamicBars = { ...newState.bars };
    if (newState.properties) context.properties = { ...newState.properties };
    if (newState.npcs) context.npcs = { ...newState.npcs };
    if (newState.buffs) context.buffs = { ...newState.buffs };
  },
  renameSave(oldName, newName) {
    const sessionId = this.saveSessions[oldName];
    if (!sessionId) return;
    delete this.saveSessions[oldName];
    this.saveSessions[newName] = sessionId;
    if (this.contexts[sessionId]) this.contexts[sessionId].saveName = newName;
  },
  reset(saveName = this.currentSaveName) {
    const sessionId = saveName ? this.saveSessions[saveName] : this.activeSessionId;
    if (sessionId) delete this.contexts[sessionId];
    if (saveName) delete this.saveSessions[saveName];
    if (this.activeSessionId === sessionId) this.activeSessionId = null;
    this.companions = [];
  },
});
