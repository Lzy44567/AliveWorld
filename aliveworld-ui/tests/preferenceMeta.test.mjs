import assert from 'node:assert/strict';
import { parsePreferenceMeta } from '../src/utils/preferenceMeta.js';

assert.deepEqual(parsePreferenceMeta('/偏好 我喜欢慢节奏'), {
  action: '', declarations: ['我喜欢慢节奏']
});
assert.deepEqual(parsePreferenceMeta('我走进酒馆\n[[偏好：不要每次都安排战斗]]'), {
  action: '我走进酒馆', declarations: ['不要每次都安排战斗']
});
assert.deepEqual(parsePreferenceMeta('我对角色说“我喜欢苹果”'), {
  action: '我对角色说“我喜欢苹果”', declarations: []
});

console.log('preference meta tests passed');
