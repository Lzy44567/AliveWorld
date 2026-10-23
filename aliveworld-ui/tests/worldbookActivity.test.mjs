import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createActivityTracker } from '../src/utils/worldbookActivity.js';

test('first view is silent; later revisions aggregate once', () => {
  const tracker = createActivityTracker();
  assert.equal(tracker.observe('a', ['old']), 0);
  assert.equal(tracker.observe('a', ['new', 'old', 'second']), 2);
  assert.equal(tracker.observe('a', ['new', 'old', 'second']), 0);
});
test('stories have independent baselines; reverted IDs do not notify again', () => {
  const tracker = createActivityTracker();
  tracker.observe('a', ['old']);
  assert.equal(tracker.observe('b', ['different']), 0);
  assert.equal(tracker.observe('a', ['old']), 0);
  assert.equal(tracker.observe('a', ['new', 'old']), 1);
});
