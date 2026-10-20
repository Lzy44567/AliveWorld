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
