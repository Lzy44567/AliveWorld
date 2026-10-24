import { test, expect } from '@playwright/test';

const interrupted = route => route.fulfill({ contentType: 'text/event-stream', body:
  'event: delta\ndata: {"text":"The door opened, revealing a quiet room."}\n\n' +
  'event: error\ndata: {"message":"length: 输出预算不足，本轮未保存","code":500}\n\n' });

test('故事失败保留可读残稿但不写入故事', async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await page.goto('/');
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill('残稿验收故事');
  await page.getByTestId('new-game-premise').fill('隔离的合成测试世界');
  await page.getByTestId('new-game-submit').click();
  const input = page.getByTestId('story-action-input');
  await expect(input).toBeVisible();
  await page.route('**/game/**/stream', interrupted);
  await input.fill('观察房间');
  await page.getByTestId('story-action-submit').click();
  await expect(page.getByTestId('story-stream-preview')).toContainText('未完成残稿');
  await expect(page.getByTestId('story-stream-preview')).toContainText('The door opened');
  const loaded = await request.post('/api/v1/game/load', { data: { save_name: '残稿验收故事' } });
  expect(JSON.stringify(await loaded.json())).not.toContain('The door opened');
  await page.screenshot({ path: '../build/dev34-story-recovery.png' });
});

test('工坊失败保留文字并恢复输入', async ({ page, request }) => {
  const name = '残稿验收文风';
  await request.post(`/api/v1/lobby/assets/styles/${encodeURIComponent(name)}`, { data: {
    content: '', parsed_data: { name, content: '原文风' },
  } });
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await page.goto('/');
  await page.getByRole('button', { name: '🧰 工坊' }).click();
  await page.getByRole('button', { name: /文风卡/ }).last().click();
  await page.locator(`[data-workshop-asset-name="${name}"]`).click();
  await page.route('**/asset-workshops/*/chat/stream', interrupted);
  const input = page.locator('textarea[placeholder*="Ctrl+Enter"]');
  await input.fill('中性测试请求');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByTestId('workshop-stream-preview')).toContainText('未完成残稿');
  await expect(input).toHaveValue('中性测试请求');
  await page.screenshot({ path: '../build/dev34-workshop-recovery.png' });
});
