import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createFeedbackOperation, feedbackSnapshot, feedbackFingerprint } from '../src/utils/feedbackOperation.js';

const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
function setup(overrides = {}) {
  const form = { category: 'bug', title: 'A', actual: '正文A', expected: '', steps: '', trace_id: '', selected_log_ids: [] };
  const state = { busy: false, preview: null, message: '', error: '', issueUrl: '' };
  const requests = [], effects = [];
  const api = {
    preview: async payload => { requests.push(payload); return { markdown: `${payload.title}:${payload.actual}:${payload.selected_log_ids.join(',')}` }; },
    exportPackage: async payload => { requests.push(payload); return { blob: {}, filename: payload.title }; },
    ...overrides,
  };
  const operation = createFeedbackOperation({ state, getForm: () => form, api,
    clipboard: async text => effects.push(['copy', text]), openWindow: url => effects.push(['issue', url]), download: value => effects.push(['download', value]) });
  return { form, state, requests, effects, operation };
}

test('snapshot is deeply detached, fingerprint stable, log opt-in unchanged', () => {
  const { form } = setup(); const copy = feedbackSnapshot(form);
  assert.equal(feedbackFingerprint(copy), feedbackFingerprint(form));
  form.selected_log_ids.push('log-B'); assert.deepEqual(copy.selected_log_ids, []);
});

for (const action of ['copy', 'issue']) test(`${action} always regenerates B after preview A, title/body share snapshot`, async () => {
  const x = setup(); await x.operation.run('preview');
  x.form.title = 'B'; x.form.actual = '正文B'; x.form.selected_log_ids.push('log-B'); x.operation.invalidate();
  assert.equal(x.state.preview, null); await x.operation.run(action);
  assert.equal(x.requests.length, 2); assert.deepEqual(x.requests[1].selected_log_ids, ['log-B']);
  if (action === 'copy') assert.equal(x.effects[0][1], 'B:正文B:log-B');
  else { const url = new URL(x.effects[0][1]); assert.equal(url.searchParams.get('title'), 'B'); assert.equal(url.searchParams.get('body'), 'B:正文B:log-B'); assert.equal(x.state.issueUrl, url.toString()); }
});

for (const action of ['preview', 'copy', 'issue', 'export']) {
  test(`${action}: changed form during request discards stale result and retry succeeds`, async () => {
    const pending = deferred(); let calls = 0;
    const x = setup({ [action === 'export' ? 'exportPackage' : 'preview']: payload => {
      x.requests.push(payload);
      return ++calls === 1 ? pending.promise : Promise.resolve({ markdown: `${payload.title}:fresh`, blob: {}, filename: payload.title });
    } });
    const running = x.operation.run(action); assert.equal(x.state.busy, true);
    x.form.title = 'B'; x.operation.invalidate(); pending.resolve({ markdown: 'old', blob: {}, filename: 'old' });
    assert.equal(await running, false); assert.deepEqual(x.effects, []); assert.equal(x.state.preview, null); assert.equal(x.state.issueUrl, ''); assert.match(x.state.message, /内容已修改/); assert.equal(x.state.busy, false);
    assert.equal(await x.operation.run(action), true); assert.equal(calls, 2); assert.equal(x.requests[1].title, 'B');
    if (action === 'preview') assert.equal(x.state.preview.markdown, 'B:fresh');
    if (action === 'copy') assert.deepEqual(x.effects, [['copy', 'B:fresh']]);
    if (action === 'issue') { const url = new URL(x.effects[0][1]); assert.equal(url.searchParams.get('title'), 'B'); assert.equal(url.searchParams.get('body'), 'B:fresh'); }
    if (action === 'export') assert.equal(x.effects[0][1].filename, 'B');
  });
  test(`${action}: unmount prevents late side effects`, async () => {
    const pending = deferred(); const x = setup({ [action === 'export' ? 'exportPackage' : 'preview']: () => pending.promise });
    const running = x.operation.run(action); x.operation.dispose(); pending.resolve({ markdown: 'late', blob: {}, filename: 'late' }); await running;
    assert.deepEqual(x.effects, []); assert.equal(x.state.preview, null);
  });
}

test('busy reentry is no-op including preview, clipboard lifetime, error and existing snapshot', async () => {
  const pending = deferred(); let calls = 0;
  const x = setup({ preview: () => { calls++; return pending.promise; } });
  const first = x.operation.run('copy'); const before = structuredClone(x.state);
  assert.equal(await x.operation.run('issue'), false); assert.deepEqual(x.state, before); assert.equal(calls, 1);
  pending.resolve({ markdown: 'A' }); assert.equal(await first, true); assert.equal(x.state.busy, false);
});

test('new request failure cannot emit old success, preview or raw exception secrets', async () => {
  let fail = false; const x = setup({ preview: async () => { if (fail) throw new Error('sk-private-secret'); return { markdown: 'A' }; } });
  await x.operation.run('copy'); fail = true; await x.operation.run('copy');
  assert.equal(x.effects.length, 1); assert.equal(x.state.preview, null); assert.equal(x.state.message, ''); assert.match(x.state.error, /失败/); assert.doesNotMatch(x.state.error, /secret/); assert.equal(x.state.busy, false);
});

test('clipboard rejects without false success and remains busy until completed', async () => {
  const state = { busy: false }; const pending = deferred(); let calls = 0;
  const operation = createFeedbackOperation({ state, getForm: () => ({ title: 'A', selected_log_ids: [] }), api: { preview: async () => ({ markdown: 'A' }) }, clipboard: () => { calls++; return pending.promise; } });
  const running = operation.run('copy'); await Promise.resolve();
  assert.equal(state.busy, true); assert.equal(await operation.run('copy'), false); assert.equal(calls, 1);
  pending.reject(new Error('denied')); assert.equal(await running, false); assert.equal(state.message, ''); assert.match(state.error, /剪贴板/); assert.equal(state.busy, false);
});

test('secret scan blocks Issue, and no log is ever automatically selected after failure/retry', async () => {
  const x = setup({ preview: async payload => { x.requests.push(payload); return { markdown: 'safe', blocked_by_secret_scan: true }; } });
  await x.operation.run('issue'); assert.deepEqual(x.effects, []); assert.equal(x.state.issueUrl, ''); assert.match(x.state.error, /密钥/);
  await x.operation.run('issue'); assert.deepEqual(x.form.selected_log_ids, []); assert.ok(x.requests.every(item => item.selected_log_ids.length === 0));
});

test('a change and reversal is still a stale operation', async () => {
  const pending = deferred(); const x = setup({ preview: () => pending.promise });
  const running = x.operation.run('issue'); x.form.title = 'B'; x.operation.invalidate(); x.form.title = 'A'; x.operation.invalidate();
  pending.resolve({ markdown: 'A' }); await running; assert.deepEqual(x.effects, []);
});
