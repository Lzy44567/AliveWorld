import test from 'node:test';
import assert from 'node:assert/strict';
import { createCharacterChatStore } from '../src/store/characterChatStore.js';
import { characterStream, CharacterApiError } from '../src/api/characterChatApi.js';

const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; };
function fixture(overrides = {}) {
  const sessions = { a: { session_id: 'a', revision: 1, turns: [], ledger: [], pending: null }, b: { session_id: 'b', revision: 1, turns: [], ledger: [], pending: null } };
  const api = { list: async () => ({ sessions: Object.values(sessions) }), get: async id => structuredClone(sessions[id]), ...overrides };
  return { sessions, api, store: createCharacterChatStore(api, async () => {}) };
}
test('streams survive session switches; committed reload belongs to initiating session and preserves new drafts', async () => {
  const wait = deferred(); let callback, payload;
  const f = fixture({ action: async (_, p, cb) => { callback = cb; payload = p; await wait.promise; return { status: 'committed' }; } });
  await f.store.open('a'); f.store.current.draft = 'hello'; const task = f.store.run('a');
  callback('accepted', { v: 1, session_id: 'a', action_id: payload.client_action_id, request_id: 'r', seq: 1 });
  callback('reply_delta', { v: 1, session_id: 'a', action_id: payload.client_action_id, request_id: 'r', seq: 2, text: '预览' });
  assert.equal(f.store.current.preview, '预览'); assert.deepEqual(f.store.current.session.turns, []);
  await f.store.open('b'); f.store.current.draft = 'B draft'; f.store.context('a').draft = 'new A draft';
  f.sessions.a.turns = [{ turn_id: 't', ai_message: { content: '正式' } }]; wait.resolve(); await task;
  assert.equal(f.store.activeId, 'b'); assert.equal(f.store.current.draft, 'B draft');
  assert.equal(f.store.context('a').draft, 'new A draft'); assert.equal(f.store.context('a').session.turns[0].ai_message.content, '正式'); assert.equal(f.store.context('a').preview, '');
});
test('request identity and monotonic sequence gate stale and duplicate deltas', async () => {
  const f = fixture(); await f.store.open('a'); const ctx = f.store.current;
  ctx.inflight = { action_id: 'x', request_id: 'r', lastSeq: 0 }; const flight = ctx.inflight;
  const event = { v: 1, session_id: 'a', action_id: 'x', request_id: 'r', seq: 1, text: '好' };
  f.store.event('a', flight, 'reply_delta', event); f.store.event('a', flight, 'reply_delta', event);
  f.store.event('a', flight, 'reply_delta', { ...event, seq: 2, request_id: 'old' });
  f.store.event('a', flight, 'reply_delta', { ...event, seq: 2, session_id: 'b' });
  assert.equal(ctx.preview, '好');
});
test('failed preview removed, draft retained, explicit retry targets original action/request with nonstream choice', async () => {
  let retry;
  const f = fixture({ action: async (_, p, cb) => { cb('accepted', { v: 1, session_id: 'a', action_id: p.client_action_id, request_id: 'r1', seq: 1 }); cb('reply_delta', { v: 1, session_id: 'a', action_id: p.client_action_id, request_id: 'r1', seq: 2, text: 'partial' }); return { status: 'failed', message: 'invalid', retryable: true }; }, retry: async (_, action, p) => { retry = { action, p }; return { status: 'committed' }; } });
  await f.store.open('a'); f.store.current.draft = 'hello'; await f.store.run('a');
  const ctx = f.store.current; assert.equal(ctx.preview, ''); assert.equal(ctx.draft, 'hello'); assert.equal(ctx.session.turns.length, 0);
  const action = ctx.failure.action_id; ctx.delivery = 'non_stream'; await f.store.run('a', 'send', true);
  assert.equal(retry.action, action); assert.equal(retry.p.retry_of, 'r1'); assert.equal(retry.p.delivery, 'non_stream'); assert.equal(ctx.draft, '');
});
test('EOF/network uncertainty only queries status; never automatically calls model twice', async () => {
  let calls = 0, queries = 0;
  const f = fixture({ action: async () => { calls++; throw new CharacterApiError('unknown'); }, actionStatus: async () => { queries++; return { status: 'committed' }; } });
  await f.store.open('a'); f.store.current.draft = 'hello'; await f.store.run('a');
  assert.equal(calls, 1); assert.equal(queries, 1); assert.equal(f.store.current.busy, false);
});
test('interrupted startup attempt becomes retryable, not an endless poll', async () => {
  const f = fixture({ actionStatus: async () => ({ status: 'interrupted', request_id: 'r', retryable: true }) });
  f.sessions.a.pending = { action_id: 'old', request_id: 'r' }; await f.store.open('a');
  await new Promise(r => setTimeout(r, 0)); assert.equal(f.store.current.busy, false); assert.equal(f.store.current.failure.status, 'interrupted');
});
test('reload restores interrupted retry identity/input but ignores failures before later successful revision', async () => {
  const f = fixture(); f.sessions.a.last_failed_action = { action_id: 'a1', request_id: 'r1', status: 'interrupted', base_revision: 1, operation: 'send', retry_input: 'restore draft' };
  await f.store.open('a'); assert.equal(f.store.current.failure.request_id, 'r1'); assert.equal(f.store.current.draft, 'restore draft');
  f.sessions.b.last_failed_action = { ...f.sessions.a.last_failed_action, base_revision: 0 }; await f.store.open('b'); assert.equal(f.store.current.failure, null); assert.equal(f.store.current.draft, '');
});
test('HTTP provider failures recover persisted action and enable explicit retry', async () => {
  const f = fixture({ action: async () => { throw new CharacterApiError('bad provider', 'PROVIDER_FAILED', true); }, actionStatus: async () => ({ status: 'failed', request_id: 'r', retryable: true }) });
  await f.store.open('a'); f.store.current.draft = 'hello'; await f.store.run('a');
  assert.equal(f.store.current.failure.request_id, 'r'); assert.equal(f.store.current.busy, false); assert.equal(f.store.current.draft, 'hello');
});
test('undo restores withdrawn input only into an empty draft', async () => {
  const f = fixture({ action: async () => ({ status: 'committed' }) });
  f.sessions.a.turns = [{ turn_id: 't', user_message: { content: 'withdraw me' } }]; await f.store.open('a');
  await f.store.run('a', 'undo'); assert.equal(f.store.current.draft, 'withdraw me');
  f.store.current.draft = 'new draft'; await f.store.run('a', 'undo'); assert.equal(f.store.current.draft, 'new draft');
});
test('committed reload failure blocks send until authoritative reload', async () => {
  let calls = 0; const f = fixture({ action: async () => { calls++; return { status: 'committed' }; } });
  await f.store.open('a'); f.api.get = async () => { throw new Error('offline'); }; f.store.current.draft = 'hello'; await f.store.run('a');
  assert.equal(f.store.current.needsReload, true); f.store.current.draft = 'next'; await f.store.run('a'); assert.equal(calls, 1);
});
test('stop cancellation is request-specific and leaves official history intact', async () => {
  let requestId; const f = fixture({ cancel: async (_, rid) => { requestId = rid; return { status: 'cancelled' }; } });
  await f.store.open('a'); f.store.current.inflight = { action_id: 'a', request_id: 'r' }; f.store.current.busy = true; f.store.current.preview = 'partial';
  await f.store.stop('a'); assert.equal(requestId, 'r'); assert.equal(f.store.current.preview, ''); assert.equal(f.store.current.session.turns.length, 0);
});
test('SSE decoder preserves UTF8 across every byte and CRLF, ignores heartbeat, returns authoritative terminal', async t => {
  const old = globalThis.fetch; t.after(() => globalThis.fetch = old);
  const frame = (event, data) => `event: ${event}\r\ndata: ${JSON.stringify(data)}\r\n\r\n`;
  const bytes = new TextEncoder().encode(': heartbeat\r\n\r\n' + frame('reply_delta', { text: '中文😀\n' }) + frame('committed', { revision: 2 }));
  let i = 0; globalThis.fetch = async () => new Response(new ReadableStream({ pull(c) { if (i < bytes.length) c.enqueue(bytes.slice(i, ++i)); else c.close(); } }), { headers: { 'Content-Type': 'text/event-stream' } });
  const events = []; const result = await characterStream('/a/actions', {}, (event, data) => events.push([event, data]));
  assert.equal(events[0][1].text, '中文😀\n'); assert.equal(result.status, 'committed'); assert.equal(result.revision, 2);
});
test('SSE EOF is unknown and bounded malformed data does not commit', async t => {
  const old = globalThis.fetch; t.after(() => globalThis.fetch = old);
  globalThis.fetch = async () => new Response('event: reply_delta\ndata: {"text":"partial"}\n\n', { headers: { 'Content-Type': 'text/event-stream' } });
  await assert.rejects(characterStream('/a', {}, () => {}), /状态待确认/);
  globalThis.fetch = async () => new Response('event: committed\ndata: broken\n\n', { headers: { 'Content-Type': 'text/event-stream' } });
  await assert.rejects(characterStream('/a', {}, () => {}), /格式错误/);
});
test('rejected foreign/stale terminal cannot complete stream or clear the originating draft', async t => {
  const old = globalThis.fetch; t.after(() => globalThis.fetch = old);
  const f = fixture(); await f.store.open('a'); const ctx = f.store.current;
  ctx.draft = 'keep'; ctx.inflight = { action_id: 'x', request_id: 'r', lastSeq: 2 }; ctx.busy = true;
  const terminal = { v: 1, session_id: 'b', action_id: 'x', request_id: 'r', seq: 3 };
  globalThis.fetch = async () => new Response(`event: committed\ndata: ${JSON.stringify(terminal)}\n\n`, { headers: { 'Content-Type': 'text/event-stream' } });
  await assert.rejects(characterStream('/a', {}, (name, data) => f.store.event('a', ctx.inflight, name, data)), /状态待确认/);
  assert.equal(ctx.draft, 'keep'); assert.equal(ctx.busy, true);
  assert.equal(f.store.event('a', ctx.inflight, 'committed', { ...terminal, session_id: 'a', seq: 2 }), false);
});
