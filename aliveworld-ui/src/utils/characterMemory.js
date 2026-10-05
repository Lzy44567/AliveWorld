const id = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);
export function characterMemoryReport(value) {
  if (!value || !Array.isArray(value.entries) || value.entries.length > 128) return null;
  const entries = [];
  for (const e of value.entries) {
    if (!e || !id(e.entry_id) || !['important', 'related', 'recent'].includes(e.reason) || !['sent', 'budget', 'not_selected'].includes(e.state)) return null;
    entries.push({ entry_id: e.entry_id, reason: e.reason, state: e.state });
  }
  return { entries };
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
