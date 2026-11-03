import { readFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { episodeResponseSchema, experimentResponseSchema, parseApi } from '../src/apiContracts';

test('single run exposes the bounded reflection toggle and saved Trace', async ({ page, request }) => {
  await page.goto('/?mode=single');
  await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
  await page.locator('#single-task-search').fill('reflection-stale-alias-001');
  await page.getByRole('button', { name: /reflection-stale-alias-001/ }).click();
  await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
  await page.locator('.single-advanced-settings > summary').click();
  await page.getByLabel('启用停滞后一次行动修正', { exact: true }).check();
  await expect(page.locator('#single-call-mode')).toBeDisabled();
  await page.locator('#run-button').click();
  await expect(page).toHaveURL(/episode_id=/);
  const id = new URL(page.url()).searchParams.get('episode_id')!;
  const saved = parseApi(episodeResponseSchema,
    await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact;
  expect(saved.evaluation.success).toBe(true);
  expect(saved.agent.reflection?.algorithm_version).toBe('no-progress-revision-v1');
  expect(saved.events.filter(event => event.event_type === 'REFLECTION_PRODUCED')).toHaveLength(1);
  await expect(page.locator('.episode-runtime')).toContainText('停滞后最多一次');
  await page.reload();
  await page.getByRole('button', { name: '过程概览', exact: true }).click();
  await expect(page.locator('.step-card').filter({ hasText: '生成行动修正' })).toBeVisible();
});

test('bounded reflection runs as a saved single-variable pair and stays read-only on refresh', async ({ page, request }, testInfo) => {
  await page.goto('/?mode=experiment');
  await page.getByLabel('对照变量', { exact: true }).selectOption('reflection');
  await page.getByLabel('评测模型', { exact: true }).selectOption('fake');
  await page.locator('#exp-scenario-select').selectOption('clean');
  await page.getByRole('button', { name: '全选', exact: true }).click();
  await expect(page.locator('#task-checkbox-list label')).toHaveCount(1);
  await expect(page.locator('#task-checkbox-list')).toContainText('reflection-stale-alias-001');
  await page.locator('#run-exp-button').click();
  await expect(page).toHaveURL(/experiment_id=/);
  const id = new URL(page.url()).searchParams.get('experiment_id')!;
  const saved = parseApi(experimentResponseSchema,
    await (await request.get(`/api/v1/experiments/${id}`)).json()).experiment;

  expect(saved.schema_version).toBe('1.8');
  expect(saved.config.comparison_axis).toBe('reflection');
  expect(saved.config.baseline_agent?.reflection ?? null).toBeNull();
  expect(saved.config.recovery_agent?.reflection?.algorithm_version).toBe('no-progress-revision-v1');
  expect(saved.metrics.baseline_success_count).toBe(0);
  expect(saved.metrics.recovery_success_count).toBe(1);
  await expect(page.getByText('仅有界反思通过', { exact: true })).toBeVisible();
  await expect(page.getByLabel('已保存反思对照')).toContainText('最多一次');

  const review = page.getByRole('region', { name: '停滞反思差异', exact: true });
  await review.getByRole('button', { name: '读取两侧执行记录', exact: true }).click();
  await expect(review.getByRole('status')).toContainText('已读取 2 / 2 侧');
  await expect(review.getByRole('region', { name: '无反思执行记录' })).toContainText('本侧未启用');
  const right = review.getByRole('region', { name: '有界反思执行记录' });
  await expect(right).toContainText('已生成一次行动修正');
  await expect(right).toContainText('ORD-001');

  const downloadEvent = page.waitForEvent('download');
  await page.locator('#btn-export-experiment-csv').click();
  const csv = await readFile((await (await downloadEvent).path())!, 'utf8');
  expect(csv.split('\r\n')[0]).toContain('reflection_algorithm_version');
  expect(csv).toContain('"no_reflection"');
  expect(csv).toContain('"bounded_reflection"');
  expect(csv).toContain('"no-progress-revision-v1"');

  const mutations: string[] = [];
  page.on('request', event => { if (event.url().includes('/api/') && event.method() !== 'GET') mutations.push(event.url()); });
  await page.reload();
  await expect(page.getByLabel('已保存反思对照')).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await review.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath('reflection-result-390.png') });
  expect(mutations).toEqual([]);
  expect(parseApi(experimentResponseSchema,
    await (await request.get(`/api/v1/experiments/${id}`)).json()).experiment).toEqual(saved);
});
