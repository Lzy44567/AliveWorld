import { test, expect } from '@playwright/test';

test('普通字数范围继承、单局修改、重载及实际提示词生效', async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await page.goto('/');
  await page.getByRole('button', { name: '⚙️ 设置', exact: true }).click();
  await page.getByTestId('story-setting-targetStoryLength').fill('1200');
  await page.getByTestId('story-setting-minimumStoryLength').fill('400');
  await page.getByTestId('story-setting-minimumStoryLength').blur();
  await expect(page.getByRole('spinbutton', { name: '最大输出tokens' })).toHaveCount(0);
  await page.getByRole('button', { name: '✕', exact: true }).click();
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill('软字数验收');
  const started = page.waitForResponse(r => r.url().endsWith('/game/start') && r.request().method() === 'POST');
  await page.getByTestId('new-game-submit').click();
  const created = await (await started).json();
  expect(created.story_settings.minimumStoryLength).toBe(400);
  expect(created.story_settings.targetStoryLength).toBe(1200);
  await page.getByTestId('tab-local_edit').click();
  const saved = page.waitForResponse(r => r.url().endsWith('/story_config') && r.request().postDataJSON()?.story_settings.minimumStoryLength === 600);
  await page.getByTestId('story-setting-minimumStoryLength').fill('600');
  await page.getByTestId('story-setting-minimumStoryLength').blur();
  expect((await (await saved).json()).story_settings.minimumStoryLength).toBe(600);
  await request.delete('http://127.0.0.1:18765/__test__/requests');
  await page.getByTestId('story-action-input').fill('观察测试房间');
  await page.getByTestId('story-action-submit').click();
  await expect(page.getByTestId('story-action-submit')).toBeEnabled();
  const calls = (await (await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests;
  expect(calls.some(c => `${c.system}\n${c.user}`.includes('600–1200'))).toBeTruthy();
  await page.getByTestId('tab-saves').click();
  await page.reload();
  await page.locator('[data-save-name="软字数验收"]').getByTestId('save-load').click();
  await page.getByTestId('tab-local_edit').click();
  await expect(page.getByTestId('story-setting-minimumStoryLength')).toHaveValue('600');
  await expect(page.getByTestId('story-setting-targetStoryLength')).toHaveValue('1200');
  await page.screenshot({ path: '../build/stage54-story-range.png' });
  const cleared = page.waitForResponse(r => r.url().endsWith('/story_config') && r.request().postDataJSON()?.story_settings.minimumStoryLength === 0);
  await page.getByTestId('story-setting-minimumStoryLength').fill('');
  await page.getByTestId('story-setting-minimumStoryLength').blur();
  expect((await (await cleared).json()).story_settings.minimumStoryLength).toBe(0);
  await page.getByRole('button', { name: '⚙️ 设置', exact: true }).click();
  await expect(page.getByTestId('story-setting-minimumStoryLength').last()).toHaveValue('400');
  await page.getByRole('button', { name: '✕', exact: true }).click();
  await request.post('/api/v1/lobby/assets/worldbooks/length-isolation', { data: {
    content: '', parsed_data: { name: 'length-isolation', overview: '中性字数隔离测试', entries: [] },
  } });
  await page.getByRole('button', { name: '🧰 工坊' }).click();
  await page.locator('[data-workshop-asset-name="length-isolation"]').click();
  await request.delete('http://127.0.0.1:18765/__test__/requests');
  await page.getByRole('textbox', { name: '工坊消息', exact: true }).fill('AW_REVIEW_BATCH 请给出三个条目草案');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByTestId('workshop-review-proposed').locator('article')).toHaveCount(3);
  const workshopCalls = (await (await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests;
  expect(workshopCalls.length).toBeGreaterThan(0);
  for (const call of workshopCalls) {
    expect(`${call.system}\n${call.user}`).not.toContain('【本回合正文篇幅】');
    expect(`${call.system}\n${call.user}`).not.toContain('600–1200');
  }
});

test('token预算仅在接口高级配置中可编辑并持久保存', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  async function openEditor() {
    await page.getByRole('button', { name: '⚙️ 设置', exact: true }).click();
    await page.getByRole('button', { name: '🔌 接口与模型', exact: true }).click();
    await page.getByRole('button', { name: '⋮', exact: true }).first().click();
    await page.getByRole('button', { name: '编辑', exact: true }).click();
    await expect(page.getByRole('spinbutton', { name: '最大输出tokens' })).toBeHidden();
    await page.getByText('高级：上下文预算', { exact: true }).click();
  }
  await page.goto('/');
  await openEditor();
  const budget = page.getByRole('spinbutton', { name: '最大输出tokens' });
  const oldValue = await budget.inputValue();
  await budget.fill('12000');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(budget).toHaveCount(0);
  await page.reload();
  await openEditor();
  await expect(budget).toHaveValue('12000');
  await expect(page.getByText('此处明确配置的输出上限优先于任务默认值。', { exact: false })).toBeVisible();
  await page.screenshot({ path: '../build/stage54-token-budget.png' });
  await budget.fill(oldValue);
  await page.getByRole('button', { name: '保存', exact: true }).click();
});
