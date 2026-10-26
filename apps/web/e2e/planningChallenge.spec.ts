import { readFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { experimentResponseSchema, episodeResponseSchema, parseApi } from '../src/apiContracts';

const RIGHT_TRACE = '查看 planning-branch-001 的 声明计划 Trace';

for (const [task, prefix, answer] of [
  ['planning-route-002', 'RTE', 'eligible'], ['planning-omit-003', 'OMT', 'ineligible'],
]) {
  test(`conditional task ${task} streams its applicable evidence and actual answer`, async ({ page, request }, testInfo) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/?mode=single');
    await page.locator('#single-task-search').fill(task);
    await page.getByRole('button', { name: new RegExp(task) }).click();
    await page.locator('.single-advanced-settings > summary').click();
    await page.getByLabel('启用声明计划', { exact: true }).check();
    await page.locator('#run-button').focus();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/episode_id=/);
    const id = new URL(page.url()).searchParams.get('episode_id')!;
    const saved = parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact;
    expect(saved.evaluation.success).toBe(true);
    expect(saved.episode.final_state.submission).toMatchObject({ answer, evidence: expect.any(Array) });
    expect((saved.episode.final_state.submission as { evidence: unknown[] }).evidence).toHaveLength(4);
    const flow = page.getByRole('region', { name: '本次工具执行过程', exact: true });
    await expect(flow.getByLabel('最终输出', { exact: true })).toContainText(answer);
    await expect(flow.getByRole('slider', { name: '动画进度' })).toHaveCount(0);
    const declaration = page.getByRole('region', { name: '当前计划声明', exact: true });
    await expect(declaration).toContainText('全部适用核验');
    const sources = page.getByLabel('关联资料与实际引用', { exact: true });
    await expect(sources).toContainText(`${prefix}-CHECK`);
    const mutations: string[] = [];
    page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
    await page.reload();
    await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
    const replay = page.getByRole('region', { name: '工具调用动画回放', exact: true });
    const slider = replay.getByRole('slider', { name: '动画进度' });
    await slider.fill((await slider.getAttribute('max'))!);
    await expect(replay.getByLabel('最终输出', { exact: true })).toContainText(answer);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    for (const width of [1440, 1280, 768, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await declaration.scrollIntoViewIfNeeded();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: testInfo.outputPath(`${task}-${width}.png`) });
    }
    await slider.fill('0');
    await expect(declaration).toHaveCount(0);
    expect(mutations).toEqual([]);
    expect(errors).toEqual([]);
    expect(parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact).toEqual(saved);
  });
}

test('conditional planning pair uses the normal Web matrix and downloads all four CSV rows', async ({ page, request }, testInfo) => {
  await page.goto('/?mode=experiment');
  await page.getByLabel('对照变量', { exact: true }).selectOption('planning');
  await page.getByLabel('评测模型', { exact: true }).selectOption('fake');
  await page.locator('#exp-scenario-select').selectOption('clean');
  await page.getByRole('button', { name: '清空', exact: true }).click();
  for (const name of ['planning-route-002', 'planning-omit-003']) {
    await page.locator('#task-checkbox-list label').filter({ hasText: name }).getByRole('checkbox').check();
  }
  await page.locator('#run-exp-button').click();
  await expect(page).toHaveURL(/experiment_id=/);
  const id = new URL(page.url()).searchParams.get('experiment_id')!;
  const saved = parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${id}`)).json()).experiment;
  expect(saved.metrics.baseline_success_count).toBe(2);
  expect(saved.metrics.recovery_success_count).toBe(2);
  expect(saved.metrics.retry_recovery_rate).toBeNull();
  const review = page.getByRole('region', { name: '规划执行差异', exact: true });
  await review.getByRole('button', { name: '读取两侧执行记录', exact: true }).click();
  await expect(review.getByRole('status')).toContainText('已读取 2 / 2 侧');
  const downloading = page.waitForEvent('download');
  await page.locator('#btn-export-experiment-csv').click();
  const download = await downloading;
  const csv = await readFile((await download.path())!, 'utf8');
  expect(csv.trim().split('\r\n')).toHaveLength(5);
  expect(csv).toContain('planning-route-002');
  expect(csv).toContain('planning-omit-003');
  expect(csv).toContain('plan-update-v1');
  await download.saveAs(testInfo.outputPath('conditional-planning.csv'));
  const mutations: string[] = [];
  page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.reload();
  await expect(page.getByLabel('已保存规划对照')).toBeVisible();
  expect(mutations).toEqual([]);
  expect(parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${id}`)).json()).experiment).toEqual(saved);
});

test('single planning has an explicit draft, an arrived declaration and read-only history', async ({ page, request }, testInfo) => {
  await page.goto('/?mode=single');
  await page.locator('#single-task-search').fill('planning-branch-001');
  await page.getByRole('button', { name: /planning-branch-001/ }).click();
  await page.locator('.single-advanced-settings > summary').click();
  await page.getByLabel('启用声明计划', { exact: true }).check();
  await page.locator('#run-button').click();
  await expect(page).toHaveURL(/episode_id=/);
  const id = new URL(page.url()).searchParams.get('episode_id')!;
  const artifact = parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact;
  expect(artifact.evaluation.success).toBe(true);
  expect(artifact.agent.planning?.algorithm_version).toBe('plan-update-v1');
  const declaration = page.getByRole('region', { name: '当前计划声明', exact: true });
  await expect(declaration).toContainText('模型声明');
  await expect(declaration).toContainText('facts');
  const mutations: string[] = [];
  page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.reload();
  await expect(page.locator('.episode-runtime')).toContainText('声明计划');
  const flow = page.getByRole('region', { name: '工具调用动画回放', exact: true });
  const slider = flow.getByRole('slider', { name: '动画进度' });
  await slider.fill((await slider.getAttribute('max'))!);
  await page.setViewportSize({ width: 390, height: 900 });
  await declaration.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('single-plan-390.png') });
  // The first cursor predates any declaration, even though the complete artifact contains it.
  await flow.getByRole('slider', { name: '动画进度' }).fill('0');
  await expect(declaration).toHaveCount(0);
  expect(mutations).toEqual([]);
});

test('planning challenge runs from Web and shows the declared plan apart from executed tools', async ({ page, request }, testInfo) => {
  await page.goto('/');
  await page.getByLabel('对照变量', { exact: true }).selectOption('planning');
  await page.getByLabel('评测模型', { exact: true }).selectOption('fake');
  await page.locator('#exp-scenario-select').selectOption('clean');
  await page.getByRole('button', { name: '清空', exact: true }).click();
  await page.locator('#task-checkbox-list label').filter({ hasText: 'planning-branch-001' }).getByRole('checkbox').check();
  await page.locator('#run-exp-button').click();
  await expect(page).toHaveURL(/experiment_id=/);
  const experimentId = new URL(page.url()).searchParams.get('experiment_id')!;
  const original = parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${experimentId}`)).json()).experiment;
  expect(original.schema_version).toBe('1.6');
  expect(original.config.comparison_axis).toBe('planning');
  // The declared plan is the only changed variable: the left arm declares nothing and both fix full context.
  expect(original.config.baseline_agent?.planning ?? null).toBeNull();
  expect(original.config.recovery_agent?.planning?.algorithm_version).toBe('plan-update-v1');
  expect(original.config.baseline_agent?.context_policy?.mode).toBe('full');
  expect(original.config.recovery_agent?.context_policy?.mode).toBe('full');
  expect(original.metrics.baseline_success_count).toBe(1);
  expect(original.metrics.recovery_success_count).toBe(1);
  expect(original.metrics.retry_recovery_rate).toBeNull();
  const savedNote = page.getByLabel('已保存规划对照');
  await expect(savedNote).toContainText('plan-update-v1');
  await expect(page.getByText('有无声明均通过', { exact: true })).toBeVisible();
  await page.locator('.experiment-draft > summary').click();
  await page.locator('#planning-recovery').selectOption('handwritten_recovery');
  await expect(savedNote).toContainText('plan-update-v1');
  const mutations: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.reload();
  await expect(savedNote).toContainText('plan-update-v1');
  const review = page.getByRole('region', { name: '规划执行差异', exact: true });
  const episodeGets: string[] = [];
  page.on('request', r => { if (/\/api\/v1\/episodes\/[^/?]+$/.test(r.url())) episodeGets.push(r.url()); });
  await expect(review.getByText('按需读取两条记录，不批量加载全部 Trace。')).toBeVisible();
  expect(episodeGets).toEqual([]);
  await review.getByRole('button', { name: '读取两侧执行记录', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(review.getByRole('status')).toContainText('已读取 2 / 2 侧');
  expect(episodeGets).toHaveLength(2);
  const left = review.getByRole('region', { name: '无声明计划执行记录', exact: true });
  const right = review.getByRole('region', { name: '声明计划执行记录', exact: true });
  await expect(left).toContainText('评测通过');
  await expect(right).toContainText('评测通过');
  // The declaration is a claim, so it must be shown separately from the tools that actually ran.
  await expect(left).toContainText('计划声明：0 次（本侧未声明计划）');
  await expect(right).toContainText('计划声明：1 次');
  await expect(right.locator('ul.memory-read-documents').first().locator('li')).toHaveCount(2);
  await expect(right.locator('ul.memory-read-documents').first()).toContainText('facts');
  await right.getByText('已实际执行的工具', { exact: true }).click();
  await expect(right.locator('details.chart-data')).toContainText('update_plan');
  await expect(left.locator('details.chart-data')).not.toContainText('update_plan');
  const downloadEvent = page.waitForEvent('download');
  await page.locator('#btn-export-experiment-csv').click();
  const download = await downloadEvent;
  const csv = await readFile((await download.path())!, 'utf8');
  expect(csv.split('\r\n')[0]).toContain('planning_algorithm_version');
  expect(csv).toContain('"no_plan"');
  expect(csv).toContain('"declared_plan"');
  const csvRows = csv.trim().split('\r\n').slice(1);
  expect(csvRows[0].split(',').at(-1)).toBe('');
  expect(csvRows[1].split(',').at(-1)).toBe('"plan-update-v1"');
  await download.saveAs(testInfo.outputPath('planning-challenge.csv'));
  for (const [width, height] of [[1440, 900], [1280, 800], [768, 1024], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await review.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(`planning-result-${width}.png`) });
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole('button', { name: RIGHT_TRACE, exact: true }).click();
  const episodeId = new URL(page.url()).searchParams.get('episode_id')!;
  const artifact = parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${episodeId}`)).json()).artifact;
  expect(artifact.events.some((event) => event.event_type === 'PLAN_UPDATED')).toBeTruthy();
  // The declared plan is a real recorded step, shown from the saved event, not from the task goal.
  await page.getByRole('button', { name: '过程概览', exact: true }).click();
  await expect(page.locator('.step-card').filter({ hasText: 'update_plan' }).first()).toBeVisible();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.screenshot({ path: testInfo.outputPath('planning-trace-reduce.png') });
  await page.goBack();
  await expect(savedNote).toContainText('plan-update-v1');
  await page.goForward();
  await expect(page).toHaveURL(new RegExp(`episode_id=${episodeId}`));
  expect(mutations).toEqual([]);
  expect(parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${experimentId}`)).json()).experiment).toEqual(original);
});

test('planning review isolates failed reads and empty traces without rerunning the task', async ({ page, request }, testInfo) => {
  const original = parseApi(experimentResponseSchema, await (await request.post('/api/v1/experiments', { data: {
    schema_version: '1.9', provider: 'fake', model: 'fake-model', scenario: 'clean', task_ids: ['planning-branch-001'], seeds: [1, 2],
    comparison_axis: 'planning',
  } })).json()).experiment;
  const [first, second] = original.pairs;
  const mutations: string[] = [];
  page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.goto(`/?experiment_id=${original.experiment_id}`);
  const review = page.getByRole('region', { name: '规划执行差异', exact: true });
  const leftRoute = `**/api/v1/episodes/${first.baseline_episode_id}`;
  await page.route(leftRoute, route => route.fulfill({ status: 404, json: { detail: 'unavailable' } }));
  await review.getByRole('button', { name: '读取两侧执行记录', exact: true }).click();
  await expect(review.getByRole('alert')).toContainText('此侧记录读取失败');
  await expect(review.getByRole('status')).toContainText('已读取 1 / 2 侧');
  await page.unroute(leftRoute);
  const rightBody = await (await request.get(`/api/v1/episodes/${first.recovery_episode_id}`)).json();
  await page.route(leftRoute, route => route.fulfill({ json: rightBody }));
  await review.getByRole('button', { name: '重新读取两侧执行记录', exact: true }).click();
  await expect(review.getByRole('alert')).toContainText('结果 ID 与请求不一致');
  await page.unroute(leftRoute);
  await page.route(`**/api/v1/episodes/${first.recovery_episode_id}`, route => route.fulfill({ json: {
    ...rightBody, artifact: { ...rightBody.artifact, events: [] },
  } }));
  await review.getByRole('button', { name: '重新读取两侧执行记录', exact: true }).click();
  const right = review.getByRole('region', { name: '声明计划执行记录', exact: true });
  await expect(right).toContainText('未保存完整起止 Trace，计划声明未知，不按零处理。');
  await page.unroute(`**/api/v1/episodes/${first.recovery_episode_id}`);

  let release!: () => void;
  let arrived!: () => void;
  const received = new Promise<void>(resolve => { arrived = resolve; });
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route(leftRoute, async route => {
    const response = await route.fetch();
    arrived();
    await held;
    await route.fulfill({ response }).catch(() => {}); // Request may already be cancelled by task selection.
  });
  await review.getByRole('button', { name: '重新读取两侧执行记录', exact: true }).click();
  await received;
  await review.getByLabel('选择要审查的任务对').selectOption('1');
  await expect(review.locator('.memory-review-arms')).toHaveCount(0);
  await review.getByRole('button', { name: '读取两侧执行记录', exact: true }).click();
  await expect(review.getByRole('status')).toContainText('已读取 2 / 2 侧');
  release();
  await expect(review).toContainText(second.baseline_episode_id);
  await expect(review).not.toContainText(first.baseline_episode_id);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await review.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath('planning-review-reduce.png') });
  expect(mutations).toEqual([]);
  expect(parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${original.experiment_id}`)).json()).experiment).toEqual(original);
});
