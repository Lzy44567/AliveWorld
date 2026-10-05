import test from 'node:test';
import assert from 'node:assert/strict';
import { characterCognition, cognitionRows, sourceRecallReport } from '../src/utils/characterCognition.js';
import { createCharacterChatStore } from '../src/store/characterChatStore.js';
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const session = (revision=1) => ({session_id:id(1),revision,participants:[{instance_id:id(2),controller:'user'},{instance_id:id(3),controller:'ai'}],ledger:[{entry_id:id(4),kind:'knowledge',content:'平时喜欢甜食；睡前不吃',about_instance_id:id(2),source:{type:'player_statement'}}]});
const report = (revision=1) => ({version:1,session_id:id(1),revision,entries:[{entry_id:id(4),about_instance_id:id(2),kind:'knowledge',basis:'player_statement',root_entry_id:id(4),supersedes_entry_id:null,annotation_reason:null}]});
const recall = () => ({version:1,entries:[{entry_id:id(4),state:'sent'}]});
const storage = {getItem(){return null;},setItem(){}};

test('cognition uses current public ledger and strips auxiliary data, without semantic guessing', () => {
  const raw = report(); raw.private_count=3; raw.entries[0].content='hidden';
  assert.deepEqual(characterCognition(raw,session()),report());
  assert.equal(cognitionRows(report(),session(),'player_statement',id(2))[0].content,'平时喜欢甜食；睡前不吃');
  assert.deepEqual(cognitionRows(report(),session(),'model_inference'),[]);
  assert.deepEqual(cognitionRows(report(),session(),'','unspecified'),[]);
  assert.deepEqual(cognitionRows(report(),session(2)),[]);
  for (const changed of [{session_id:id(9)},{version:2},{revision:0},{entries:[{...raw.entries[0],entry_id:id(9)}]},{entries:[{...raw.entries[0],basis:'model_inference'}]},{entries:[{...raw.entries[0],about_instance_id:id(9)}]},{entries:Array(129).fill(raw.entries[0])},{entries:[raw.entries[0],raw.entries[0]]}]) assert.equal(characterCognition({...raw,...changed},session()),null);
});
test('source report is bounded and strips quoted text or private counts', () => {
  const raw=recall(); raw.private_count=5; raw.entries[0].quote='not exported';
  assert.deepEqual(sourceRecallReport(raw),recall());
  for (const state of ['sent','budget','limit']) assert.equal(sourceRecallReport({version:1,entries:[{entry_id:id(4),state}]}).entries[0].state,state);
  for (const changed of [{version:2},{entries:Array(33).fill(raw.entries[0])},{entries:[raw.entries[0],raw.entries[0]]},{entries:[{...raw.entries[0],state:'hidden'}]}]) assert.equal(sourceRecallReport({...raw,...changed}),null);
});
test('index refresh sequences discard stale results and errors, deleted contexts remain deleted', async () => {
  const jobs=[]; const store=createCharacterChatStore({cognition:()=>new Promise((resolve,reject)=>jobs.push({resolve,reject}))},undefined,storage);
  const ctx=store.context(id(1));ctx.session=session();
  const first=store.refreshCognition(id(1)),second=store.refreshCognition(id(1));
  jobs[1].resolve(report());await second;jobs[0].reject(Error('old'));await first;
  assert.deepEqual(JSON.parse(JSON.stringify(ctx.cognition)),report());assert.equal(ctx.cognitionError,'');
  const gone=store.refreshCognition(id(1));delete store.contexts[id(1)];jobs[2].resolve(report());await gone;assert.equal(store.contexts[id(1)],undefined);
});
test('revision mismatch reloads authoritative session once, failures show unknown without changing draft', async () => {
  let reads=0; const store=createCharacterChatStore({cognition:async()=>report(2),get:async()=>{reads++;return session(2);}},undefined,storage);
  const ctx=store.context(id(1));ctx.session=session();ctx.draft='unsent';await store.refreshCognition(id(1));
  assert.equal(reads,1);assert.equal(ctx.cognition.revision,2);assert.equal(ctx.draft,'unsent');
  const broken=createCharacterChatStore({cognition:async()=>{throw Error('network');}},undefined,storage);broken.context(id(1)).session=session();await broken.refreshCognition(id(1));assert.equal(broken.context(id(1)).cognition,null);assert.match(broken.context(id(1)).cognitionError,/无法/);
});
test('recall SSE is request scoped and switch/reload does not reconstruct old reports', async () => {
  const store=createCharacterChatStore({get:async sid=>({...session(),session_id:sid}),capacity:async()=>null},undefined,storage);
  const ctx=store.context(id(1));ctx.session=session();ctx.inflight={action_id:id(6),request_id:id(7),lastSeq:0};const flight=ctx.inflight;
  const event={v:1,session_id:id(1),action_id:id(6),request_id:id(7),seq:1,source_recall_report:recall()};
  assert.equal(store.event(id(1),flight,'accepted',event),true);assert.deepEqual(JSON.parse(JSON.stringify(ctx.sourceRecallReport)),recall());
  assert.equal(store.event(id(1),flight,'accepted',{...event,seq:2,session_id:id(8)}),false);assert.equal(store.context(id(8)).sourceRecallReport,undefined);
  await store.open(id(1));assert.equal(ctx.sourceRecallReport,null);
});
test('an opened index refreshes after formal completion, nonstream reports remain request owned', async () => {
  let indexReads=0; const store=createCharacterChatStore({get:async()=>session(2),cognition:async()=>{indexReads++;return report(2);},capacity:async()=>null,list:async()=>({sessions:[]})},undefined,storage);
  const ctx=store.context(id(1));ctx.session=session();ctx.cognitionOpen=true;ctx.inflight={action_id:id(6),request_id:id(7),operation:'send',content:'query'};
  await store.settle(id(1),ctx.inflight,{status:'committed',source_recall_report:recall()});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(indexReads,1);assert.equal(ctx.cognition.revision,2);assert.deepEqual(JSON.parse(JSON.stringify(ctx.sourceRecallReport)),recall());assert.equal(store.context(id(8)).cognition,undefined);
});
test('repeated revision disagreement is bounded, not an API/model polling loop', async () => {
  let gets=0,reads=0;const store=createCharacterChatStore({cognition:async()=>{reads++;return report(3);},get:async()=>{gets++;return session(2);}},undefined,storage);
  const ctx=store.context(id(1));ctx.session=session();await store.refreshCognition(id(1));
  assert.equal(reads,2);assert.equal(gets,1);assert.equal(ctx.cognition,null);assert.match(ctx.cognitionError,/核对/);
});
