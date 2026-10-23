import { test, expect } from '@playwright/test';

test('通知设置独立保存：详细默认隐私、授权摘录、关闭后仍捕获', async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await page.goto('/');
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill('通知设置验收');
  const started = page.waitForResponse(r => r.url().endsWith('/game/start') && r.request().method() === 'POST');
  await page.getByTestId('new-game-submit').click();
  const { session_id } = await (await started).json();
  await page.getByTestId('tab-local_edit').click();
  await page.getByTestId('advanced-settings-toggle').check();
  await page.getByText('📚 世界书辅助（高级）', { exact: true }).click();
  async function setting(key, value) {
    const saved = page.waitForResponse(r => r.url().endsWith('/story_config') && r.request().method() === 'POST');
    await page.getByTestId(`story-setting-${key}`).setChecked(value);
    const data = await (await saved).json();
    expect(data.story_settings[key]).toBe(value);
  }
  await setting('worldbookCaptureReview', true);
  await setting('worldbookDetailedNotices', true);
  const notice = page.getByTestId('worldbook-activity-notice');
  async function action(text) {
    await page.getByTestId('story-action-input').fill(text);
    await page.getByTestId('story-action-submit').click();
    await expect(page.getByTestId('story-action-submit')).toBeEnabled({ timeout: 25000 });
  }
  await action('【AW_BOOK:manual】法令');
  await expect(notice).toContainText('待审阅', { timeout: 20000 });
  await expect(notice.getByTestId('worldbook-notice-row')).toHaveCount(2);
  expect(await notice.textContent()).not.toContain('候选法令');
  await setting('worldbookNoticeContent', true);
  await expect(notice).toHaveCount(0);
  await action('【AW_BOOK:notice2】下一条法令');
  await expect(notice).toContainText('候选法令', { timeout: 20000 });
  await page.screenshot({ path: '../build/worldbook49-notices.png' });
  await setting('worldbookNoticeContent', false);
  await expect(notice).toHaveCount(0);
  await setting('worldbookNotices', false);
  const base = `/api/v1/game/${session_id}`;
  const before = (await (await request.get(`${base}/worldbook-activity`)).json()).total;
  await action('【AW_BOOK:notice3】静默法令');
  await expect.poll(async () => (await (await request.get(`${base}/worldbook-activity`)).json()).total).toBeGreaterThan(before);
  await expect(notice).toHaveCount(0);
  await setting('worldbookNotices', true);
  await expect(notice).toHaveCount(0);
  await page.getByTestId('tab-saves').click();
  await page.reload();
  await page.locator('[data-save-name="通知设置验收"]').getByTestId('save-load').click();
  await page.getByTestId('tab-local_edit').click();
  await page.getByText('📚 世界书辅助（高级）', { exact: true }).click();
  await expect(page.getByTestId('story-setting-worldbookDetailedNotices')).toBeChecked();
  await expect(page.getByTestId('story-setting-worldbookNoticeContent')).not.toBeChecked();
});
