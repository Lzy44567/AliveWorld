import { test, expect } from '@playwright/test';

test('主次书真实请求识别冲突，本局覆盖可恢复且撤回失效', async ({ page, request }) => {
  await request.delete('http://127.0.0.1:18765/__test__/requests');
  for (const [name, content] of [['协作主书', '验收地区禁止飞行'], ['协作次书', '验收地区允许飞行']]) {
    const saved = await request.post(`/api/v1/lobby/assets/worldbooks/${encodeURIComponent(name)}`, { data: {
      content: '', parsed_data: { name, entries: [{ id: 'same', name: '飞行规则', keys: '飞行', content, tags: ['常驻'] }] },
    } });
    expect(saved.ok(), await saved.text()).toBeTruthy();
  }
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await page.goto('/');
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill('多世界书验收');
  const created = page.waitForResponse(r => r.url().endsWith('/game/start') && r.request().method() === 'POST');
  await page.getByTestId('new-game-submit').click();
  const session = await (await created).json();
  const base = `/api/v1/game/${session.session_id}`;
  for (const name of ['协作主书', '协作次书']) {
    expect((await request.post(`${base}/pull_asset`, { data: { asset_type: 'worldbooks', asset_name: name } })).ok()).toBeTruthy();
  }
  await page.getByTestId('tab-world').click();
  await page.getByRole('button', { name: '🛡️ 本局专属', exact: true }).click();
  const panel = page.getByRole('region', { name: '世界书协作' });
  await expect(panel.getByText('请选择一本主书', { exact: false })).toBeVisible();
  await panel.getByRole('button', { name: '协作主书 设为主书' }).click();
  await expect(panel.getByRole('button', { name: '协作主书 主书', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByTestId('story-action-input').fill('多世界书验收：尝试飞行');
  await page.getByTestId('story-action-submit').click();
  await expect(panel.getByRole('button', { name: /查看冲突记录/ })).toBeVisible({ timeout: 25_000 });
  await panel.getByRole('button', { name: /查看冲突记录/ }).click();
  await expect(panel.getByText('本局已停用', { exact: true })).toBeVisible();
  await panel.getByText('查看双方依据', { exact: true }).click();
  await expect(panel.getByText('次书：验收地区允许飞行', { exact: true })).toBeVisible();
  await page.screenshot({ path: '../build/worldbook45-collaboration.png' });
  await page.getByTestId('story-action-input').fill('多世界书验收：再次检查飞行');
  const second = page.waitForResponse(r => /\/action(?:\/stream)?$/.test(r.url()) && r.request().method() === 'POST');
  await page.getByTestId('story-action-submit').click();
  await second;
  await expect(page.getByTestId('story-action-submit')).toBeEnabled();
  const calls = (await (await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests;
  const settlements = calls.filter(call => call.kind === 'settlement');
  expect(settlements).toHaveLength(2);
  expect(settlements[0].user).toContain('验收地区允许飞行');
  expect(settlements[1].user).not.toContain('验收地区允许飞行');
  const local = await (await request.get(`${base}/local_assets`)).json();
  expect(local.worldbooks.find(book => book.name === '协作次书').entries[0].is_active).not.toBe(false);
  await panel.getByRole('button', { name: '恢复此条', exact: true }).click();
  await expect(panel.getByText('已恢复 / 不再自动停用', { exact: true })).toBeVisible();
  await panel.getByRole('button', { name: '停用此条', exact: true }).click();
  await expect(panel.getByText('本局已停用', { exact: true })).toBeVisible();
  await page.getByTestId('story-undo').click();
  await expect(page.getByTestId('story-action-submit')).toBeEnabled();
  await page.getByTestId('story-undo').click();
  await expect(panel.getByText('来源已变化 · 不再生效', { exact: true })).toBeVisible();
  const state = await (await request.get(`${base}/worldbook-collaboration`)).json();
  expect(state.primary_book).toBe('协作主书');
  expect(state.conflicts[0].current).toBe(false);
});
