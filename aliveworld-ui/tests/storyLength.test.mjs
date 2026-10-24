import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeStorySettings } from '../src/utils/storySettings.js';

test('soft range retains old upper default and optional lower bound', () => {
  assert.equal(normalizeStorySettings().minimumStoryLength, 0);
  for (const [value, expected] of [[null, 0], ['', 0], [-2, 0], [350, 350], [900, 800]]) {
    const result = normalizeStorySettings({ targetStoryLength: 800, minimumStoryLength: value });
    assert.equal(result.minimumStoryLength, expected);
    assert.equal(result.targetStoryLength, 800);
  }
  const defaults = normalizeStorySettings({ targetStoryLength: 1200, minimumStoryLength: 600 });
  assert.equal(normalizeStorySettings({}, defaults).minimumStoryLength, 600);
  assert.equal(normalizeStorySettings({minimumStoryLength: 0}, defaults).minimumStoryLength, 0);
});
