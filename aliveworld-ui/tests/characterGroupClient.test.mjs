import test from 'node:test';
import assert from 'node:assert/strict';
import { characterGroupStream } from '../src/api/characterGroupStream.js';
import { characterChatApi } from '../src/api/characterChatApi.js';
import { createCharacterInteractionPreferences } from '../src/utils/characterInteraction.js';

const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const frame = (name, seq, extras = {}) => `event: ${name}\r\ndata: ${JSON.stringify({session_id:id(1),stream_id:id(2),event_seq:seq,...extras})}\r\n\r\n`;
const ready = () => frame('ready',1,{revision:0});
const identity = {v:1,action_id:id(3),request_id:id(4),group_id:id(5),seq:1};
const disk = raw => ({ raw, getItem() {return this.raw;}, setItem(_,value) {this.raw=value;} });
const fake = parts => async () => new Response(new ReadableStream({start(controller) {
  const encoder = new TextEncoder(); for(const p of parts) controller.enqueue(typeof p === 'string' ? encoder.encode(p) : p);
  controller.close();
}}),{headers:{'content-type':'text/event-stream'}});

test('one connection reads multiple requests and bubbles, UTF8 chunks, no terminal shutdown',async()=>{
  const controller = new AbortController(), got=[];
  const raw=ready()+frame('accepted',2,{...identity,reserved_ai_ids:[id(6),id(7)]})
    +frame('preview_start',3,{...identity,seq:2,ordinal:0})+frame('preview_delta',4,{...identity,seq:3,ordinal:0,text:'😀甲'})
    +frame('preview_end',5,{...identity,seq:4,ordinal:0})+frame('preview_start',6,{...identity,seq:5,ordinal:1})
    +frame('preview_delta',7,{...identity,seq:6,ordinal:1,text:'乙'})+frame('group_saved',8,{...identity,seq:7})
    +frame('accepted',9,{...identity,request_id:id(8),reserved_ai_ids:[id(9)]});
  const bytes=new TextEncoder().encode(raw),parts=Array.from(bytes,b=>Uint8Array.of(b));
  await characterGroupStream(id(1),(name,data)=>{got.push([name,data]);if(data.event_seq===9)controller.abort();},{signal:controller.signal,fetchImpl:fake(parts)});
  assert.equal(got.length,9);assert.equal(got[3][1].text,'😀甲');assert.equal(got[6][1].ordinal,1);
});

test('bad ready, connection gaps, wrong identities and malformed JSON reject without resending',async()=>{
  for(const raw of [frame('preview_start',1,identity),ready()+frame('state_changed',3),
    ready()+frame('state_changed',2,{stream_id:id(99)}),ready()+frame('preview_delta',2,{...identity,ordinal:6,text:'bad'}),
    ready()+frame('preview_start',2,{...identity,action_id:'bad',ordinal:0}),ready()+'event: preview_delta\ndata: {bad}\n\n']){
    let calls=0;
    await assert.rejects(characterGroupStream(id(1),()=>{},{fetchImpl:async()=>{calls++;return fake([raw])();}}),{code:'OUTCOME_UNKNOWN'});
    assert.equal(calls,1);
  }
});

test('EOF and oversized UTF8 frames fail; explicit detach only cancels reader',async()=>{
  await assert.rejects(characterGroupStream(id(1),()=>{},{fetchImpl:fake([ready()])}),{code:'OUTCOME_UNKNOWN'});
  await assert.rejects(characterGroupStream(id(1),()=>{},{fetchImpl:fake([ready(),frame('state_changed',2,{text:'汉'.repeat(90000)})])}));
  let cancelled=0,calls=0;const abort=new AbortController();
  const fetchImpl=async()=>{calls++;return new Response(new ReadableStream({start(c){c.enqueue(new TextEncoder().encode(ready()));},cancel(){cancelled++;}}),{headers:{'content-type':'text/event-stream'}});};
  await characterGroupStream(id(1),()=>abort.abort(),{signal:abort.signal,fetchImpl});
  assert.equal(cancelled,1);assert.equal(calls,1);
});

test('API errors stay safe and heartbeat/unknown event does not dispatch',async()=>{
  await assert.rejects(characterGroupStream(id(1),()=>{},{fetchImpl:async()=>new Response(JSON.stringify({error:{code:'SERVICE_UNAVAILABLE',message:'未就绪'}}),{status:503})}),{code:'SERVICE_UNAVAILABLE'});
  const abort=new AbortController(),got=[];
  await characterGroupStream(id(1),(name)=>{got.push(name);if(name==='state_changed')abort.abort();},{signal:abort.signal,
    fetchImpl:fake([': keepalive\n\n'+ready()+frame('future_event',2)+frame('state_changed',3)])});
  assert.deepEqual(got,['ready','state_changed']);
});

test('switch detaches while waiting for a future frame, without generation cancellation',async()=>{
  const abort=new AbortController();let cancelled=0,resolve;
  const readySeen=new Promise(r=>resolve=r);
  const fetchImpl=async()=>new Response(new ReadableStream({start(c){c.enqueue(new TextEncoder().encode(ready()));},cancel(){cancelled++;}}),{headers:{'content-type':'text/event-stream'}});
  const task=characterGroupStream(id(1),()=>resolve(),{signal:abort.signal,fetchImpl});
  await readySeen;abort.abort();await task;assert.equal(cancelled,1);
});

test('group commands always use JSON and subscription never calls model command',async()=>{
  const previous=globalThis.fetch,calls=[];
  globalThis.fetch=async(url,options)=>{calls.push([url,options]);return new Response('{}',{status:202,headers:{'content-type':'application/json'}});};
  try{
    await characterChatApi.groupAction(id(1),{display_mode:'stream'});
    await characterChatApi.groupRetry(id(1),id(3),{display_mode:'gaps'});
    await characterChatApi.groups(id(1),id(5));await characterChatApi.read(id(1),7);
    assert.equal(calls[0][1].method,'POST');assert.ok(!calls[0][1].headers.Accept);
    assert.ok(calls[2][0].includes('/groups?'));assert.equal(calls[3][1].body,'{"seq":7}');
  }finally{globalThis.fetch=previous;}
});

test('legacy settings migrate without writes or automatic gaps and preserve old API shape',()=>{
  for(const delivery of ['stream','non_stream']){
    const raw=JSON.stringify({version:1,entries:{[id(1)]:{delivery,sendKey:'enter'}}});
    const storage=disk(raw),settings=createCharacterInteractionPreferences(storage);
    assert.equal(settings.display(id(1)),delivery==='stream'?'stream':'instant');assert.equal(storage.raw,raw);
    assert.deepEqual(settings.get(id(1)),{delivery,sendKey:'enter'});
    settings.set(id(1),{sendKey:'ctrl_enter'});assert.equal(JSON.parse(storage.raw).version,2);
  }
});

test('two switches are atomic, mutually exclusive or both off; no typing flag',()=>{
  const storage=disk(),settings=createCharacterInteractionPreferences(storage);
  assert.equal(settings.display(id(1)),'stream');
  settings.toggleDisplay(id(1),'gaps',true);assert.equal(settings.display(id(1)),'gaps');assert.equal(settings.get(id(1)).delivery,'non_stream');
  settings.toggleDisplay(id(1),'stream',true);assert.equal(settings.display(id(1)),'stream');
  settings.toggleDisplay(id(1),'stream',false);assert.equal(settings.display(id(1)),'instant');
  assert.equal(settings.set(id(1),{displayMode:'gaps',delivery:'stream'}),false);
  assert.equal(settings.set(id(1),{typing:true}),false);assert.equal(settings.toggleDisplay(id(1),'typing',true),false);
  assert.equal(createCharacterInteractionPreferences(storage).display(id(1)),'instant');
});

test('corrupt/future new settings do not overwrite original',()=>{
  for(const raw of [JSON.stringify({version:3,entries:{}}),JSON.stringify({version:2,entries:{[id(1)]:{displayMode:'gaps',delivery:'stream',sendKey:'enter'}}})]){
    const storage=disk(raw),settings=createCharacterInteractionPreferences(storage);
    assert.ok(settings.warning);settings.toggleDisplay(id(1),'gaps',true);assert.equal(storage.raw,raw);
  }
});
