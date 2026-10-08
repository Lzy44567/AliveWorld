import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';
const base='/api/v1/character-sessions', fake='http://127.0.0.1:18765';
const card='C4浏览器合成角色';
async function create(request,title) {
  await request.post(`/api/v1/lobby/assets/characters/${encodeURIComponent(card)}`,{data:{parsed_data:{name:card,description:'成年合成角色，仅测试消息组，不访问玩家数据。'},overwrite:true}});
  const response=await request.post(base,{data:{client_creation_id:randomUUID(),schema_version:2,title,ai_asset_ref:{kind:'character',key:card},presentation_mode:'messenger'}});
  expect(response.ok()).toBeTruthy();return response.json();
}
async function enter(page,sid) {
  await page.goto('/');const later=page.getByRole('button',{name:'稍后再说'});if(await later.isVisible().catch(()=>false))await later.click();
  await page.getByTestId('mode-character').click();await page.getByTestId(`character-session-${sid}`).click();
  await expect(page.getByTestId('character-composer')).toBeVisible();
}
async function send(page,text) {await page.getByTestId('character-composer').fill(text);await page.getByTestId('character-send').click();await expect(page.getByTestId('character-composer')).toHaveValue('');}
async function detail(request,sid) {return(await request.get(`${base}/${sid}`)).json();}
async function records(request) {return(await(await request.get(`${fake}/__test__/requests`)).json()).requests.filter(r=>r.kind==='character.reply'&&JSON.parse(r.user).reply_contract_id==='character.reply.v3');}
test.describe.configure({mode:'serial'});
test('C4真实流式气泡原位确认、连发合并下一请求、互斥设置及宽窄布局',async({page,request})=>{
  test.setTimeout(90000);const session=await create(request,'C4流式与连发');await request.delete(`${fake}/__test__/requests`);await enter(page,session.session_id);
  await send(page,'【角色慢流】第一组');
  const preview=page.locator('[data-testid="character-message-row"][data-temporary="true"]').first();await expect(preview).toBeVisible();
  const key=await preview.getAttribute('data-message-id');const handle=await preview.elementHandle();
  await send(page,'排队输入甲');await send(page,'排队输入乙');
  await expect(page.getByTestId('character-user-message')).toHaveCount(3);
  await expect.poll(async()=> (await detail(request,session.session_id)).busy_group,{timeout:45000}).toBeNull();
  await expect(page.getByTestId('character-ai-message')).toHaveCount(4);
  expect(await handle.evaluate(el=>el.isConnected)).toBeTruthy();await expect(page.locator(`[data-message-id="${key}"]`)).toHaveAttribute('data-temporary','false');
  const calls=await records(request);expect(calls).toHaveLength(2);expect(JSON.parse(calls[1].user).current_user_messages.map(m=>m.content)).toEqual(['排队输入甲','排队输入乙']);
  expect(await page.getByTestId('character-ai-message').allTextContents()).not.toEqual(expect.arrayContaining([expect.stringContaining('ledger_ops')]));
  await page.getByRole('button',{name:'会话资料',exact:true}).click();
  const stream=page.getByTestId('character-delivery'),gaps=page.getByTestId('character-bubble-gaps');await expect(stream).toBeChecked();await gaps.check();await expect(stream).not.toBeChecked();await gaps.uncheck();await expect(stream).not.toBeChecked();await stream.check();await expect(gaps).not.toBeChecked();
  await page.getByRole('button',{name:'关闭资料'}).click();await page.screenshot({path:'../build/e2e-results/character-c4-wide.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.getByTestId('character-history').evaluate(el=>el.scrollWidth<=el.clientWidth)).toBeTruthy();await page.screenshot({path:'../build/e2e-results/character-c4-narrow.png'});
});
test('C4间隔后台送达、未读、重新打开不重播；整批撤回重生成',async({page,request})=>{
  test.setTimeout(60000);const a=await create(request,'C4间隔后台'),b=await create(request,'C4背景切换');await enter(page,a.session_id);
  await page.getByRole('button',{name:'会话资料',exact:true}).click();await page.getByTestId('character-bubble-gaps').check();await page.getByRole('button',{name:'关闭资料'}).click();
  await send(page,'间隔后台测试');await expect(page.getByTestId('character-ai-message')).toHaveCount(1);await expect(page.getByTestId('character-stop')).toHaveCount(0);
  await page.getByTestId(`character-session-${b.session_id}`).click();await expect.poll(async()=> (await detail(request,a.session_id)).busy_group,{timeout:15000}).toBeNull();
  await page.getByRole('button',{name:'刷新列表',exact:true}).click();await expect(page.getByTestId(`character-unread-${a.session_id}`)).toBeVisible();
  await page.getByTestId(`character-session-${a.session_id}`).click();await expect(page.getByTestId('character-ai-message')).toHaveCount(2);await expect(page.locator('[data-temporary="true"]')).toHaveCount(0);
  await expect.poll(async()=> (await detail(request,a.session_id)).unread_count).toBe(0);
  await page.getByRole('button',{name:'会话资料',exact:true}).click();await page.getByTestId('character-bubble-gaps').uncheck();await page.getByRole('button',{name:'关闭资料'}).click();
  page.once('dialog',dialog=>dialog.accept());await page.getByTestId('character-regenerate').click();await expect.poll(async()=> (await detail(request,a.session_id)).revision).toBeGreaterThan(4);await expect(page.getByTestId('character-ai-message')).toHaveCount(2);
  page.once('dialog',dialog=>dialog.accept());await page.getByTestId('character-undo').click();await expect(page.getByTestId('character-ai-message')).toHaveCount(0);await expect(page.getByTestId('character-user-message')).toHaveCount(0);
});
test('C4最终JSON失败不把预览保存为正文或未读，正式输入保留',async({page,request})=>{
  test.setTimeout(60000);const session=await create(request,'C4失败隔离');await enter(page,session.session_id);await send(page,'【C4坏JSON】保留这条输入');
  await expect(page.locator('[data-temporary="true"]')).not.toHaveCount(0);await expect(page.getByTestId('character-error')).toBeVisible({timeout:20000});
  await expect(page.getByTestId('character-ai-message')).toHaveCount(0);await expect(page.getByTestId('character-user-message')).toHaveCount(1);await expect(page.getByTestId('character-composer')).toHaveValue('');
  const saved=await detail(request,session.session_id);expect(saved.messages).toHaveLength(1);expect(saved.unread_count).toBe(0);expect(saved.last_failed_action.status).toBe('failed');
});
