import assert from 'node:assert/strict';
import {
  formatUndercurrentDebug,
  projectLocalEntity
} from '../src/utils/entityVisibility.js';

const entity = {
  name: '皇城',
  motive: '追捕玩家',
  description: '不应在非 full 模式泄露',
  tags: ['暗流实体'],
  is_active: true
};
const event = '🌌 潜流涌动: 【皇城】：派遣密探调查客栈';

assert.equal(projectLocalEntity(entity, 'hidden'), null);
assert.equal(projectLocalEntity(entity, 'names').desc, '暗流详情已隐藏');
assert.equal(projectLocalEntity(entity, 'motives').desc, '动机：追捕玩家');
assert.equal(projectLocalEntity(entity, 'full').description, '不应在非 full 模式泄露');
assert.equal(formatUndercurrentDebug(event, 'hidden', [entity]), '');
assert.equal(formatUndercurrentDebug(event, 'names', [entity]), '🌌 暗流变化：[皇城]');
assert.equal(formatUndercurrentDebug(event, 'motives', [entity]), '🌌 暗流变化：[皇城]（动机：追捕玩家）');
assert.equal(formatUndercurrentDebug(event, 'full', [entity]), event);

console.log('entity visibility behavior: OK');
