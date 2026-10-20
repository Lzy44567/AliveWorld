import test from 'node:test';
import assert from 'node:assert/strict';
import { messageActions } from '../src/utils/characterMessageActions.js';
const row = { message: { message_id: 'u1' }, temporary: false };
const state = () => ({ session: { groups: [{ input_ids: ['u1'], origin: 'user' }] }, failure: null });
test('only last input anchors whole-batch actions', () => {
  assert.deepEqual(messageActions(row,state()),{undo:true,regenerate:true});
  assert.deepEqual(messageActions({...row,message:{message_id:'older'}},state()),{});
  const ctx=state();ctx.session.groups[0].input_ids.push('u2');
  assert.deepEqual(messageActions(row,ctx),{});
});
test('saved input with failed response has truthful retry and edit actions', () => {
  const ctx=state();ctx.failure={input_ids:['u1'],operation:'send',retryable:true};
  ctx.queuedCount=1;
  assert.deepEqual(messageActions(row,ctx),{failed:true,retry:true,edit:true});
  ctx.failure.operation='regenerate';ctx.failure.retryable=false;
  assert.deepEqual(messageActions(row,ctx),{failed:true,retry:false,edit:false});
});
test('uncertain, active, queued and preview states cannot resubmit', () => {
  for(const flag of ['busy','commandPending','settingsBusy','needsReload','queuedCount']) assert.deepEqual(messageActions(row,{...state(),[flag]:true}),{});
  assert.deepEqual(messageActions({...row,temporary:true},state()),{});
});
