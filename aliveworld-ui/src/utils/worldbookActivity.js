// Per-browser-session baseline: opening an old story must not replay old alerts.
export function createActivityTracker() {
  const seen = new Map();
  return {
    reset(sessionId) { seen.delete(sessionId); },
    observeIds(sessionId, ids) {
      const previous = seen.get(sessionId);
      const current = new Set(ids);
      seen.set(sessionId, current);
      return previous ? ids.filter(id => !previous.has(id)) : [];
    },
    observe(sessionId, ids) { return this.observeIds(sessionId, ids).length; },
  };
}

export const activityTracker = createActivityTracker();
export const activityStatus = {
  recorded: '已记录', pending: '待审阅', accepted: '已接受', rejected: '已拒绝',
  reverted: '源回合已撤回', detached: '保留人工修改', changed: '候选已更改',
};
export const activityOperation = { add: '新增', update: '修改', retire: '停用', remove: '移除候选' };

export function notificationRows(items, ids, showContent = false) {
  const wanted = new Set(ids);
  return items.filter(item => wanted.has(item.id)).slice(0, 3).map(item => ({
    id: item.id, book: item.book_name,
    summary: `${activityOperation[item.operation] || item.operation} · ${activityStatus[item.status] || item.status}`,
    title: showContent ? (item.name || '').slice(0, 60) : '',
    excerpt: showContent ? (item.after?.content || item.before?.content || '').slice(0, 160) : '',
  }));
}
