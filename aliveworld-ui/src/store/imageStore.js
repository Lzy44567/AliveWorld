import { reactive } from 'vue';
import { imageApi } from '../api/imageApi';
import { uiStore } from './uiStore';

const ACTIVE = new Set(['queued', 'compiling_prompt', 'ready', 'submitted', 'running']);

export const imageStore = reactive({
  tasks: [],
  sessionId: '',
  pollingHandle: null,
  initialized: false,
  notified: new Set(),

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
  }
});
