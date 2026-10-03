import test from 'node:test';
import assert from 'node:assert/strict';
import { createConversationPreferences, conversationRows } from '../src/utils/characterConversationList.js';
import { createCharacterChatStore } from '../src/store/characterChatStore.js';
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const row = (n, revision = 0) => ({ session_id: id(n), title: `会话${n}`, ai_name: '合成角色', latest_ai_committed_revision: revision, latest_ai_message_id: revision ? id(10000 + revision) : null });
const storage = raw => ({ raw, getItem() { return this.raw; }, setItem(_, value) { this.raw = value; } });
test('initial history baseline, monotonic read watermark, undo and regenerated identity', () => {
  const disk = storage(); const p = createConversationPreferences(disk);
  p.ensure(row(1, 2)); assert.equal(p.unread(row(1, 2)), false);
  assert.equal(p.unread(row(1, 3)), true); p.read(row(1, 3));
  p.read(row(1, 1)); assert.equal(p.entries[id(1)].readRevision, 3);
  assert.equal(p.unread(row(1, 2)), false); assert.equal(p.unread(row(1, 4)), true);
  p.pin(row(1)); assert.equal(createConversationPreferences(disk).entries[id(1)].pinned, true);
  assert.equal(disk.raw.includes('合成角色'), false); assert.equal(disk.raw.includes('会话'), false);
});
test('unknown version never overwritten and quota failure remains usable', () => {
  const disk = storage('{"version":99,"entries":{}}'), original = disk.raw;
  const p = createConversationPreferences(disk); p.pin(row(1)); assert.equal(disk.raw, original); assert.ok(p.warning);
  const q = createConversationPreferences({ getItem() { return null; }, setItem() { throw Error('quota'); } });
  q.pin(row(1)); assert.equal(q.entries[id(1)].pinned, true); assert.ok(q.warning);
});
test('malformed preferences rejected; all-pinned capacity does not evict pins', () => {
  const p = createConversationPreferences(storage('{"version":1,"entries":{"bad":{"pinned":true}}}'));
  assert.deepEqual(p.entries, {}); assert.ok(p.warning);
  for (let n = 1; n <= 2000; n++) p.entries[id(n)] = { pinned: true, touched: n, readRevision: 0, readId: null };
  assert.equal(p.ensure(row(2001)), null); assert.equal(Object.keys(p.entries).length, 2000);
  p.entries[id(1)].pinned = false; p.ensure(row(2001)); assert.equal(p.entries[id(1)], undefined);
});
test('search by character/title, pinned first, unavailable last, stable id tie', () => {
  const p = createConversationPreferences(storage()); p.pin(row(2));
  const rows = [row(3), row(2), row(1), { ...row(4), schema_read_only: true }];
  assert.deepEqual(conversationRows(rows, '合成', p).map(r => r.session_id), [id(2), id(1), id(3), id(4)]);
  assert.equal(conversationRows(rows, '会话3', p).length, 1);
});
test('census covers second page; failed refresh preserves rows; repeated cursor is explicit incomplete', async () => {
  let fail = false; const api = { list: async cursor => { if (fail) throw Error('offline'); return cursor ? { sessions: [row(51)] } : { sessions: Array.from({ length: 50 }, (_, n) => row(n + 1)), next_cursor: id(50) }; } };
  const s = createCharacterChatStore(api, undefined, storage()); await s.refreshList();
  assert.equal(s.sessions.length, 51); assert.equal(s.listComplete, true);
  assert.equal(conversationRows(s.sessions, '会话51', s.preferences).length, 1);
  fail = true; await s.refreshList(); assert.equal(s.sessions.length, 51); assert.ok(s.listWarning);
  api.list = async () => ({ sessions: [row(1)], next_cursor: id(1) }); await s.refreshList();
  assert.equal(s.listComplete, false); assert.ok(s.listWarning);
});
test('late refresh cannot overwrite newer census and page cap is bounded', async () => {
  let resolve; const wait = new Promise(r => resolve = r); let calls = 0;
  const api = { list: async () => ++calls === 1 ? wait : { sessions: [row(2)] } };
  const s = createCharacterChatStore(api, undefined, storage()); const first = s.refreshList();
  await s.refreshList(); resolve({ sessions: [row(1)] }); await first;
  assert.equal(s.sessions[0].session_id, id(2));
  calls = 0; api.list = async () => ({ sessions: [row(++calls)], next_cursor: id(calls) });
  await s.refreshList(); assert.equal(calls, 40); assert.equal(s.listComplete, false);
});
test('hidden/background conversations do not mark read; late spoiler discarded on close or switch', async () => {
  let resolve; const api = { get: async sid => ({ session_id: sid, turns: [{ committed_revision: 2, ai_message: { message_id: id(10002) } }] }), ledger: async () => new Promise(r => resolve = r) };
  const s = createCharacterChatStore(api, undefined, storage()); s.preferences.ensure(row(1));
  await s.open(id(1)); s.markPresented(id(1)); assert.equal(s.preferences.unread(row(1, 2)), true);
  s.setVisible(true); s.markPresented(id(1)); assert.equal(s.preferences.unread(row(1, 2)), false);
  const load = s.loadSpoiler(id(1)); s.clearSpoiler(); resolve({ ledger: ['secret'] }); await load;
  assert.equal(s.current.spoiler, null);
  const late = s.loadSpoiler(id(1)); await s.open(id(2)); resolve({ ledger: ['secret'] }); await late;
  assert.equal(s.context(id(1)).spoiler, null); s.context(id(2)).spoiler = ['secret']; s.setVisible(false);
  assert.equal(s.current.spoiler, null);
});
