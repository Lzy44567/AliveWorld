import { test, expect } from '@playwright/test';

test('局内人设提取预览、独立保存并在全局可见', async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await request.post('/api/v1/lobby/assets/characters/提取来源', { data: { parsed_data: {name:'提取来源',description:'认真负责的测试角色'}, overwrite:true } });
  await page.goto('/');
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', {name:'+ 新局'}).click();
  await page.getByTestId('new-game-name').fill('提取测试');
  await page.getByTestId('new-game-opening').fill('旅人在旧世界的蓝色灯塔旁介绍自己。');
  const response = page.waitForResponse(r => r.url().endsWith('/game/start') && r.request().method()==='POST');
  await page.getByTestId('new-game-submit').click();
  const created = await (await response).json();
  expect((await request.post(`/api/v1/game/${created.session_id}/pull_asset`, {data:{asset_type:'characters',asset_name:'提取来源'}})).ok()).toBeTruthy();
  await page.getByTestId('tab-character').click();
  await page.getByRole('button', {name:'🛡️ 本局专属'}).click();
  await page.getByRole('button', {name:'提取为独立角色卡'}).click();
  const dialog = page.getByRole('dialog', {name:'提取角色卡',exact:true});
  await dialog.getByText('从故事整理人设与经历 · 可选').click();
  await dialog.getByRole('checkbox', {name:/第 .* 回合/}).first().check();
  await dialog.getByRole('checkbox', {name:/允许将选中公开回合/}).check();
  await dialog.getByRole('button', {name:'AI 整理所选回合'}).click();
  await expect(dialog.getByText(/待审说明：仅依据/)).toBeVisible();
  await dialog.getByRole('checkbox', {name:/保存旧世界经历/}).check();
  await dialog.getByRole('textbox', {name:'新卡名称'}).fill('提取结果');
  await dialog.getByRole('checkbox', {name:'已审阅内容，保存为独立角色卡'}).check();
  await dialog.getByRole('button', {name:'保存到全局角色库'}).click();
  await expect(dialog).toBeHidden();
  await page.getByRole('button', {name:'🌐 全局图鉴'}).click();
  await expect(page.locator('[data-asset-name="提取结果"]')).toBeVisible();
  for (const carry of [false, true]) {
    const pulled = await request.post(`/api/v1/game/${created.session_id}/pull_asset`, {data:{
      asset_type:'characters', asset_name:'提取结果', include_experiences:carry,
    }});
    expect(pulled.ok()).toBeTruthy();
    const local = await (await request.get(`/api/v1/game/${created.session_id}/local_assets`)).json();
    const card = local.characters.find(c => c.name==='提取结果');
    expect(card.description.includes('旧世界的蓝色灯塔')).toBe(carry);
    const res = await request.post('/api/v1/character-sessions', {data:{
      client_creation_id: crypto.randomUUID(), ai_asset_ref:{kind:'character',key:'提取结果'},
      presentation_mode:'messenger', include_experiences:carry,
    }});
    expect(res.status()).toBe(201);
    const chat = await res.json();
    const loaded = await request.get(`/api/v1/character-sessions/${chat.session_id}`);
    expect((await loaded.text()).includes('旧世界的蓝色灯塔')).toBe(carry);
  }
  await page.screenshot({path:'../build/character59-global.png'});
});

test('无角色卡人物改名后以同一身份取材并保存', async ({page, request}) => {
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({completed:true})));
  await page.goto('/');
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', {name:'+ 新局'}).click();
  await page.getByTestId('new-game-name').fill('场景人物提取');
  await page.getByTestId('new-game-submit').click();
  for (const action of ['【AW_NPC:init】观察看守', '【AW_NPC:rename】询问名字']) {
    await page.getByTestId('story-action-input').fill(action);
    await page.getByTestId('story-action-submit').click();
    await expect(page.getByTestId('story-action-submit')).toBeEnabled();
  }
  await page.getByTestId('tab-character').click();
  await page.getByRole('button', {name:'🛡️ 本局专属'}).click();
  await page.getByRole('button', {name:'从故事人物提取角色卡'}).click();
  const picker = page.getByRole('dialog', {name:'选择故事人物'});
  await expect(picker.getByRole('button', {name:/阿林/})).toHaveCount(1);
  await picker.getByRole('button', {name:/阿林/}).click();
  const dialog = page.getByRole('dialog', {name:'提取角色卡',exact:true});
  await dialog.getByRole('checkbox', {name:/第 .* 回合/}).first().check();
  await dialog.getByRole('checkbox', {name:/允许将选中公开回合/}).check();
  await dialog.getByRole('button', {name:'AI 整理所选回合'}).click();
  await expect(dialog.getByText(/待审说明：仅依据/)).toBeVisible();
  await dialog.getByRole('textbox', {name:'新卡名称'}).fill('独立阿林');
  await dialog.getByRole('checkbox', {name:'已审阅内容，保存为独立角色卡'}).check();
  await page.screenshot({path:'../build/character59-review.png'});
  await dialog.getByRole('button', {name:'保存到全局角色库'}).click();
  await expect(dialog).toBeHidden();
  await page.getByRole('button', {name:'🌐 全局图鉴'}).click();
  await expect(page.locator('[data-asset-name="独立阿林"]')).toBeVisible();
});
