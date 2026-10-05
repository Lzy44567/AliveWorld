const id = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);
export function characterMemoryReport(value) {
  if (!value || !Array.isArray(value.entries) || value.entries.length > 128) return null;
  const entries = [];
  for (const e of value.entries) {
    if (!e || !id(e.entry_id) || !['important', 'auto_important', 'auto_highlight', 'related', 'recent'].includes(e.reason) || !['sent', 'budget', 'not_selected'].includes(e.state)) return null;
    entries.push({ entry_id: e.entry_id, reason: e.reason, state: e.state });
  }
  return { entries };
}

export const memoryReasonLabels = Object.freeze({ explicit_preference: '明确喜好', explicit_boundary: '明确边界', commitment: '承诺', relationship_turn: '关系转折', goal_turn: '目标转折', conflict_repair: '冲突修复' });
const uuidList = (value, limit) => Array.isArray(value) && value.length <= limit && value.every(id) && new Set(value).size === value.length;
export function automaticMemoryState(value) {
  if (!value || value.version !== 2 || value.automatic_enabled !== true || !uuidList(value.important_entry_ids, 8) || !uuidList(value.inactive_root_ids, 8) || !uuidList(value.inactive_dismissed_root_ids, 128) || !Number.isSafeInteger(value.notice_ack_revision) || value.notice_ack_revision < 0 || !Array.isArray(value.protected_entries) || value.protected_entries.length > 128 || !Array.isArray(value.automatic_entries) || value.automatic_entries.length > 128) return null;
  const protected_entries = [], automatic_entries = [];
  for (const e of value.protected_entries) {
    if (!e || !id(e.entry_id) || !id(e.root_entry_id)) return null;
    protected_entries.push({ entry_id: e.entry_id, root_entry_id: e.root_entry_id });
  }
  for (const e of value.automatic_entries) {
    if (!e || !id(e.entry_id) || !id(e.root_entry_id) || !Object.hasOwn(memoryReasonLabels, e.reason) || !['important', 'highlight'].includes(e.level) || typeof e.dismissed !== 'boolean') return null;
    const expected = ['explicit_preference', 'explicit_boundary', 'commitment'].includes(e.reason) ? 'important' : 'highlight';
    if (e.level !== expected) return null;
    automatic_entries.push({ entry_id: e.entry_id, root_entry_id: e.root_entry_id, reason: e.reason, level: e.level, dismissed: e.dismissed });
  }
  if (new Set(automatic_entries.map(e => e.entry_id)).size !== automatic_entries.length || new Set(protected_entries.map(e => e.entry_id)).size !== protected_entries.length) return null;
  return { version: 2, automatic_enabled: true, important_entry_ids: [...value.important_entry_ids], protected_entries, inactive_root_ids: [...value.inactive_root_ids], automatic_entries, inactive_dismissed_root_ids: [...value.inactive_dismissed_root_ids], notice_ack_revision: value.notice_ack_revision };
}

export function memoryNotice(value) {
  if (!value || !id(value.action_id) || !Number.isSafeInteger(value.committed_revision) || value.committed_revision < 1 || !uuidList(value.entry_ids, 6) || !value.entry_ids.length) return null;
  return { action_id: value.action_id, committed_revision: value.committed_revision, entry_ids: [...value.entry_ids] };
}
export function correctionDraft(entry, existing = '') {
  // Do not replace or automatically submit the player's unsent text.
  if (existing.trim()) return null;
  return `关于这条记忆「${entry.content}」，我要更正：`;
}
export function memorySourceMessages(value, entry) {
  if (!value || value.entry_id !== entry || !Number.isSafeInteger(value.revision) || !Array.isArray(value.messages) || value.messages.length > 2) throw Error('记忆来源格式错误');
  return value.messages.map(m => {
    if (!m || !id(m.message_id) || !id(m.speaker_instance_id) || typeof m.content !== 'string' || Array.from(m.content).length > 8000) throw Error('记忆来源格式错误');
    return { message_id: m.message_id, speaker_instance_id: m.speaker_instance_id, content: m.content };
  });
}
