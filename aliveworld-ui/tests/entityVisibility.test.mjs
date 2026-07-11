import assert from 'node:assert/strict';
import {
  formatUndercurrentDebug,
  normalizeEntityDisclosure,
  projectLocalEntity
} from '../src/utils/entityVisibility.js';
import { buildEntityPayload, createEntityEditorForm } from '../src/utils/entityForm.js';

const entity = {
  name: '皇城',
  motive: '追捕玩家',
  description: '不应在非 full 模式泄露',
  tags: ['暗流实体'],
  is_active: true
};
const event = '🌌 潜流涌动: 【皇城】：派遣密探调查客栈';

const hidden = {};
const names = { showEntityNames: true };
const motives = { showEntityMotives: true };
const bubbles = { showEntityNames: true, showEntityBubbles: true };
assert.equal(projectLocalEntity(entity, hidden), null);
assert.equal(projectLocalEntity(entity, names).desc, '暗流详情已隐藏');
assert.equal(projectLocalEntity(entity, motives).desc, '动机：追捕玩家');
assert.equal(normalizeEntityDisclosure({ allowEntityEditing: true }).showNames, true);
assert.equal(projectLocalEntity(entity, normalizeEntityDisclosure(names)).name, '皇城');
assert.equal(projectLocalEntity(entity, normalizeEntityDisclosure(motives)).desc, '动机：追捕玩家');
assert.equal(formatUndercurrentDebug(event, hidden, [entity]), '');
assert.equal(formatUndercurrentDebug(event, bubbles, [entity]), '🌌 暗流变化：[皇城]');
assert.equal(formatUndercurrentDebug(event, { ...bubbles, showEntityMotives: true }, [entity]), '🌌 暗流变化：[皇城]（动机：追捕玩家）');

const editorForm = createEntityEditorForm({ ...entity, plans: ['搜查客栈'], triggers: [{ condition: '进城', result: '盘查' }] });
const entityPayload = buildEntityPayload({ ...editorForm, importance: '0.6', relationships: [{ target: '玩家', relation: '敌对' }] });
assert.deepEqual(entityPayload.plans, ['搜查客栈']);
assert.deepEqual(entityPayload.triggers, [{ condition: '进城', result: '盘查' }]);
assert.deepEqual(entityPayload.relationships, { 玩家: '敌对' });
assert.equal(entityPayload.importance, 0.6);
assert.deepEqual(buildEntityPayload({ ...editorForm, triggers: [{ condition: '雨天', result: '' }] }).triggers, [{ condition: '雨天', result: '' }]);

console.log('entity UI behavior: OK');
