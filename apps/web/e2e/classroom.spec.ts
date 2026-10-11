import { expect, test } from '@playwright/test';
import { episodeResponseSchema, experimentResponseSchema, parseApi } from '../src/apiContracts';
import { flowFrames } from '../src/flowFrames';

test('global Token draft stays separate from history and a stopped Job refresh is read-only', async ({ page, request }, testInfo) => {
  const response = await request.post('/api/v1/experiments', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'success', task_ids: ['order-status-001'], max_total_tokens: 121,
  } });
  expect(response.ok()).toBeTruthy();
  const original = parseApi(experimentResponseSchema, await response.json()).experiment;
  expect(original.schema_version).toBe('1.3');
  await page.goto(`/?experiment_id=${original.experiment_id}`);
  const savedBudget = page.getByLabel('已保存全局 Token 预算');
  await expect(savedBudget).toContainText('121');
  await expect(savedBudget).toContainText('240');
  await expect(savedBudget).toContainText('在途执行已超额');
  await page.locator('.experiment-draft > summary').click();
  await page.locator('.experiment-settings > summary').click();
  await page.getByLabel('整场实验 Token 预算（可选）').fill('1.5');
  await page.locator('#run-exp-button').click();
  await expect(page.getByText('整场实验 Token 预算须为 1–1,000,000,000 的整数，或留空', { exact: true })).toBeVisible();
  await page.getByLabel('整场实验 Token 预算（可选）').fill('1');
  await expect(savedBudget).toContainText('121');
  const accepted = page.waitForResponse((reply) => reply.url().endsWith('/api/v1/experiments/jobs') && reply.request().method() === 'POST');
  await page.locator('#run-exp-button').click();
  const job = await (await accepted).json() as { experiment_id: string };
  const stopped = page.getByLabel('已停止实验说明');
  await expect(stopped).toBeVisible();
  await expect(stopped).toContainText('已达到整场实验 Token 预算，后续运行已停止');
  await expect(page).toHaveURL(new RegExp(`experiment_job_id=${job.experiment_id}`));
  const state = await (await request.get(`/api/v1/experiments/jobs/${job.experiment_id}`)).json() as { status: string; error_code: string };
  expect(state).toMatchObject({ status: 'failed', error_code: 'EXPERIMENT_TOKEN_BUDGET_EXCEEDED' });
  const mutations: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.reload();
  await expect(stopped).toBeVisible();
  await expect(stopped).toContainText('已达到整场实验 Token 预算');
  expect(mutations).toEqual([]);
  const saved = parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${original.experiment_id}`)).json()).experiment;
  expect(saved).toEqual(original);
  for (const [width, height] of [[1440, 900], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await stopped.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(`global-token-stopped-${width}.png`) });
  }
});

test('failed frame keeps its cursor across views and never shows later feedback', async ({ page, request }, testInfo) => {
  const response = await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'invalid-then-success',
    task_id: 'order-status-001', runtime_strategy: 'handwritten_recovery',
  } });
  expect(response.ok()).toBeTruthy();
  const artifact = parseApi(episodeResponseSchema, await response.json()).artifact;
  const frames = flowFrames(artifact.events, artifact.run_config.environment_version ?? '');
  const rejected = frames.findIndex((frame) => frame.phase === 'reject');
  expect(rejected).toBeGreaterThan(0);
  const mutations: string[] = [];
  const errors: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`/?episode_id=${artifact.episode.episode_id}`);
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
  const slider = page.getByRole('slider', { name: '动画进度' });
  await slider.press('Home');
  for (let i = 0; i < rejected; i++) await slider.press('ArrowRight');
  const inspector = page.getByLabel('当前阶段摘要');
  await expect(inspector).toContainText('INVALID_ARGUMENTS');
  await expect(inspector).toContainText('工具未执行');
  await expect(inspector).not.toContainText('工具返回');
  const cursor = await slider.inputValue();
  await page.getByRole('button', { name: '技术 Trace', exact: true }).click();
  await expect(page.locator('.replay-event-panel')).toContainText('TOOL_CALL_VALIDATED');
  await page.getByRole('button', { name: '过程概览', exact: true }).click();
  await expect(page.locator('.step-card[aria-current="step"]')).toContainText('参数错误');
  await page.getByRole('button', { name: '流程动画', exact: true }).click();
  await expect(slider).toHaveValue(cursor);
  await expect(inspector).toContainText('INVALID_ARGUMENTS');
  for (const [width, height] of [[1440, 900], [1280, 800], [768, 900], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await inspector.scrollIntoViewIfNeeded();
    await expect(inspector.getByRole('heading', { name: '调用被拒绝' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(`recovery-${width}.png`) });
  }
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await slider.press('Home');
  for (let i = 0; i < frames.findIndex(frame => frame.phase === 'request'); i++) await slider.press('ArrowRight');
  await expect(inspector).toContainText('等待模型响应');
  await page.getByRole('button', { name: '播放', exact: true }).click();
  await expect(page.locator('.flow-packet')).toHaveCount(0);
  await page.getByRole('button', { name: '暂停', exact: true }).click();
  expect(mutations).toEqual([]);
  expect(errors).toEqual([]);
  const saved = parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${artifact.episode.episode_id}`)).json()).artifact;
  expect(saved).toEqual(artifact);
});

test('saved comparison shows scores first and retains a separate next-run draft', async ({ page, request }, testInfo) => {
  const response = await request.post('/api/v1/experiments', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'invalid-then-success', task_ids: ['order-status-001'], seeds: [1],
  } });
  expect(response.ok()).toBeTruthy();
  const original = parseApi(experimentResponseSchema, await response.json()).experiment;
  const mutations: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.goto(`/?experiment_id=${original.experiment_id}`);
  const draft = page.locator('.experiment-draft');
  const savedConfig = page.locator('.experiment-record');
  await expect(page.getByText('1 组任务对比', { exact: true })).toBeVisible();
  await expect(draft).not.toHaveAttribute('open');
  await expect(savedConfig).not.toHaveAttribute('open');
  await expect(page.locator('.experiment-reading-note')).toContainText('离线模拟');
  await expect(page.getByLabel('已保存实验来源')).toContainText('fake-model');
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.locator('#exp-metrics-panel').evaluate((element) => Boolean(element.parentElement
    && element.parentElement.compareDocumentPosition(document.querySelector('#exp-config-panel')!) & Node.DOCUMENT_POSITION_FOLLOWING))).toBeTruthy();
  const resultBox = await page.locator('#exp-metrics-panel').boundingBox();
  const configBox = await page.locator('#exp-config-panel').boundingBox();
  expect(resultBox!.y + resultBox!.height).toBeLessThanOrEqual(configBox!.y);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await draft.locator(':scope > summary').press('Enter');
  await page.getByLabel('对照变量', { exact: true }).selectOption('runtime_backend');
  await draft.locator(':scope > summary').press('Enter');
  await savedConfig.locator(':scope > summary').press('Enter');
  await expect(savedConfig).toContainText('handwritten_recovery');
  await expect(page.locator('#exp-metrics-panel')).toContainText('挽救转化 (Recovery)');
  await page.screenshot({ path: testInfo.outputPath('comparison.png') });
  expect(mutations).toEqual([]);
  const saved = parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${original.experiment_id}`)).json()).experiment;
  expect(saved).toEqual(original);
});
