import { test, expect } from '@playwright/test';

test('从故事筛选设定、重名保护、独立保存并打包到新故事', async ({ page, request }) => {
  await page.addInitScript(() => {
    localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true }));
    localStorage.removeItem('aliveworld.world-package-builder.v1');
  });
  await page.goto('/');
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill('提取来源故事');
  const created = page.waitForResponse(r => r.url().endsWith('/game/start') && r.request().method() === 'POST');
  await page.getByTestId('new-game-submit').click();
  const { session_id } = await (await created).json();
  const book = { name: '游玩成果', overview: '空岛世界', axioms: ['重力恒定'], entries: [
    { id: 'public', name: '飞船', keys: '飞船', content: '飞船以晶石驱动' },
    { id: 'private', name: '私人番外', content: '不分享的经历' },
    { id: 'pending', name: '尚未成立', content: '待审内容', tags: ['待确认'] },
  ] };
  expect((await request.post(`/api/v1/game/${session_id}/assets/worldbooks/${encodeURIComponent(book.name)}`, { data: { parsed_data: book } })).ok()).toBeTruthy();
  expect((await request.post('/api/v1/lobby/assets/worldbooks/提取重名', { data: { content: '', parsed_data: { name: '提取重名', overview: '不能覆盖' } } })).ok()).toBeTruthy();
  const original = await (await request.get(`/api/v1/game/${session_id}/local_assets`)).json();
  await page.getByRole('button', { name: '🧰 工坊', exact: true }).click();
  await page.getByTestId('open-world-package-builder').click();
  const builder = page.getByRole('dialog', { name: '创建世界包', exact: true });
  await builder.getByRole('button', { name: '从当前故事提取世界书', exact: true }).click();
  const panel = page.getByRole('dialog', { name: '提取故事世界书', exact: true });
  await panel.getByRole('button', { name: /游玩成果/ }).click();
  await expect(panel).not.toContainText('尚未成立');
  await panel.getByRole('checkbox', { name: '提取 私人番外', exact: true }).uncheck();
  await panel.getByTestId('extraction-name').fill('提取重名');
  const confirm = panel.getByRole('checkbox', { name: '我已审阅选中内容，确认没有不希望带出的隐私或剧透' });
  await confirm.check();
  await panel.getByRole('button', { name: '保存副本并加入打包', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText('同名');
  await panel.getByTestId('extraction-name').fill('分享空岛');
  await confirm.check();
  await page.screenshot({ path: '../build/worldbook51-extraction.png' });
  await panel.getByRole('button', { name: '保存副本并加入打包', exact: true }).click();
  await expect(panel).toBeHidden();
  await expect(builder.getByTestId('package-builder-asset').filter({ hasText: '分享空岛' }).getByRole('checkbox')).toBeChecked();
  await builder.getByTestId('package-builder-name').fill('空岛分享包');
  await builder.getByPlaceholder('创作者名称').fill('测试作者');
  const exported = page.waitForResponse(r => r.url().endsWith('/authoring/export') && r.request().method() === 'POST');
  await builder.getByTestId('package-builder-export').click();
  const exportResponse = await exported; expect(exportResponse.ok()).toBeTruthy();
  const result = await exportResponse.json();
  const bytes = await (await request.get(result.download_url)).body();
  const installed = await request.post('/api/v1/world-packages/import-and-start?save_name=提取作品新故事', {
    data: bytes, headers: { 'Content-Type': 'application/octet-stream' },
  });
  expect(installed.ok()).toBeTruthy();
  const newGame = await installed.json();
  const newAssets = await (await request.get(`/api/v1/game/${newGame.session_id}/local_assets`)).json();
  const extracted = newAssets.worldbooks.find(b => b.name === '分享空岛');
  expect(extracted.entries).toHaveLength(1);
  expect(extracted.entries[0].content).toBe('飞船以晶石驱动');
  expect(extracted.entries[0].id).not.toBe('public');
  expect(JSON.stringify(newAssets)).not.toContain('不分享的经历');
  const after = await (await request.get(`/api/v1/game/${session_id}/local_assets`)).json();
  expect(after).toEqual(original);
});
