import { expect, test } from '@playwright/test';

test('long-task budget presets preserve explicit user limits without execution', async ({ page, request }) => {
  const meta = await (await request.get('/api/v1/meta')).json();
  await page.route('**/api/v1/meta', (route) => route.fulfill({ json: { ...meta,
    models: [...meta.models, { ...meta.models[0], id: 'tested-budget-candidate', name: 'Budget candidate', provider: 'aihubmix' }],
  } }));
  const posts: string[] = [];
  page.on('request', (req) => { if (req.url().includes('/api/') && req.method() !== 'GET') posts.push(req.url()); });
  await page.goto('/?mode=single');
  await page.locator('#model-select').selectOption('tested-budget-candidate');
  await page.getByRole('button').filter({ has: page.getByText('refund-evidence-chain-003', { exact: true }) }).click();
  await page.locator('.advanced-settings > summary').click();
  await expect(page.locator('#single-token-budget')).toHaveValue('20000');
  await expect(page.locator('#steps-input')).toHaveValue('10');
  await page.locator('#single-token-budget').fill('6000');
  await page.locator('#steps-input').fill('3');
  await page.getByRole('button').filter({ has: page.getByText('return-evidence-chain-001', { exact: true }) }).click();
  await expect(page.locator('#single-token-budget')).toHaveValue('6000');
  await expect(page.locator('#steps-input')).toHaveValue('3');
  expect(posts).toEqual([]);
});

test('linked evidence task runs from the actual UI and stays read-only on refresh', async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/?mode=single');
  await page.getByRole('button').filter({ has: page.getByText('refund-evidence-chain-003', { exact: true }) }).click();
  await expect(page.getByText('跨文档证据链 · 自建仿真', { exact: true })).toHaveCount(3);
  await page.getByRole('button', { name: '开始运行 Episode', exact: true }).click();
  await expect(page).toHaveURL(/episode_id=[a-f0-9-]+/);
  const id = new URL(page.url()).searchParams.get('episode_id');
  const saved = await (await request.get(`/api/v1/episodes/${id}`)).json();
  expect(saved.artifact.evaluation.success).toBe(true);
  expect(saved.artifact.episode.tool_call_count).toBe(7);
  expect(saved.artifact.episode.final_state.submission.evidence).toHaveLength(5);
  const flow = page.getByRole('region', { name: '本次工具执行过程' });
  await expect(flow.getByLabel('最终输出')).toContainText('refund_approved');
  await expect(flow.getByRole('slider', { name: '动画进度' })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('linked-evidence-completed.png'), fullPage: true });
  const posts: string[] = [];
  page.on('request', (req) => { if (req.url().includes('/api/') && req.method() !== 'GET') posts.push(req.url()); });
  await page.reload();
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
  expect((await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact).toEqual(saved.artifact);
  expect(posts).toEqual([]);
  expect(errors).toEqual([]);
});
