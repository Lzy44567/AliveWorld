import { test } from 'node:test';
import assert from 'node:assert/strict';
import { canRestoreRequest, recoveryExport } from '../src/utils/recoveryPresentation.js';
test('残稿恢复保护新草稿，导出明确未结算', () => {
  assert.equal(canRestoreRequest('', 'old'), true);
  assert.equal(canRestoreRequest('old', 'old'), true);
  assert.equal(canRestoreRequest('new', 'old'), false);
  const output = recoveryExport({ created_at: 'test', text: 'safe text', request: 'request', reason: 'output_limit' });
  assert.match(output, /不是正式故事或资产/);
  assert.match(output, /tokens/);
  assert.match(output, /safe text/);
});
