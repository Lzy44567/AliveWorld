import { test, expect } from '@playwright/test';

for (const [type, label] of [['characters', '角色卡'], ['styles', '文风卡'], ['entities', '实体卡'], ['preferences', '偏好卡']]) {
  test(`${label}部分审阅、重载和发布`, async ({ page, request }) => {
    const name = `部分审阅-${type}`;
    if (type !== 'preferences') {
      const created = await request.post(`/api/v1/lobby/assets/${type}/${encodeURIComponent(name)}`, { data: {
        content: '', parsed_data: { name, description: '测试描述', content: '测试文风', motive: '测试动机', tags: [] },
      } });
      expect(created.ok(), await created.text()).toBeTruthy();
    }
    await page.goto('/');
    const later = page.getByRole('button', { name: '稍后再说' });
    await later.click();
    await page.getByRole('button', { name: '🧰 工坊' }).click();
    await page.getByRole('button', { name: new RegExp(label) }).last().click();
    if (type === 'preferences') await page.getByRole('button', { name: /我的用户偏好卡/ }).click();
    else await page.locator(`[data-workshop-asset-name="${name}"]`).click();
    const brief = page.getByTestId('workshop-creative-brief');
    await page.getByTestId('workshop-settings-toggle').click();
    await brief.locator('summary').click();
    await brief.locator('textarea').fill(`  ${label}持续目标  `);
    await brief.getByRole('button', { name: '保存目标' }).click();
    await expect(brief.getByRole('button', { name: '保存目标' })).toBeDisabled();
    await page.getByRole('button', { name: '关闭创作设置' }).click();
    await page.locator('textarea[placeholder*="Ctrl+Enter"]').fill(`AW_OTHER_REVIEW_${type}`);
    await page.getByRole('button', { name: '发送', exact: true }).click();
    const review = page.getByTestId('workshop-review-proposed');
    await expect(review.locator('article')).toHaveCount(3);
    if (type === 'characters') await page.screenshot({ path: '../build/other-workshop-review.png', fullPage: true });
    await review.locator('article').first().getByRole('checkbox').check();
    await review.getByRole('button', { name: '接受所选', exact: true }).click();
    await expect(review.locator('article')).toHaveCount(2);
    await review.locator('article').first().getByRole('button', { name: '拒绝', exact: true }).click();
    await expect(review.locator('article')).toHaveCount(1);
    await page.reload();
    await later.click();
    await page.getByRole('button', { name: '🧰 工坊' }).click();
    await page.getByRole('button', { name: new RegExp(label) }).last().click();
    if (type === 'preferences') await page.getByRole('button', { name: /我的用户偏好卡/ }).click();
    else await page.locator(`[data-workshop-asset-name="${name}"]`).click();
    await expect(review.locator('article')).toHaveCount(1);
    await expect(review).toContainText('方案丙');
    await page.getByTestId('workshop-settings-toggle').click();
    await brief.locator('summary').click();
    await expect(brief.locator('textarea')).toHaveValue(`${label}持续目标`);
    await page.getByRole('button', { name: '关闭创作设置' }).click();
    await review.getByRole('button', { name: '接受全部', exact: true }).click();
    await expect(review).toBeHidden();
    await page.getByTestId('workshop-publish').click();
    await expect(page.getByTestId('workshop-conversation')).toContainText('已保存发布检查点');
    await page.getByTestId('workshop-new-round').click();
    await page.getByTestId('workshop-settings-toggle').click();
    await brief.locator('summary').click();
    await expect(brief.locator('textarea')).toHaveValue(type === 'preferences' ? '' : `${label}持续目标`);
  });
}
