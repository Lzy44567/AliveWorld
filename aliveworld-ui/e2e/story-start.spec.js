import { test, expect } from '@playwright/test';

test('新建故事开场可空，系统引导不入档，自填开场保留', async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await page.goto('/');
  for (const [name, opening] of [['空开场验收', ''], ['作者开场验收', '你站在山间驿站门外，屋内灯光明亮。']]) {
    await page.getByTestId('tab-saves').click();
    await page.getByRole('button', { name: '+ 新局' }).click();
    await page.getByTestId('new-game-name').fill(name);
    await page.getByTestId('new-game-premise').fill('山间驿站测试世界');
    await page.getByTestId('new-game-opening').fill(opening);
    await page.setViewportSize({ width: 900, height: 700 });
    await expect(page.getByTestId('new-game-submit')).toBeInViewport();
    await page.screenshot({ path: '../build/story-start-dialog.png' });
    const created = page.waitForResponse(r => r.url().endsWith('/game/start') && r.request().method() === 'POST');
    await page.getByTestId('new-game-submit').click();
    const result = await (await created).json();
    expect(result.chat_messages.map(m => m.content)).toEqual(opening ? [opening] : []);
    await expect(page.getByTestId('new-game-modal')).toBeHidden();
    if (!opening) await expect(page.getByTestId('story-empty-start')).toBeVisible();
    const loaded = await request.post('/api/v1/game/load', { data: { save_name: name } });
    expect((await loaded.json()).chat_messages).toEqual(result.chat_messages);
  }
});

test('创建前卡片选择复制到局内且源角色不变', async ({ page, request }) => {
  for (const [type, name, data] of [
    ['worldbooks', '开局世界测试', { overview: '山间驿站', axioms: [], entries: [] }],
    ['characters', '开局角色测试', { description: '喜欢探索', is_player: false }],
    ['styles', '开局文风测试', { content: '语言简洁' }],
  ]) {
    const saved = await request.post(`/api/v1/lobby/assets/${type}/${encodeURIComponent(name)}`, { data: { content: '', parsed_data: { name, ...data }, overwrite: false } });
    expect(saved.ok()).toBeTruthy();
  }
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await page.goto('/');
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill('预选资产验收');
  for (const [key, name] of [['worldbook', '开局世界测试'], ['player_character', '开局角色测试'], ['style', '开局文风测试']]) {
    await page.getByTestId(`start-select-${key}`).click();
    const picker = page.getByTestId('asset-card-picker');
    await picker.getByTestId('asset-picker-search').fill(name);
    await picker.getByRole('button', { name: '选择', exact: true }).click();
    await expect(page.getByTestId(`start-select-${key}`)).toContainText(name);
  }
  const created = page.waitForResponse(r => r.url().endsWith('/game/start') && r.request().method() === 'POST');
  await page.getByTestId('new-game-submit').click();
  const session = await (await created).json();
  const local = await (await request.get(`/api/v1/game/${session.session_id}/local_assets`)).json();
  expect(local.worldbooks.some(x => x.name === '开局世界测试')).toBeTruthy();
  expect(local.characters.find(x => x.name === '开局角色测试').is_player).toBe(true);
  expect(local.styles.some(x => x.name === '开局文风测试')).toBeTruthy();
});

test('世界包沿用作者开场，切换来源不丢草稿，重名不覆盖', async ({ page, request }) => {
  const name = '开局包独立世界';
  expect((await request.post(`/api/v1/lobby/assets/worldbooks/${encodeURIComponent(name)}`, { data: { content: '', parsed_data: { name, overview: '海边灯塔', axioms: [], entries: [] } } })).ok()).toBeTruthy();
  const exported = await request.post('/api/v1/world-packages/authoring/export', { data: {
    name: '开局世界包验收', author: '自动测试', version: '1.0.0',
    assets: [{ type: 'worldbooks', name }], world_premise: '海边灯塔世界',
    opening: '灯塔的光扫过夜海。', experience_preset: { defaults: { aiSuggestions: false } },
  } });
  expect(exported.ok(), await exported.text()).toBeTruthy();
  const archive = await request.get((await exported.json()).download_url);
  expect((await request.post('/api/v1/world-packages/import', { data: await archive.body(), headers: { 'Content-Type': 'application/octet-stream' } })).ok()).toBeTruthy();
  await page.addInitScript(() => localStorage.setItem('aw_onboarding_v1', JSON.stringify({ completed: true })));
  await page.goto('/');
  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill('包开局验收');
  await page.getByTestId('new-game-opening').fill('自行设置草稿');
  async function choosePackage() {
    await page.getByRole('button', { name: '选择已安装的世界包' }).click();
    await page.getByRole('button', { name: '开局世界包验收 v1.0.0' }).click();
  }
  await choosePackage();
  await page.getByRole('button', { name: '改为自行设置' }).click();
  await expect(page.getByTestId('new-game-opening')).toHaveValue('自行设置草稿');
  await choosePackage();
  const created = page.waitForResponse(r => r.url().includes('/world-packages/') && r.url().endsWith('/start'));
  await page.getByTestId('new-game-submit').click();
  const session = await (await created).json();
  expect(session.chat_messages.map(m => m.content)).toEqual(['灯塔的光扫过夜海。']);
  expect(session.story_settings.aiSuggestions).toBe(false);
  await expect(page.getByTestId('new-game-modal')).toBeHidden();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill('包开局验收');
  await page.getByTestId('new-game-opening').fill('不能覆盖原故事');
  await page.getByTestId('new-game-submit').click();
  await expect(page.getByTestId('new-game-opening')).toHaveValue('不能覆盖原故事');
  const loaded = await (await request.post('/api/v1/game/load', { data: { save_name: '包开局验收' } })).json();
  expect(loaded.chat_messages).toEqual(session.chat_messages);
});
