import { test, expect } from '@playwright/test';

test('局内人设提取预览、独立保存并在全局可见', async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await request.post('/api/v1/lobby/assets/characters/提取来源', { data: { parsed_data: {name:'提取来源',description:'认真负责的测试角色'}, overwrite:true } });
  await page.goto('/');
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', {name:'+ 新局'}).click();
  await page.getByTestId('new-game-name').fill('提取测试');
  const response = page.waitForResponse(r => r.url().endsWith('/game/start') && r.request().method()==='POST');
  await page.getByTestId('new-game-submit').click();
  const created = await (await response).json();
  expect((await request.post(`/api/v1/game/${created.session_id}/pull_asset`, {data:{asset_type:'characters',asset_name:'提取来源'}})).ok()).toBeTruthy();
  await page.getByTestId('tab-character').click();
  await page.getByRole('button', {name:'🛡️ 本局专属'}).click();
  await page.getByRole('button', {name:'提取为独立角色卡'}).click();
  const dialog = page.getByRole('dialog', {name:'提取角色卡',exact:true});
  await dialog.getByRole('textbox', {name:'新卡名称'}).fill('提取结果');
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', {name:'保存到全局角色库'}).click();
  await expect(dialog).toBeHidden();
  await page.getByRole('button', {name:'🌐 全局图鉴'}).click();
  await expect(page.locator('[data-asset-name="提取结果"]')).toBeVisible();
});
