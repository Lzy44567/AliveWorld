import { test, expect } from '@playwright/test';

test('阅读面积、配置不挤压、嵌套展开和草稿保留', async ({ page, request }) => {
  await request.post('/api/v1/lobby/assets/worldbooks/layout-test', { data: {
    content: '', parsed_data: { name: 'layout-test', overview: '中性布局测试', entries: [] },
  } });
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await page.goto('/');
  await page.getByRole('button', { name: '🧰 工坊' }).click();
  await page.locator('[data-workshop-asset-name="layout-test"]').click();
  const input = page.getByRole('textbox', { name: '工坊消息', exact: true });
  await input.fill('AW_REVIEW_BATCH 请给出三个条目草案');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByTestId('workshop-review-proposed').locator('article')).toHaveCount(3);
  await expect(page.getByTestId('workshop-stream-preview')).toBeHidden();
  await input.fill('尚未发送的草稿');
  const main = page.getByTestId('workshop-main'), reading = page.getByTestId('workshop-conversation');
  for (const [width, height] of [[1440, 900], [1280, 720], [900, 720]]) {
    await page.setViewportSize({ width, height });
    for (const focused of [false, true]) {
      if (focused) await page.getByTestId('workshop-focus-toggle').click();
      const box = await reading.boundingBox(), total = await main.boundingBox();
      expect(box.height / total.height).toBeGreaterThanOrEqual(0.60);
      console.log(`reading ${width}x${height} focused=${focused}: ${(100 * box.height / total.height).toFixed(1)}%`);
      await expect(input).toBeInViewport();
      await page.getByTestId('workshop-settings-toggle').click();
      await expect(page.getByTestId('workshop-settings')).toBeVisible();
      expect((await reading.boundingBox()).height).toBe(box.height);
      await page.keyboard.press('Escape');
      await expect(page.getByTestId('workshop-settings')).toBeHidden();
      await expect(page.getByTestId('workshop-focus-toggle')).toHaveAttribute('aria-pressed', String(focused));
      await expect(input).toHaveValue('尚未发送的草稿');
      await page.screenshot({ path: `../build/layout52-${width}-${height}-${focused}.png` });
      if (focused) await page.keyboard.press('Escape');
    }
  }
  await page.getByRole('button', { name: '选择资产', exact: true }).click();
  await expect(page.locator('[data-workshop-asset-name="layout-test"]')).toBeVisible();
  await page.getByRole('button', { name: '收起资产', exact: true }).click();
  await page.getByRole('button', { name: '查看草稿', exact: true }).click();
  await expect(page.getByTestId('workshop-draft-sidebar')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('workshop-draft-sidebar')).toBeHidden();
  await page.getByTestId('workshop-settings-toggle').click();
  const brief = page.getByTestId('workshop-creative-brief');
  await brief.locator('summary').click();
  await brief.getByRole('textbox', { name: '创作目标', exact: true }).fill('未保存目标');
  await brief.getByTestId('expand-textarea').click();
  await page.getByRole('textbox', { name: '创作目标（大屏编辑）' }).fill('大屏编辑未保存目标');
  await page.screenshot({ path: '../build/layout52-expanded.png' });
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('expanded-textarea-dialog')).toBeHidden();
  await expect(page.getByTestId('workshop-settings')).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByTestId('workshop-focus-toggle').click();
  await page.getByTestId('workshop-settings-toggle').click();
  await expect(brief.getByRole('textbox', { name: '创作目标', exact: true })).toHaveValue('大屏编辑未保存目标');
  await expect(page.getByTestId('workshop-stream-toggle')).toBeVisible();
  await page.screenshot({ path: '../build/layout52-settings.png' });
});
