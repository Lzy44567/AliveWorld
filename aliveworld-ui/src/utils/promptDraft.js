import { visiblePrompts } from './promptNavigation.js';

export function promptDraftState() {
  return {
    unlocked: false, slices: [], variables: [], coverage: {}, recentRequests: [],
    mode: 'game', selectedId: '', selectedBaseline: '', retainedSelection: null,
    draft: '', activeVariable: null, variableQuery: '', showAllVariables: false,
    busy: false, error: '', notice: '',
  };
}

// Shared by the real editor and deterministic tests; never persists a draft outside this component.
export function createPromptDraft({ state, api, confirmDiscard }) {
  let disposed = false;
  let generation = 0;
  const selected = () => state.slices.find(item => item.id === state.selectedId) || state.retainedSelection;
  const available = () => state.slices.some(item => item.id === state.selectedId);
  const dirty = () => !!state.selectedId && state.draft !== state.selectedBaseline;
  const canEdit = () => !state.busy && state.unlocked && available() && !!selected()?.editable;
  const clearMessages = () => { state.error = ''; state.notice = ''; };
  function failure(reason, fallback) {
    if (disposed) return;
    if (reason?.status === 401 || reason?.status === 403) {
      state.unlocked = false;
      state.error = '认证已失效，请重新解锁；未保存内容仍保留，可复制后再离开。';
    } else state.error = reason?.message || fallback;
  }
  function allowLeave() {
    if (state.busy) { state.error = '操作正在进行，请完成后再离开。'; return false; }
    return !dirty() || confirmDiscard('放弃未保存修改？');
  }
  function assign(item) {
    state.selectedId = item?.id || '';
    state.retainedSelection = item || null;
    state.selectedBaseline = item?.active || '';
    state.draft = item?.active || '';
    state.activeVariable = null;
    clearMessages();
  }
  function select(item) {
    if (disposed || state.busy || item.id === state.selectedId) return false;
    if (!allowLeave()) return false;
    assign(item); return true;
  }
  function changeMode(mode) {
    if (disposed || state.busy || mode === state.mode) return false;
    const visible = visiblePrompts(state.slices, mode);
    if (visible.some(item => item.id === state.selectedId)) { state.mode = mode; return true; }
    if (!allowLeave()) return false;
    state.mode = mode; assign(visible[0]); return true;
  }
  function acceptPrompts(result) {
    const preserve = dirty();
    const prior = selected();
    state.slices = result.slices || [];
    state.variables = result.variables || [];
    state.coverage = result.coverage || {};
    state.recentRequests = result.recentRequests || [];
    state.unlocked = true;
    if (state.selectedId && !available()) {
      state.retainedSelection = prior;
      state.error = '切片已不可用；当前内容仍保留，请复制或明确放弃后选择其他切片。';
      return;
    }
    if (preserve) return;
    assign(state.slices.find(item => item.id === state.selectedId) || visiblePrompts(state.slices, state.mode)[0]);
  }
  async function loadPrompts() {
    const token = generation;
    const result = await api.prompts();
    if (!disposed && token === generation) acceptPrompts(result);
  }
  async function refreshDiagnostics() {
    if (disposed || state.busy || !state.unlocked) return false;
    const token = generation;
    try {
      const result = await api.prompts();
      if (disposed || token !== generation) return false;
      state.coverage = result.coverage || {}; state.recentRequests = result.recentRequests || [];
      return true;
    } catch (reason) { if (token === generation) failure(reason, '刷新失败。'); return false; }
  }
  async function refreshOrigin(originId) {
    try {
      const result = await api.prompts();
      if (disposed) return;
      const updated = result.slices?.find(item => item.id === originId);
      if (updated) {
        state.slices = state.slices.map(item => item.id === originId ? updated : item);
        state.retainedSelection = selected();
      }
    } catch (reason) {
      failure(reason, '操作已完成，但切片信息刷新失败，请稍后重试。');
    }
  }
  function setDraft(value) { if (!canEdit()) return false; state.draft = value; return true; }
  async function save() {
    if (disposed || !canEdit() || !dirty()) return false;
    const originId = state.selectedId;
    const content = state.draft;
    state.busy = true; clearMessages();
    try {
      const result = await api.savePrompt(originId, content);
      if (disposed) return false;
      state.slices = state.slices.map(item => item.id === originId
        ? { ...item, active: content, source: 'override', overrideVersion: result.overrideVersion } : item);
      state.retainedSelection = selected(); state.selectedBaseline = content;
      await refreshOrigin(originId);
      if (disposed) return false;
      state.notice = '已保存为新的本地覆盖版本。'; return true;
    } catch (reason) { failure(reason, '保存失败，未保存内容仍保留。'); return false; }
    finally { if (!disposed) state.busy = false; }
  }
  async function restore() {
    if (disposed || !canEdit() || selected()?.source !== 'override') return false;
    if (!confirmDiscard('恢复官方基线？将放弃未保存修改，当前覆盖不会再参与后续请求。')) return false;
    const originId = state.selectedId;
    const baseline = selected().baseline;
    state.busy = true; clearMessages();
    try {
      await api.restorePrompt(originId);
      if (disposed) return false;
      state.slices = state.slices.map(item => item.id === originId
        ? { ...item, active: baseline, source: 'builtin', overrideVersion: null } : item);
      assign(state.slices.find(item => item.id === originId));
      await refreshOrigin(originId);
      if (disposed) return false;
      state.notice = '已恢复官方基线。'; return true;
    } catch (reason) { failure(reason, '恢复失败，未保存内容仍保留。'); return false; }
    finally { if (!disposed) state.busy = false; }
  }
  async function lock() {
    if (disposed || state.busy || !allowLeave()) return false;
    state.busy = true; clearMessages();
    try {
      await api.lock();
      if (disposed) return false;
      generation += 1;
      Object.assign(state, promptDraftState()); return true;
    } catch (reason) { failure(reason, '锁定失败，未保存内容仍保留。'); return false; }
    finally { if (!disposed) state.busy = false; }
  }
  return { selected, available, dirty, canEdit, allowLeave, select, changeMode, setDraft,
    loadPrompts, refreshDiagnostics, save, restore, lock,
    dispose() { disposed = true; generation += 1; } };
}
