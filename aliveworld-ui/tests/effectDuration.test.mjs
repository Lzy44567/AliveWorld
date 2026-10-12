import { test } from 'node:test';
import assert from 'node:assert/strict';
import { effectDurationLabel } from '../src/utils/effectDuration.js';

test('effect label distinguishes cycles and story seconds', () => {
  assert.equal(effectDurationLabel({ duration: 3 }), '剩3轮');
  assert.equal(effectDurationLabel({ duration: 3, tick_seconds: 10, tick_elapsed: 5 }), '剩25秒');
  assert.equal(effectDurationLabel({ duration: 3, tick_seconds: 60, tick_elapsed: 5 }), '剩2分55秒');
  assert.equal(effectDurationLabel({ duration: -1 }), '');
});
