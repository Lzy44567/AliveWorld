import test from 'node:test';
import assert from 'node:assert/strict';
import { createCharacterChatStore } from '../src/store/characterChatStore.js';
import { characterStream, CharacterApiError } from '../src/api/characterChatApi.js';
import { cardOpening } from '../src/utils/characterOpening.js';
import { structuredDraft, compatibleRoleText, roleFieldsError } from '../src/utils/characterFields.js';
import { characterWorldReport } from '../src/utils/characterWorldReport.js';
import { characterMemoryReport, correctionDraft, memorySourceMessages, automaticMemoryState, memoryNotice } from '../src/utils/characterMemory.js';
import { createMemoryNoticeCache } from '../src/utils/characterMemoryNotices.js';
import { characterCapacity, capacityWarning } from '../src/utils/characterCapacity.js';
import { oocLength, oocError, restoreInputPair } from '../src/utils/characterOoc.js';

test('OOC Unicode limits and dual restore never mix old and new drafts', () => {
  assert.equal(oocLength(' 😀 '.repeat(1000)), 2998);
  assert.equal(oocError('😀'.repeat(1000)), ''); assert.match(oocError('😀'.repeat(1001)), /1000/);
  assert.match(oocError('\ud800'), /无效/);
  const ctx={draft:'',oocDraft:'new',oocOpen:false};
  assert.equal(restoreInputPair(ctx,'old','old-note'),false);assert.equal(ctx.draft,'');
  ctx.oocDraft='';assert.equal(restoreInputPair(ctx,'old','old-note'),true);assert.equal(ctx.oocOpen,true);
});

test('OOC send freezes both drafts, session switch and edits preserve both new inputs', async () => {
  const wait=deferred();let payload;
  const f=fixture({action:async(_,p)=>{payload=structuredClone(p);await wait.promise;return{status:'committed'};}});
  await f.store.open('a');const ctx=f.store.current;ctx.draft=' original ';ctx.oocDraft=' note ';ctx.oocOpen=false;
  const task=f.store.run('a');assert.equal(payload.content,'original');assert.equal(payload.ooc_note,'note');
  ctx.oocDraft='new';await f.store.open('b');wait.resolve();await task;
  assert.equal(ctx.draft,' original ');assert.equal(ctx.oocDraft,'new');assert.equal(f.store.current.oocDraft,'');
});

test('OOC unchanged successful pair clears together, empty OOC omitted and OOC-only does not send', async () => {
  const payloads=[];const f=fixture({action:async(_,p)=>{payloads.push(p);return{status:'committed'};}});
  await f.store.open('a');const ctx=f.store.current;ctx.draft='dialogue';ctx.oocDraft=' note ';
  await f.store.run('a');assert.equal(ctx.draft,'');assert.equal(ctx.oocDraft,'');
  ctx.draft='dialogue';ctx.oocDraft=' ';await f.store.run('a');assert.ok(!('ooc_note'in payloads[1]));
  ctx.oocDraft='only';await f.store.run('a');assert.equal(payloads.length,2);
  ctx.draft='dialogue';ctx.oocDraft='😀'.repeat(1001);await f.store.run('a');assert.equal(payloads.length,2);
});

test('OOC retry uses original server pair, changed drafts preserved; reload restores only empty pair', async () => {
  let calls=0;let retryPayload;
  const f=fixture({action:async()=>{calls++;return{status:'failed',request_id:'rid',retryable:true};},retry:async(_,__,p)=>{retryPayload=p;return{status:'committed'};}});
  await f.store.open('a');const ctx=f.store.current;ctx.draft='old';ctx.oocDraft='old-note';await f.store.run('a');
  ctx.draft='new';ctx.oocDraft='new-note';await f.store.run('a','send',true);
  assert.ok(!('content'in retryPayload));assert.ok(!('ooc_note'in retryPayload));assert.equal(calls,1);
  assert.equal(ctx.draft,'new');assert.equal(ctx.oocDraft,'new-note');
  f.sessions.a.last_failed_action={base_revision:1,retry_input:'old',retry_ooc_note:'old-note',operation:'send',status:'failed'};
  ctx.draft='';ctx.oocDraft='new-note';await f.store.open('a');assert.equal(ctx.draft,'');assert.equal(ctx.oocDraft,'new-note');
  ctx.oocDraft='';await f.store.open('a');assert.equal(ctx.draft,'old');assert.equal(ctx.oocDraft,'old-note');
});

test('OOC undo restores original pair only to empty editor; regeneration never sends new draft', async () => {
  const payloads=[];const f=fixture({action:async(_,p)=>{payloads.push(p);return{status:'committed'};}});
  f.sessions.a.turns=[{turn_id:'turn',user_message:{content:'original'},ooc_note:'original-note'}];
  await f.store.open('a');const ctx=f.store.current;await f.store.run('a','undo');
  assert.equal(ctx.draft,'original');assert.equal(ctx.oocDraft,'original-note');
  ctx.draft='new';ctx.oocDraft='new-note';await f.store.run('a','regenerate');
  assert.ok(!('content'in payloads[1]));assert.ok(!('ooc_note'in payloads[1]));assert.equal(ctx.oocDraft,'new-note');
  ctx.draft='';await f.store.run('a','undo');assert.equal(ctx.draft,'');assert.equal(ctx.oocDraft,'new-note');
});

test('pending reload failure takes original input pair from authoritative terminal, not empty flight', async () => {
  const f=fixture();await f.store.open('a');const ctx=f.store.current;
  ctx.inflight={action_id:'action',fromReload:true,content:''};ctx.busy=true;
  await f.store.settle('a',ctx.inflight,{status:'interrupted',operation:'send',retry_input:'original',retry_ooc_note:'note',request_id:'request'});
  assert.equal(ctx.failure.content,'original');assert.equal(ctx.failure.oocDraft,'note');
  assert.equal(ctx.draft,'original');assert.equal(ctx.oocDraft,'note');
});

test('local retry retains raw draft snapshots despite normalized server retry projection', async () => {
  const f=fixture({action:async()=>({status:'failed',request_id:'request',retry_input:'dialogue',retry_ooc_note:'note'}),retry:async()=>({status:'committed'})});
  await f.store.open('a');const ctx=f.store.current;ctx.draft=' dialogue ';ctx.oocDraft=' note ';
  await f.store.run('a');assert.equal(ctx.failure.content,' dialogue ');assert.equal(ctx.failure.oocDraft,' note ');
  await f.store.run('a','send',true);assert.equal(ctx.draft,'');assert.equal(ctx.oocDraft,'');
});

const capacityFixture = (sessionId = 'a', used = 0) => ({ session_id: sessionId, revision: 1, version: 1, public_counts: { formal_turns: { used, limit: 512, state: used === 512 ? 'at_limit' : used >= 410 ? 'near' : 'normal' }, actions: { used: 0, limit: 2048, state: 'normal' }, attempts: { used: 0, limit: 4096, state: 'normal' } }, recording_pressure: 'normal', operation_capacity: { send: used === 512 ? 'blocked' : 'not_known_blocked', retry: 'not_known_blocked', regenerate: 'not_known_blocked', undo: 'not_known_blocked' } });

test('capacity decoder whitelists data and validates counts, states and known gates', () => {
  const raw = capacityFixture(); raw.private_count = 44;
  assert.deepEqual(characterCapacity(raw, 'a'), capacityFixture());
  assert.equal(characterCapacity(raw, 'b'), null);
  assert.equal(characterCapacity({ ...raw, revision: true }, 'a'), null);
  raw.public_counts.formal_turns.used = true; assert.equal(characterCapacity(raw, 'a'), null);
  assert.equal(capacityWarning(capacityFixture()), '');
  assert.match(capacityWarning(capacityFixture('a', 410)), /接近/);
  assert.match(capacityWarning(capacityFixture('a', 512)), /上限/);
  const bad = capacityFixture('a', 512); bad.operation_capacity.undo = 'blocked'; assert.equal(characterCapacity(bad, 'a'), null);
});

test('capacity refresh discards out-of-order responses even at the same domain revision', async () => {
  const waits = [deferred(), deferred()]; let index = 0;
  const f = fixture({ capacity: async () => waits[index++].promise });
  f.store.context('a').session = structuredClone(f.sessions.a);
  const first = f.store.refreshCapacity('a'), second = f.store.refreshCapacity('a');
  waits[1].resolve(capacityFixture('a', 410)); await second;
  waits[0].resolve(capacityFixture()); await first;
  assert.equal(f.store.context('a').capacity.public_counts.formal_turns.used, 410);
});

test('capacity is session owned; errors and deletion do not become false zero capacity', async () => {
  const wait = deferred();
  const f = fixture({ capacity: async () => wait.promise });
  f.store.context('a').session = structuredClone(f.sessions.a); f.store.context('a').draft = '保留草稿';
  const task = f.store.refreshCapacity('a'); f.store.activeId = 'b'; wait.resolve(capacityFixture()); await task;
  assert.equal(f.store.context('a').draft, '保留草稿'); assert.equal(f.store.context('b').capacity, undefined);
  f.api.capacity = async () => { throw Error('offline'); }; await f.store.refreshCapacity('a');
  assert.equal(f.store.context('a').capacity, null); assert.match(f.store.context('a').capacityError, /暂时无法读取/);
  const later = deferred(); f.api.capacity = async () => later.promise;
  const pending = f.store.refreshCapacity('a'); delete f.store.contexts.a; later.resolve(capacityFixture()); await pending;
  assert.equal(f.store.contexts.a, undefined);
});

const memoryId = '11111111-1111-4111-8111-111111111111';
const memoryReport = () => ({ entries: [{ entry_id: memoryId, reason: 'important', state: 'budget' }] });
const autoState = () => ({ version: 2, automatic_enabled: true, important_entry_ids: [], protected_entries: [], inactive_root_ids: [], automatic_entries: [{ entry_id: memoryId, root_entry_id: memoryId, reason: 'explicit_boundary', level: 'important', dismissed: false }], inactive_dismissed_root_ids: [], notice_ack_revision: 0 });
const noticeStorage = () => { const data = new Map(); return { getItem: k => data.get(k) ?? null, setItem: (k, v) => data.set(k, v), removeItem: k => data.delete(k) }; };

test('M2 automatic settings and notices are bounded public whitelists', () => {
  const raw = autoState(); raw.secret = 'private'; raw.automatic_entries[0].meaning = 'private';
  assert.deepEqual(automaticMemoryState(raw), autoState());
  for (const change of [{ version: 3 }, { automatic_enabled: 'yes' }, { notice_ack_revision: true }, { automatic_entries: Array(129).fill(raw.automatic_entries[0]) }, { automatic_entries: [{ ...raw.automatic_entries[0], level: 'highlight' }] }]) assert.equal(automaticMemoryState({ ...raw, ...change }), null);
  assert.ok(characterMemoryReport({ entries: [{ entry_id: memoryId, reason: 'auto_highlight', state: 'sent' }] }));
  const n = { action_id: memoryId, committed_revision: 2, entry_ids: [memoryId], secret: 'private' };
  assert.deepEqual(memoryNotice(n), { action_id: memoryId, committed_revision: 2, entry_ids: [memoryId] });
  assert.equal(memoryNotice({ ...n, committed_revision: true }), null);
  assert.equal(memoryNotice({ ...n, entry_ids: [memoryId, memoryId] }), null);
});

test('M2 notice identities persist without text and corruption suppresses history replay', () => {
  const storage = noticeStorage(), cache = createMemoryNoticeCache(storage);
  assert.equal(cache.claim('a', memoryId), true); assert.equal(cache.claim('a', memoryId), false);
  assert.equal(createMemoryNoticeCache(storage).claim('a', memoryId), false);
  assert.equal(cache.claim('b', memoryId), true); cache.removeSession('a');
  assert.equal(createMemoryNoticeCache(storage).claim('a', memoryId), true);
  const broken = { getItem: () => '{broken', setItem: () => {} };
  assert.equal(createMemoryNoticeCache(broken).claim('a', memoryId), false);
  assert.equal(createMemoryNoticeCache({ getItem: () => null, setItem: () => { throw Error('quota'); } }).claim('a', memoryId), false);
});

test('M2 explicit enable and dismissal preserve session fields and initiating ownership', async () => {
  const wait = deferred(); let payload;
  const f = fixture({ enableAutomaticMemory: async (id, value) => { payload = value; await wait.promise; return { session_id: id, revision: 2, memory_settings: autoState() }; } });
  await f.store.open('a'); f.store.current.draft = '原草稿';
  const task = f.store.enableAutomaticMemory('a'); await f.store.open('b'); wait.resolve(); await task;
  assert.deepEqual(payload, { expected_revision: 1, enabled: true });
  assert.equal(f.store.context('a').session.memory_settings.version, 2); assert.equal(f.store.context('a').draft, '原草稿'); assert.deepEqual(f.store.context('a').session.turns, []);
  assert.equal(f.store.current.session.memory_settings, undefined);
});

test('M2 lost setting response reloads authority without toggling or automatic retry', async () => {
  let calls = 0;
  const f = fixture({ selectAutomaticMemory: async () => { ++calls; f.sessions.a.memory_settings = autoState(); f.sessions.a.memory_settings.automatic_entries[0].dismissed = true; throw Error('lost'); } });
  await f.store.open('a'); await f.store.selectAutomaticMemory('a', memoryId, true);
  assert.equal(calls, 1); assert.equal(f.store.current.session.memory_settings.automatic_entries[0].dismissed, true); assert.equal(f.store.current.settingsBusy, false);
  f.store.current.busy = true; await f.store.selectAutomaticMemory('a', memoryId, false); assert.equal(calls, 1);
});

test('M2 current successful send shows one public notice and acknowledges real action only', async () => {
  const calls = [], storage = noticeStorage();
  const f = fixture({ action: async (id, p) => { f.sessions[id].revision = 2; f.sessions[id].memory_settings = autoState(); return { status: 'committed', memory_notice: { action_id: p.client_action_id, committed_revision: 2, entry_ids: [memoryId] } }; }, acknowledgeMemoryNotice: async (id, p) => { calls.push(p); const state = autoState(); state.notice_ack_revision = 2; return { session_id: id, revision: 3, memory_settings: state }; } }, storage);
  await f.store.open('a'); f.store.setVisible(true); f.store.current.draft = 'hello'; await f.store.run('a');
  assert.equal(f.store.current.memoryNotice.entry_ids.length, 1); assert.equal(calls.length, 1);
  assert.equal(calls[0].action_id, f.store.current.memoryNotice.action_id); assert.equal(calls[0].expected_revision, 2);
  await f.store.open('a'); assert.equal(f.store.current.memoryNotice, null);
});

test('M2 background or regenerated replies never surface a first-time notice', async () => {
  const f = fixture({}, noticeStorage()); await f.store.open('a'); f.store.setVisible(true);
  const ctx = f.store.current, flight = { action_id: memoryId, operation: 'regenerate', content: '' }; ctx.inflight = flight; ctx.busy = true;
  await f.store.settle('a', ctx.inflight, { status: 'committed', memory_notice: { action_id: memoryId, committed_revision: 1, entry_ids: [memoryId] } });
  assert.equal(ctx.memoryNotice, null);
  const other = { action_id: memoryId, operation: 'send', content: '' }; ctx.inflight = other; ctx.busy = true;
  await f.store.open('b'); await f.store.settle('a', ctx.inflight, { status: 'committed', memory_notice: { action_id: memoryId, committed_revision: 1, entry_ids: [memoryId] } });
  assert.equal(ctx.memoryNotice, null); assert.equal(f.store.current.memoryNotice, null);
});

test('M2 lost acknowledgement reloads before one bounded idempotent supplement, never generates', async () => {
  for (const committed of [false, true]) {
    let calls = 0;
    const f = fixture({ acknowledgeMemoryNotice: async (id, p) => {
      calls++;
      if (calls === 1) {
        if (committed) { f.sessions[id].revision = 3; f.sessions[id].memory_settings.notice_ack_revision = 2; }
        throw Error('response lost');
      }
      assert.equal(p.expected_revision, 2);
      f.sessions[id].revision = 3; f.sessions[id].memory_settings.notice_ack_revision = 2;
      return { session_id: id, revision: 3, memory_settings: f.sessions[id].memory_settings };
    } });
    f.sessions.a.revision = 2; f.sessions.a.memory_settings = autoState();
    await f.store.open('a');
    await f.store.acknowledgeMemoryNotice('a', { action_id: memoryId, committed_revision: 2 });
    assert.equal(calls, committed ? 1 : 2);
    assert.equal(f.store.current.session.memory_settings.notice_ack_revision, 2);
    assert.equal(f.store.current.error, '');
  }
});
test('memory report and source projections are bounded whitelists; correction never overwrites draft', () => {
  const raw = memoryReport(); raw.private_count = 5; raw.entries[0].quote = 'private';
  assert.deepEqual(characterMemoryReport(raw), memoryReport());
  assert.equal(characterMemoryReport({ entries: [{ ...raw.entries[0], reason: 'private' }] }), null);
  assert.equal(characterMemoryReport({ entries: Array(129).fill(raw.entries[0]) }), null);
  assert.equal(correctionDraft({ content: '合成承诺' }, '未发送的草稿'), null);
  assert.match(correctionDraft({ content: '合成承诺' }), /我要更正/);
  const source = { entry_id: memoryId, revision: 1, messages: [{ message_id: memoryId, speaker_instance_id: memoryId, content: '合成原文', private: 'secret' }] };
  assert.ok(!JSON.stringify(memorySourceMessages(source, memoryId)).includes('secret'));
  assert.throws(() => memorySourceMessages(source, 'another'));
});
test('memory marking belongs to initiating session, no optimistic success, correction keeps draft', async () => {
  let resolve;
  const f = fixture({ markMemory: async () => new Promise(r => resolve = r) });
  await f.store.open('a'); const original = f.store.current;
  const change = f.store.markMemory('a', memoryId, true);
  assert.equal(original.settingsBusy, true);
  await f.store.open('b'); resolve({ ...original.session, revision: 2, memory_settings: { important_entry_ids: [memoryId] } });
  await change; assert.equal(original.session.revision, 2); assert.notEqual(f.store.current.session.revision, 2);
  f.store.correctMemory('a', { content: '承诺' }); assert.match(original.draft, /我要更正/);
  const draft = original.draft; f.store.correctMemory('a', { content: '另一条' }); assert.equal(original.draft, draft);
});
test('memory marking lost response reloads authority without toggling or retry', async () => {
  let calls = 0;
  const f = fixture({ markMemory: async () => { ++calls; throw Error('lost'); } });
  await f.store.open('a'); await f.store.markMemory('a', memoryId, true);
  assert.equal(calls, 1); assert.equal(f.store.current.settingsBusy, false); assert.match(f.store.current.error, /需核对/);
});

const worldReport = () => ({ window_turns: 4, resident_count: 1, omitted_by_limit: 0, omitted_by_budget: 0, entries: [{ entry_id: 'entry', entry_name: '合成规则', source: 'recent', turn_distance: 1, planned: true }] });

test('world matching display is a bounded whitelist without text or keywords', () => {
  const raw = worldReport(); raw.full_book = 'secret'; raw.entries[0].quote = 'private';
  const safe = characterWorldReport(raw);
  assert.ok(safe); assert.ok(!JSON.stringify(safe).includes('secret')); assert.ok(!JSON.stringify(safe).includes('private'));
  for (const change of [{ window_turns: 5 }, { resident_count: -1 }, { entries: Array(17).fill(raw.entries[0]) }, { entries: [{ ...raw.entries[0], source: 'current' }] }]) assert.equal(characterWorldReport({ ...raw, ...change }), null);
});

test('world reports remain in their initiating context and reject stale events', async () => {
  const f = fixture(); await f.store.open('a'); const ctx = f.store.current;
  ctx.inflight = { action_id: 'action', request_id: 'request', lastSeq: 0 }; const flight = ctx.inflight;
  await f.store.open('b');
  const data = { v: 1, session_id: 'a', action_id: 'action', request_id: 'request', seq: 1, world_context_report: worldReport() };
  f.store.event('a', flight, 'accepted', data);
  assert.equal(ctx.worldReport.entries[0].source, 'recent'); assert.equal(f.store.current.worldReport, undefined);
  f.store.event('a', flight, 'accepted', { ...data, request_id: 'stale', seq: 2, world_context_report: null });
  assert.ok(ctx.worldReport);
});

test('nonstream committed world report survives detail reload but not a new request', async () => {
  let second = false;
  const f = fixture({ action: async () => ({ status: 'committed', world_context_report: second ? null : worldReport() }) });
  await f.store.open('a'); f.store.current.delivery = 'non_stream'; f.store.current.draft = 'one'; await f.store.run('a');
  assert.ok(f.store.current.worldReport); second = true;
  f.store.current.draft = 'two'; await f.store.run('a'); assert.equal(f.store.current.worldReport, null);
});

test('structured conversion preserves original text and does not invent examples/opening', () => {
  const fields = structuredDraft('自由人设😀', '旧场景');
  assert.equal(fields.description, '自由人设😀'); assert.equal(fields.scenario, '旧场景');
  assert.equal(fields.dialogue_examples, ''); assert.equal(fields.first_message, '');
  assert.equal(roleFieldsError(fields), '');
});

test('structured limits count Unicode characters and never silently truncate', () => {
  const fields = structuredDraft('😀'.repeat(16000));
  assert.equal(roleFieldsError(fields), '');
  fields.description += '😀'; assert.match(roleFieldsError(fields), /超过16000/);
  assert.equal(Array.from(fields.description).length, 16001);
  assert.ok(roleFieldsError({ ...structuredDraft(), extra: '' }));
  assert.ok(roleFieldsError({ ...structuredDraft(), version: true }));
});

test('compatibility description labels examples but excludes optional author opening', () => {
  const fields = { ...structuredDraft('人设', '情景'), personality: '谨慎', dialogue_examples: '表达参考', first_message: '独立开场' };
  assert.match(compatibleRoleText(fields), /【对话示例】\n表达参考/);
  assert.ok(!compatibleRoleText(fields).includes('独立开场'));
});

test('explicit card opening validates all v1 fields and never guesses legacy/source', () => {
  const fields = { version: 1, description: '', personality: '', scenario: '', dialogue_examples: '', first_message: '  你好😀  ' };
  assert.equal(cardOpening({ role_fields: fields }), fields.first_message);
  assert.equal(cardOpening({ starting_scene: 'legacy', _external_import: { source: { first_mes: 'hidden' } } }), '');
  for (const change of [{ version: true }, { extra: '' }, { scenario: null }, { first_message: '😀'.repeat(8001) }]) assert.equal(cardOpening({ role_fields: { ...fields, ...change } }), '');
});

test('lost creation response freezes identity and payload; explicit retry reuses them', async () => {
  const calls = []; let first = true;
  const f = fixture({ create: async payload => { calls.push(structuredClone(payload)); if (first) { first = false; throw Error('response lost'); } return { session_id: 'created', turns: [] }; } });
  const input = { client_creation_id: 'fixed-id', ai_asset_ref: { kind: 'character', key: 'original' }, opening_text: 'original opening' };
  await assert.rejects(f.store.create(input)); input.ai_asset_ref.key = 'changed'; input.opening_text = 'changed';
  await assert.rejects(f.store.create(input), /原请求/); assert.equal(calls.length, 1);
  await f.store.create();
  assert.deepEqual(calls[0], calls[1]); assert.equal(calls[1].client_creation_id, 'fixed-id'); assert.equal(calls[1].opening_text, 'original opening');
  assert.equal(f.store.creationPending, null); assert.equal(f.store.creationBusy, false);
});

test('busy creation is not duplicated and definite rejection permits editing', async () => {
  const wait = deferred(); let calls = 0;
  const f = fixture({ create: async () => { calls++; await wait.promise; throw new CharacterApiError('bad', 'INVALID_REQUEST'); } });
  const operation = f.store.create({ ai_asset_ref: { kind: 'character', key: 'original' } });
  await assert.rejects(f.store.create(), /稍候/); assert.equal(calls, 1);
  wait.resolve(); await assert.rejects(operation); assert.equal(f.store.creationPending, null);
});

const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; };
function fixture(overrides = {}, storage) {
  const sessions = { a: { session_id: 'a', revision: 1, turns: [], ledger: [], pending: null }, b: { session_id: 'b', revision: 1, turns: [], ledger: [], pending: null } };
  const api = { list: async () => ({ sessions: Object.values(sessions) }), get: async id => structuredClone(sessions[id]), capacity: async id => ({ ...capacityFixture(id), revision: sessions[id].revision }), ...overrides };
  return { sessions, api, store: createCharacterChatStore(api, async () => {}, storage) };
}

test('preference settings update is owned by initiating session and revision, not the active view', async () => {
  const wait = deferred(); let payload;
  const f = fixture({ update: async (id, value) => { payload = { id, value }; await wait.promise; return { ...f.sessions[id], revision: 2, preference_settings: value.preference_settings }; } });
  await f.store.open('a');
  const settings = { enabled: true, include_sensitive: false };
  const task = f.store.update('a', { preference_settings: settings });
  assert.equal(f.store.context('a').settingsBusy, true);
  await f.store.open('b'); wait.resolve(); await task;
  assert.equal(payload.id, 'a'); assert.equal(payload.value.expected_revision, 1);
  assert.deepEqual(f.store.context('a').session.preference_settings, settings);
  assert.equal(f.store.current.session.preference_settings, undefined); assert.equal(f.store.activeId, 'b');
});

test('failed preference settings update preserves server state and cannot run while busy', async () => {
  let calls = 0;
  const f = fixture({ update: async () => { calls++; throw Error('revision conflict'); } });
  f.sessions.a.preference_settings = { enabled: false, include_sensitive: false };
  await f.store.open('a');
  await assert.rejects(f.store.update('a', { preference_settings: { enabled: true, include_sensitive: true } }));
  assert.equal(f.store.current.session.preference_settings.enabled, false); assert.equal(f.store.current.settingsBusy, false);
  f.store.current.busy = true; await f.store.update('a', { preference_settings: { enabled: true, include_sensitive: false } });
  assert.equal(calls, 1);
});
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
