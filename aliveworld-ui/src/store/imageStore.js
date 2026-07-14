import { reactive } from 'vue';
import { imageApi } from '../api/imageApi';
import { uiStore } from './uiStore';
import { assetStore } from './assetStore';

const ACTIVE = new Set(['queued', 'compiling_prompt', 'ready', 'submitted', 'running']);

export const imageStore = reactive({
  tasks: [],
  sessionId: '',
  pollingHandle: null,
  initialized: false,
  notified: new Set(),
  portraitHandled: new Set(),
  libraryWatches: new Map(),
  libraryPollingHandle: null,

  forMessage(messageId) {
    return this.tasks.filter(task => task.source_message_id === messageId);
  },

  async load(sessionId, { notify = false } = {}) {
    if (!sessionId) return;
    const previous = new Map(this.tasks.map(task => [task.id, task.status]));
    const tasks = await imageApi.listTasks(sessionId);
    this.tasks = tasks;
    this.sessionId = sessionId;
    if (notify && this.initialized) {
      for (const task of tasks) {
        if (task.context_snapshot?.portrait_assignment && !this.portraitHandled.has(task.id)) {
          this.portraitHandled.add(task.id);
          if (task.context_snapshot.portrait_assignment.status === 'success' && this.sessionId) {
            assetStore.fetchLocalAssets(this.sessionId).catch(() => {});
          } else if (task.context_snapshot.portrait_assignment.status === 'failed') {
            uiStore.showToast(`图片已生成，但自动设为立绘失败：${task.context_snapshot.portrait_assignment.message || '角色卡不存在'}`, 'error');
          }
        }
        if (task.status === 'succeeded' && previous.get(task.id) !== 'succeeded' && !this.notified.has(task.id)) {
          this.notified.add(task.id);
          uiStore.showToast('图片已生成，可在正文或画廊查看', 'success');
        }
        if (task.status === 'failed' && previous.get(task.id) !== 'failed' && !this.notified.has(task.id)) {
          this.notified.add(task.id);
          uiStore.showToast(`生图失败：${task.error_message || '未知错误'}`, 'error');
        }
      }
    }
    this.initialized = true;
    this.syncPolling();
  },

  async create(sessionId, data) {
    const task = await imageApi.createTask(sessionId, data);
    this.upsert(task);
    this.sessionId = sessionId;
    this.syncPolling();
    return task;
  },

  async compileAndCreate(sessionId, taskData, compileData) {
    const task = await imageApi.compileAndCreateTask(sessionId, taskData, compileData);
    this.upsert(task);
    this.sessionId = sessionId;
    this.syncPolling();
    return task;
  },

  watchLibraryTask(scopeId, task) {
    this.libraryWatches.set(`${scopeId}:${task.id}`, { scopeId, task });
    if (!this.libraryPollingHandle) {
      this.libraryPollingHandle = window.setInterval(() => this.pollLibraryTasks(), 1500);
    }
  },

  async pollLibraryTasks() {
    for (const [key, entry] of [...this.libraryWatches.entries()]) {
      try {
        const task = await imageApi.getLibraryTask(entry.scopeId, entry.task.id);
        entry.task = task;
        this.libraryWatches.set(key, entry);
        if (!ACTIVE.has(task.status)) {
          this.libraryWatches.delete(key);
          if (task.status === 'succeeded') {
            const assignment = task.context_snapshot?.portrait_assignment;
            if (assignment?.status === 'success') {
              assetStore.fetchAssets().catch(() => {});
              uiStore.showToast('全局角色立绘已生成并自动挂载', 'success');
            } else if (assignment?.status === 'failed') {
              uiStore.showToast(`图片已生成，但挂载全局立绘失败：${assignment.message || '角色卡不存在'}`, 'error');
            } else {
              uiStore.showToast('全局图片已生成，可在画廊查看', 'success');
            }
          } else if (task.status === 'failed') {
            uiStore.showToast(`生图失败：${task.error_message || '未知错误'}`, 'error');
          }
        }
      } catch (_) { /* 临时网络错误留待下一轮轮询 */ }
    }
    if (!this.libraryWatches.size && this.libraryPollingHandle) {
      window.clearInterval(this.libraryPollingHandle);
      this.libraryPollingHandle = null;
    }
  },

  async cancel(taskId) {
    const task = await imageApi.cancelTask(this.sessionId, taskId);
    this.upsert(task);
    this.syncPolling();
  },

  async retry(taskId) {
    this.notified.delete(taskId);
    const task = await imageApi.retryTask(this.sessionId, taskId);
    this.upsert(task);
    this.syncPolling();
  },

  async regenerate(taskId) {
    const task = await imageApi.regenerateTask(this.sessionId, taskId);
    this.upsert(task);
    this.syncPolling();
    return task;
  },

  async remove(taskId) {
    await imageApi.deleteTask(this.sessionId, taskId);
    this.tasks = this.tasks.filter(task => task.id !== taskId);
    this.syncPolling();
  },

  upsert(task) {
    const index = this.tasks.findIndex(item => item.id === task.id);
    if (index >= 0) this.tasks[index] = task;
    else this.tasks.unshift(task);
  },

  syncPolling() {
    const needsPolling = this.tasks.some(task => ACTIVE.has(task.status));
    if (needsPolling && !this.pollingHandle && this.sessionId) {
      this.pollingHandle = window.setInterval(() => {
        this.load(this.sessionId, { notify: true }).catch(() => {});
      }, 1500);
    } else if (!needsPolling && this.pollingHandle) {
      window.clearInterval(this.pollingHandle);
      this.pollingHandle = null;
    }
  },

  reset() {
    if (this.pollingHandle) window.clearInterval(this.pollingHandle);
    this.tasks = [];
    this.sessionId = '';
    this.pollingHandle = null;
    this.initialized = false;
    this.notified = new Set();
    this.portraitHandled = new Set();
  }
});
