import { test, expect } from '@playwright/test';

async function setup(page) {
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await page.goto('/');
}
async function expand(page) {
  const panel = page.getByTestId('generation-recovery');
  await expect(panel).toContainText('1 份本地残稿');
  await panel.locator(':scope > summary').click();
  await page.getByTestId('recovery-item').locator('summary').click();
  await expect(page.getByTestId('recovery-text')).toContainText('Recovered neutral text');
  return panel;
}
for (const streaming of [false, true]) {
  test(`故事真实${streaming ? '流式' : '非流式'}截断恢复、重载、保护输入和删除`, async ({ page, request }) => {
    await setup(page);
    const name = `恢复组-${streaming}`;
    await page.getByTestId('tab-saves').click();
    await page.getByRole('button', { name: '+ 新局' }).click();
    await page.getByTestId('new-game-name').fill(name);
    await page.getByTestId('new-game-submit').click();
    await page.getByTestId('story-stream-toggle').setChecked(streaming);
    const input = page.getByTestId('story-action-input');
    await input.fill('AW_RECOVERY_LENGTH 观察花园');
    await page.getByTestId('story-action-submit').click();
    const panel = await expand(page);
    await expect(panel).toContainText('输出额度不足');
    await input.fill('不要覆盖的新草稿');
    await panel.getByRole('button', { name: '原请求放回输入框' }).click();
    await expect(input).toHaveValue('不要覆盖的新草稿');
    await input.fill('');
    await panel.getByRole('button', { name: '原请求放回输入框' }).click();
    await expect(input).toHaveValue('AW_RECOVERY_LENGTH 观察花园');
    const download = page.waitForEvent('download');
    await panel.getByRole('button', { name: '导出文本' }).click();
    expect((await download).suggestedFilename()).toMatch(/残稿.*txt$/);
    await panel.getByRole('button', { name: '复制内容' }).click();
    await expect(page.getByText('内容已复制', { exact: true })).toBeVisible();
    const loaded = await request.post('/api/v1/game/load', { data: { save_name: name } });
    expect(JSON.stringify(await loaded.json())).not.toContain('Recovered neutral text');
    await page.reload();
    await page.getByTestId('tab-saves').click();
    await page.locator(`[data-save-name="${name}"]`).getByTestId('save-load').click();
    await expand(page);
    await page.screenshot({ path: `../build/recovery55-story-${streaming}.png` });
    await input.fill('正常观察花园');
    await page.getByTestId('story-action-submit').click();
    await expect(page.getByTestId('story-action-submit')).toBeEnabled();
    await expect(panel).toContainText('1 份本地残稿');
    page.once('dialog', dialog => dialog.accept());
    await panel.getByRole('button', { name: '删除残稿' }).click();
    await expect(panel).toHaveCount(0);
  });
}

test('服务商过滤后不展示也不保存收到的流式残片', async ({ page }) => {
  await setup(page);
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill('过滤隔离验收');
  await page.getByTestId('new-game-submit').click();
  await page.getByTestId('story-action-input').fill('AW_RECOVERY_FILTER 观察花园');
  await page.getByTestId('story-action-submit').click();
  await expect(page.getByTestId('story-action-submit')).toBeEnabled();
  await expect(page.getByTestId('story-stream-preview')).toHaveCount(0);
  await expect(page.getByTestId('generation-recovery')).toHaveCount(0);
  await expect(page.getByText(/content_filter:/).first()).toBeVisible();
});
for (const [type, label, streaming] of [['worldbooks', '世界书', false], ['characters', '角色卡', true], ['styles', '文风卡', false], ['entities', '实体卡', true], ['preferences', '偏好卡', false]]) {
  test(`${label}真实格式错误保留残稿、跨新轮重载且不修改资产`, async ({ page, request }) => {
    const name = `恢复组-${type}`;
    if (type !== 'preferences') await request.post(`/api/v1/lobby/assets/${type}/${encodeURIComponent(name)}`, { data: {
      content: '', parsed_data: { name, description: '原角色', content: '原文风', motive: '原动机', overview: '原概述', entries: [] },
    } });
    await setup(page);
    async function open() {
      await page.getByRole('button', { name: '🧰 工坊' }).click();
      await page.getByRole('button', { name: new RegExp(label) }).last().click();
      if (type === 'preferences') await page.getByRole('button', { name: /我的用户偏好卡/ }).click();
      else await page.locator(`[data-workshop-asset-name="${name}"]`).click();
    }
    await open();
    await page.getByTestId('workshop-settings-toggle').click();
    await page.getByTestId('workshop-stream-toggle').setChecked(streaming);
    await page.getByRole('button', { name: '关闭创作设置' }).click();
    await page.getByRole('textbox', { name: '工坊消息', exact: true }).fill('AW_RECOVERY_FORMAT 说明花园设计');
    await page.getByRole('button', { name: '发送', exact: true }).click();
    await expand(page);
    await expect(page.getByTestId('generation-recovery')).toContainText('回复格式不完整');
    await expect(page.getByTestId('workshop-review-proposed')).toHaveCount(0);
    await page.reload();
    await open();
    const panel = await expand(page);
    await panel.getByRole('button', { name: '原请求放回输入框' }).click();
    await expect(page.getByRole('textbox', { name: '工坊消息', exact: true })).toHaveValue('AW_RECOVERY_FORMAT 说明花园设计');
    if (type === 'worldbooks') await page.screenshot({ path: '../build/recovery55-workshop.png' });
    page.once('dialog', dialog => dialog.accept());
    await panel.getByRole('button', { name: '删除残稿' }).click();
    await expect(panel).toHaveCount(0);
  });
}
