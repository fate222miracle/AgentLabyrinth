import { expect, test } from '@playwright/test';
import { episodeResponseSchema, experimentResponseSchema, parseApi } from '../src/apiContracts';

test('labelled history accepts Enter and keyboard navigation identifies the workspace', async ({ page, request }) => {
  const episodeResponse = await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'success', task_id: 'order-status-001',
  } });
  expect(episodeResponse.ok()).toBeTruthy();
  const episodeValue: unknown = await episodeResponse.json();
  const original = parseApi(episodeResponseSchema, episodeValue).artifact;
  const experimentResponse = await request.post('/api/v1/experiments', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'invalid-then-success', task_ids: ['order-status-001'], seeds: [1],
  } });
  expect(experimentResponse.ok()).toBeTruthy();
  const experimentValue: unknown = await experimentResponse.json();
  const experiment = parseApi(experimentResponseSchema, experimentValue).experiment;
  const mutations: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.goto('/?mode=single');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: '跳至工作区' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();
  await expect(page.getByRole('navigation', { name: '工作区模式' })
    .getByRole('button', { name: '单次运行 Single Episode' })).toHaveAttribute('aria-pressed', 'true');
  await page.getByLabel('历史 Episode ID', { exact: true }).fill(original.episode.episode_id);
  await page.getByLabel('历史 Episode ID', { exact: true }).press('Enter');
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`episode_id=${original.episode.episode_id}`));
  await page.locator('#tab-experiment').click();
  await expect(page.locator('#tab-experiment')).toHaveAttribute('aria-pressed', 'true');
  await page.getByLabel('历史 Experiment ID', { exact: true }).fill(experiment.experiment_id);
  await page.getByLabel('历史 Experiment ID', { exact: true }).press('Enter');
  await expect(page).toHaveURL(new RegExp(`experiment_id=${experiment.experiment_id}`));
  await expect(page.locator('#exp-metrics-panel')).toContainText('1 组任务对比');
  await page.locator('#tab-single').click();
  await page.getByLabel('历史 Episode ID', { exact: true }).fill('00000000-0000-4000-8000-000000000000');
  await page.getByLabel('历史 Episode ID', { exact: true }).press('Enter');
  await expect(page.getByRole('alert')).toContainText('错误');
  await expect(page.locator('#eval-badge')).toHaveCount(0);
  expect(mutations).toEqual([]);
  const savedValue: unknown = await (await request.get(`/api/v1/episodes/${original.episode.episode_id}`)).json();
  expect(parseApi(episodeResponseSchema, savedValue).artifact).toEqual(original);
});

test('configure before running, retain advanced settings, and explain a disabled action', async ({ page, request }) => {
  await page.goto('/?mode=single');
  await page.getByLabel('搜索任务', { exact: true }).fill('order-status-007');
  await page.getByRole('button', { name: /order-status-007 多步规划/ }).click();
  await page.getByRole('radio', { name: 'LangGraph 独立图节点调度' }).check();
  const model = await page.getByLabel('评测模型', { exact: true }).boundingBox();
  const run = await page.locator('#run-button').boundingBox();
  expect(model).not.toBeNull(); expect(run).not.toBeNull();
  expect(run!.y).toBeGreaterThan(model!.y + model!.height);
  await expect(page.locator('.single-launch-summary')).toContainText('order-status-007');
  await expect(page.locator('.single-launch-summary')).toContainText('LangGraph');
  await page.locator('#run-button').click();
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
  const id = new URL(page.url()).searchParams.get('episode_id');
  const savedValue: unknown = await (await request.get(`/api/v1/episodes/${id}`)).json();
  const saved = parseApi(episodeResponseSchema, savedValue).artifact;
  expect(saved.task.name).toBe('order-status-007');
  expect(saved.agent.runtime_backend).toBe('langgraph');
  await page.locator('#tab-experiment').click();
  const settings = page.locator('.experiment-settings');
  await settings.locator('summary').press('Enter');
  await page.getByLabel('随机种子集合 (Seeds)', { exact: true }).fill('1, 1');
  await settings.locator('summary').press('Enter');
  await expect(page.locator('#run-exp-button')).toBeDisabled();
  await expect(page.getByRole('status').filter({ hasText: '请展开种子与预算设置' })).toBeVisible();
  await settings.locator('summary').press('Enter');
  await page.getByLabel('随机种子集合 (Seeds)', { exact: true }).fill('1, 7');
  await page.getByLabel('每个 Seed 重复次数', { exact: true }).fill('2');
  await settings.locator('summary').press('Enter');
  await expect(settings.locator('summary')).toContainText('Seed 1, 7 · 重复 2 次');
  await expect(page.locator('#run-exp-button')).toBeEnabled();
  await settings.locator('summary').press('Enter');
  await expect(page.getByLabel('随机种子集合 (Seeds)', { exact: true })).toHaveValue('1, 7');
  await expect(page.getByLabel('每个 Seed 重复次数', { exact: true })).toHaveValue('2');
});

test('saved results foreground provenance and replay, retaining detailed facts at four viewports', async ({ page, request }, testInfo) => {
  const response = await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'success', task_id: 'order-status-007',
  } });
  expect(response.ok()).toBeTruthy();
  const value: unknown = await response.json();
  const original = parseApi(episodeResponseSchema, value).artifact;
  const mutations: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto(`/?episode_id=${original.episode.episode_id}`);
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
  await expect(page.getByLabel('已保存运行来源')).toContainText('Fake 离线模拟');
  await expect(page.locator('#metric-model')).toHaveText(original.agent.model.model);
  await expect(page.locator('#metric-tokens')).toHaveText(String(original.episode.token_usage.prompt_tokens + original.episode.token_usage.completion_tokens));
  const result = await page.locator('#results-panel').boundingBox();
  expect(result!.height).toBeLessThan(380);
  await page.screenshot({ path: testInfo.outputPath('results-desktop.png') });
  const details = page.locator('.episode-details');
  await expect(details).not.toHaveAttribute('open');
  await expect(details.locator('summary')).toContainText('原厂参考：未知');
  await details.locator('summary').press('Enter');
  await expect(page.locator('#metric-cost')).toHaveText(`$${original.episode.estimated_cost.amount} USD`);
  await expect(details).toContainText('非实付费用');
  await expect(details).toContainText(original.run_config.runtime_version!);
  await details.locator('summary').press('Enter');
  const savedUrl = page.url();
  await page.getByRole('link', { name: '查看调用过程', exact: true }).click();
  await expect(page.locator('#trace-panel')).toBeFocused();
  await expect(page).toHaveURL(savedUrl);
  await page.screenshot({ path: testInfo.outputPath('replay-desktop.png') });
  for (const width of [390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByLabel('最初输入')).toContainText('搜索订单政策文档');
    await expect(page.getByLabel('最终输出')).toContainText('approved');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (width === 390) {
      // The focused Trace can consume Home; explicitly reset the capture scroll position.
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
      await page.screenshot({ path: testInfo.outputPath('results-mobile.png'), fullPage: true });
    }
  }
  expect(mutations).toEqual([]);
  const savedValue: unknown = await (await request.get(`/api/v1/episodes/${original.episode.episode_id}`)).json();
  expect(parseApi(episodeResponseSchema, savedValue).artifact).toEqual(original);
});

test('unknown cost never reads as zero and failure stays visible outside details', async ({ page, request }) => {
  const response = await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'invalid-arguments', task_id: 'order-status-001',
  } });
  expect(response.ok()).toBeTruthy();
  const value: unknown = await response.json();
  const original = parseApi(episodeResponseSchema, value).artifact;
  // A response fixture exercises the unknown-cost display; it does not rewrite saved data.
  const fixture = structuredClone(original);
  fixture.episode.estimated_cost = { ...fixture.episode.estimated_cost, amount: '0', is_known: false };
  await page.route(`**/api/v1/episodes/${original.episode.episode_id}`, async (route) => {
    await route.fulfill({ json: { schema_version: '1.0', request_id: '00000000-0000-4000-8000-000000000001', artifact: fixture } });
  });
  await page.goto(`/?episode_id=${original.episode.episode_id}`);
  await expect(page.getByText('评测未通过 (FAILED)', { exact: true })).toBeVisible();
  await expect(page.locator('#metric-status')).toHaveText(original.episode.termination_reason);
  await expect(page.locator('.episode-metrics')).toContainText('INVALID_ARGUMENTS');
  const details = page.locator('.episode-details');
  await expect(details).not.toHaveAttribute('open');
  await expect(details.locator('summary')).toContainText('模拟费用：未知 (未验证)');
  await expect(details.locator('summary')).not.toContainText('$0');
  await details.locator('summary').press('Enter');
  await expect(page.locator('#metric-cost')).toHaveText('未知 (未验证)');
  const savedValue: unknown = await (await request.get(`/api/v1/episodes/${original.episode.episode_id}`)).json();
  expect(parseApi(episodeResponseSchema, savedValue).artifact).toEqual(original);
});

test('an interrupted stream keeps received events visible without inventing a result', async ({ page, request }, testInfo) => {
  const response = await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'success', task_id: 'order-status-007',
  } });
  expect(response.ok()).toBeTruthy();
  const value: unknown = await response.json();
  const original = parseApi(episodeResponseSchema, value).artifact;
  for (const partial of [false, true]) {
    // Use real saved events as a truncated SSE response fixture, with no completion.
    await page.route('**/api/v1/episodes/stream', async (route) => {
      await route.fulfill({ contentType: 'text/event-stream', body: partial
        ? original.events.slice(0, 6).map((event) => `event: trace\ndata: ${JSON.stringify(event)}\n\n`).join('') : '',
      });
    });
    await page.goto('/?mode=single');
    await page.locator('#run-button').click();
    await expect(page.getByRole('alert')).toContainText('实时连接中断');
    await expect(page.locator('#trace-panel')).toBeVisible();
    await expect(page.locator('#trace-panel')).toContainText('后端运行状态未知');
    await expect(page.locator('#eval-badge')).toHaveCount(0);
    expect(new URL(page.url()).searchParams.has('episode_id')).toBe(false);
    if (partial) {
      await expect(page.locator('#trace-panel')).toContainText(original.episode.episode_id);
      await expect(page.getByRole('region', { name: '实时工具调用流程' })).toBeVisible();
      await expect(page.getByLabel('最终输出')).toContainText('请稍后按 Episode ID 回读最终产物');
      await page.locator('#trace-panel').scrollIntoViewIfNeeded();
      await page.screenshot({ path: testInfo.outputPath('interrupted-stream.png') });
    } else {
      await expect(page.getByRole('region', { name: '实时工具调用流程' })).toHaveCount(0);
    }
    await page.unroute('**/api/v1/episodes/stream');
  }
});
