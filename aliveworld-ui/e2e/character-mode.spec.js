import { test, expect } from '@playwright/test';

const fakeBase = 'http://127.0.0.1:18765';
const sessionsBase = '/api/v1/character-sessions';
const cardName = '角色闭环合成卡';

async function dismissStartup(page) {
  await page.waitForTimeout(500);
  const later = page.getByRole('button', { name: '稍后再说' });
  if (await later.isVisible().catch(() => false)) await later.click();
}

async function createCard(page) {
  await page.getByTestId('tab-character').click();
  await page.getByRole('button', { name: '🌐 全局图鉴' }).click();
  await page.getByTestId('asset-new').click();
  const editor = page.getByTestId('asset-editor');
  await editor.getByTestId('asset-name').fill(cardName);
  await editor.getByTestId('asset-description').fill('【AWTEST:角色独立卡】成年合成测试角色，保留本人立场，不替玩家决定。');
  await editor.getByTestId('asset-editor-save').click();
  await expect(editor).toBeHidden();
}

async function records(request) {
  return (await (await request.get(`${fakeBase}/__test__/requests`)).json()).requests.filter(item => item.kind === 'character.reply');
}

async function savedSession(request, title) {
  const list = await (await request.get(sessionsBase)).json();
  const row = list.sessions.find(item => item.title === title);
  expect(row, `persisted session ${title}`).toBeTruthy();
  return (await (await request.get(`${sessionsBase}/${row.session_id}`)).json());
}

test.describe.configure({ mode: 'serial' });

async function enterCharacters(page) {
  await page.goto('/');
  await dismissStartup(page);
  await page.getByTestId('mode-character').click();
  await expect(page.getByTestId('character-workspace')).toBeVisible();
}

async function createSession(page, title, mode = 'messenger') {
  await page.getByTestId('character-new').click();
  await page.getByTestId('character-title').fill(title);
  await page.getByTestId('character-ai-card').selectOption(cardName);
  await page.getByTestId('character-create-mode').selectOption(mode);
  await page.getByTestId('character-create').click();
  await expect(page.getByTestId('character-composer')).toBeVisible();
}

async function send(page, content, preview = true) {
  await page.getByTestId('character-composer').fill(content);
  await page.getByTestId('character-send').click();
  if (preview) await expect(page.getByTestId('character-preview')).toContainText('自动验收角色回复');
  await expect(page.getByTestId('character-preview')).toBeHidden();
}

async function selectSession(page, request, title) {
  const session = await savedSession(request, title);
  await page.getByTestId(`character-session-${session.session_id}`).click();
  await expect(page.getByTestId('character-composer')).toBeVisible();
  return session;
}

test('现有角色卡建立即时聊天，真实预览先于消息与来源账本提交', async ({ page, request }) => {
  await page.goto('/');
  await dismissStartup(page);
  await createCard(page);
  await page.getByTestId('mode-character').click();
  await createSession(page, '角色验收A');
  await request.delete(`${fakeBase}/__test__/requests`);
  await page.getByTestId('character-composer').fill('【角色账本】我喜欢蓝色🙂');
  await page.getByTestId('character-send').click();
  await expect(page.getByTestId('character-preview')).toContainText('自动验收角色回复');
  await expect(page.getByTestId('character-preview')).toContainText('未保存');
  await expect(page.getByTestId('character-ai-message')).toHaveCount(0);
  const pending = await savedSession(request, '角色验收A');
  expect(pending.turns).toHaveLength(0);
  expect(pending.ledger).toHaveLength(0);
  await expect(page.getByTestId('character-preview')).toBeHidden();
  await expect(page.getByTestId('character-ai-message')).toContainText('messenger');
  const persisted = await savedSession(request, '角色验收A');
  expect(persisted.turns).toHaveLength(1);
  expect(persisted.ledger).toHaveLength(1);
  const entry = persisted.ledger[0], message = persisted.turns[0].user_message;
  expect(entry.source.type).toBe('player_statement');
  expect(entry.source.message_ids).toEqual([message.message_id]);
  expect(entry.source.evidence).toEqual([{ message_id: message.message_id, quote: message.content }]);
  expect(entry.visibility.audience_instance_ids).toHaveLength(2);
  const privateResponse = await request.get(`${sessionsBase}/${persisted.session_id}/ledger?view=spoiler`);
  expect(privateResponse.ok()).toBeTruthy();
  const ledgerPayload = await privateResponse.json();
  expect(ledgerPayload.ledger || ledgerPayload.entries).toHaveLength(2);
  await page.getByRole('button', { name: '会话资料', exact: true }).click();
  await expect(page.getByTestId('character-public-ledger')).toContainText('公开记录');
  await expect(page.getByTestId('character-public-ledger')).not.toContainText('内部记录');
  await page.getByTestId('character-public-ledger').getByText('来源证据', { exact: true }).click();
  await expect(page.getByTestId('character-public-ledger')).toContainText(message.content);
  await expect(page.getByTestId('character-public-ledger')).toContainText(message.message_id);
  await page.getByTestId('character-spoiler').click();
  await expect(page.getByTestId('character-private-ledger')).toContainText('内部记录');
  await page.screenshot({ path: '../build/e2e-results/character-wide.png', fullPage: true });
  const calls = await records(request);
  expect(calls).toHaveLength(1);
  expect(calls[0].stream).toBe(true);
  expect(calls[0].user).toContain('角色独立卡');
  expect(calls[0].system).not.toContain('角色独立卡');
});

test('情景扮演与即时聊天共享会话历史，显式非流式与重载保持模式标签', async ({ page, request }) => {
  await enterCharacters(page);
  await createSession(page, '角色验收B', 'roleplay');
  await send(page, '情景消息B');
  await expect(page.getByTestId('character-ai-message')).toContainText('roleplay');
  await page.getByRole('button', { name: '会话资料', exact: true }).click();
  await page.getByTestId('character-mode').selectOption('messenger');
  await expect(page.getByTestId('character-mode')).toHaveValue('messenger');
  await page.getByRole('button', { name: '关闭资料' }).click();
  await page.getByTestId('character-delivery').selectOption('non_stream');
  await send(page, '非流式消息B', false);
  await expect(page.getByTestId('character-ai-message')).toHaveCount(2);
  let persisted = await savedSession(request, '角色验收B');
  expect(persisted.turns.map(turn => turn.mode_at_generation)).toEqual(['roleplay', 'messenger']);
  expect((await records(request)).at(-1).stream).toBe(false);
  await enterCharacters(page);
  persisted = await selectSession(page, request, '角色验收B');
  await expect(page.getByTestId('character-ai-message')).toHaveCount(2);
  await expect(page.getByTestId('character-history')).toContainText('情景消息B');
  await expect(page.getByTestId('character-history')).toContainText('非流式消息B');
  expect(persisted.presentation_mode).toBe('messenger');
});

test('切换会话与故事工坊不取消流，结果和草稿只属于发起会话', async ({ page, request }) => {
  await enterCharacters(page);
  const a = await selectSession(page, request, '角色验收A');
  await page.getByTestId('character-composer').fill('会话A后台完成隔离');
  await page.getByTestId('character-send').click();
  await expect(page.getByTestId('character-preview')).toContainText('自动验收角色回复');
  const b = await selectSession(page, request, '角色验收B');
  await expect(page.getByTestId('character-preview')).toBeHidden();
  await expect(page.getByTestId('character-history')).not.toContainText('会话A后台完成隔离');
  await page.getByTestId('character-composer').fill('会话B保留的草稿');
  await page.getByTestId('mode-story').click();
  await expect(page.getByTestId('character-workspace')).toBeHidden();
  await page.getByRole('button', { name: '🧰 工坊', exact: true }).click();
  await page.getByTestId('mode-character').click();
  await expect(page.getByTestId('character-composer')).toHaveValue('会话B保留的草稿');
  await expect.poll(async () => (await (await request.get(`${sessionsBase}/${a.session_id}`)).json()).turns.length).toBe(2);
  expect((await (await request.get(`${sessionsBase}/${b.session_id}`)).json()).turns).toHaveLength(2);
  await selectSession(page, request, '角色验收A');
  await expect(page.getByTestId('character-ai-message').last()).toContainText('会话A后台完成隔离');
});

test('非法最终JSON清掉预览但保留历史草稿，重生成与撤回同步恢复账本', async ({ page, request }) => {
  await enterCharacters(page);
  await selectSession(page, request, '角色验收A');
  const before = await savedSession(request, '角色验收A');
  await send(page, '【角色坏JSON】故障输入不进入正式历史');
  await expect(page.getByTestId('character-error')).toBeVisible();
  await expect(page.getByTestId('character-composer')).toHaveValue('【角色坏JSON】故障输入不进入正式历史');
  await expect(page.getByTestId('character-ai-message')).toHaveCount(before.turns.length);
  const failed = await savedSession(request, '角色验收A');
  expect(failed.turns).toEqual(before.turns);
  expect(failed.ledger).toEqual(before.ledger);
  page.on('dialog', dialog => dialog.accept());
  await page.getByTestId('character-regenerate').click();
  await expect(page.getByTestId('character-preview')).toBeVisible();
  await expect(page.getByTestId('character-preview')).toBeHidden();
  const regenerated = await savedSession(request, '角色验收A');
  expect(regenerated.turns).toHaveLength(before.turns.length);
  expect(regenerated.turns.at(-1).turn_id).not.toBe(before.turns.at(-1).turn_id);
  await page.getByTestId('character-undo').click();
  await expect(page.getByTestId('character-ai-message')).toHaveCount(1);
  await page.getByTestId('character-undo').click();
  await expect(page.getByTestId('character-ai-message')).toHaveCount(0);
  const undone = await savedSession(request, '角色验收A');
  expect(undone.turns).toHaveLength(0);
  expect(undone.ledger).toHaveLength(0);
  const spoiler = await (await request.get(`${sessionsBase}/${undone.session_id}/ledger?view=spoiler`)).json();
  expect(spoiler.ledger || spoiler.entries).toHaveLength(0);
});

test('停止未完成请求和显式重试失败请求均不留下半轮历史', async ({ page, request }) => {
  await enterCharacters(page);
  await createSession(page, '角色验收C');
  await request.delete(`${fakeBase}/__test__/requests`);
  await send(page, '【角色一次失败】显式重试输入');
  await expect(page.getByTestId('character-error')).toBeVisible();
  await expect(page.getByTestId('character-ai-message')).toHaveCount(0);
  await page.getByTestId('character-retry').click();
  await expect(page.getByTestId('character-preview')).toBeVisible();
  await expect(page.getByTestId('character-preview')).toBeHidden();
  await expect(page.getByTestId('character-ai-message')).toHaveCount(1);
  expect(await records(request)).toHaveLength(2);
  const committed = await savedSession(request, '角色验收C');
  await page.getByTestId('character-composer').fill('【角色慢流】停止请求，不保存这轮输入');
  await page.getByTestId('character-send').click();
  await expect(page.getByTestId('character-preview')).toContainText('自动验收角色回复');
  await page.getByTestId('character-stop').click();
  await expect(page.getByTestId('character-preview')).toBeHidden();
  const stopped = await savedSession(request, '角色验收C');
  expect(stopped.turns).toEqual(committed.turns);
  expect(stopped.ledger).toEqual(committed.ledger);
  await expect(page.getByTestId('character-composer')).toHaveValue('【角色慢流】停止请求，不保存这轮输入');
  await page.waitForTimeout(800);
  expect((await savedSession(request, '角色验收C')).turns).toEqual(committed.turns);
});

test('小屏顶部故事角色工坊三个入口均可见可达', async ({ page, request }) => {
  await page.setViewportSize({ width: 640, height: 900 });
  await page.goto('/');
  await dismissStartup(page);
  for (const id of ['mode-story', 'mode-character']) await expect(page.getByTestId(id)).toBeVisible();
  const workshop = page.getByRole('button', { name: '🧰 工坊', exact: true });
  await expect(workshop).toBeVisible();
  await page.getByTestId('mode-character').click();
  await expect(page.getByTestId('character-workspace')).toBeVisible();
  await page.getByRole('button', { name: '会话列表', exact: true }).click();
  await selectSession(page, request, '角色验收B');
  await page.screenshot({ path: '../build/e2e-results/character-narrow.png', fullPage: true });
  await workshop.click();
  await expect(page.getByTestId('character-workspace')).toBeHidden();
  await page.getByTestId('mode-story').click();
  await expect(page.getByTestId('story-action-input')).toBeVisible();
});
