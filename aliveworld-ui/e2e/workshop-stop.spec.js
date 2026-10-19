import { test, expect } from '@playwright/test';

test('工坊停止后恢复原输入且不写入会话', async ({ page, request }) => {
  const name = '停止验收文风';
  const created = await request.post(`/api/v1/lobby/assets/styles/${encodeURIComponent(name)}`, { data: {
    content: '', parsed_data: { name, content: '保留原文风' },
  } });
  expect(created.ok()).toBeTruthy();
  await page.goto('/');
  await page.getByRole('button', { name: '稍后再说' }).click();
  await page.getByRole('button', { name: '🧰 工坊' }).click();
  await page.getByRole('button', { name: /文风卡/ }).last().click();
  await page.locator(`[data-workshop-asset-name="${name}"]`).click();
  const input = page.locator('textarea[placeholder*="Ctrl+Enter"]');
  const original = '【停止验收慢流】停止后修改的原始请求';
  await input.fill(original);
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByTestId('workshop-stream-preview')).toBeVisible();
  await page.getByTestId('workshop-stop').click();
  await expect(page.getByTestId('workshop-stop')).toBeHidden();
  await expect(input).toHaveValue(original);
  await expect(page.getByTestId('workshop-conversation')).not.toContainText('本轮讨论已记录');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByTestId('workshop-stream-preview')).toBeVisible();
  await input.fill('我正在写的新草稿');
  await page.getByTestId('workshop-stop').click();
  await expect(page.getByTestId('workshop-stop')).toBeHidden();
  await expect(input).toHaveValue('我正在写的新草稿');
  await page.getByRole('button', { name: '编辑未完成请求' }).click();
  await expect(input).toHaveValue('我正在写的新草稿');
  await input.fill('');
  await page.getByRole('button', { name: '编辑未完成请求' }).click();
  await expect(input).toHaveValue(original);
  await input.fill('修改后的请求');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByTestId('workshop-conversation')).toContainText('本轮讨论已记录');
});
