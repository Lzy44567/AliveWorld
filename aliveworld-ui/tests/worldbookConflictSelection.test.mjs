import test from 'node:test';
import assert from 'node:assert/strict';
import { pendingConflictIds, selectedConflictIds } from '../src/utils/worldbookConflictSelection.js';

test('pending selection excludes processed and stale records', () => {
  const records = [{ id: 'a', current: true, status: 'pending' }, { id: 'b', current: false, status: 'pending' }, { id: 'c', current: true, status: 'disabled' }];
  assert.deepEqual(pendingConflictIds(records), ['a']);
  assert.deepEqual(selectedConflictIds(records, ['a', 'a', 'b', 'c', 'missing']), ['a', 'c']);
});
test('one explicit batch is bounded at 100 records', () => {
  const records = Array.from({ length: 101 }, (_, id) => ({ id, current: true, status: 'pending' }));
  assert.equal(pendingConflictIds(records).length, 100);
  assert.equal(selectedConflictIds(records, records.map(r => r.id)).length, 100);
});
