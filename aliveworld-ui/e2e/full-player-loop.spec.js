import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';


const runtimeVersion = readFileSync(new URL('../../VERSION', import.meta.url), 'utf8').trim();


const assetTabs = {
  characters: 'tab-character',
  worldbooks: 'tab-world',
  styles: 'tab-style',
  entities: 'tab-entity',
};

async function openResourceLibrary(page, section = 'images') {
  if (!await page.getByTestId('resource-library').isVisible().catch(() => false)) {
    await page.getByTestId('open-resource-library').click();
  }
  await page.getByTestId(`resource-tab-${section}`).click();
}

async function closeResourceLibrary(page) {
  if (await page.getByTestId('resource-library').isVisible().catch(() => false)) {
    await page.getByTestId('resource-library-close').click();
  }
}

async function openAssetEditor(page, type) {
  await page.getByTestId(assetTabs[type]).click();
  await page.getByRole('button', { name: '🌐 全局图鉴' }).click();
  await page.getByTestId('asset-new').click();
  await expect(page.getByTestId('asset-editor')).toBeVisible();
}


async function createAsset(page, type, name) {
  await openAssetEditor(page, type);
  const editor = page.getByTestId('asset-editor');
  await editor.getByTestId('asset-name').fill(name);
  if (type === 'characters') {
    await editor.getByTestId('asset-description').fill('测试角色卡：【AWTEST:角色卡A】看到本设定应确认角色卡上下文已经载入。');
  } else if (type === 'styles') {
    await editor.getByTestId('asset-content').fill('测试文风：【AWTEST:文风卡A】正文应自然分段，并确认文风上下文已经载入。');
  } else if (type === 'entities') {
    await editor.getByTestId('entity-motive').fill('测试实体：【AWTEST:实体卡A】持续观察自动验收世界。');
  } else if (type === 'worldbooks') {
    await editor.getByText('世界概述', { exact: true }).locator('..').getByRole('textbox').fill(
      '测试世界书：【AWTEST:世界书A】这是自动验收专用世界概述。'
    );
    await editor.getByRole('button', { name: '+ 新增条目' }).click();
    const entryEditor = page.getByRole('heading', { name: '新增世界书条目' }).locator('..').locator('..');
    await entryEditor.getByLabel('条目名称').fill('测试法术条目');
    await entryEditor.getByLabel('触发关键词').fill('测试法术');
    await entryEditor.locator('textarea').fill('测试世界书条目：测试法术会发出蓝光。');
    await entryEditor.getByRole('button', { name: '保存条目' }).click();
  }
  await editor.getByTestId('asset-editor-save').click();
  await expect(editor).toBeHidden();
  await expect(page.locator(`[data-asset-name="${name}"]`)).toBeVisible();
}


async function loadAsset(page, type, name) {
  await page.getByTestId(assetTabs[type]).click();
  await page.getByRole('button', { name: '🌐 全局图鉴' }).click();
  const card = page.locator(`[data-asset-name="${name}"]`);
  await expect(card).toBeVisible();
  await card.getByRole('button', { name: /载入局内/ }).click();
}


async function setLocalAssetEnabled(page, type, name, enabled) {
  await page.getByTestId(assetTabs[type]).click();
  await page.getByRole('button', { name: '🛡️ 本局专属' }).click();
  const card = page.locator(`[data-asset-name="${name}"]`);
  await expect(card).toBeVisible();
  const toggle = card.getByRole('switch');
  if ((await toggle.getAttribute('aria-checked')) !== String(enabled)) await toggle.click();
}


async function dismissStartupPrompt(page) {
  // 首次打开时，快速开始弹窗会在配置与资产检查结束后异步出现。
  // 等待一个很短的稳定窗口，避免测试在弹窗出现前就开始点击底层界面。
  await page.waitForTimeout(500);
  const snooze = page.getByRole('button', { name: '稍后再说' });
  if (await snooze.isVisible().catch(() => false)) {
    await snooze.click();
    await expect(snooze).toBeHidden();
  }
}


async function loadStory(page, name = '自动验收故事') {
  await page.goto('/');
  await dismissStartupPrompt(page);
  await expect(page.getByTestId('tab-character')).toBeVisible();
  await expect(page.getByTestId('open-resource-library')).toBeVisible();
  await page.getByTestId('tab-saves').click();
  const card = page.locator(`[data-save-name="${name}"]`);
  await expect(card).toBeVisible();
  const loadResponse = page.waitForResponse(response =>
    new URL(response.url()).pathname === '/api/v1/game/load' && response.request().method() === 'POST'
  );
  await card.getByTestId('save-load').click();
  const payload = await (await loadResponse).json();
  await expect(page.getByTestId('story-action-input')).toBeEnabled();
  await expect.poll(() => page.locator('#chat-container').evaluate(element => element.scrollHeight - element.scrollTop - element.clientHeight)).toBeLessThan(12);
  return payload;
}


test('前端创建和载入全类资产，正文上下文启停可由假模型验证', async ({ page, request }) => {
  await page.goto('/');
  await dismissStartupPrompt(page);

  await createAsset(page, 'characters', '测试角色卡');
  await createAsset(page, 'worldbooks', '测试世界书');
  await createAsset(page, 'styles', '测试文风');
  await createAsset(page, 'entities', '测试实体');

  await page.getByTestId('tab-saves').click();
  await page.getByRole('button', { name: '+ 新局' }).click();
  await page.getByTestId('new-game-name').fill('自动验收故事');
  await page.getByTestId('new-game-premise').fill('这是隔离的自动验收世界，不读取玩家真实存档。');
  await page.getByTestId('new-game-submit').click();
  await expect(page.getByTestId('new-game-modal')).toBeHidden();

  await page.getByTestId('tab-world').click();
  await page.getByRole('button', { name: '🛡️ 本局专属' }).click();
  await expect(page.locator('[data-asset-name="本局自动设定"]')).toBeVisible();

  await loadAsset(page, 'characters', '测试角色卡');
  await loadAsset(page, 'worldbooks', '测试世界书');
  await loadAsset(page, 'styles', '测试文风');
  await loadAsset(page, 'entities', '测试实体');

  await request.delete('http://127.0.0.1:18765/__test__/requests');
  await page.getByTestId('story-action-input').fill('我施放测试法术。');
  await page.getByTestId('story-action-submit').click();
  await expect(page.getByText('前端正文测试成功。')).toBeVisible();
  await expect(page.getByText('自动测试正文1')).toBeVisible();
  await expect(page.getByText('行动裁定就绪')).toBeVisible();
  await expect(page.getByTestId('runtime-version')).toHaveText(`v${runtimeVersion}`);
  await expect(page.getByText('自动验收阶段')).toBeVisible();
  await expect(page.getByText('第1回合', { exact: true })).toBeVisible();
  await expect(page.getByText('自动验收进度')).toBeVisible();
  await expect(page.getByText('1/5')).toBeVisible();
  await expect(page.getByText('世界书就绪')).toBeVisible();
  await expect(page.getByText('角色卡就绪')).toBeVisible();
  await expect(page.getByText('文风就绪')).toBeVisible();
  await expect(page.getByText('世界书A就绪')).toBeVisible();
  await expect(page.getByText('角色卡A就绪')).toBeVisible();
  await expect(page.getByText('文风卡A就绪')).toBeVisible();

  let records = (await (await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests;
  const settlement = records.find(item => item.kind === 'settlement');
  const overseer = records.find(item => item.kind === 'overseer');
  expect(settlement.system).not.toContain('测试世界书条目');
  expect(settlement.system).not.toContain('测试角色卡');
  expect(settlement.system).not.toContain('测试文风');
  expect(settlement.user).toContain('测试世界书条目');
  expect(settlement.user).toContain('测试角色卡');
  expect(settlement.user).toContain('测试文风');
  expect(settlement.system).toContain('目标约 500 个中文字符');
  expect(overseer.system).not.toContain('测试实体');
  expect(overseer.user).toContain('测试实体');
  expect(overseer.user).toContain('state_after_settlement');
  expect(overseer.user).toContain('自动验收阶段');
  expect(overseer.user).not.toContain('测试文风');
  expect(settlement.markers).toEqual(expect.arrayContaining(['世界书A', '角色卡A', '文风卡A']));
  expect(overseer.markers).toContain('实体卡A');

  const coverage = await (await request.get('http://127.0.0.1:18765/__test__/coverage')).json();
  expect(coverage.markers['世界书A'].settlement).toBe(1);
  expect(coverage.markers['角色卡A'].settlement).toBe(1);
  expect(coverage.markers['文风卡A'].settlement).toBe(1);
  expect(coverage.markers['实体卡A'].overseer).toBe(1);

  await setLocalAssetEnabled(page, 'characters', '测试角色卡', false);
  await setLocalAssetEnabled(page, 'worldbooks', '测试世界书', false);
  await setLocalAssetEnabled(page, 'styles', '测试文风', false);
  await request.delete('http://127.0.0.1:18765/__test__/requests');
  await page.getByTestId('story-action-input').fill('我继续进行第二次自动验收。');
  await page.getByTestId('story-action-submit').click();
  await expect(page.getByText('前端正文测试成功。')).toHaveCount(2);
  await expect(page.getByText('自动测试正文2')).toBeVisible();
  await expect(page.getByText('第2回合', { exact: true })).toBeVisible();
  await expect(page.getByText('2/5')).toBeVisible();

  records = (await (await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests;
  const secondSettlement = records.find(item => item.kind === 'settlement');
  expect(secondSettlement.user).not.toContain('测试世界书条目');
  expect(secondSettlement.user).not.toContain('测试角色卡');
  expect(secondSettlement.user).not.toContain('测试文风');
  expect(secondSettlement.markers).not.toEqual(expect.arrayContaining(['世界书A', '角色卡A', '文风卡A']));
});

test('玩家可导入世界包并一键建立带完整资产的独立故事', async ({ page, request }) => {
  await page.goto('/');
  await dismissStartupPrompt(page);
  await openResourceLibrary(page, 'packages');
  const packagePath = fileURLToPath(new URL('../../build/e2e-runtime/e2e-world.aliveworld', import.meta.url));
  await page.getByTestId('world-package-file').setInputFiles(packagePath);
  await expect(page.getByTestId('world-package-preview')).toContainText('自动验收世界包');
  await page.getByTestId('world-package-preview').locator('input').fill('世界包一键故事');
  await page.getByTestId('world-package-install-start').click();
  await expect(page.locator('[data-save-name="世界包一键故事"]')).toContainText('当前游玩');

  await openResourceLibrary(page, 'packages');
  await page.getByTestId('world-package-manage').click();
  const manager = page.getByRole('dialog', { name: '世界包管理' });
  await expect(manager).toContainText('关联故事 1 个');
  await expect(manager).toContainText('🔒 来源：自动验收世界包');
  await manager.getByRole('button', { name: '✕' }).click();

  await closeResourceLibrary(page);
  await page.getByTestId('tab-world').click();
  await page.getByRole('button', { name: '🛡️ 本局专属' }).click();
  await expect(page.locator('[data-asset-name="世界包测试世界"]')).toBeVisible();
  await request.delete('http://127.0.0.1:18765/__test__/requests');
  await page.getByTestId('story-action-input').fill('验证世界包资产。');
  await page.getByTestId('story-action-submit').click();
  await expect(page.getByText('世界包世界书就绪')).toBeVisible();
  await expect.poll(async () => {
    const coverage = await (await request.get('http://127.0.0.1:18765/__test__/coverage')).json();
    return {
      worldbook: (coverage.markers['世界包世界书']?.settlement || 0) > 0,
      character: (coverage.markers['世界包角色']?.settlement || 0) > 0,
      style: (coverage.markers['世界包文风']?.settlement || 0) > 0,
      entity: (coverage.markers['世界包实体']?.overseer || 0) > 0,
    };
  }).toEqual({ worldbook: true, character: true, style: true, entity: true });
});


test('切换故事不会丢失后台推演，响应只写回发起它的故事', async ({ page }) => {
  await loadStory(page, '自动验收故事');
  await page.route('**/api/v1/game/*/action', async route => {
    const action = JSON.parse(route.request().postData() || '{}').action || '';
    await new Promise(resolve => setTimeout(resolve, action.includes('慢故事') ? 1200 : 150));
    await route.continue();
  });

  await page.getByTestId('story-action-input').fill('慢故事后台并发验收。');
  await page.getByTestId('story-action-submit').click();
  await page.getByTestId('tab-saves').click();
  await expect(page.locator('[data-save-name="自动验收故事"]')).toContainText('推演中');
  await page.locator('[data-save-name="世界包一键故事"]').getByTestId('save-load').click();
  await expect(page.getByTestId('story-action-input')).toBeEnabled();
  await page.getByTestId('story-action-input').fill('快故事后台并发验收。');
  await page.getByTestId('story-action-submit').click();
  await expect(page.getByText('快故事后台并发验收。')).toBeVisible();
  await expect(page.getByTestId('story-action-submit')).toBeEnabled({ timeout: 10_000 });

  await page.getByTestId('tab-saves').click();
  await expect(page.locator('[data-save-name="自动验收故事"]')).toContainText('已完成', { timeout: 10_000 });
  await page.locator('[data-save-name="自动验收故事"]').getByTestId('save-load').click();
  await expect(page.getByText('慢故事后台并发验收。')).toBeVisible();
  await expect(page.getByText('前端正文测试成功。').last()).toBeVisible();
});


test('一个故事失败不会污染另一个故事的成功状态', async ({ page }) => {
  await loadStory(page, '自动验收故事');
  await page.route('**/api/v1/game/*/action', async route => {
    const action = JSON.parse(route.request().postData() || '{}').action || '';
    if (action.includes('故意失败')) {
      await new Promise(resolve => setTimeout(resolve, 500));
      await route.fulfill({ status: 502, contentType: 'application/json', body: JSON.stringify({ detail: '自动验收隔离失败' }) });
    } else await route.continue();
  });
  await page.getByTestId('story-action-input').fill('故意失败的故事请求。');
  await page.getByTestId('story-action-submit').click();
  await page.getByTestId('tab-saves').click();
  await page.locator('[data-save-name="世界包一键故事"]').getByTestId('save-load').click();
  await page.getByTestId('story-action-input').fill('另一个故事应当成功。');
  await page.getByTestId('story-action-submit').click();
  await expect(page.getByTestId('story-action-submit')).toBeEnabled({ timeout: 10_000 });
  await page.getByTestId('tab-saves').click();
  await expect(page.locator('[data-save-name="自动验收故事"]')).toContainText('失败', { timeout: 10_000 });
  await expect(page.locator('[data-save-name="世界包一键故事"]')).toContainText('已完成');
});


test('外部角色卡先显示兼容报告，再导入全局资产库', async ({ page, request }) => {
  const name = '外部兼容测试角色';
  await request.delete(`/api/v1/lobby/assets/characters/${encodeURIComponent(name)}`);
  await page.goto('/');
  await dismissStartupPrompt(page);
  await openResourceLibrary(page, 'packages');
  await page.getByTestId('world-package-manage').click();
  const manager = page.getByRole('dialog', { name: '世界包管理' });
  await manager.getByTestId('import-external-character').click();
  const dialog = page.getByRole('dialog', { name: '导入外部角色卡' });
  await dialog.getByTestId('external-asset-file').setInputFiles({
    name: 'external-card.json',
    mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify({
      spec: 'chara_card_v2', spec_version: '2.0', data: {
        name, description: '外部卡描述', personality: '沉着', first_mes: '她向玩家点头。',
        tags: ['外部测试'], system_prompt: '外部系统提示仅保留', alternate_greetings: ['备用问候'],
      },
    })),
  });
  await expect(dialog.getByText('已原生映射')).toBeVisible();
  await expect(dialog.getByText('降级处理')).toBeVisible();
  await expect(dialog.getByText('仅保留，当前不执行')).toBeVisible();
  await dialog.getByTestId('external-asset-import').click();
  await expect(dialog).toBeHidden();
  await manager.getByRole('button', { name: '✕' }).first().click();
  await closeResourceLibrary(page);
  await page.getByTestId('tab-character').click();
  await page.getByRole('button', { name: '🌐 全局图鉴' }).click();
  await expect(page.locator(`[data-asset-name="${name}"]`)).toBeVisible();
  await request.delete(`/api/v1/lobby/assets/characters/${encodeURIComponent(name)}`);
});


test('正文可用同一行动重试，随后撤回恢复上一状态', async ({ page, request }) => {
  await loadStory(page);
  const storyText = page.getByText('前端正文测试成功。');
  const before = await storyText.count();

  await request.delete('http://127.0.0.1:18765/__test__/requests');
  await page.getByTestId('story-action-input').fill('这是撤回与重试专项行动。');
  await page.getByTestId('story-action-submit').click();
  await expect(storyText).toHaveCount(before + 1);

  await page.getByTestId('story-retry').click();
  await expect.poll(async () => {
    const items = (await (await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests;
    return items.filter(item => item.kind === 'settlement').length;
  }).toBe(2);
  await expect(storyText).toHaveCount(before + 1);
  const records = (await (await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests;
  const settlements = records.filter(item => item.kind === 'settlement');
  expect(settlements).toHaveLength(2);
  expect(settlements[1].user).toContain('这是撤回与重试专项行动');

  await page.getByTestId('story-undo').click();
  await expect(storyText).toHaveCount(before);
});


test('世界书工坊修改先进入草稿，发布后成为正式资产并可重新进入', async ({ page, request }) => {
  await page.goto('/');
  await dismissStartupPrompt(page);
  await page.getByRole('button', { name: '🧰 工坊' }).click();
  const asset = page.locator('[data-workshop-asset-name="测试世界书"]');
  await expect(asset).toBeVisible();
  await asset.click();
  await expect(page.getByText('世界书工坊 · 测试世界书')).toBeVisible();

  const overviewSection = page.locator('section').filter({ hasText: '世界概述' });
  const overview = overviewSection.locator('textarea').first();
  await overview.fill('dev.19 工坊发布专项概述。');
  await expect(page.getByTestId('workshop-publish')).toBeEnabled({ timeout: 10_000 });

  const conversation = page.getByTestId('workshop-conversation');
  await page.locator('textarea[placeholder*="Ctrl+Enter"]').fill('请记录这轮工坊讨论，供发布后回看。');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(conversation).toContainText('请记录这轮工坊讨论，供发布后回看。');

  const before = await (await request.get('/api/v1/lobby/assets/worldbooks/%E6%B5%8B%E8%AF%95%E4%B8%96%E7%95%8C%E4%B9%A6')).json();
  expect(before.parsed.overview).not.toBe('dev.19 工坊发布专项概述。');

  await page.getByTestId('workshop-publish').click();
  await expect(page.getByText('工坊草稿已发布')).toBeVisible();
  await expect(page.getByTestId('workshop-new-round')).toBeVisible();
  const published = await (await request.get('/api/v1/lobby/assets/worldbooks/%E6%B5%8B%E8%AF%95%E4%B8%96%E7%95%8C%E4%B9%A6')).json();
  expect(published.parsed.overview).toBe('dev.19 工坊发布专项概述。');

  await page.getByRole('button', { name: '🎮 游戏' }).click();
  await page.getByRole('button', { name: '🧰 工坊' }).click();
  await page.locator('[data-workshop-asset-name="测试世界书"]').click();
  await expect(page.getByTestId('workshop-conversation')).toContainText('请记录这轮工坊讨论，供发布后回看。');
  await expect.poll(() => page.getByTestId('workshop-conversation').evaluate(
    element => element.scrollHeight - element.scrollTop - element.clientHeight
  )).toBeLessThan(12);

  // A real application reload discards the in-memory published context.  The
  // next selection must project the persisted session back as read-only history.
  await page.reload();
  await dismissStartupPrompt(page);
  await page.getByRole('button', { name: '🧰 工坊' }).click();
  await page.locator('[data-workshop-asset-name="测试世界书"]').click();
  await expect(page.getByTestId('workshop-history')).toContainText('请记录这轮工坊讨论，供发布后回看。');
  await expect(page.locator('section').filter({ hasText: '世界概述' }).locator('textarea').first())
    .toHaveValue('dev.19 工坊发布专项概述。');
});


test('切换工坊对象不会中断回复且结果回到原资产', async ({ page }) => {
  await page.goto('/');
  await dismissStartupPrompt(page);
  await page.route('**/api/v1/asset-workshops/*/chat', async route => {
    const message = JSON.parse(route.request().postData() || '{}').message || '';
    await new Promise(resolve => setTimeout(resolve, message.includes('慢工坊') ? 1100 : 120));
    await route.continue();
  });
  await page.getByRole('button', { name: '🧰 工坊' }).click();
  await page.getByRole('button', { name: /角色卡/ }).last().click();
  const character = page.locator('[data-workshop-asset-name="测试角色卡"]');
  await expect(character).toBeVisible();
  await character.click();
  await page.locator('textarea[placeholder*="Ctrl+Enter"]').fill('慢工坊角色并发验收。');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(character).toContainText('处理中');

  await page.getByRole('button', { name: /文风卡/ }).last().click();
  const style = page.locator('[data-workshop-asset-name="测试文风"]');
  await expect(style).toBeVisible();
  await style.click();
  await page.locator('textarea[placeholder*="Ctrl+Enter"]').fill('快工坊文风并发验收。');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByTestId('workshop-conversation')).toContainText('本轮讨论已记录', { timeout: 10_000 });

  await page.getByRole('button', { name: /角色卡/ }).last().click();
  await expect(character).toContainText('已完成', { timeout: 10_000 });
  await character.click();
  await expect(page.getByTestId('workshop-conversation')).toContainText('慢工坊角色并发验收。');
  await expect(page.getByTestId('workshop-conversation')).toContainText('本轮讨论已记录');
});


test('故事推演与工坊对话可以同时等待且互不覆盖', async ({ page }) => {
  await loadStory(page, '自动验收故事');
  await page.route('**/api/v1/game/*/action', async route => {
    await new Promise(resolve => setTimeout(resolve, 1000));
    await route.continue();
  });
  await page.getByTestId('story-action-input').fill('故事与工坊并发验收。');
  await page.getByTestId('story-action-submit').click();
  await page.getByRole('button', { name: '🧰 工坊' }).click();
  await page.getByRole('button', { name: /角色卡/ }).last().click();
  await page.locator('[data-workshop-asset-name="测试角色卡"]').click();
  await page.locator('textarea[placeholder*="Ctrl+Enter"]').fill('与正文同时运行的工坊请求。');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByTestId('workshop-conversation')).toContainText('本轮讨论已记录', { timeout: 10_000 });
  await page.getByRole('button', { name: '🎮 游戏' }).click();
  await expect(page.getByText('故事与工坊并发验收。')).toBeVisible();
  await expect(page.getByTestId('story-action-submit')).toBeEnabled({ timeout: 10_000 });
});


test('官方演示世界可一键开局，工坊可选择资产并下载世界包', async ({ page }) => {
  await page.goto('/');
  await dismissStartupPrompt(page);
  await openResourceLibrary(page, 'packages');
  const official = page.getByTestId('official-world-packages');
  await expect(official).toContainText('雾港回声');
  await official.locator('[data-official-id="mist_harbor_demo"]').getByTestId('official-world-start').click();
  const startDialog = page.getByRole('dialog', { name: '从世界包开始' });
  await startDialog.getByTestId('world-package-save-name').fill('雾港自动验收');
  await startDialog.getByTestId('world-package-confirm-start').click();
  await expect(page.locator('[data-save-name="雾港自动验收"]')).toContainText('当前游玩');
  await expect(page.getByTestId('resource-library')).toBeHidden();
  await openResourceLibrary(page, 'packages');
  await expect(page.locator('[data-official-id="mist_harbor_demo"]')).toContainText('再开一局');
  await expect(page.locator('[data-package-name="雾港回声"]')).toHaveCount(0);
  await closeResourceLibrary(page);

  await page.getByRole('button', { name: '🧰 工坊' }).click();
  await page.getByTestId('open-world-package-builder').click();
  const builder = page.getByRole('dialog', { name: '创建世界包' });
  await expect(builder).toBeVisible();
  await builder.getByTestId('package-builder-name').fill('自动导出世界');
  await builder.getByText('作者').locator('input').fill('AliveWorld Test');
  await builder.getByTestId('package-builder-asset').first().click();
  const downloadPromise = page.waitForEvent('download');
  await builder.getByTestId('package-builder-export').click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('自动导出世界-1.0.0.aliveworld');
  await expect(page.getByText('世界包“自动导出世界”已通过隐私检查并导出')).toBeVisible();
});


test('大型官方世界一键建立实体与初始动态状态', async ({ page }) => {
  await page.goto('/');
  await dismissStartupPrompt(page);
  await openResourceLibrary(page, 'packages');
  const card = page.locator('[data-official-id="ash_ring_city"]');
  await expect(card).toContainText('烬环城：停炉前夜');
  await expect(card).toContainText('三个组织会持续行动');
  await card.getByTestId('official-world-start').click();
  const startDialog = page.getByRole('dialog', { name: '从世界包开始' });
  await startDialog.getByTestId('world-package-save-name').fill('烬环自动验收');
  const responsePromise = page.waitForResponse(response => response.url().includes('/official/ash_ring_city/start'));
  await startDialog.getByTestId('world-package-confirm-start').click();
  const response = await responsePromise;
  const payload = await response.json();
  expect(payload.state.bars['下环供热'].current).toBe(62);
  expect(payload.state.properties['当前时间']).toBe('停炉前夜 21:50');
  expect(payload.story_settings.entitiesEnabled).toBe(true);
  expect(payload.story_settings.showInfluenceBubbles).toBe(true);
  await expect(page.locator('[data-save-name="烬环自动验收"]')).toContainText('当前游玩');
  await expect(page.getByText('下环供热', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /让 AI 降临并初始化世界状态/ })).toHaveCount(0);
  await page.getByTestId('story-action-input').fill('我先核对机械压力表，并要求门外两方暂时不要进入。');
  await page.getByTestId('story-action-submit').click();
  await expect(page.getByText('前端正文测试成功。')).toBeVisible();
  // 玩家端气泡只公开实体名称；完整行动与因果内容由账本接口验证。
  await expect(page.getByText(/暗流变化：\[中央炉务厅\]/)).toBeVisible();
  const ledger = await (await page.request.get(`/api/v1/game/${payload.session_id}/causal-ledger`)).json();
  expect(ledger.influences).toHaveLength(1);
  expect(ledger.influences[0].summary).toBe('炉务厅对第七中继站启动分级核查');
  const locals = await (await page.request.get(`/api/v1/game/${payload.session_id}/local_assets`)).json();
  expect(locals.entities).toHaveLength(4);
  expect(locals.entities.find(item => item.name === '中央炉务厅').influence_refs).toHaveLength(1);
});


test('生图执行失败保留任务卡，点击重试后成功交付图片', async ({ page }) => {
  await page.addInitScript(() => {
    const current = JSON.parse(localStorage.getItem('aw_config') || '{}');
    current.globalSettings = {
      ...(current.globalSettings || {}),
      imageCheckpoint: 'fake-e2e.safetensors',
      imageWorkflowId: 'builtin_basic',
    };
    localStorage.setItem('aw_config', JSON.stringify(current));
  });
  await loadStory(page);
  const latest = page.locator('[data-message-role="ai"]').last();
  await latest.getByRole('button', { name: '🎨 生成此处 CG' }).click();
  await latest.getByPlaceholder(/用自然语言补充/).fill('dev.19 failure recovery scene');
  await latest.getByRole('button', { name: '直接使用当前提示词' }).click();

  await expect(latest.getByText('ComfyUI 工作流执行失败')).toBeVisible({ timeout: 15_000 });
  await latest.getByRole('button', { name: '重试', exact: true }).click();
  await expect(latest.locator('img')).toBeVisible({ timeout: 15_000 });
  await expect(latest.getByText(/已完成/)).toBeVisible();
});


test('正文气泡可以拖选且普通气泡不显示复制按钮', async ({ page }) => {
  await loadStory(page);
  const latest = page.locator('[data-message-role="ai"]').last();
  await expect(latest.getByTestId('copy-text')).toHaveCount(0);
  expect(await latest.locator('.select-text').evaluate(element => getComputedStyle(element).userSelect)).not.toBe('none');
  await expect(page.locator('[data-message-role="reactions"]').first()).toBeVisible();
  await expect(page.locator('[data-message-role="reactions"]').getByTestId('copy-text')).toHaveCount(0);
  await expect(page.locator('[data-message-role="system"]').getByTestId('copy-text')).toHaveCount(0);
});


test('页面重载后可重新唤醒故事并恢复正文、局内资产和图片任务', async ({ page }) => {
  const loaded = await loadStory(page);
  await expect(page.getByText('我继续进行第二次自动验收。')).toBeVisible();
  const restoredReplies = page.locator('[data-message-role="ai"]');
  await expect(restoredReplies.filter({ hasText: '前端正文测试成功。' }).first()).toBeVisible();
  await expect(restoredReplies.filter({ hasText: '自动测试正文2' })).toBeVisible();
  await expect(page.getByText(loaded.state.properties['当前时间'], { exact: true })).toBeVisible();
  const progress = loaded.state.bars['自动验收进度'];
  await expect(page.getByText(`${progress.current}/${progress.max}`)).toBeVisible();
  await expect(page.locator('[data-message-role="ai"] img')).toBeVisible({ timeout: 10_000 });
  await page.getByTestId('tab-character').click();
  await page.getByRole('button', { name: '🛡️ 本局专属' }).click();
  await expect(page.locator('[data-asset-name="测试角色卡"]')).toBeVisible();
  await page.getByTestId('tab-style').click();
  await page.getByRole('button', { name: '🛡️ 本局专属' }).click();
  await expect(page.locator('[data-asset-name="测试文风"]')).toBeVisible();
  await page.getByTestId('tab-saves').click();
  await expect(page.locator('[data-save-name="自动验收故事"]')).toContainText('当前游玩');
});


test('高级设置默认隐藏并可由总开关统一显示', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '⚙️ 设置', exact: true }).click();
  await expect(page.getByText('用户偏好（高级）')).toHaveCount(0);
  await page.getByTestId('advanced-settings-toggle').check();
  await expect(page.getByText('用户偏好（高级）')).toBeVisible();
  await expect(page.getByText('故事记忆（高级）')).toBeVisible();
  await expect(page.getByText('叙事体验（高级）')).toBeVisible();
  await page.getByText('叙事体验（高级）').click();
  const experiencePreset = page.getByTestId('story-setting-storyExperiencePreset');
  await experiencePreset.selectOption('engine_only');
  await expect(experiencePreset).toHaveValue('engine_only');
  await page.getByTestId('advanced-settings-toggle').uncheck();
  await expect(page.getByText('用户偏好（高级）')).toHaveCount(0);
});


test('开发者密码保护真实提示词切片并支持覆盖与恢复', async ({ page }) => {
  await page.goto('/');
  await dismissStartupPrompt(page);
  await page.getByRole('button', { name: '⚙️ 设置', exact: true }).click();
  await page.getByRole('button', { name: '🧰 开发者模式' }).click();
  await expect(page.getByTestId('developer-settings')).toBeVisible();
  await page.getByTestId('developer-password').fill('aliveworld-e2e');
  const confirmation = page.getByPlaceholder('再次输入密码');
  if (await confirmation.isVisible().catch(() => false)) await confirmation.fill('aliveworld-e2e');
  await page.getByRole('button', { name: /设置并解锁|解锁/ }).click();
  await page.getByTestId('prompt-mode-game').click();
  const futureCore = page.locator('[data-prompt-slice="story.future.core"]');
  await expect(futureCore).toBeVisible();
  await futureCore.click();
  const editor = page.getByTestId('prompt-slice-editor');
  const baseline = await editor.inputValue();
  const variableBrowser = page.getByTestId('prompt-variable-browser');
  await variableBrowser.getByText(/变量表/).click();
  await page.getByTestId('prompt-variable-search').fill('玩家角色');
  const variableHelp = variableBrowser.getByRole('button', { name: /玩家角色设定/ }).first();
  await expect(variableHelp).toHaveAttribute('title', /当前由玩家扮演的角色资料/);
  await editor.focus();
  await editor.press('Control+End');
  await variableBrowser.getByRole('button', { name: '插入变量：玩家角色设定' }).click();
  await expect(editor).toHaveValue(`${baseline}{{context.player_character}}`);
  await editor.fill(baseline);
  await editor.locator('..').getByTestId('expand-textarea').click();
  await expect(page.getByTestId('expanded-textarea-dialog')).toBeVisible();
  await page.getByTestId('expanded-textarea-close').click();
  await expect(page.getByTestId('expanded-textarea-dialog')).toHaveCount(0);
  await editor.fill(`${baseline}\n开发者工作台自动验收规则`);
  const unsaved = `${baseline}\n开发者工作台自动验收规则`;
  for (const target of [page.locator('[data-prompt-slice="undercurrent.core"]'), page.getByTestId('prompt-mode-character'), page.getByRole('button', { name: '立即锁定' }), page.getByRole('button', { name: '💬 反馈与诊断 · 已实装' }), page.getByRole('button', { name: '✕', exact: true })]) {
    page.once('dialog', dialog => dialog.dismiss());
    await target.click();
    await expect(editor).toHaveValue(unsaved);
    await expect(page.getByTestId('prompt-mode-game')).toHaveAttribute('aria-selected', 'true');
  }
  await futureCore.click();
  await expect(editor).toHaveValue(unsaved);
  await page.getByRole('button', { name: '保存新覆盖版本' }).click();
  await expect(page.getByText('已保存为新的本地覆盖版本。')).toBeVisible();
  await expect(futureCore).toContainText('本地覆盖 v1');
  await page.getByTestId('prompt-mode-character').click();
  await expect(page.getByTestId('prompt-mode-empty')).toContainText('角色提示词尚未接入');
  await expect(editor).toHaveCount(0);
  await page.getByTestId('prompt-mode-workshop').click();
  await page.locator('[data-prompt-slice="workshop.runtime"]').click();
  await expect(editor).toHaveAttribute('readonly', '');
  await expect(page.locator('[data-prompt-slice="workshop.runtime"]')).toContainText('尚未迁移');
  await page.getByTestId('prompt-mode-game').click();
  await futureCore.click();
  await expect(editor).toHaveValue(unsaved);
  await expect(futureCore).toContainText('本地覆盖 v1');
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: '恢复官方基线' }).click();
  await expect(page.getByText('已恢复官方基线。')).toBeVisible();
  await expect(futureCore).toContainText('官方基线');
  const diagnostics = page.getByTestId('prompt-request-diagnostics');
  await diagnostics.locator('summary').first().click();
  await expect(diagnostics).toContainText('undercurrent：已接入');
  await expect(diagnostics).toContainText('world.capture：待迁移');
  await editor.fill(`${baseline}\n未保存的编辑内容`);
  await diagnostics.getByRole('button', { name: '刷新请求记录' }).click();
  await expect(editor).toHaveValue(`${baseline}\n未保存的编辑内容`);
  page.once('dialog', dialog => dialog.accept());
  await page.locator('[data-prompt-slice="undercurrent.core"]').click();
  await expect(editor).toHaveAttribute('readonly', '');
  await expect(page.locator('[data-prompt-slice="undercurrent.core"]')).toContainText('已接入 · 只读契约');
  await futureCore.click();
  await editor.fill(`${baseline}\n认证失效后保留稿`);
  await page.route('**/api/v1/developer/prompts/story.future.core', route => route.fulfill({ status: 401, json: { detail: 'expired' } }));
  await page.getByRole('button', { name: '保存新覆盖版本' }).click();
  await expect(page.getByText('认证已失效，请重新解锁；未保存内容仍保留，可复制后再离开。')).toBeVisible();
  await expect(editor).toHaveValue(`${baseline}\n认证失效后保留稿`);
  await expect(editor).toHaveAttribute('readonly', '');
  await expect(editor).toBeEnabled();
  await editor.click(); await editor.press('Control+A');
  expect(await editor.evaluate(el => el.value.slice(el.selectionStart, el.selectionEnd))).toBe(`${baseline}\n认证失效后保留稿`);
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('button', { name: '✕', exact: true }).click();
  await expect(editor).toBeVisible();
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: '💬 反馈与诊断 · 已实装' }).click();
  await expect(page.getByTestId('feedback-settings')).toBeVisible();
});


test('接口可从卡片直接启停并发现模型列表', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '⚙️ 设置', exact: true }).click();
  await page.getByRole('button', { name: '🔌 接口与模型' }).click();
  const card = page.locator('article').filter({ hasText: 'fake-story' });
  await expect(card).toBeVisible();
  const toggle = card.getByRole('switch');
  await toggle.uncheck();
  await expect(card.getByText('已停用', { exact: true }).last()).toBeVisible();
  await toggle.check();
  await expect(card.getByText('已启用', { exact: true })).toBeVisible();
  await card.getByRole('button', { name: '⋮' }).click();
  await page.getByRole('button', { name: '编辑', exact: true }).click();
  await page.getByRole('button', { name: '读取模型' }).click();
  await expect(page.getByText('已读取可用模型')).toBeVisible();
  await expect(page.getByRole('button', { name: 'fake-story', exact: true })).toBeVisible();
  await page.getByText('高级：上下文预算', { exact: true }).click();
  await page.getByRole('spinbutton', { name: '上下文窗口', exact: true }).fill('64000');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await card.getByRole('button', { name: '⋮' }).click();
  await page.getByRole('button', { name: '编辑', exact: true }).click();
  await page.getByText('高级：上下文预算', { exact: true }).click();
  await expect(page.getByRole('spinbutton', { name: '上下文窗口', exact: true })).toHaveValue('64000');
});


test('生图工作流显示映射报告并独立保存配置档案', async ({ page }) => {
  await page.goto('/');
  await dismissStartupPrompt(page);
  await page.getByRole('button', { name: '⚙️ 设置', exact: true }).click();
  await page.getByRole('button', { name: '🎨 生图配置' }).click();
  await expect(page.getByText('工作流配置档案', { exact: true })).toBeVisible();
  await expect(page.getByText('正向提示词', { exact: true }).first()).toBeVisible();
  await page.getByRole('textbox', { name: '玩家固定正向补充', exact: true }).fill('自动验收固定画风');
  await page.getByRole('checkbox', { name: /允许覆盖工作流设定/ }).check();
  await page.getByRole('button', { name: '保存配置档案' }).click();
  await expect(page.getByText('工作流配置档案已保存')).toBeVisible();
  await page.getByText('预览提示词合成顺序').click();
  await expect(page.getByText(/自动验收固定画风/)).toBeVisible();
});


test('运行日志从最新处打开，可选择、复制、逐条或批量导出并追踪调用', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /日志/ }).click();
  await expect(page.getByRole('dialog', { name: '运行日志' })).toBeVisible();
  await page.getByRole('button', { name: '正文', exact: true }).click();
  const entries = page.getByTestId('log-entry');
  await expect(entries.first()).toBeVisible();
  await expect.poll(() => page.locator('#terminal-log-container').evaluate(element => element.scrollHeight - element.scrollTop - element.clientHeight)).toBeLessThan(12);
  expect(await entries.first().locator('pre').evaluateAll(elements => elements.length ? getComputedStyle(elements[0]).userSelect : 'text')).not.toBe('none');
  await expect(entries.first().getByTestId('copy-log-entry')).toBeVisible();
  const singleDownload = page.waitForEvent('download');
  await entries.first().getByTestId('export-log-entry').click();
  expect((await singleDownload).suggestedFilename()).toMatch(/^AliveWorld-log-/);
  await entries.first().getByRole('checkbox', { name: '选择这条日志' }).check();
  const batchDownload = page.waitForEvent('download');
  await page.getByTestId('export-selected-logs').click();
  expect((await batchDownload).suggestedFilename()).toMatch(/^AliveWorld-logs-/);
  await entries.first().locator('summary').click();
  await expect(entries.first().locator('pre')).toBeVisible();
  const traceButton = entries.first().getByTestId('trace-log-entry');
  if (await traceButton.count()) {
    const traceId = await traceButton.textContent();
    await traceButton.click();
    await expect(page.getByRole('button', { name: new RegExp(`退出关联追踪 ${traceId}`) })).toBeVisible();
  }
});


test('启动后非阻塞提示新版本，并可直接进入更新设置', async ({ page }) => {
  await page.route('**/api/v1/updates/check?*', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        current_version: '1.5.0-dev.20',
        latest_version: '1.5.0-dev.21',
        update_available: true,
        prerelease: true,
        title: 'AliveWorld dev.21',
        notes: '自动更新提示专项测试',
        release_url: 'https://github.com/Lzy44567/AliveWorld-Releases/releases/tag/v1.5.0-dev.21',
      }),
    });
  });
  await page.goto('/');
  const notice = page.getByTestId('startup-update-notice');
  await expect(notice).toContainText('发现新版本 1.5.0-dev.21', { timeout: 5000 });
  await notice.getByRole('button', { name: '查看更新' }).click();
  await expect(page.getByRole('heading', { name: /关于与更新/ })).toBeVisible();
});


test('便携版一键更新从下载进度自动进入独立助手安装', async ({ page }) => {
  let phase = 'idle';
  let installCalled = false;
  const release = {
    current_version: '1.5.0-dev.20',
    latest_version: '1.5.0-dev.21',
    update_available: true,
    prerelease: true,
    title: 'AliveWorld dev.21',
    notes: '一键更新界面专项测试',
    release_url: 'https://github.com/Lzy44567/AliveWorld/releases/tag/v1.5.0-dev.21',
  };
  await page.route('**/api/v1/updates/check?*', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(release),
  }));
  await page.route('**/api/v1/updates/status', route => {
    const ready = phase === 'downloading';
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        supported: true,
        status: ready ? 'ready' : phase,
        progress: ready ? 100 : 0,
        message: ready ? '更新已下载并通过校验，可以安装。' : '尚未开始下载。',
      }),
    });
  });
  await page.route('**/api/v1/updates/prepare?*', route => {
    phase = 'downloading';
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ supported: true, status: phase, progress: 30, message: '正在下载更新……' }),
    });
  });
  await page.route('**/api/v1/updates/install', route => {
    installCalled = true;
    phase = 'installing';
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: phase, message: '正在退出 AliveWorld 并安装更新……' }),
    });
  });

  await page.goto('/');
  const notice = page.getByTestId('startup-update-notice');
  await expect(notice).toBeVisible({ timeout: 5000 });
  await notice.getByRole('button', { name: '查看更新' }).click();
  await page.getByRole('button', { name: '检查更新' }).click();
  const updateButton = page.getByRole('button', { name: '一键更新并重启' });
  await expect(updateButton).toBeVisible();
  await updateButton.click();
  await expect.poll(() => installCalled).toBe(true);
  await expect(page.getByText('正在重启并安装更新……')).toBeVisible();
});


test('反馈面板默认不附带私人日志并可生成本机安全预览', async ({ page }) => {
  await page.goto('/');
  await dismissStartupPrompt(page);
  await page.getByRole('button', { name: '⚙️ 设置', exact: true }).click();
  await page.getByRole('button', { name: '💬 反馈与诊断 · 已实装' }).click();
  await expect(page.getByTestId('feedback-settings')).toBeVisible();
  await page.getByTestId('feedback-title').fill('自动验收反馈');
  await page.getByRole('textbox', { name: '实际发生了什么', exact: true }).fill('按钮没有响应。');
  await page.getByRole('textbox', { name: '你期望看到什么', exact: true }).fill('按钮应正常响应。');
  await page.getByTestId('feedback-preview').click();
  const preview = page.getByTestId('feedback-preview-content');
  await expect(preview).toContainText('自动验收反馈');
  await expect(preview).toContainText(`AliveWorld：${runtimeVersion}`);
  await expect(preview).not.toContainText('玩家私人正文');
  await expect(page.getByTestId('feedback-settings')).toContainText('需手动发送给开发者；不会自动提交');
  await page.evaluate(() => {
    window.__feedbackCopies = []; window.__feedbackIssues = [];
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async text => window.__feedbackCopies.push(text) } });
    window.open = url => { window.__feedbackIssues.push(url); return null; };
  });
  await page.getByTestId('feedback-title').fill('修改后的反馈B');
  await expect(preview).toHaveCount(0);
  await page.getByRole('button', { name: '复制摘要', exact: true }).click();
  await expect(page.getByText('反馈摘要已复制；需手动粘贴发送给开发者。')).toBeVisible();
  expect(await page.evaluate(() => window.__feedbackCopies[0])).toContain('修改后的反馈B');
  await page.getByRole('button', { name: '打开 GitHub Issue' }).click();
  const issueUrl = new URL(await page.evaluate(() => window.__feedbackIssues[0]));
  expect(issueUrl.searchParams.get('title')).toBe('修改后的反馈B');
  expect(issueUrl.searchParams.get('body')).toContain('修改后的反馈B');
  await expect(page.getByRole('link', { name: '继续打开预填 Issue' })).toHaveAttribute('href', issueUrl.toString());
  await page.route('**/api/v1/feedback/preview', route => route.fulfill({ status: 500, json: { detail: 'sk-private-secret' } }));
  await page.getByRole('button', { name: '复制摘要', exact: true }).click();
  await expect(page.getByText('反馈操作失败，请重试。')).toBeVisible();
  await expect(preview).toHaveCount(0);
  await expect(page.getByRole('link', { name: '继续打开预填 Issue' })).toHaveCount(0);
  expect(await page.evaluate(() => window.__feedbackCopies.length)).toBe(1);
  await expect(page.getByTestId('feedback-settings')).not.toContainText('sk-private-secret');
});
