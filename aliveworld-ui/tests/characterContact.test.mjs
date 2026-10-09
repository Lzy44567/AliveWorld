import test from 'node:test';
import assert from 'node:assert/strict';
import { createCharacterContactController } from '../src/store/characterContactController.js';
import { displayRows } from '../src/utils/characterGroupState.js';
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const tick = async () => { for (let i=0;i<8;i++) await Promise.resolve(); };
function fixture() {
  let time = 10000;
  const ctx = { session: { session_id:'a', schema_version:2, revision:3 }, contact: { settings:{enabled:true,paused:false} } };
  const state = { contexts:{a:ctx}, visible:true, activeId:'a' }, calls=[];
  const api = { proactive:async()=>({settings:{enabled:true,paused:false}}), contactActivity:async(...args)=>calls.push(args), updateProactive:async(_,body)=>{calls.push(body);return{settings:body.settings};}, updateContactQuota:async body=>calls.push(body) };
  const groups = {beforeMutation:async()=>{},refresh:async()=>{}};
  const controller = createCharacterContactController(state,api,groups,()=>time);
  return {ctx,state,calls,api,groups,controller,setTime:value=>{time=value;}};
}
test('real edits are throttled with no timer, draft upload or inactive-session renewal',async()=>{
  const f=fixture();f.ctx.draft='private draft';f.controller.activity('a');f.controller.activity('a');await tick();assert.equal(f.calls.length,1);
  assert.equal(f.calls[0].length,2);assert.match(f.calls[0][1],/^[0-9a-f-]{36}$/);assert.ok(!JSON.stringify(f.calls).includes('private draft'));
  f.setTime(15000);f.controller.activity('a');await tick();assert.equal(f.calls.length,2);
  f.state.activeId='b';f.setTime(20000);f.controller.activity('a');f.state.activeId='a';f.state.visible=false;f.controller.activity('a');await tick();assert.equal(f.calls.length,2);
  f.state.visible=true;f.ctx.contact.settings.paused=true;f.controller.activity('a');f.ctx.contact.settings.paused=false;f.ctx.contact.settings.enabled=false;f.controller.activity('a');await tick();assert.equal(f.calls.length,2);
});
test('authorization waits for read barrier and uses current session revision, no automatic retry',async()=>{
  const f=fixture(),barrier=deferred();f.groups.beforeMutation=()=>barrier.promise;
  const task=f.controller.update('a',{enabled:true});await tick();assert.equal(f.ctx.settingsBusy,true);assert.equal(f.calls.length,0);
  f.ctx.session.revision=4;barrier.resolve();await task;assert.deepEqual(f.calls,[{expected_revision:4,settings:{enabled:true}}]);assert.equal(f.ctx.settingsBusy,false);
  f.api.updateProactive=async()=>{f.calls.push('failure');throw Error('lost response');};await f.controller.update('a',{paused:true});assert.equal(f.calls.filter(v=>v==='failure').length,1);assert.match(f.ctx.contactError,/lost response/);
});
test('old schema cannot authorize or send edit activity',async()=>{
  const f=fixture();f.ctx.session.schema_version=1;await f.controller.refresh('a');await f.controller.update('a',{enabled:true});f.controller.activity('a');assert.equal(f.calls.length,0);
});
test('late GET cannot replace newer authorization state',async()=>{
  const f=fixture(),wait=deferred();f.api.proactive=()=>wait.promise;
  const loading=f.controller.refresh('a');await f.controller.update('a',{enabled:false});wait.resolve({settings:{enabled:true}});await loading;assert.equal(f.ctx.contact.settings.enabled,false);
});
test('global quotas use shared API fields, not approximate token fees',async()=>{
  const f=fixture();await f.controller.quota('a',{call_limit:7,contact_limit:14});assert.deepEqual(f.calls,[{call_limit:7,contact_limit:14}]);
});
test('proactive rows use only real AI messages and mark origin without fabricated input',()=>{
  const rows=displayRows({session:{groups:[{group_id:'g',origin:'proactive',input_ids:[]}],messages:[{group_id:'g',message:{message_id:'ai',content:'hello'}}]},previewByRequestOrdinal:{}});
  assert.equal(rows.length,1);assert.equal(rows[0].origin,'proactive');assert.equal(rows[0].temporary,false);assert.equal(rows[0].key,'ai');
});
