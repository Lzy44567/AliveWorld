import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { promptMode, visiblePrompts, groupPrompts, promptModes } from '../src/utils/promptNavigation.js';
import { createPromptDraft, promptDraftState } from '../src/utils/promptDraft.js';

const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const fixture = [
  { id: 'a', task: 'story.future', active: 'A', baseline: 'A', source: 'builtin', editable: true },
  { id: 'b', task: 'story.settlement', active: 'B', baseline: 'B', source: 'builtin', editable: true },
  { id: 'w', task: 'workshop', active: '', baseline: '', source: 'builtin', editable: false },
  { id: 'g', task: 'memory', active: 'G', baseline: 'G', source: 'builtin', editable: true },
];
async function setup(overrides = {}) {
  const state = promptDraftState(); const calls = []; let confirm = false;
  const slices = structuredClone(fixture);
  const api = {
    prompts: async () => ({ slices: structuredClone(slices), variables: [], coverage: { test: 'integrated' } }),
    savePrompt: async (id, content) => { calls.push(['save', id, content]); Object.assign(slices.find(x => x.id === id), { active: content, source: 'override', overrideVersion: 2 }); return { overrideVersion: 2 }; },
    restorePrompt: async id => { calls.push(['restore', id]); Object.assign(slices.find(x => x.id === id), { active: 'A', source: 'builtin', overrideVersion: null }); return {}; },
    lock: async () => { calls.push(['lock']); }, ...overrides,
  };
  const controller = createPromptDraft({ state, api, confirmDiscard: () => confirm });
  await controller.loadPrompts(); return { state, controller, calls, api, slices, confirm(value) { confirm = value; } };
}

test('real registry: every slice reachable once, stable API order and unchanged input/assembly fixture', () => {
  const source = readFileSync(new URL('../../core/prompt_studio.py', import.meta.url), 'utf8');
  const slices = [...source.matchAll(/PromptSlice\("([^"]+)", "([^"]+)"/g)].map((match, index) => ({ id: match[1], task: match[2], priority: index, content: 'request-fixture' }));
  assert.equal(slices.length, 36); const before = JSON.stringify(slices);
  const lists = promptModes.map(mode => visiblePrompts(slices, mode.id));
  assert.equal(new Set(lists.flat().map(x => x.id)).size, slices.length); assert.equal(lists.flat().length, slices.length);
  for (const list of lists) { assert.deepEqual(list, slices.filter(x => promptMode(x.task) === promptMode(list[0]?.task))); assert.equal(new Set(list.map(x => x.id)).size, list.length); }
  assert.deepEqual(visiblePrompts(slices, 'character').map(x => x.id), ['character.reply.c3.v1.core', 'character.reply.c3.v1.ooc', 'character.reply.c3.v1.contract', 'character.reply.c3.v1.presentation', 'character.reply.c3.v2.core', 'character.reply.c3.v2.ooc', 'character.reply.c3.v2.contract', 'character.reply.c3.v2.presentation', 'character.reply.m3.v1.core', 'character.reply.m3.v1.contract', 'character.reply.m3.v1.presentation', 'character.reply.m3.v2.core', 'character.reply.m3.v2.contract', 'character.reply.m3.v2.presentation', 'character.reply.v2.core', 'character.reply.v2.contract', 'character.reply.v2.presentation', 'character.reply.core', 'character.reply.contract', 'character.reply.presentation']);
  assert.deepEqual(visiblePrompts(slices, 'general'), []);
  assert.equal(promptMode(slices.find(x => x.id === 'undercurrent.core').task), 'game');
  assert.equal(promptMode(slices.find(x => x.id === 'workshop.runtime').task), 'workshop');
  assert.equal(JSON.stringify(slices), before); assert.deepEqual(Object.values(groupPrompts(slices)).flat(), slices);
});

test('all mapping families and future unknown tasks have one mode', () => {
  for (const task of ['story.future', 'story.new', 'world.capture', 'undercurrent']) assert.equal(promptMode(task), 'game');
  for (const task of ['character', 'character.new']) assert.equal(promptMode(task), 'character');
  for (const task of ['workshop', 'workshop.new']) assert.equal(promptMode(task), 'workshop');
  for (const task of ['story', 'world.capture.future', 'undercurrent.future', 'memory', 'new.unknown', '']) assert.equal(promptMode(task), 'general');
});

for (const action of ['select', 'mode', 'lock', 'leave']) test(`dirty ${action}: cancel preserves all state, confirm permits departure`, async () => {
  const x = await setup(); x.controller.setDraft('unsaved'); const before = structuredClone(x.state);
  const run = () => action === 'select' ? x.controller.select(x.state.slices[1]) : action === 'mode' ? x.controller.changeMode('workshop') : action === 'lock' ? x.controller.lock() : x.controller.allowLeave();
  assert.equal(await run(), false); assert.deepEqual(x.state, before); assert.deepEqual(x.calls, []);
  x.confirm(true); assert.equal(await run(), true);
  if (action === 'select') assert.equal(x.state.draft, 'B');
  if (action === 'mode') assert.equal(x.state.selectedId, 'w');
  if (action === 'lock') assert.deepEqual(x.state, promptDraftState());
});

test('same selection and same category never reset dirty draft or prompt confirmation', async () => {
  const x = await setup(); x.controller.setDraft('unsaved'); assert.equal(x.controller.select(x.state.slices[0]), false); assert.equal(x.controller.changeMode('game'), false); assert.equal(x.state.draft, 'unsaved');
});

test('empty category clears selection only with accepted discard', async () => {
  const x = await setup(); x.controller.setDraft('unsaved'); assert.equal(x.controller.changeMode('character'), false); x.confirm(true); assert.equal(x.controller.changeMode('character'), true); assert.equal(x.state.selectedId, ''); assert.equal(x.state.draft, '');
});

test('save captures origin, blocks reentry/edit/navigation/lock/restore/leave until response', async () => {
  const pending = deferred(); let calls = 0;
  const x = await setup({ savePrompt: () => { calls++; return pending.promise; } }); x.controller.setDraft('saved');
  const running = x.controller.save(); assert.equal(x.state.busy, true);
  assert.equal(x.controller.setDraft('race'), false); assert.equal(x.controller.select(x.state.slices[1]), false); assert.equal(x.controller.changeMode('workshop'), false);
  assert.equal(await x.controller.lock(), false); assert.equal(await x.controller.restore(), false); assert.equal(await x.controller.save(), false); assert.equal(x.controller.allowLeave(), false); assert.equal(calls, 1);
  x.api.prompts = async () => ({ slices: [{ ...fixture[0], active: 'saved', source: 'override', overrideVersion: 7, estimatedTokens: 99 }, fixture[1]] });
  pending.resolve({ overrideVersion: 7 }); assert.equal(await running, true); assert.equal(x.state.draft, 'saved'); assert.equal(x.controller.dirty(), false); assert.equal(x.controller.selected().estimatedTokens, 99); assert.equal(x.state.busy, false);
});

for (const action of ['save', 'restore', 'lock']) test(`${action} failure retains dirty draft, selection, mode and unlock state`, async () => {
  const x = await setup({ [action === 'save' ? 'savePrompt' : action === 'restore' ? 'restorePrompt' : 'lock']: async () => { throw new Error('failure'); } });
  x.state.slices[0].source = 'override'; x.controller.setDraft('unsaved'); x.confirm(true);
  assert.equal(await x.controller[action](), false); assert.equal(x.state.draft, 'unsaved'); assert.equal(x.state.selectedId, 'a'); assert.equal(x.state.mode, 'game'); assert.equal(x.state.unlocked, true); assert.equal(x.state.busy, false); assert.equal(x.state.notice, '');
});

test('restore has one explicit destructive confirmation and refreshes original metadata', async () => {
  const x = await setup(); x.state.slices[0].source = 'override'; x.controller.setDraft('unsaved');
  assert.equal(await x.controller.restore(), false); assert.equal(x.state.draft, 'unsaved'); x.confirm(true);
  assert.equal(await x.controller.restore(), true); assert.equal(x.state.draft, 'A'); assert.equal(x.controller.selected().source, 'builtin'); assert.equal(x.controller.dirty(), false);
});

test('diagnostics refresh does not reset selection, draft, mode or dirty baseline', async () => {
  const x = await setup(); x.controller.setDraft('unsaved'); x.api.prompts = async () => ({ slices: [], coverage: { refreshed: 'integrated' }, recentRequests: [1] });
  await x.controller.refreshDiagnostics(); assert.equal(x.state.draft, 'unsaved'); assert.equal(x.state.selectedId, 'a'); assert.equal(x.controller.dirty(), true); assert.deepEqual(x.state.recentRequests, [1]);
});

test('authentication expiry retains draft for copying, blocks saves, re-unlock keeps it', async () => {
  let calls = 0; const x = await setup({ savePrompt: async () => { calls++; throw Object.assign(new Error('expired'), { status: 401 }); } }); x.controller.setDraft('unsaved');
  await x.controller.save(); assert.equal(x.state.unlocked, false); assert.equal(x.state.draft, 'unsaved'); assert.equal(await x.controller.save(), false); assert.equal(calls, 1); assert.equal(x.controller.setDraft('new'), false);
  await x.controller.loadPrompts(); assert.equal(x.state.unlocked, true); assert.equal(x.state.draft, 'unsaved'); assert.equal(x.controller.dirty(), true);
});

test('missing selection retains current draft and disables save until explicit discard', async () => {
  const x = await setup(); x.controller.setDraft('unsaved'); x.api.prompts = async () => ({ slices: [fixture[1], fixture[2]] });
  await x.controller.loadPrompts(); assert.equal(x.state.draft, 'unsaved'); assert.equal(x.state.selectedId, 'a'); assert.equal(x.controller.available(), false); assert.equal(await x.controller.save(), false); assert.match(x.state.error, /切片已不可用/);
  assert.equal(x.controller.select(x.state.slices[0]), false); x.confirm(true); assert.equal(x.controller.select(x.state.slices[0]), true); assert.equal(x.state.draft, 'B');
});

test('readonly rejects JavaScript draft/save/restore paths', async () => {
  const x = await setup(); x.controller.changeMode('workshop'); assert.equal(x.controller.setDraft('illegal'), false); assert.equal(await x.controller.save(), false); assert.equal(await x.controller.restore(), false); assert.deepEqual(x.calls, []);
});

test('lock clears variables, messages, diagnostics and all in-memory draft state', async () => {
  const x = await setup(); Object.assign(x.state, { variableQuery: 'secret', activeVariable: { id: 'secret' }, notice: 'saved', recentRequests: [1] });
  await x.controller.lock(); assert.deepEqual(x.state, promptDraftState());
});

test('late diagnostics result cannot repopulate locked state', async () => {
  const x = await setup(); const pending = deferred(); x.api.prompts = () => pending.promise;
  const running = x.controller.refreshDiagnostics(); await x.controller.lock(); pending.resolve({ coverage: { late: 'integrated' }, recentRequests: [1] }); await running; assert.deepEqual(x.state, promptDraftState());
});
