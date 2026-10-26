import { readFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { episodeResponseSchema, experimentResponseSchema, parseApi } from '../src/apiContracts';

test('multiple calls render independently live and in a saved step without mutating history', async ({ page, request }, testInfo) => {
  await page.goto('/?mode=single');
  await page.locator('#single-task-search').fill('memory-fact-reuse-001');
  await page.getByRole('button', { name: /memory-fact-reuse-001/ }).click();
  await page.locator('.advanced-settings > summary').click();
  await expect(page.locator('#single-call-mode')).toHaveValue('serial');
  await page.locator('#run-button').click();
  await expect(page).toHaveURL(/episode_id=/);
  const id = new URL(page.url()).searchParams.get('episode_id')!;
  const saved = parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact;
  expect(saved.evaluation.success).toBe(true);
  expect(saved.episode.model_call_count).toBe(4);
  expect(saved.episode.tool_call_count).toBe(5);
  expect(saved.agent.model.tool_call_mode).toBe('serial');
  const flow = page.getByRole('region', { name: '本次工具执行过程', exact: true });
  await expect(flow.getByLabel('最终输出', { exact: true })).toContainText('ineligible');
  await expect(flow.locator('.react-flow__node').filter({ hasText: 'INSPECTION' })).toHaveCount(1);
  await expect(flow.locator('.react-flow__node').filter({ hasText: 'POLICY-B' })).toHaveCount(1);
  const mutations: string[] = [];
  page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.reload();
  await expect(page.locator('.episode-runtime')).toContainText('多工具 · 顺序执行');
  await page.getByRole('button', { name: '过程概览', exact: true }).click();
  await page.locator('.step-card').filter({ hasText: '多工具调用 · 2 个' }).click();
  const list = page.getByLabel('本轮工具列表', { exact: true });
  await expect(list).toContainText('INSPECTION');
  await expect(list).toContainText('POLICY-B');
  await expect(list.getByText(/执行成功/)).toHaveCount(2);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await list.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`batch-${width}.png`) });
  }
  expect(mutations).toEqual([]);
  expect(parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact).toEqual(saved);
});

test('formal memory pair freezes the same call mode and exports it in downloaded CSV', async ({ page, request }) => {
  await page.goto('/?mode=experiment');
  await page.getByLabel('对照变量', { exact: true }).selectOption('memory_ablation');
  await page.getByLabel('评测模型', { exact: true }).selectOption('fake');
  await page.locator('#exp-scenario-select').selectOption('clean');
  await page.getByRole('button', { name: '清空', exact: true }).click();
  await page.locator('#task-checkbox-list label').filter({ hasText: 'memory-fact-reuse-001' }).getByRole('checkbox').check();
  await expect(page.locator('#experiment-call-mode')).toHaveValue('serial');
  await page.locator('#run-exp-button').click();
  await expect(page).toHaveURL(/experiment_id=/);
  const id = new URL(page.url()).searchParams.get('experiment_id')!;
  const saved = parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${id}`)).json()).experiment;
  expect(typeof saved.config.model === 'object' && saved.config.model?.tool_call_mode).toBe('serial');
  const downloading = page.waitForEvent('download');
  await page.locator('#btn-export-experiment-csv').click();
  const download = await downloading;
  const csv = await readFile((await download.path())!, 'utf8');
  expect(csv).toContain('"tool_call_mode"');
  expect(csv.split('\n').filter(row => row.includes('"serial"'))).toHaveLength(2);
  await page.reload();
  await expect(page.getByLabel('已保存实验来源')).toContainText('多工具 · 顺序执行');
});
