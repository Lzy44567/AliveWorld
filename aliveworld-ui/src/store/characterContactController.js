// Current-session authorization and edit activity only; delivery is server-owned.
export function createCharacterContactController(state, api, groups, now = () => Date.now()) {
  const clientId = globalThis.crypto.randomUUID(), edits = new Map();
  const supported = ctx => ctx?.session?.schema_version === 2 && !ctx.session.schema_read_only;
  async function refresh(id) {
    const ctx = state.contexts[id];
    if (!supported(ctx) || !api.proactive) return;
    const seq = ctx.contactSeq = (ctx.contactSeq || 0) + 1;
    ctx.contactLoading = true;
    try {
      const result = await api.proactive(id);
      if (state.contexts[id] === ctx && seq === ctx.contactSeq) { ctx.contact = result; ctx.contactError = ''; }
    } catch (e) { if (seq === ctx.contactSeq) ctx.contactError = e.message; }
    finally { if (seq === ctx.contactSeq) ctx.contactLoading = false; }
  }
  async function update(id, settings) {
    const ctx = state.contexts[id];
    if (!supported(ctx) || ctx.settingsBusy || ctx.commandPending || ctx.needsReload) return;
    ctx.settingsBusy = true; ctx.contactError = '';
    ctx.contactSeq = (ctx.contactSeq || 0) + 1;
    try {
      await groups.beforeMutation(id);
      ctx.contact = await api.updateProactive(id, { expected_revision: ctx.session.revision, settings });
      await groups.refresh(id);
    } catch (e) {
      ctx.contactError = '主动联系设置需核对：' + e.message;
      await groups.refresh(id); await refresh(id);
      ctx.contactError = '主动联系设置未确认，请核对当前状态：' + e.message;
    } finally { ctx.settingsBusy = false; }
  }
  function activity(id) {
    const ctx = state.contexts[id];
    if (!supported(ctx) || !state.visible || state.activeId !== id || !ctx.contact?.settings?.enabled || ctx.contact.settings.paused) return;
    const time = now();
    if (edits.has(id) && time - edits.get(id) < 5000) return;
    edits.set(id, time);
    // No timer or draft watcher: switching/focus/static drafts never renew a lease.
    void api.contactActivity(id, clientId).catch(e => { ctx.contactError = '编辑活动未确认：' + e.message; });
  }
  async function quota(id, changes) {
    const ctx = state.contexts[id]; if (!ctx || ctx.contactQuotaBusy) return;
    ctx.contactQuotaBusy = true; ctx.contactError = '';
    try { await api.updateContactQuota(changes); await refresh(id); }
    catch (e) { ctx.contactError = '每日限额设置未确认：' + e.message; }
    finally { ctx.contactQuotaBusy = false; }
  }
  async function batch(ids, enabled) {
    if (state.contactBatchBusy || !ids.length) return;
    state.contactBatchBusy = true; state.contactBatchError = ''; state.contactBatchResults = [];
    try {
      if (supported(state.current)) await groups.beforeMutation(state.activeId);
      await state.refreshList();
      const targets = ids.map(id => {
        const item = state.sessions.find(s => s.session_id === id);
        return { session_id: id, expected_revision: item?.revision ?? 0 };
      });
      const result = await api.updateContactBatch({ targets, enabled });
      state.contactBatchResults = result.results;
      await state.refreshList();
      if (supported(state.current)) await groups.refresh(state.activeId);
    } catch (e) { state.contactBatchError = '批量结果需核对，请刷新列表后查看：' + e.message; }
    finally { state.contactBatchBusy = false; }
  }
  return { refresh, update, activity, quota, batch };
}
