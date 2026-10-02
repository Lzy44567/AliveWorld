export function feedbackSnapshot(form) {
  return JSON.parse(JSON.stringify({
    category: form.category, title: form.title, actual: form.actual, expected: form.expected,
    steps: form.steps, trace_id: form.trace_id, selected_log_ids: form.selected_log_ids || [],
  }));
}

export const feedbackFingerprint = form => JSON.stringify(feedbackSnapshot(form));

// The component owns reactive state; this coordinator owns operation lifetime and side effects.
export function createFeedbackOperation({ state, getForm, api, clipboard, openWindow, download }) {
  let disposed = false;
  let revision = 0;
  const invalidate = () => {
    revision += 1;
    const hadResult = state.preview || state.issueUrl || state.message || state.busy;
    state.preview = null; state.issueUrl = ''; state.error = '';
    state.message = hadResult ? '内容已修改，请重新生成。' : '';
  };
  async function run(action) {
    if (disposed || state.busy) return false;
    const snapshot = feedbackSnapshot(getForm());
    const fingerprint = feedbackFingerprint(snapshot);
    const originRevision = revision;
    const current = () => !disposed && revision === originRevision && feedbackFingerprint(getForm()) === fingerprint;
    state.busy = true; state.preview = null; state.issueUrl = ''; state.error = ''; state.message = '';
    let stage = action;
    try {
      const result = action === 'export' ? await api.exportPackage(snapshot) : await api.preview(snapshot);
      if (!current()) {
        if (!disposed) state.message = '内容已修改，请重新生成。';
        return false;
      }
      if (action === 'export') {
        download(result);
        state.message = '诊断包已导出；需手动发送，发送前请检查主动选择的私人日志。';
      } else {
        if (action === 'issue') {
          if (result.blocked_by_secret_scan) {
            state.error = '内容疑似仍含密钥，不能直接打开 Issue。';
            return false;
          }
          const url = new URL('https://github.com/Lzy44567/AliveWorld/issues/new');
          url.searchParams.set('title', snapshot.title || 'AliveWorld 玩家反馈');
          url.searchParams.set('body', result.markdown);
          state.issueUrl = url.toString();
          openWindow(state.issueUrl);
          state.message = '已准备预填 Issue；若未打开，请点击下方链接，仍需你手动提交。';
        } else if (action === 'copy') {
          stage = 'clipboard';
          await clipboard(result.markdown);
          if (!current()) {
            if (!disposed) state.message = '内容已修改，请重新生成。';
            return false;
          }
          state.message = '反馈摘要已复制；需手动粘贴发送给开发者。';
        }
        state.preview = result;
      }
      return true;
    } catch {
      if (!disposed && current()) {
        state.preview = null; state.issueUrl = '';
        state.error = stage === 'clipboard' ? '复制失败，请检查剪贴板权限后重试。'
          : action === 'export' ? '诊断包导出失败，请重试。' : '反馈操作失败，请重试。';
      } else if (!disposed) state.message = '内容已修改，请重新生成。';
      return false;
    } finally { if (!disposed) state.busy = false; }
  }
  return { run, invalidate, dispose() { disposed = true; revision += 1; } };
}
