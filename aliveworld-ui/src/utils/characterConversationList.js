const KEY = 'aw_character_conversations_v1';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const integer = n => Number.isSafeInteger(n) && n >= 0;
const MAX_ITEMS = 2000, MAX_BYTES = 262144;
export function createConversationPreferences(storage) {
  let entries = {}, writable = true, warning = '';
  try {
    if (storage === undefined) storage = globalThis.localStorage;
    const raw = storage?.getItem(KEY);
    if (raw) {
      if (new TextEncoder().encode(raw).length > MAX_BYTES) throw Error();
      const parsed = JSON.parse(raw);
      if (parsed.version !== 1) { writable = false; throw Error(); }
      if (!parsed.entries || typeof parsed.entries !== 'object' || Array.isArray(parsed.entries) || Object.keys(parsed.entries).length > MAX_ITEMS) throw Error();
      for (const [id, p] of Object.entries(parsed.entries)) {
        if (!UUID.test(id) || !p || typeof p.pinned !== 'boolean' || !integer(p.readRevision) || !integer(p.touched) || !(p.readId === null || UUID.test(p.readId))) throw Error();
        entries[id] = { pinned: p.pinned, readRevision: p.readRevision, readId: p.readId, touched: p.touched };
      }
    }
  } catch { entries = {}; writable = false; warning = '会话偏好无法读取，聊天仍可使用。'; }
  return {
    entries, warning, writable,
    save() {
      if (!this.writable) { this.warning = '会话偏好仅保存在本次运行，未覆盖原有数据。'; return; }
      try {
        const data = JSON.stringify({ version: 1, entries: this.entries });
        if (new TextEncoder().encode(data).length > MAX_BYTES || !storage) throw Error();
        storage.setItem(KEY, data);
      } catch { this.warning = '会话偏好未保存；聊天数据不受影响。'; }
    },
    ensure(row, persist = true) {
      const id = row.session_id;
      if (!UUID.test(id)) return null;
      if (!this.entries[id]) {
        if (Object.keys(this.entries).length >= MAX_ITEMS) {
          const oldest = Object.keys(this.entries).filter(k => !this.entries[k].pinned).sort((a, b) => this.entries[a].touched - this.entries[b].touched)[0];
          if (!oldest) { this.warning = '本机会话偏好达到上限，未移除已有置顶。'; return null; }
          delete this.entries[oldest];
        }
        this.entries[id] = { pinned: false, readRevision: integer(row.latest_ai_committed_revision) ? row.latest_ai_committed_revision : 0, readId: UUID.test(row.latest_ai_message_id || '') ? row.latest_ai_message_id : null, touched: Date.now() };
        if (persist) this.save();
      }
      return this.entries[id];
    },
    unread(row) {
      const p = this.entries[row.session_id];
      return Boolean(p && integer(row.latest_ai_committed_revision) && row.latest_ai_committed_revision > p.readRevision && UUID.test(row.latest_ai_message_id || '') && row.latest_ai_message_id !== p.readId);
    },
    read(row) {
      const p = this.ensure(row); if (!p) return;
      p.readRevision = Math.max(p.readRevision, integer(row.latest_ai_committed_revision) ? row.latest_ai_committed_revision : 0);
      p.readId = UUID.test(row.latest_ai_message_id || '') ? row.latest_ai_message_id : p.readId; p.touched = Date.now(); this.save();
    },
    pin(row) { const p = this.ensure(row); if (p) { p.pinned = !p.pinned; p.touched = Date.now(); this.save(); } },
    remove(id) { delete this.entries[id]; this.save(); },
  };
}
export function conversationRows(rows, query, preferences) {
  const needle = String(query || '').trim().slice(0, 80).toLocaleLowerCase();
  return rows.filter(r => [r.title, r.ai_name].join(' ').toLocaleLowerCase().includes(needle)).sort((a, b) => {
    const unavailable = r => Boolean(r.read_error || r.schema_read_only);
    if (unavailable(a) !== unavailable(b)) return unavailable(a) ? 1 : -1;
    const pin = r => Boolean(preferences.entries[r.session_id]?.pinned);
    return Number(pin(b)) - Number(pin(a)) || (Date.parse(b.last_activity_at) || 0) - (Date.parse(a.last_activity_at) || 0) || a.session_id.localeCompare(b.session_id);
  });
}
export function detailReadMarker(session) {
  const last = session?.turns?.at(-1);
  return { session_id: session.session_id, latest_ai_message_id: last?.ai_message?.message_id || null, latest_ai_committed_revision: last?.committed_revision || 0 };
}
