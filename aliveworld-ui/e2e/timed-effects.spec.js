import { test, expect } from '@playwright/test';

async function createStory(page, name) {
  await page.goto('/');
  await page.waitForTimeout(500);
  const later = page.getByRole('button', { name: '稍后再说' });
  if (await later.isVisible()) await later.click();
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill(name);
  await page.getByTestId('new-game-premise').fill('合成效果测试，每轮十秒；生命归零中断，绝不读取游玩存档。');
  const created = page.waitForResponse(r => r.url().endsWith('/game/start') && r.request().method() === 'POST');
  await page.getByTestId('new-game-submit').click();
  return (await (await created).json()).session_id;
}

async function send(page, action) {
  await page.getByTestId('story-action-input').fill(action);
  await page.getByTestId('story-action-submit').click();
  await expect(page.getByTestId('story-action-submit')).toBeEnabled();
}

test('持续效果：真请求、流式正文、余时、重生成、失败、跳月、存取和撤回', async ({ page, request }) => {
  let id = await createStory(page, '持续效果端到端');
  await send(page, '【AW_EFFECT:init】建立中毒场景');
  const buff = page.locator('[data-effect-name="中毒测试"]');
  await expect(buff).toContainText('剩50秒');
  await send(page, '【AW_EFFECT:seconds:15】继续战斗十五秒');
  await expect(buff).toContainText('剩35秒');
  await expect(page.getByText('效果验收：程序生命值95；实际推进15；中断False。')).toBeVisible();
  const reroll = await request.post(`/api/v1/game/${id}/reroll`, { data: { entities_enabled: false } });
  expect(reroll.ok()).toBeTruthy();
  expect((await reroll.json()).state.bars['生命'].current).toBe(95);
  const failed = await request.post(`/api/v1/game/${id}/action`, { data: { action: '【AW_EFFECT:bad】失败请求' } });
  expect(failed.status()).toBe(502);
  await send(page, '【AW_EFFECT:month】逃跑并修炼一个月');
  await expect(buff).toHaveCount(0);
  await expect(page.getByText('效果验收：程序生命值75；实际推进2592000；中断False。')).toBeVisible();
  await page.screenshot({ path: '../build/timed-effects-desktop.png', fullPage: true });
  await page.reload();
  await page.getByTestId('tab-saves').click();
  const load = page.waitForResponse(r => r.url().endsWith('/game/load') && r.request().method() === 'POST');
  await page.locator('[data-save-name="持续效果端到端"]').getByTestId('save-load').click();
  const loaded = await (await load).json();
  id = loaded.session_id;
  expect(loaded.state.bars['生命'].current).toBe(75);
  expect(loaded.state.buffs).toEqual({});
  const undo = await request.post(`/api/v1/game/${id}/undo`);
  expect(undo.ok()).toBeTruthy();
  const restored = await undo.json();
  expect(restored.state.bars['生命'].current).toBe(95);
  expect(restored.state.buffs['中毒测试'].tick_elapsed).toBe(5);
  const records = (await (await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests;
  const month = records.find(r => r.kind === 'settlement' && r.user.includes('【行动】：【AW_EFFECT:month】'));
  expect(month.user).toContain('"current": 75');
  expect(month.user).toContain('runtime.effect_progress');
});

test('临界毒伤在长休前中断并显示剩余效果', async ({ page }) => {
  await createStory(page, '效果临界端到端');
  await send(page, '【AW_EFFECT:init-critical】建立低生命场景');
  await send(page, '【AW_EFFECT:month】尝试修炼一个月');
  await expect(page.getByText('效果验收：程序生命值0；实际推进20；中断True。')).toBeVisible();
  await expect(page.locator('[data-effect-name="中毒测试"]')).toContainText('剩30秒');
  await page.screenshot({ path: '../build/timed-effects-critical.png', fullPage: true });
});
