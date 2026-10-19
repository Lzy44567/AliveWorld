import { test, expect } from '@playwright/test';

test('真实503退避显示次数，停止后不发第二次，成功重试只保存一次', async ({page, request}) => {
  const base='/api/v1/model-connections';
  const response=await request.post(`${base}/profiles`,{data:{name:'重试验收接口',category:'text',protocol:'openai_compatible',
    baseUrl:'http://127.0.0.1:18765/v1',apiKey:'test-only',defaultModel:'fake-workshop',advancedOptions:{automatic_retries:2}}});
  expect(response.ok()).toBeTruthy();const profile=await response.json();
  expect((await request.post(`${base}/routes/workshop`,{data:{connectionId:profile.id}})).ok()).toBeTruthy();
  const name='重试验收文风';
  await request.post(`/api/v1/lobby/assets/styles/${encodeURIComponent(name)}`,{data:{parsed_data:{name,content:'原有文风'}}});
  try {
    await page.goto('/');await page.getByRole('button',{name:'稍后再说'}).click();
    await page.getByRole('button',{name:'🧰 工坊'}).click();
    await page.getByRole('button',{name:/文风卡/}).last().click();
    await page.locator(`[data-workshop-asset-name="${name}"]`).click();
    const input=page.getByRole('textbox',{name:'工坊消息',exact:true});
    await input.fill('【重试取消验收】检查取消');await page.getByRole('button',{name:'发送',exact:true}).click();
    await expect(page.getByTestId('generation-retry-status')).toContainText('第 1/2 次');
    await page.getByTestId('workshop-stop').click();await expect(page.getByTestId('workshop-stop')).toBeHidden();
    await expect(input).toHaveValue('【重试取消验收】检查取消');
    // Finish another backoff (> first retry deadline), then inspect actual provider calls.
    await input.fill('【重试成功验收】修改后的请求');await page.getByRole('button',{name:'发送',exact:true}).click();
    await expect(page.getByTestId('generation-retry-status')).toContainText('第 1/2 次');
    await expect(page.getByTestId('workshop-stop')).toBeHidden({timeout:15000});
    const calls=(await(await request.get('http://127.0.0.1:18765/__test__/requests')).json()).requests;
    expect(calls.filter(r=>r.user.includes('【重试取消验收】'))).toHaveLength(1);
    expect(calls.filter(r=>r.user.includes('【重试成功验收】'))).toHaveLength(2);
    await expect(page.getByTestId('workshop-conversation')).toContainText('本轮讨论已记录');
  } finally {
    await request.post(`${base}/routes/workshop`,{data:{inheritFrom:'story'}});
  }
});
