import test from 'node:test';
import assert from 'node:assert/strict';
import { createCharacterChatStore } from '../src/store/characterChatStore.js';
import { displayRows, groupDetail, mergeGroupPage } from '../src/utils/characterGroupState.js';
import { characterCapacity } from '../src/utils/characterCapacity.js';
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const copy = value => JSON.parse(JSON.stringify(value));
const deferred = () => { let resolve,reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };
const tick = async () => { for(let i=0;i<10;i++) await Promise.resolve(); };
const message = (n,seq,content='text',ai=true) => ({message:{message_id:id(n),speaker_instance_id:id(ai?3:2),seq,content,created_at:'2026-10-08T00:00:00Z'},group_id:ai?id(4):null});
function fixture(overrides={}) {
  const session = { session_id:id(1),schema_version:2,revision:0,title:'chat',participants:[{instance_id:id(2),controller:'user'},{instance_id:id(3),controller:'ai'}],read_ai_seq:0,unread_count:0,queued_count:0,busy_group:null,groups:[],messages:[],next_cursor:null,memory_settings:{notice_ack_revision:0},last_failed_action:null };
  const sessions = {[id(1)]:session,[id(9)]:{...copy(session),session_id:id(9)}};
  const callbacks=new Map(),signals=new Map(),calls=[];
  const api={get:async sid=>copy(sessions[sid]),list:async()=>({sessions:[]}),capacity:async()=>null,
    subscribe:(sid,callback,{signal})=>{callbacks.set(sid,callback);signals.set(sid,signal);return new Promise(resolve=>signal.addEventListener('abort',resolve,{once:true}));},
    groupAction:async(sid,p)=>{calls.push(copy(p));session.revision++;session.queued_count++;return{session_id:sid,action_id:p.client_action_id,status:'queued'};},
    ...overrides};
  const storage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  const store=createCharacterChatStore(api,undefined,storage);
  return{store,session,sessions,callbacks,signals,calls,api,emit:(name,data={})=>callbacks.get(id(1))?.(name,{session_id:id(1),...data})};
}
const accepted = { action_id:id(5),request_id:id(6),group_id:id(4),seq:1,display_mode:'stream',reserved_ai_ids:[id(7),id(8)] };
test('schema2 switches detach subscription only; foreground reopen loads formal background messages',async()=>{
  const f=fixture();f.store.setVisible(true);await f.store.open(id(1));assert.equal(f.signals.get(id(1)).aborted,false);
  await f.store.open(id(9));assert.equal(f.signals.get(id(1)).aborted,true);
  f.session.messages=[message(7,2)];f.session.revision=1;f.session.unread_count=1;
  await f.store.open(id(1));assert.equal(f.store.current.session.messages.length,1);assert.equal(f.store.current.session.read_ai_seq,0);
  f.store.setVisible(false);assert.equal(f.signals.get(id(1)).aborted,true);
});
test('stream previews use reserved keys and atomic formal replacement never repeats bubbles',async()=>{
  const f=fixture();f.store.setVisible(true);await f.store.open(id(1));
  f.emit('accepted',accepted);f.emit('preview_start',{...accepted,seq:2,ordinal:0});f.emit('preview_delta',{...accepted,seq:3,ordinal:0,text:'first'});
  f.emit('preview_end',{...accepted,seq:4,ordinal:0});f.emit('preview_start',{...accepted,seq:5,ordinal:1});f.emit('preview_delta',{...accepted,seq:6,ordinal:1,text:'second'});
  assert.deepEqual(displayRows(f.store.current).map(row=>row.key),[id(7),id(8)]);assert.equal(f.store.current.session.messages.length,0);
  f.session.messages=[message(7,2,'first'),message(8,3,'second')];f.session.groups=[{...accepted,status:'complete',input_ids:[],bubbles:[]}];f.session.revision=1;
  f.emit('group_saved',{...accepted,seq:7,group:{status:'complete'}});await tick();
  assert.deepEqual(displayRows(f.store.current).map(row=>row.key),[id(7),id(8)]);assert.ok(displayRows(f.store.current).every(row=>!row.temporary));
  f.store.setVisible(false);
});
test('v3 busy allows new send; clearing is paired and display snapshot follows next command only',async()=>{
  const f=fixture();await f.store.open(id(1));const ctx=f.store.current;ctx.busy=true;ctx.draft=' hello ';ctx.oocDraft=' note ';
  f.store.setInteraction(id(1),{displayMode:'gaps'});await f.store.run(id(1));
  assert.equal(f.calls[0].display_mode,'gaps');assert.equal(f.calls[0].delivery,'non_stream');assert.equal(f.calls[0].content,'hello');assert.equal(ctx.draft,'');assert.equal(ctx.oocDraft,'');
  f.store.setInteraction(id(1),{displayMode:'stream'});assert.equal(f.calls[0].display_mode,'gaps');assert.equal(ctx.displayMode,'stream');
});
test('input_saved clears only own unchanged pair; new drafts survive delayed quick response',async()=>{
  const wait=deferred();let payload;const f=fixture({groupAction:async(_,p)=>{payload=p;return wait.promise;}});f.store.setVisible(true);await f.store.open(id(1));
  const ctx=f.store.current;ctx.draft='old';ctx.oocDraft='old-note';const task=f.store.run(id(1));
  f.emit('input_saved',{action_id:payload.client_action_id});await tick();assert.equal(ctx.draft,'');
  ctx.draft='new';ctx.oocDraft='new-note';wait.resolve({session_id:id(1),action_id:payload.client_action_id,status:'queued'});await task;
  assert.equal(ctx.draft,'new');assert.equal(ctx.oocDraft,'new-note');f.store.setVisible(false);
});
test('lost command response checks same action without resend and keeps unresolved draft',async()=>{
  let checks=0,calls=0;const f=fixture({groupAction:async()=>{calls++;throw Error('offline');},actionStatus:async()=>{checks++;throw Error('offline');}});
  await f.store.open(id(1));f.store.current.draft='retain';await f.store.run(id(1));
  assert.equal(calls,1);assert.equal(checks,1);assert.equal(f.store.current.commandPending,true);assert.equal(f.store.current.draft,'retain');
  const action=f.store.current.groupCommand.action_id;f.api.actionStatus=async(_,aid)=>{assert.equal(aid,action);return{status:'queued'};};
  await f.store.recover(id(1));assert.equal(f.store.current.commandPending,false);assert.equal(f.store.current.draft,'');assert.equal(calls,1);
});
test('failure discards temporary output without restoring already saved input or acknowledging preview',async()=>{
  let reads=0;const f=fixture({read:async()=>{reads++;}});f.store.setVisible(true);await f.store.open(id(1));
  f.emit('accepted',accepted);f.emit('preview_start',{...accepted,seq:2,ordinal:0});f.emit('preview_delta',{...accepted,seq:3,ordinal:0,text:'unvalidated'});
  await f.store.markPresented(id(1));assert.equal(reads,0);
  f.session.messages=[message(10,1,'user',false)];f.session.revision=1;f.session.last_failed_action={action_id:id(5),status:'failed',retryable:true};
  f.emit('failed',{...accepted,seq:4});await tick();assert.equal(displayRows(f.store.current).length,1);assert.equal(f.store.current.draft,'');assert.equal(reads,0);f.store.setVisible(false);
});
test('formal read ack only foreground and cannot overwrite newer detail with old acknowledgement',async()=>{
  const f=fixture();f.session.messages=[message(7,2)];f.session.unread_count=1;let count=0;
  f.api.read=async(sid,seq)=>{count++;assert.equal(seq,2);f.session.read_ai_seq=2;f.session.unread_count=0;f.session.revision=2;return{session_id:sid,read_ai_seq:2,revision:1};};
  await f.store.open(id(1));await f.store.markPresented(id(1));assert.equal(count,0);
  f.store.setVisible(true);await f.store.markPresented(id(1));assert.equal(count,1);assert.equal(f.store.current.session.revision,2);assert.equal(f.store.current.session.read_ai_seq,2);f.store.setVisible(false);
});
test('schema2 page merges IDs/sequence, changed cursor revision refused; capacity is explicit group version',()=>{
  const f=fixture();f.session.messages=[message(7,2)];const session=groupDetail(f.session,id(1));
  const page={schema_version:2,session_id:id(1),revision:0,groups:[],messages:[message(10,1,'input',false),message(7,2)],next_cursor:null};
  assert.deepEqual(mergeGroupPage(session,page).messages.map(row=>row.message.seq),[1,2]);assert.throws(()=>mergeGroupPage(session,{...page,revision:1}),/修订/);
  const report={version:2,session_id:id(1),revision:0,recording_pressure:'normal',public_counts:Object.fromEntries([['formal_groups',512],['actions',2048],['attempts',4096]].map(([key,limit])=>[key,{used:0,limit,state:'normal'}])),operation_capacity:Object.fromEntries(['send','retry','regenerate','undo'].map(op=>[op,'not_known_blocked']))};
  assert.equal(characterCapacity(report,id(1)).version,2);assert.equal(characterCapacity({...report,version:1},id(1)),null);
});
test('explicit retry never consumes current drafts and compatibility busy rejection preserves them',async()=>{
  const f=fixture({groupRetry:async(sid,aid)=>({session_id:sid,action_id:aid,status:'pending'})});
  f.session.last_failed_action={action_id:id(5),request_id:id(6),operation:'send',retryable:true,status:'failed'};
  await f.store.open(id(1));const ctx=f.store.current;ctx.draft='new draft';ctx.oocDraft='new note';await f.store.run(id(1),'send',true);
  assert.equal(ctx.draft,'new draft');assert.equal(ctx.oocDraft,'new note');
  f.api.groupAction=async()=>{const e=Error('旧请求执行中');e.code='SESSION_BUSY';throw e;};
  await f.store.run(id(1));assert.equal(ctx.draft,'new draft');assert.equal(ctx.commandPending,false);
});
test('authoritative refresh revalidates loaded historical pages without retaining withdrawn rows',async()=>{
  const f=fixture();f.session.messages=[message(7,22)];f.session.next_cursor=id(4);let pages=0;
  f.api.groups=async()=>{pages++;return{schema_version:2,session_id:id(1),revision:f.session.revision,groups:[],messages:[message(10,1,'old',false)],next_cursor:null};};
  f.store.setVisible(true);await f.store.open(id(1));await f.store.loadEarlier(id(1));assert.equal(pages,1);
  f.session.revision=1;f.emit('state_changed');await tick();assert.equal(pages,2);assert.deepEqual(f.store.current.session.messages.map(row=>row.message.seq),[1,22]);f.store.setVisible(false);
});
