import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';
const base='/api/v1/character-sessions', card='C5浏览器合成角色';
async function create(request,title,version=2) {
  await request.post(`/api/v1/lobby/assets/characters/${encodeURIComponent(card)}`,{data:{parsed_data:{name:card,description:'成年合成角色，仅用于主动联系隔离验收。'},overwrite:true}});
  const response=await request.post(base,{data:{client_creation_id:randomUUID(),schema_version:version,title,ai_asset_ref:{kind:'character',key:card},presentation_mode:'messenger'}});
  expect(response.ok()).toBeTruthy();return response.json();
}
async function enter(page,sid) {
  await page.goto('/');const later=page.getByRole('button',{name:'稍后再说'});if(await later.isVisible().catch(()=>false))await later.click();
  await page.getByTestId('mode-character').click();await page.getByTestId(`character-session-${sid}`).click();await expect(page.getByTestId('character-composer')).toBeVisible();
}
async function panel(page) {await page.getByRole('button',{name:'会话资料',exact:true}).click();await page.getByTestId('character-details-settings').click();await page.getByTestId('character-proactive-panel').locator('summary').first().click();}
async function detail(request,sid) {return(await request.get(`${base}/${sid}`)).json();}
test.describe.configure({mode:'serial'});
test('C5当前会话授权、真实无输入主动组、编辑节流、撤回与宽窄设置',async({page,request})=>{
  test.setTimeout(90000);
  const session=await create(request,'C5主动联系真实UI');await enter(page,session.session_id);await panel(page);
  const enabled=page.getByTestId('character-proactive-enabled');await expect(enabled).not.toBeChecked();
  page.once('dialog',d=>d.accept());await enabled.check();await expect(enabled).toBeChecked();
  await expect(page.getByTestId('character-proactive-state')).toContainText('等待下一条');
  await page.getByTestId('character-proactive-idle').fill('1');await page.getByTestId('character-proactive-max').fill('1');await page.getByTestId('character-proactive-save').click();
  await expect.poll(async()=> (await(await request.get(`${base}/${session.session_id}/proactive`)).json()).settings.idle_seconds).toBe(60);
  const activities=[];page.on('request',r=>{if(r.url().endsWith(`/${session.session_id}/activity`))activities.push(r.postDataJSON());});
  await page.getByRole('button',{name:'关闭资料'}).click();await page.getByTestId('character-composer').fill('【C5联系】开始周期');await page.getByTestId('character-composer').fill('【C5联系】开始周期，先正常聊');
  await expect.poll(()=>activities.length).toBe(1);expect(Object.keys(activities[0])).toEqual(['client_id']);
  await page.getByTestId('character-send').click();await expect(page.getByTestId('character-composer')).toHaveValue('');
  // Test server injects a fast clock; production still requires legal idle settings.
  await expect.poll(async()=> (await detail(request,session.session_id)).groups.some(g=>g.origin==='proactive'),{timeout:65000}).toBeTruthy();
  await expect(page.getByTestId('character-proactive-label')).toBeVisible();
  const saved=await detail(request,session.session_id), contact=saved.groups.find(g=>g.origin==='proactive');expect(contact.input_ids).toEqual([]);
  await expect(page.getByTestId('character-user-message')).toHaveCount(1);await expect(page.getByTestId('character-regenerate')).toHaveCount(0);await expect(page.getByTestId('character-retry')).toHaveCount(0);
  page.once('dialog',d=>d.accept());await page.getByTestId('character-undo').click();await expect(page.getByTestId('character-proactive-label')).toHaveCount(0);await expect(page.getByTestId('character-user-message')).toHaveCount(1);
  await panel(page);await expect(enabled).toBeChecked();await page.getByTestId('character-proactive-pause').click();await expect(page.getByTestId('character-proactive-state')).toContainText('已暂停');
  await page.screenshot({path:'../build/e2e-results/character-c5-wide.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.getByTestId('character-proactive-panel').evaluate(el=>el.scrollWidth<=el.clientWidth)).toBeTruthy();await page.screenshot({path:'../build/e2e-results/character-c5-narrow.png'});
  await enabled.uncheck();await expect(enabled).not.toBeChecked();
});
test('C5旧会话说明不提供隐式升级或开启',async({page,request})=>{
  const old=await create(request,'C5旧会话',1);await enter(page,old.session_id);await panel(page);
  await expect(page.getByTestId('character-proactive-unsupported')).toContainText('不会自动转换');await expect(page.getByTestId('character-proactive-enabled')).toHaveCount(0);
  expect(await detail(request,old.session_id)).toEqual(old);
});

test('C5列表批量开启关闭、旧会话禁选与免打扰保存',async({page,request})=>{
  const first=await create(request,'C5批量甲'),second=await create(request,'C5批量乙'),old=await create(request,'C5批量旧格式',1);
  await enter(page,first.session_id);await page.getByTestId('character-session-search').fill('C5批量');
  await page.getByTestId('character-contact-manage').click();
  await expect(page.getByTestId(`character-contact-select-${old.session_id}`)).toBeDisabled();
  await page.getByTestId('character-contact-select-all').click();
  await expect(page.getByTestId('character-contact-batch-enable')).toContainText('2');
  page.once('dialog',d=>d.accept());await page.getByTestId('character-contact-batch-enable').click();
  await expect(page.getByTestId('character-contact-batch-results')).toContainText('已保存');
  for(const item of [first,second])expect((await(await request.get(`${base}/${item.session_id}/proactive`)).json()).settings.enabled).toBe(true);
  const future=await create(request,'C5新建仍默认关闭');expect((await(await request.get(`${base}/${future.session_id}/proactive`)).json()).settings.enabled).toBe(false);
  await panel(page);await page.getByTestId('character-quiet-enabled').check();
  await page.getByTestId('character-quiet-start').fill('22:00');await page.getByTestId('character-quiet-end').fill('08:00');await page.getByTestId('character-quiet-save').click();
  await expect.poll(async()=> (await(await request.get(`${base}/${first.session_id}/proactive`)).json()).settings.quiet_hours).toEqual({enabled:true,start:'22:00',end:'08:00'});
  await page.screenshot({path:'../build/e2e-results/character-c5-batch-wide.png'});
  await page.getByRole('button',{name:'关闭资料'}).click();
  await page.getByTestId('character-contact-select-all').click();await page.getByTestId('character-contact-batch-disable').click();
  await expect.poll(async()=> (await(await request.get(`${base}/${second.session_id}/proactive`)).json()).settings.enabled).toBe(false);
  await expect(page.getByTestId('character-contact-batch-results')).toContainText('已保存');
  await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'会话列表',exact:true}).click();
  await expect(page.getByTestId('character-contact-batch')).toBeVisible();await page.screenshot({path:'../build/e2e-results/character-c5-batch-narrow.png'});
});
