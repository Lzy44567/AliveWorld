import { test, expect } from '@playwright/test';


const assetTabs = {
  characters: 'tab-character',
  worldbooks: 'tab-world',
  styles: 'tab-style',
  entities: 'tab-entity',
};


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
  const snooze = page.getByRole('button', { name: '稍后再说' });
  if (await snooze.isVisible().catch(() => false)) await snooze.click();
}


async function loadStory(page, name = '自动验收故事') {
  await page.goto('/');
  await dismissStartupPrompt(page);
  await page.getByTestId('tab-saves').click();
  const card = page.locator(`[data-save-name="${name}"]`);
  await expect(card).toBeVisible();
  await card.getByTestId('save-load').click();
  await expect(page.getByTestId('story-action-input')).toBeEnabled();
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

  await loadAsset(page, 'characters', '测试角色卡');
  await loadAsset(page, 'worldbooks', '测试世界书');
  await loadAsset(page, 'styles', '测试文风');
  await loadAsset(page, 'entities', '测试实体');

  await request.delete('http://127.0.0.1:18765/__test__/requests');
  await page.getByTestId('story-action-input').fill('我施放测试法术。');
  await page.getByTestId('story-action-submit').click();
  await expect(page.getByText('前端正文测试成功。')).toBeVisible();
  await expect(page.getByText('自动测试正文1')).toBeVisible();
  await expect(page.getByText('世界书就绪')).toBeVisible();
  await expect(page.getByText('角色卡就绪')).toBeVisible();
  await expect(page.getByText('文风就绪')).toBeVisible();
  await expect(page.getByText('世界书A就绪')).toBeVisible();
  await expect(page.getByText('角色卡A就绪')).toBeVisible();
  await expect(page.getByText('文风卡A就绪')).toBeVisible();

  let records = (await (await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests;
  const settlement = records.find(item => item.kind === 'settlement');
  const overseer = records.find(item => item.kind === 'overseer');
  expect(settlement.system).toContain('测试世界书条目');
  expect(settlement.system).toContain('测试角色卡');
  expect(settlement.system).toContain('测试文风');
  expect(settlement.system).toContain('目标约 500 个中文字符');
  expect(overseer.system).toContain('测试实体');
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

  records = (await (await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests;
  const secondSettlement = records.find(item => item.kind === 'settlement');
  expect(secondSettlement.system).not.toContain('测试世界书条目');
  expect(secondSettlement.system).not.toContain('测试角色卡');
  expect(secondSettlement.system).not.toContain('测试文风');
  expect(secondSettlement.markers).not.toEqual(expect.arrayContaining(['世界书A', '角色卡A', '文风卡A']));
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

  const before = await (await request.get('/api/v1/lobby/assets/worldbooks/%E6%B5%8B%E8%AF%95%E4%B8%96%E7%95%8C%E4%B9%A6')).json();
  expect(before.parsed.overview).not.toBe('dev.19 工坊发布专项概述。');

  await page.getByTestId('workshop-publish').click();
  await expect(page.getByText('工坊草稿已发布')).toBeVisible();
  const published = await (await request.get('/api/v1/lobby/assets/worldbooks/%E6%B5%8B%E8%AF%95%E4%B8%96%E7%95%8C%E4%B9%A6')).json();
  expect(published.parsed.overview).toBe('dev.19 工坊发布专项概述。');

  await page.getByRole('button', { name: '🎮 游戏' }).click();
  await page.getByRole('button', { name: '🧰 工坊' }).click();
  await page.locator('[data-workshop-asset-name="测试世界书"]').click();
  await expect(page.locator('section').filter({ hasText: '世界概述' }).locator('textarea').first())
    .toHaveValue('dev.19 工坊发布专项概述。');
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


test('页面重载后可重新唤醒故事并恢复正文、局内资产和图片任务', async ({ page }) => {
  await loadStory(page);
  await expect(page.getByText('我继续进行第二次自动验收。')).toBeVisible();
  const restoredReplies = page.locator('[data-message-role="ai"]');
  await expect(restoredReplies.filter({ hasText: '前端正文测试成功。' }).first()).toBeVisible();
  await expect(restoredReplies.filter({ hasText: '自动测试正文2' })).toBeVisible();
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
  await page.getByRole('button', { name: /设置/ }).click();
  await expect(page.getByText('用户偏好（高级）')).toHaveCount(0);
  await page.getByTestId('advanced-settings-toggle').check();
  await expect(page.getByText('用户偏好（高级）')).toBeVisible();
  await expect(page.getByText('故事记忆（高级）')).toBeVisible();
  await page.getByTestId('advanced-settings-toggle').uncheck();
  await expect(page.getByText('用户偏好（高级）')).toHaveCount(0);
});


test('接口可从卡片直接启停并发现模型列表', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /设置/ }).click();
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
});


test('生图工作流显示映射报告并独立保存配置档案', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /设置/ }).click();
  await page.getByRole('button', { name: '🎨 生图配置' }).click();
  await expect(page.getByText('工作流配置档案', { exact: true })).toBeVisible();
  await expect(page.getByText('正向提示词', { exact: true }).first()).toBeVisible();
  await page.getByLabel('玩家固定正向补充').fill('自动验收固定画风');
  await page.getByRole('checkbox', { name: /允许覆盖工作流设定/ }).check();
  await page.getByRole('button', { name: '保存配置档案' }).click();
  await expect(page.getByText('工作流配置档案已保存')).toBeVisible();
  await page.getByText('预览提示词合成顺序').click();
  await expect(page.getByText(/自动验收固定画风/)).toBeVisible();
});


test('运行日志按任务分类、折叠详情并关联同一次模型调用', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /日志/ }).click();
  await expect(page.getByRole('dialog', { name: '运行日志' })).toBeVisible();
  await page.getByRole('button', { name: '正文', exact: true }).click();
  const entries = page.locator('details');
  await expect(entries.first()).toBeVisible();
  await entries.first().locator('summary').click();
  await expect(entries.first().locator('pre')).toBeVisible();
  const traceButton = entries.first().locator('summary button').first();
  if (await traceButton.count()) {
    const traceId = await traceButton.textContent();
    await traceButton.click();
    await expect(page.getByRole('button', { name: new RegExp(`退出关联追踪 ${traceId}`) })).toBeVisible();
  }
});
