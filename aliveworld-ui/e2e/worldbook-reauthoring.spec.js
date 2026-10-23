import { test, expect } from '@playwright/test';

test('多书参考到定向改写、重开、审阅撤销和发布的完整流程', async ({ page, request }) => {
  await request.delete('http://127.0.0.1:18765/__test__/requests');
  for (const [name, content] of [['再创作目标', '力量来自魔力'], ['再创作参考', '灵力来自山川']]) {
    expect((await request.post(`/api/v1/lobby/assets/worldbooks/${encodeURIComponent(name)}`, { data: {
      content: '', parsed_data: { name, overview: content, entries: [{ id: 'power', name: '力量规则', content }] },
    } })).ok()).toBeTruthy();
  }
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  async function open() {
    await page.getByRole('button', { name: '🧰 工坊', exact: true }).click();
    await page.locator('[data-workshop-asset-name="再创作目标"]').click();
  }
  await page.goto('/'); await open();
  const refs = page.getByTestId('worldbook-reauthoring');
  await refs.locator('summary').click();
  await refs.getByRole('checkbox', { name: '参考 再创作参考', exact: true }).check();
  await refs.getByRole('button', { name: '保存 / 更新参考快照', exact: true }).click();
  await expect(refs.locator('summary')).toContainText('已保存 1 本');
  await page.getByRole('button', { name: '条目 1', exact: true }).click();
  await page.getByRole('button', { name: '让 AI 修改', exact: true }).click();
  await expect(refs).toContainText('定向重写：力量规则');
  await page.reload(); await open();
  await expect(refs).toContainText('定向重写：力量规则');
  await expect(refs.locator('summary')).toContainText('已保存 1 本');
  const input = page.locator('textarea[placeholder*="Ctrl+Enter"]');
  await input.fill('AW_REAUTHOR 请参考其他书改写力量规则');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  const review = page.getByTestId('workshop-review-proposed');
  await expect(review).toContainText('灵力经过魔力转化后才能使用');
  await expect(page.getByTestId('workshop-conversation')).toContainText('参考适配依据就绪');
  await review.getByRole('button', { name: '接受全部', exact: true }).click();
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await page.getByRole('button', { name: '条目 1', exact: true }).click();
  await expect(page.getByTestId('workshop-draft-sidebar')).toContainText('力量来自魔力');
  await input.fill('AW_REAUTHOR 再给出同样的待审修改');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await review.getByRole('button', { name: '接受全部', exact: true }).click();
  await page.getByTestId('workshop-publish').click();
  await expect(page.getByTestId('workshop-new-round')).toBeVisible();
  const source = await (await request.get(`/api/v1/lobby/assets/worldbooks/${encodeURIComponent('再创作参考')}`)).json();
  expect(JSON.stringify(source)).toContain('灵力来自山川');
  expect(JSON.stringify(source)).not.toContain('灵力经过魔力转化');
  await page.getByTestId('workshop-new-round').click();
  await expect(refs.locator('summary')).toContainText('已保存 0 本');
  await expect(refs).not.toContainText('定向重写：');
  await refs.locator('summary').click();
  await refs.getByRole('checkbox', { name: '参考 再创作参考', exact: true }).check();
  await refs.getByRole('button', { name: '保存 / 更新参考快照', exact: true }).click();
  await expect(refs.locator('summary')).toContainText('已保存 1 本');
  await page.getByRole('button', { name: '参考与融合', exact: true }).click();
  await input.fill('AW_REAUTHOR 为目标世界设计兼容桥梁');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(review).toContainText('融合桥梁');
  await page.screenshot({ path: '../build/worldbook50-reauthoring.png' });
  await review.getByRole('button', { name: '拒绝全部', exact: true }).click();
  await refs.getByRole('button', { name: '清空参考', exact: true }).click();
  await expect(refs.locator('summary')).toContainText('已保存 0 本');
  await input.fill('AW_REAUTHOR 确认没有参考');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByTestId('workshop-conversation')).toContainText('未使用参考快照');
  const calls = (await (await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests.filter(c => c.kind === 'workshop');
  expect(calls).toHaveLength(4);
  expect(calls.at(-1).user).not.toContain('【玩家明确选择的参考快照');
});
