import { test, expect } from '@playwright/test';

test('一次后台请求将新增分到主书知识书与自动书，撤回全部失效', async ({ page, request }) => {
  await request.delete('http://127.0.0.1:18765/__test__/requests');
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await page.goto('/');
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill('归属验收');
  const created = page.waitForResponse(r => r.url().endsWith('/game/start') && r.request().method() === 'POST');
  await page.getByTestId('new-game-submit').click();
  const { session_id } = await (await created).json();
  const base = `/api/v1/game/${session_id}`;
  for (const name of ['归属主书', '归属知识书']) {
    const saved = await request.post(`/api/v1/lobby/assets/worldbooks/${encodeURIComponent(name)}`, { data: {
      content: '', parsed_data: { name, capture_topic: name === '归属主书' ? '基础法令' : '通用技法', entries: [] },
    } });
    expect(saved.ok(), await saved.text()).toBeTruthy();
    expect((await request.post(`${base}/pull_asset`, { data: { asset_type: 'worldbooks', asset_name: name } })).ok()).toBeTruthy();
  }
  await page.getByTestId('tab-world').click();
  await page.getByRole('button', { name: '🛡️ 本局专属', exact: true }).click();
  await page.getByRole('region', { name: '世界书协作' }).getByRole('button', { name: '归属主书 设为主书' }).click();
  const card = page.locator('[data-asset-name="归属知识书"]');
  await card.hover();
  await card.getByRole('button', { name: /微调/ }).click();
  await page.getByText('收录主题（可选）', { exact: true }).click();
  const topic = page.getByTestId('worldbook-capture-topic');
  await expect(topic).toHaveValue('通用技法');
  await topic.fill('通用技法与学徒训练');
  await page.screenshot({ path: '../build/worldbook46-topic.png' });
  await page.getByTestId('asset-editor-save').click();
  await expect(page.getByTestId('asset-editor-save')).toBeHidden();
  await page.getByTestId('story-action-input').fill('【AW_BOOK:routing】确认这些长期设定');
  await page.getByTestId('story-action-submit').click();
  const read = async () => (await (await request.get(`${base}/local_assets`)).json()).worldbooks;
  await expect.poll(async () => (await read()).reduce((n, b) => n + b.entries.length, 0)).toBe(3);
  const books = await read();
  expect(books.find(b => b.name === '归属主书').entries[0].name).toBe('基础法令');
  expect(books.find(b => b.name === '归属知识书').entries[0].name).toBe('通用技法');
  expect(books.find(b => b.name === '归属知识书').capture_topic).toBe('通用技法与学徒训练');
  expect(books.find(b => b.is_auto_capture_book).entries[0].name).toBe('交叉设定');
  const calls = (await (await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests;
  expect(calls.filter(c => c.kind === 'worldbook_capture')).toHaveLength(1);
  expect(calls.find(c => c.kind === 'worldbook_capture').user).toContain('capture_topic');
  await page.screenshot({ path: '../build/worldbook46-routing.png' });
  await page.getByTestId('story-undo').click();
  await expect.poll(async () => (await read()).reduce((n, b) => n + b.entries.length, 0)).toBe(0);
});
