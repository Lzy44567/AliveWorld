const limits = { formal_turns: 512, actions: 2048, attempts: 4096 };
const states = ['normal', 'near', 'at_limit'];
export function characterCapacity(value, sessionId) {
  if (!value || ![1,2].includes(value.version) || value.session_id !== sessionId || !Number.isSafeInteger(value.revision) || value.revision < 0 || !states.includes(value.recording_pressure)) return null;
  const public_counts = {}, operation_capacity = {};
  const groupKey = value.version === 2 ? 'formal_groups' : 'formal_turns';
  const versionLimits = value.version === 2 ? { formal_groups: limits.formal_turns, actions: limits.actions, attempts: limits.attempts } : limits;
  for (const [key, limit] of Object.entries(versionLimits)) {
    const item = value.public_counts?.[key];
    if (!item || !Number.isSafeInteger(item.used) || item.used < 0 || item.used > limit || item.limit !== limit) return null;
    const state = item.used >= limit ? 'at_limit' : item.used * 100 >= limit * 80 ? 'near' : 'normal';
    if (item.state !== state) return null;
    public_counts[key] = { used: item.used, limit, state };
  }
  const allBlocked = public_counts.actions.state === 'at_limit' || public_counts.attempts.state === 'at_limit';
  for (const key of ['send', 'retry', 'regenerate', 'undo']) {
    const state = allBlocked || (key === 'send' && public_counts[groupKey].state === 'at_limit') ? 'blocked' : 'not_known_blocked';
    if (value.operation_capacity?.[key] !== state) return null;
    operation_capacity[key] = state;
  }
  return { session_id: sessionId, revision: value.revision, version: value.version, public_counts, recording_pressure: value.recording_pressure, operation_capacity };
}
export function capacityWarning(value) {
  if (!value) return '';
  const levels = [value.recording_pressure, ...Object.values(value.public_counts).map(item => item.state)];
  return levels.includes('at_limit') ? '部分记录或保存容量已达到上限；请查看容量说明。' : levels.includes('near') ? '接近当前版本的保存上限；请查看容量说明。' : '';
}
