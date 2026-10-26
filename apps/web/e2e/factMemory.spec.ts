import { readFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { episodeResponseSchema, experimentResponseSchema, parseApi } from '../src/apiContracts';
import { flowFrames } from '../src/flowFrames';

test('empty literal search displays actual guidance without granting read evidence or rerunning history', async ({ page, request }, testInfo) => {
  const response = await request.post('/api/v1/episodes', { data: {
    schema_version: '1.5', provider: 'fake', model: 'fake', tool_call_mode: 'serial',
    task_id: 'memory-fact-reuse-001', fault_profile: 'empty_result', max_steps: 2,
  } });
  expect(response.ok()).toBe(true);
  const saved = parseApi(episodeResponseSchema, await response.json()).artifact;
  expect(saved.evaluation.success).toBe(false);
  expect(saved.episode.final_state.acquired_evidence).toEqual([]);
  const frames = flowFrames(saved.events, saved.run_config.environment_version ?? 'unknown');
  const index = frames.findIndex(frame => frame.phase === 'return' && frame.tool === 'search_documents');
  expect(index).toBeGreaterThan(-1);
  const mutations: string[] = [];
  page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.goto(`/?episode_id=${saved.episode.episode_id}`);
  const flow = page.getByRole('region', { name: '工具调用动画回放', exact: true });
  await flow.getByRole('slider', { name: '动画进度' }).fill(String(index));
  await expect(flow).toContainText('无匹配');
  await expect(flow).toContainText('搜索不做同义词、翻译或语义推断');
  await page.setViewportSize({ width: 390, height: 900 });
  await flow.getByText('检索建议', { exact: true }).scrollIntoViewIfNeeded();
  await expect(flow.getByRole('complementary', { name: '当前阶段摘要' }).getByText(/没有字面匹配。搜索不做/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('empty-search-guidance-390.png') });
  await page.reload();
  expect(mutations).toEqual([]);
  expect(parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${saved.episode.episode_id}`)).json()).artifact).toEqual(saved);
});

for (const task of ['memory-fact-reuse-001', 'memory-large-return-002', 'memory-policy-version-003']) {
  test(`public fact task ${task} streams an actual derived answer and preserves history`, async ({ page, request }, testInfo) => {
    await page.goto('/?mode=single');
    await page.locator('#single-task-search').fill(task);
    await page.getByRole('button', { name: new RegExp(task) }).click();
    await page.locator('.advanced-settings > summary').click();
    await page.locator('#single-context-mode').selectOption('memory');
    await page.locator('#single-context-window').fill('1');
    await page.locator('#run-button').click();
    await expect(page).toHaveURL(/episode_id=/);
    const id = new URL(page.url()).searchParams.get('episode_id')!;
    const saved = parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact;
    expect(saved.evaluation.success).toBe(true);
    expect(saved.agent.tool_set_version).toBe('v1.5.0');
    expect(saved.episode.final_state.submission).toMatchObject({ answer: 'ineligible', evidence: ['document:INSPECTION', 'document:INTAKE', 'document:POLICY-B'] });
    const flow = page.getByRole('region', { name: '本次工具执行过程', exact: true });
    await expect(flow.getByLabel('最终输出', { exact: true })).toContainText('ineligible');
    await expect(flow.getByRole('slider', { name: '动画进度' })).toHaveCount(0);
    const sources = page.getByLabel('关联资料与实际引用', { exact: true });
    await expect(sources).toContainText('INTAKE');
    await expect(sources).toContainText('POLICY-B');
    const mutations: string[] = [];
    page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
    await page.reload();
    await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
    await page.emulateMedia({ reducedMotion: 'reduce' });
    for (const width of [1440, 1280, 768, 390]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: testInfo.outputPath(`${task}-${width}.png`) });
    }
    expect(mutations).toEqual([]);
    expect(parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact).toEqual(saved);
  });
}

test('fact task formal memory pair supports lazy diagnostics and the actual downloaded CSV', async ({ page, request }) => {
  await page.goto('/?mode=experiment');
  await page.getByLabel('对照变量', { exact: true }).selectOption('memory_ablation');
  await page.getByLabel('评测模型', { exact: true }).selectOption('fake');
  await page.locator('#exp-scenario-select').selectOption('clean');
  await page.getByRole('button', { name: '清空', exact: true }).click();
  await page.locator('#task-checkbox-list label').filter({ hasText: 'memory-fact-reuse-001' }).getByRole('checkbox').check();
  await page.locator('#run-exp-button').click();
  await expect(page).toHaveURL(/experiment_id=/);
  const id = new URL(page.url()).searchParams.get('experiment_id')!;
  const saved = parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${id}`)).json()).experiment;
  expect(saved.metrics.baseline_success_count).toBe(0);
  expect(saved.metrics.recovery_success_count).toBe(1);
  const review = page.getByRole('region', { name: '工具记忆执行差异', exact: true });
  await review.getByRole('button', { name: '读取两侧执行记录', exact: true }).click();
  await expect(review.getByRole('status')).toContainText('已读取 2 / 2 侧');
  await expect(review.getByRole('region', { name: '近期窗口 + 工具记忆执行记录', exact: true })).toContainText('POLICY-B');
  const downloading = page.waitForEvent('download');
  await page.locator('#btn-export-experiment-csv').click();
  const download = await downloading;
  const csv = await readFile((await download.path())!, 'utf8');
  expect(csv).toContain('memory-fact-reuse-001');
  expect(csv).toContain('memory_ablation');
  expect(csv).toContain('8192');
  const mutations: string[] = [];
  page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.reload();
  await expect(page.getByLabel('已保存工具记忆对照')).toBeVisible();
  expect(mutations).toEqual([]);
});
