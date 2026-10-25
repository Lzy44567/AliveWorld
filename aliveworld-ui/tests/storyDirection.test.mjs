import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeStorySettings } from '../src/utils/storySettings.js';
import { STORY_SETTING_GROUPS } from '../src/utils/storySettingDefinitions.js';

test('偏好融入档位保留类型，旧档默认适中，全局默认可被本局覆盖', () => {
  assert.equal(normalizeStorySettings().preferenceEmphasis, 'balanced');
  for (const level of ['light', 'balanced', 'prominent']) {
    assert.equal(normalizeStorySettings({ preferenceEmphasis: level }).preferenceEmphasis, level);
  }
  const defaults = normalizeStorySettings({ preferenceEmphasis: 'prominent' });
  assert.equal(normalizeStorySettings({}, defaults).preferenceEmphasis, 'prominent');
  assert.equal(normalizeStorySettings({ preferenceEmphasis: 'light' }, defaults).preferenceEmphasis, 'light');
  assert.equal(defaults.preferenceEmphasis, 'prominent');
  assert.equal(normalizeStorySettings({ preferenceEmphasis: true }).preferenceEmphasis, 'balanced');
});

test('融入程度为普通设置三档按钮而不是新增下拉列表', () => {
  const group = STORY_SETTING_GROUPS.find(group => group.items.some(item => item.key === 'preferenceEmphasis'));
  assert.equal(group.advanced, false);
  assert.equal(group.items.find(item => item.key === 'preferenceEmphasis').type, 'segments');
});
