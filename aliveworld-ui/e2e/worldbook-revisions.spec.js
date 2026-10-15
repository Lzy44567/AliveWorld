import { test, expect } from '@playwright/test';

test('世界书捕获、自动修订废止、撤回和批量审阅', async ({ page, request }) => {
  await page.goto('/');
  await page.waitForTimeout(500);
  const later = page.getByRole('button', { name: '稍后再说' });
  if (await later.isVisible()) await later.click();
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill('世界书修订验收');
  const creation = page.waitForResponse(r => r.url().endsWith('/game/start') && r.request().method() === 'POST');
  await page.getByTestId('new-game-submit').click();
  const id = (await (await creation).json()).session_id;
  async function book() { return (await (await request.get(`/api/v1/game/${id}/local_assets`)).json()).worldbooks[0]; }
  async function send(tag) {
    await page.getByTestId('story-action-input').fill(`【AW_BOOK:${tag}】法令`);
    await page.getByTestId('story-action-submit').click();
    await expect(page.getByTestId('story-action-submit')).toBeEnabled();
  }
  await send('init');
  await expect.poll(async () => (await book()).entries[0]?.content).toBe('蓝灯时通行');
  const originalId = (await book()).entries[0].id;
  await send('update');
  await expect.poll(async () => (await book()).entries[0]?.content).toBe('绿灯时通行');
  expect((await book()).entries[0].id).toBe(originalId);
  await send('retire');
  await expect.poll(async () => (await book()).entries[0]?.is_active).toBe(false);
  expect((await request.post(`/api/v1/game/${id}/undo`)).ok()).toBeTruthy();
  expect((await book()).entries[0].is_active).toBe(true);
  expect((await request.post(`/api/v1/game/${id}/undo`)).ok()).toBeTruthy();
  expect((await book()).entries[0].content).toBe('蓝灯时通行');
  await request.post(`/api/v1/game/${id}/story_config`, { data: { world_premise: '', plot_compass: '', story_settings: { worldbookCaptureReview: true, entitiesEnabled: false } } });
  await send('manual');
  await expect.poll(async () => (await book()).entries.filter(e => e.tags.includes('待确认')).length).toBe(2);
  await page.getByTestId('tab-world').click();
  await page.getByRole('button', { name: '🛡️ 本局专属' }).click();
  await page.locator('[data-asset-name="本局自动设定"]').getByRole('button', { name: '✏️ 微调' }).click();
  const editor = page.getByTestId('asset-editor');
  await expect(editor.getByTestId('worldbook-review-toolbar')).toContainText('待审 2 项');
  await editor.getByRole('checkbox', { name: '选择候选 候选1' }).check();
  await editor.getByRole('button', { name: '接受选中', exact: true }).click();
  await expect(editor.getByTestId('worldbook-review-toolbar')).toContainText('待审 1 项');
  await page.screenshot({ path: '../build/worldbook-review.png', fullPage: true });
  await editor.getByRole('button', { name: '全部拒绝', exact: true }).click();
  await expect(editor.getByTestId('worldbook-review-toolbar')).toHaveCount(0);
  expect((await book()).entries.map(e => e.name)).toEqual(['验收法令', '候选1']);
  expect((await request.post(`/api/v1/game/${id}/undo`)).ok()).toBeTruthy();
  expect((await book()).entries.map(e => e.name)).toEqual(['验收法令']);
});
