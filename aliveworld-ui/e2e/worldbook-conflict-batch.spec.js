import { test, expect } from '@playwright/test';

test('批量审阅：部分停用、全部待审保留、全部恢复且原书不变', async ({ page, request }) => {
  await request.delete('http://127.0.0.1:18765/__test__/requests');
  const names = ['批量主书', '批量次书甲', '批量次书乙'];
  for (const [index, name] of names.entries()) {
    const result = await request.post(`/api/v1/lobby/assets/worldbooks/${encodeURIComponent(name)}`, { data: {
      content: '', parsed_data: { name, entries: [{ id: 'same', name: '飞行规则', keys: '飞行', content: index ? '验收地区允许飞行' : '验收地区禁止飞行', tags: ['常驻'] }] },
    } });
    expect(result.ok()).toBeTruthy();
  }
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await page.goto('/');
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill('多世界书验收批量');
  const created = page.waitForResponse(r => r.url().endsWith('/game/start') && r.request().method() === 'POST');
  await page.getByTestId('new-game-submit').click();
  const { session_id } = await (await created).json();
  const base = `/api/v1/game/${session_id}`;
  for (const name of names) expect((await request.post(`${base}/pull_asset`, { data: { asset_type: 'worldbooks', asset_name: name } })).ok()).toBeTruthy();
  await page.getByTestId('tab-world').click();
  await page.getByRole('button', { name: '🛡️ 本局专属', exact: true }).click();
  const panel = page.getByRole('region', { name: '世界书协作' });
  await panel.getByRole('button', { name: '批量主书 设为主书' }).click();
  await panel.getByText('冲突处理设置', { exact: true }).click();
  await panel.getByLabel('新冲突先由我逐条确认').check();
  await expect(panel.getByLabel('新冲突先由我逐条确认')).toBeEnabled();
  await page.getByTestId('story-action-input').fill('多世界书验收：尝试飞行');
  await page.getByTestId('story-action-submit').click();
  await panel.getByRole('button', { name: /查看冲突记录/ }).click({ timeout: 25000 });
  await expect(panel.getByText('待你处理', { exact: true })).toHaveCount(2);
  await expect(panel.getByTestId('worldbook-conflict-batch')).toContainText('已选 0 条');
  await panel.getByRole('checkbox', { name: /选择冲突 批量次书甲/ }).check();
  await panel.getByRole('button', { name: '停用选中', exact: true }).click();
  await expect(panel.getByText('本局已停用', { exact: true })).toHaveCount(1);
  await panel.getByLabel('仅看待审').check();
  await panel.getByRole('button', { name: '全选待审（1）', exact: true }).click();
  await panel.getByRole('button', { name: '保留/恢复选中', exact: true }).click();
  await expect(panel.getByText('没有待审冲突。')).toBeVisible();
  await panel.getByLabel('仅看待审').uncheck();
  for (const choice of await panel.getByRole('checkbox', { name: /选择冲突/ }).all()) await choice.check();
  await panel.getByRole('button', { name: '保留/恢复选中', exact: true }).click();
  await expect(panel.getByText('已恢复 / 不再自动停用', { exact: true })).toHaveCount(2);
  await panel.getByText('查看双方依据', { exact: true }).first().click();
  await page.screenshot({ path: '../build/worldbook48-batch.png' });
  const local = await (await request.get(`${base}/local_assets`)).json();
  for (const name of names) expect(local.worldbooks.find(b => b.name === name).entries[0].is_active).not.toBe(false);
  const calls = (await (await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests;
  expect(calls.filter(c => c.kind === 'settlement')).toHaveLength(1);
});
