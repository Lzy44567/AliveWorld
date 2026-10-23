import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createActivityTracker, notificationRows } from '../src/utils/worldbookActivity.js';
import { normalizeStorySettings } from '../src/utils/storySettings.js';

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

test('detailed notices never copy private fields without explicit permission', () => {
  const items = Array.from({ length: 5 }, (_, i) => ({ id: String(i), book_name: '书', operation: 'add', status: 'pending', name: '隐秘', after: { content: '秘'.repeat(200) } }));
  const ids = items.map(r => r.id);
  const safe = notificationRows(items, ids);
  assert.equal(safe.length, 3);
  assert.equal(JSON.stringify(safe).includes('秘'), false);
  assert.equal(safe[0].summary, '新增 · 待审阅');
  assert.equal(notificationRows(items, ids, true)[0].excerpt.length, 160);
  assert.deepEqual(notificationRows(items, ['missing'], true), []);
});

test('silent observation consumes IDs and defaults preserve summary notices', () => {
  const tracker = createActivityTracker();
  assert.deepEqual(tracker.observeIds('a', ['old']), []);
  assert.deepEqual(tracker.observeIds('a', ['new', 'old']), ['new']);
  assert.deepEqual(tracker.observeIds('a', ['new', 'old']), []);
  tracker.reset('a');
  assert.deepEqual(tracker.observeIds('a', ['silent', 'new', 'old']), []);
  const defaults = normalizeStorySettings();
  assert.equal(defaults.worldbookNotices, true);
  assert.equal(defaults.worldbookDetailedNotices, false);
  assert.equal(defaults.worldbookNoticeContent, false);
});
