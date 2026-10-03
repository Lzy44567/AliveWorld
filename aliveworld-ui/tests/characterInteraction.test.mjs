import test from 'node:test';
import assert from 'node:assert/strict';
import { createCharacterInteractionPreferences, shouldSendCharacterKey } from '../src/utils/characterInteraction.js';
import { createCharacterChatStore } from '../src/store/characterChatStore.js';
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const disk = () => ({ values: {}, getItem(key) { return this.values[key]; }, setItem(key,value) { this.values[key]=value; } });

test('Enter/Shift/IME/repeat and long text shortcuts', () => {
  assert.equal(shouldSendCharacterKey({ key:'Enter' }),true);
  for (const changes of [{shiftKey:true},{altKey:true},{repeat:true},{isComposing:true},{keyCode:229},{key:'a'}]) assert.equal(shouldSendCharacterKey({key:'Enter',...changes}),false);
  assert.equal(shouldSendCharacterKey({key:'Enter'},'enter',true),false);
  assert.equal(shouldSendCharacterKey({key:'Enter'},'ctrl_enter'),false);
  for (const modifier of ['ctrlKey','metaKey']) assert.equal(shouldSendCharacterKey({key:'Enter',[modifier]:true},'ctrl_enter'),true);
});
test('settings are bounded per session and survive reload without content', () => {
  const storage=disk(), p=createCharacterInteractionPreferences(storage);
  assert.deepEqual(p.get(id(1)),{delivery:'stream',sendKey:'enter'});
  assert.equal(p.set(id(1),{delivery:'non_stream',sendKey:'ctrl_enter'}),true);
  const reload=createCharacterInteractionPreferences(storage);
  assert.deepEqual(reload.get(id(1)),{delivery:'non_stream',sendKey:'ctrl_enter'});
  assert.equal(reload.get(id(2)).delivery,'stream');
  assert.equal(p.set(id(1),{draft:'private'}),false);
  p.remove(id(1)); assert.equal(createCharacterInteractionPreferences(storage).get(id(1)).delivery,'stream');
});
test('unknown/broken settings never overwrite original; quota failure keeps in-memory choice', () => {
  for (const raw of ['{bad','{"version":99,"entries":{}}','{"version":1,"entries":{"bad":{}}}']) {
    let current=raw; const p=createCharacterInteractionPreferences({getItem(){return current;},setItem(_,s){current=s;}});
    assert.ok(p.warning); p.set(id(1),{delivery:'non_stream'}); assert.equal(current,raw); assert.equal(p.get(id(1)).delivery,'non_stream');
  }
  const p=createCharacterInteractionPreferences({getItem(){return null;},setItem(){throw Error('quota');}});
  p.set(id(1),{sendKey:'ctrl_enter'}); assert.ok(p.warning); assert.equal(p.get(id(1)).sendKey,'ctrl_enter');
});
test('capacity and invalid keys reject without removing settings', () => {
  const p=createCharacterInteractionPreferences(disk());
  assert.equal(p.set('not-an-id',{sendKey:'enter'}),false);
  assert.equal(p.set(id(1),{delivery:'unknown'}),false);
  for(let i=1;i<=2000;i++) p.entries[id(i)]={delivery:'stream',sendKey:'enter'};
  assert.equal(p.set(id(2001),{delivery:'non_stream'}),false); assert.equal(Object.keys(p.entries).length,2000);
  assert.equal(p.set(id(1),{delivery:'non_stream'}),true);
});
test('per-session context reads persisted settings and cannot change an in-flight delivery', () => {
  const storage=disk(); const a=createCharacterChatStore({},undefined,storage);
  a.setInteraction(id(1),{delivery:'non_stream'});
  const b=createCharacterChatStore({},undefined,storage);
  assert.equal(b.context(id(1)).delivery,'non_stream'); assert.equal(b.context(id(2)).delivery,'stream');
  b.context(id(1)).busy=true; b.setInteraction(id(1),{delivery:'stream'}); assert.equal(b.context(id(1)).delivery,'non_stream');
});
test('mode update blocks same-session sends/removes and preserves prior mode on failure', async () => {
  let resolve; const wait=new Promise(r=>resolve=r); let calls=0;
  const api={update:async()=>{await wait;throw Error('synthetic');},action:async()=>{calls++;},remove:async()=>{calls++;}};
  const s=createCharacterChatStore(api,undefined,disk()), ctx=s.context(id(1));
  ctx.session={revision:0,presentation_mode:'messenger',turns:[]}; ctx.draft='hello';
  const updating=s.update(id(1),{presentation_mode:'roleplay'}); assert.equal(ctx.settingsBusy,true);
  await s.run(id(1)); await s.remove(id(1)); assert.equal(calls,0);
  resolve(); await assert.rejects(updating,/synthetic/); assert.equal(ctx.settingsBusy,false); assert.equal(ctx.session.presentation_mode,'messenger');
});
