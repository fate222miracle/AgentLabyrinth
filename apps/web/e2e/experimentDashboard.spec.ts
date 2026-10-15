import { expect, test } from '@playwright/test';
import { dashboardSchema, experimentResponseSchema, parseApi, type ExperimentArtifact } from '../src/apiContracts';

test('experiment setup spans the workspace, pairs controls with tasks and preserves drafts at four widths', async ({ page }, testInfo) => {
  const mutations: string[] = [];
  page.on('request', req => { if (req.url().includes('/api/') && req.method() !== 'GET') mutations.push(req.url()); });
  await page.goto('/?mode=experiment');
  const config = page.locator('#exp-config-panel');
  await expect(config).toBeVisible();
  await expect(config.locator('.experiment-model-note')).not.toHaveAttribute('open');
  await page.getByLabel('对照变量', { exact: true }).selectOption('context_policy');
  await page.locator('#context-window').fill('3');
  await page.locator('.experiment-settings > summary').click();
  await page.locator('#exp-seed-input').fill('1, 7');
  await page.locator('#exp-repeat-input').fill('2');
  await page.locator('.experiment-settings > summary').click();
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const boxes = await config.evaluate(element => ({ config: element.getBoundingClientRect().width,
      parent: element.parentElement!.getBoundingClientRect().width,
      controls: element.querySelector('.experiment-controls')!.getBoundingClientRect().toJSON(),
      tasks: element.querySelector('.experiment-task-picker')!.getBoundingClientRect().toJSON() }));
    expect(boxes.config / boxes.parent).toBeGreaterThan(0.98);
    if (width > 900) expect(boxes.controls.right).toBeLessThan(boxes.tasks.left);
    else expect(boxes.controls.bottom).toBeLessThanOrEqual(boxes.tasks.top);
    await expect(page.locator('#context-window')).toHaveValue('3');
    await config.screenshot({ path: testInfo.outputPath(`setup-${width}.png`) });
  }
  expect(mutations).toEqual([]);
});

test('saved charts show exact metrics and compatible history only, with read-only point navigation', async ({ page, request }, testInfo) => {
  const artifacts: ExperimentArtifact[] = [];
  for (let i = 0; i < 2; i++) artifacts.push(parseApi(experimentResponseSchema, await (await request.post('/api/v1/experiments', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'invalid-then-success', task_ids: ['order-status-001'],
  } })).json()).experiment);
  const context = parseApi(experimentResponseSchema, await (await request.post('/api/v1/experiments', { data: {
    schema_version: '1.5', provider: 'fake', model: 'fake-model', scenario: 'clean', task_ids: ['return-evidence-chain-001'],
    comparison_axis: 'context_policy', context_policy: { mode: 'recent_tool_rounds', max_tool_rounds: 1 },
  } })).json()).experiment;
  const runtime: ExperimentArtifact[] = [];
  for (let i = 0; i < 2; i++) runtime.push(parseApi(experimentResponseSchema, await (await request.post('/api/v1/experiments', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'clean', task_ids: ['order-status-001'], comparison_axis: 'runtime_backend',
  } })).json()).experiment);
  const ids = new Set([...artifacts.map(item => item.experiment_id), context.experiment_id, ...runtime.map(item => item.experiment_id)]);
  const dashboard = parseApi(dashboardSchema, await (await request.get('/api/v1/experiments')).json());
  const source = { ...dashboard, items: dashboard.items.filter(item => ids.has(item.experiment_id)) };
  await page.route('**/api/v1/experiments', route => route.fulfill({ json: source }));
  const mutations: string[] = [];
  const errors: string[] = [];
  page.on('request', req => { if (req.url().includes('/api/') && req.method() !== 'GET') mutations.push(req.url()); });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`/?experiment_id=${artifacts[0].experiment_id}`);
  const result = page.locator('#exp-metrics-panel');
  await expect(result.getByRole('img', { name: 'Baseline Policy：通过 0.0%，未通过 100.0%' })).toBeVisible();
  await expect(result.getByRole('img', { name: 'Recovery Policy：通过 100.0%，未通过 0.0%' })).toBeVisible();
  const tokens = result.getByLabel('已报告 Token', { exact: true });
  await expect(tokens).toContainText(artifacts[0].metrics.baseline_total_tokens.toLocaleString());
  await expect(tokens).toContainText(artifacts[0].metrics.recovery_total_tokens.toLocaleString());
  await result.screenshot({ path: testInfo.outputPath('saved-visual-metrics.png') });
  await page.locator('.experiment-draft > summary').click();
  await page.locator('#comparison-axis').selectOption('runtime_backend');
  await expect(result.getByRole('img', { name: /Recovery Policy：/ })).toBeVisible(); // Saved chart ignores draft axis.
  await page.locator('.history-disclosure > summary').click();
  const trend = page.getByLabel('同配置历史折线图');
  await expect(trend).toContainText('选择同配置组');
  await expect(trend.locator('.chart-line')).toHaveCount(0);
  const key = source.items.find(item => item.experiment_id === artifacts[0].experiment_id)!.comparison_key!;
  await page.getByLabel('实验历史范围').selectOption(key);
  await expect(trend.locator('.chart-line')).toHaveCount(2);
  await expect(trend.locator('a')).toHaveCount(4);
  await expect(trend).not.toContainText('近期窗口');
  await trend.getByLabel('历史趋势指标').selectOption('tokens');
  await expect(trend.getByRole('img')).toHaveAttribute('aria-label', /Token 总量：2 次/);
  await trend.getByLabel('历史趋势指标').selectOption('duration');
  await expect(trend.getByRole('img')).toHaveAttribute('aria-label', /平均耗时：2 次/);
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await trend.screenshot({ path: testInfo.outputPath(`trend-${width}.png`) });
  }
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const point = trend.locator('a').first();
  await point.focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/experiment_id=/);
  await expect(page.locator('.experiment-draft')).not.toHaveAttribute('open');
  const contextKey = source.items.find(item => item.experiment_id === context.experiment_id)!.comparison_key!;
  await page.getByLabel('实验历史范围').selectOption(contextKey);
  await expect(trend).toContainText('只有一次完整运行');
  await expect(trend.locator('.chart-line')).toHaveCount(0);
  await expect(page.locator('.dashboard-spotlight')).toContainText('上下文对照');
  await expect(page.locator('.dashboard-spotlight')).toContainText('完整历史');
  const runtimeKey = source.items.find(item => item.experiment_id === runtime[0].experiment_id)!.comparison_key!;
  await page.getByLabel('实验历史范围').selectOption(runtimeKey);
  await trend.getByLabel('历史趋势指标').selectOption('success');
  await expect(trend).toContainText('两侧数值相同，曲线重合');
  await expect(trend).toContainText('Reference · 实线');
  await expect(trend).toContainText('LangGraph · 虚线');
  await expect(trend.locator('.chart-line.arm-1')).toHaveCSS('stroke-dasharray', '6px, 4px');
  expect(mutations).toEqual([]);
  expect(errors).toEqual([]);
  expect(parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${artifacts[0].experiment_id}`)).json()).experiment).toEqual(artifacts[0]);
});

test('history failure, unknown charges and empty samples never become fabricated graphics', async ({ page, request }) => {
  const original = parseApi(experimentResponseSchema, await (await request.post('/api/v1/experiments', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'clean', task_ids: ['order-status-001'],
  } })).json()).experiment;
  const dashboard = parseApi(dashboardSchema, await (await request.get('/api/v1/experiments')).json());
  const item = dashboard.items.find(value => value.experiment_id === original.experiment_id)!;
  let failed = true;
  await page.route('**/api/v1/experiments', route => failed ? route.fulfill({ status: 503, body: '{}' })
    : route.fulfill({ json: { ...dashboard, items: [{ ...item, provider: 'aihubmix', total_pairs: 0, comparison_key: null,
      baseline_total_cost: null, recovery_total_cost: null, baseline_reference_cost: null, recovery_reference_cost: null }] } }));
  await page.goto('/?mode=experiment');
  await page.locator('.history-disclosure > summary').click();
  await expect(page.getByRole('alert')).toContainText('历史指标读取失败');
  await expect(page.locator('.dashboard-spotlight')).toHaveCount(0);
  failed = false;
  await page.getByRole('button', { name: '刷新记录' }).click();
  await expect(page.locator('.dashboard-spotlight').getByRole('img', { name: /没有样本/ })).toHaveCount(2);
  await expect(page.locator('.dashboard-spotlight .ring-arm')).toHaveCount(0);
  await expect(page.locator('.experiment-dashboard-item progress')).toHaveCount(0);
  await expect(page.locator('.experiment-dashboard-item')).toContainText('无样本');
  await expect(page.locator('.experiment-dashboard-item')).toContainText('网关估算费用 未知 / 未知');
  await expect(page.locator('.experiment-dashboard-item')).not.toContainText('$0');
  await expect(page.getByLabel('同配置历史折线图').locator('.chart-line')).toHaveCount(0);
});
