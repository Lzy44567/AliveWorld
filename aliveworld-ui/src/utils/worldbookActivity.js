// Per-browser-session baseline: opening an old story must not replay old alerts.
export function createActivityTracker() {
  const seen = new Map();
  return {
    observe(sessionId, ids) {
      const previous = seen.get(sessionId);
      const current = new Set(ids);
      seen.set(sessionId, current);
      return previous ? ids.filter(id => !previous.has(id)).length : 0;
    },
  };
}

export const activityTracker = createActivityTracker();
export const activityStatus = {
  recorded: '已记录', pending: '待审阅', accepted: '已接受', rejected: '已拒绝',
  reverted: '源回合已撤回', detached: '保留人工修改', changed: '候选已更改',
};
export const activityOperation = { add: '新增', update: '修改', retire: '停用', remove: '移除候选' };
