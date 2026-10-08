// Public schema2 projections only. Candidates and previews are never history.
const uuid = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const count = value => Number.isSafeInteger(value) && value >= 0;
export function groupRows(rows) {
  if (!Array.isArray(rows) || rows.length > 8192) throw Error('消息列表格式错误');
  const ids = new Set(), sequences = new Set();
  return rows.map(row => {
    const m = row?.message;
    if (!m || !uuid(m.message_id) || !uuid(m.speaker_instance_id) || typeof m.content !== 'string' ||
        !count(m.seq) || !m.seq || ids.has(m.message_id) || sequences.has(m.seq) ||
        (row.group_id !== null && !uuid(row.group_id))) throw Error('消息身份格式错误');
    ids.add(m.message_id); sequences.add(m.seq);
    return { message: { ...m }, group_id: row.group_id, ...(typeof row.ooc_note === 'string' ? { ooc_note: row.ooc_note } : {}) };
  }).sort((a,b) => a.message.seq - b.message.seq);
}
export function groupDetail(value, id) {
  if (value?.schema_version !== 2 || value.session_id !== id || !count(value.revision) ||
      !count(value.read_ai_seq) || !count(value.unread_count) || !count(value.queued_count) ||
      !Array.isArray(value.groups) || !Array.isArray(value.participants)) throw Error('会话格式待核对');
  return { ...value, messages: groupRows(value.messages) };
}
export function mergeGroupPage(session, page) {
  if (page.schema_version !== 2 || page.session_id !== session.session_id || page.revision !== session.revision || !Array.isArray(page.groups)) throw Error('历史修订已变化，请刷新会话');
  const rows = new Map(groupRows(page.messages).map(row => [row.message.message_id,row]));
  for (const row of session.messages) rows.set(row.message.message_id,row);
  const groups = new Map(page.groups.map(group => [group.group_id,group]));
  for (const group of session.groups) groups.set(group.group_id,group);
  return { ...session, messages: groupRows([...rows.values()]), groups: [...groups.values()], next_cursor: page.next_cursor };
}
export function presentedAiSeq(session) {
  const ai = session.participants.find(p => p.controller === 'ai')?.instance_id;
  return Math.max(session.read_ai_seq, ...session.messages.filter(row => row.message.speaker_instance_id === ai).map(row => row.message.seq));
}
export function displayRows(ctx) {
  const formal = ctx.session?.messages || [], ids = new Set(formal.map(row => row.message.message_id));
  const previews = Object.values(ctx.previewByRequestOrdinal || {}).flatMap(request => request.bubbles)
    .filter(bubble => bubble && !ids.has(bubble.message_id));
  return [...formal.map(row => ({ ...row, key: row.message.message_id, temporary: false })),
    ...previews.map(bubble => ({ key: bubble.message_id, temporary: true, group_id: bubble.group_id,
      message: { message_id: bubble.message_id, content: bubble.text, speaker_instance_id: bubble.speaker_instance_id }, ended: bubble.ended }))];
}
