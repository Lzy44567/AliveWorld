import test from 'node:test';
import assert from 'node:assert/strict';
import { postEventStream } from '../src/api/streaming.js';
import { gameApi } from '../src/api/gameApi.js';
import { worldbookWorkshopApi } from '../src/api/worldbookWorkshopApi.js';
import { preferenceWorkshopApi } from '../src/api/preferenceWorkshopApi.js';
import { assetWorkshopApi } from '../src/api/assetWorkshopApi.js';
import { gameStore } from '../src/store/gameStore.js';

const encoder = new TextEncoder();
const frame = (event, data) => `event: ${event}\r\ndata: ${JSON.stringify(data)}\r\n\r\n`;
function mockStream(t, body, chunkSize = 1) {
  const original = globalThis.fetch;
  const bytes = encoder.encode(body);
  const calls = [];
  let cancelled = false;
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    let offset = 0;
    return new Response(new ReadableStream({
      pull(controller) {
        if (offset >= bytes.length) { controller.close(); return; }
        controller.enqueue(bytes.slice(offset, offset + chunkSize));
        offset += chunkSize;
      },
      cancel() { cancelled = true; },
    }), { headers: { 'Content-Type': 'text/event-stream; charset=utf-8' } });
  };
  t.after(() => { globalThis.fetch = original; });
  return { calls, get cancelled() { return cancelled; } };
}

test('chunk-safe UTF8/CRLF, start/unknown/comment ignored, complete authoritative', async t => {
  const final = { chat_messages: [{ role: 'ai', content: '最终文本' }], state: { bars: { hp: 10 } } };
  const mock = mockStream(t, ': heartbeat\r\n\r\n' + frame('start', { id: 'a' }) + frame('internal', { secret: 'hidden' }) + frame('delta', { text: '中文😀\n' }) + frame('delta', { text: '<script>安全转义</script>' }) + frame('complete', final));
  const deltas = [];
  assert.deepEqual(await postEventStream('/stream', { action: 'hello' }, text => deltas.push(text)), final);
  assert.deepEqual(deltas, ['中文😀\n', '<script>安全转义</script>']);
  assert.equal(mock.calls.length, 1);
  assert.equal(mock.calls[0].options.headers.Accept, 'text/event-stream');
  assert.deepEqual(JSON.parse(mock.calls[0].options.body), { action: 'hello' });
});

test('multiple events and multiline JSON data in one chunk', async t => {
  mockStream(t, 'event: delta\ndata: {\ndata: "text":"a"}\n\nevent: complete\ndata: {"ok":true}\n\n', 4096);
  const deltas = [];
  assert.deepEqual(await postEventStream('/s', {}, text => deltas.push(text)), { ok: true });
  assert.deepEqual(deltas, ['a']);
});

test('EOF without complete is unknown outcome, never automatically resends', async t => {
  const mock = mockStream(t, frame('delta', { text: 'partial' }));
  await assert.rejects(postEventStream('/s', {}), /结果未确认.*重新载入.*不会自动重发/);
  assert.equal(mock.calls.length, 1);
});

test('server error is surfaced without automatic fallback', async t => {
  const mock = mockStream(t, frame('error', { message: '供应商不支持stream', code: 'unsupported' }));
  await assert.rejects(postEventStream('/s', {}), /供应商不支持stream.*关闭流式/);
  assert.equal(mock.calls.length, 1);
});

test('malformed event JSON releases reader and does not retry', async t => {
  const mock = mockStream(t, 'event: delta\ndata: {broken}\n\n' + 'remaining'.repeat(100));
  await assert.rejects(postEventStream('/s', {}), /格式错误/);
  assert.equal(mock.cancelled, true);
  assert.equal(mock.calls.length, 1);
});

test('delta must be text, not a state patch', async t => {
  mockStream(t, frame('delta', { text: { hp: 1 } }));
  await assert.rejects(postEventStream('/s', {}), /正文格式错误/);
});

test('bounded event buffer refuses oversized frame', async t => {
  mockStream(t, 'event: delta\ndata: ' + 'x'.repeat(8 * 1024 * 1024 + 1), 1024 * 1024);
  await assert.rejects(postEventStream('/s', {}), /安全长度/);
});

for (const [name, api, method, args, path] of [
  ['story action', gameApi, 'processActionStream', ['story', { action: 'x' }], '/api/v1/game/story/action/stream'],
  ['story retry', gameApi, 'retryTurnStream', ['story', { action: 'x' }], '/api/v1/game/story/retry/stream'],
  ['story reroll', gameApi, 'rerollTurnStream', ['story', {}], '/api/v1/game/story/reroll/stream'],
  ['worldbook', worldbookWorkshopApi, 'chatStream', ['work', 'x', 'expand', false], '/api/v1/worldbooks/workshops/work/chat/stream'],
  ['preference', preferenceWorkshopApi, 'chatStream', ['work', 'x', 'refine', false], '/api/v1/preferences/workshops/work/chat/stream'],
  ['asset', assetWorkshopApi, 'chatStream', ['work', 'x', 'create', true], '/api/v1/asset-workshops/work/chat/stream'],
]) {
  test(`${name} adapter uses sibling endpoint and callback`, async t => {
    const mock = mockStream(t, frame('delta', { text: 'hello' }) + frame('complete', { saved: true }), 4096);
    const deltas = [];
    assert.deepEqual(await api[method](...args, text => deltas.push(text)), { saved: true });
    assert.deepEqual(deltas, ['hello']);
    assert.equal(mock.calls[0].url, path);
  });
}

test('legacy JSON methods remain available without stream flag', async t => {
  const original = globalThis.fetch;
  const urls = [];
  globalThis.fetch = async url => { urls.push(url); return new Response('{"saved":true}', { headers: { 'Content-Type': 'application/json' } }); };
  t.after(() => { globalThis.fetch = original; });
  await gameApi.processAction('s', {});
  await gameApi.retryTurn('s', {});
  await gameApi.rerollTurn('s', {});
  await worldbookWorkshopApi.chat('w', 'x', 'expand');
  await preferenceWorkshopApi.chat('w', 'x', 'refine');
  await assetWorkshopApi.chat('w', 'x', 'create');
  assert.equal(urls.length, 6);
  assert.ok(urls.every(url => !url.endsWith('/stream')));
});

test('story failure retains uncommitted prose in its initiating context; success clears it', async () => {
  gameStore.registerSession({ session_id: 'a', chat_messages: [{ role: 'ai', content: 'old-a' }], state: { bars: { hp: 1 } }, action_suggestions: ['old suggestion'] }, 'a');
  gameStore.registerSession({ session_id: 'b', chat_messages: [{ role: 'ai', content: 'old-b' }], state: { bars: { hp: 2 } } }, 'b');
  const a = gameStore.beginTask('a', 'reroll');
  a.preview += 'new preview';
  assert.equal(gameStore.currentContext.sessionId, 'b');
  assert.equal(gameStore.currentContext.preview, '');
  assert.equal(a.chatLog[0].content, 'old-a');
  assert.equal(a.dynamicBars.hp, 1);
  assert.deepEqual(a.aiSuggestions, ['old suggestion']);
  gameStore.failTask('a', new Error('failed'));
  assert.equal(a.preview, 'new preview');
  assert.equal(a.chatLog[0].content, 'old-a');
  gameStore.beginTask('a', 'retry');
  a.preview = 'new';
  gameStore.finishTask('a', context => { context.chatLog = [{ role: 'ai', content: 'saved' }]; });
  assert.equal(a.preview, '');
  assert.equal(a.chatLog[0].content, 'saved');
  assert.equal(gameStore.chatLog[0].content, 'old-b');
  gameStore.reset('a'); gameStore.reset('b');
});
