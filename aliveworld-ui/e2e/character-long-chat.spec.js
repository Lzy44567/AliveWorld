import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';

test('长聊逐会话授权、真实HTTP整理、来源与关闭', async ({ page, request }) => {
  test.setTimeout(120000);
  const base='/api/v1/character-sessions', fake='http://127.0.0.1:18765';
  const card='长聊合成角色';
  await request.post(`/api/v1/lobby/assets/characters/${encodeURIComponent(card)}`, {data:{parsed_data:{name:card,description:'成年合成角色，仅验收。'},overwrite:true}});
  const created=await request.post(base,{data:{client_creation_id:randomUUID(),schema_version:2,title:'长聊整理验收',ai_asset_ref:{kind:'character',key:card},presentation_mode:'messenger'}});
  expect(created.ok()).toBeTruthy(); const sid=(await created.json()).session_id;
  await request.delete(`${fake}/__test__/requests`);
  await page.addInitScript(()=>localStorage.setItem('aw_onboarding_v1',JSON.stringify({completed:true})));
  await page.goto('/'); await page.getByTestId('mode-character').click(); await page.getByTestId(`character-session-${sid}`).click();
  await page.getByRole('button',{name:'会话资料',exact:true}).click(); await page.getByTestId('character-details-memory').click();
  const panel=page.getByTestId('character-long-chat');
  await expect(panel).toContainText('已关闭');
  await panel.getByRole('button',{name:'开启长聊整理',exact:true}).click();
  await expect(panel).toContainText('额外调用');
  await panel.getByRole('button',{name:'确认并开启'}).click(); await expect(panel).toContainText('已开启');
  await page.getByTestId('mode-story').click();
  for(let i=0;i<22;i++) {
    const session=await (await request.get(`${base}/${sid}`)).json();
    const sent=await request.post(`${base}/${sid}/actions`,{data:{operation:'send',client_action_id:randomUUID(),expected_revision:session.revision,content:`【C4单句】共同经历${i}`,display_mode:'instant'}});
    expect(sent.ok(), await sent.text()).toBeTruthy();
    await expect.poll(async()=> {const s=await (await request.get(`${base}/${sid}`)).json();return !s.busy_group && s.queued_count===0;},{timeout:10000}).toBeTruthy();
  }
  await page.getByTestId('mode-character').click();
  await page.getByTestId(`character-session-${sid}`).click();
  await page.getByRole('button',{name:'会话资料',exact:true}).click();
  await page.getByTestId('character-details-memory').click();
  await expect(panel).toContainText('已整理 1 段',{timeout:15000});
  await panel.getByText('已整理 1 段 · 查看摘要与来源').click();
  await panel.getByRole('button',{name:'查看关联原文'}).click();
  await expect(panel).toContainText('共同经历0');
  await page.getByTestId('character-composer').fill('【C4单句】整理完成后继续');
  await page.getByTestId('character-send').click();
  await expect(page.getByTestId('character-composer')).toHaveValue('');
  await expect.poll(async()=> {const s=await (await request.get(`${base}/${sid}`)).json();return !s.busy_group && s.queued_count===0;},{timeout:15000}).toBeTruthy();
  const calls=(await (await request.get(`${fake}/__test__/requests`)).json()).requests;
  expect(calls.filter(r=>r.kind==='character.compaction')).toHaveLength(1);
  expect(calls.filter(r=>r.kind==='character.reply').some(r=>JSON.parse(r.user).derived_summaries?.length)).toBeTruthy();
  await page.screenshot({path:'../build/character44-long-chat.png'});
  await panel.getByRole('button',{name:'关闭',exact:true}).click(); await expect(panel).toContainText('已关闭');
  const count=(await (await request.get(`${fake}/__test__/requests`)).json()).requests.length;
  await request.get(`${base}/${sid}/long-chat`);
  expect((await (await request.get(`${fake}/__test__/requests`)).json()).requests).toHaveLength(count);
});
