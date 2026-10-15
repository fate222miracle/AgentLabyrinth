import { readFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { episodeResponseSchema, experimentResponseSchema, parseApi } from '../src/apiContracts';
import { flowFrames } from '../src/flowFrames';

test('live single memory keeps successful sources and saved history independent from the next draft', async ({ page, request }, testInfo) => {
  await page.goto('/?mode=single');
  await page.locator('#single-task-search').fill('order-status-007');
  await page.getByRole('button', { name: /order-status-007/ }).click();
  await page.locator('.advanced-settings > summary').click();
  await page.locator('#single-context-mode').selectOption('memory');
  await page.locator('#single-context-window').fill('1');
  await page.locator('#run-button').click();
  await expect(page).toHaveURL(/episode_id=/);
  const id = new URL(page.url()).searchParams.get('episode_id')!;
  const saved = parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact;
  expect(saved.evaluation.success).toBe(true);
  expect(saved.agent.context_policy?.memory_max_bytes).toBe(8192);
  const requests = saved.events.filter(event => event.event_type === 'MODEL_REQUESTED');
  expect(requests.at(-1)?.payload.context).toMatchObject({ memory_entries_count: 1, memory_source_call_ids: ['call_search_1'] });
  await expect(page.locator('.episode-runtime')).toContainText('工具记忆（最多 8192 字节）');
  const posts: string[] = [];
  page.on('request', event => { if (event.url().includes('/api/') && event.method() !== 'GET') posts.push(event.url()); });
  await page.locator('#config-panel > summary').click();
  await page.locator('#single-context-mode').selectOption('full');
  await expect(page.locator('.episode-runtime')).toContainText('工具记忆（最多 8192 字节）');
  await page.reload();
  await expect(page.locator('.episode-runtime')).toContainText('工具记忆（最多 8192 字节）');
  await expect(page.getByLabel('已保存模型输入诊断')).toHaveCount(0);
  const frames = flowFrames(saved.events, saved.run_config.environment_version ?? '');
  const memoryFrame = frames.findIndex(frame => frame.phase === 'request' && frame.step === 3);
  expect(memoryFrame).toBeGreaterThan(0);
  const slider = page.getByRole('slider', { name: '动画进度' });
  await slider.fill(String(memoryFrame));
  await slider.dispatchEvent('input');
  await expect(page.getByLabel('已保存模型输入诊断')).toContainText('记忆来源调用 ID');
  await expect(page.getByLabel('已保存模型输入诊断')).toContainText('call_search_1');
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`memory-${width}.png`) });
  }
  expect(posts).toEqual([]);
  expect(parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact).toEqual(saved);
});

test('context pair freezes memory limits, CSV exports them, and invalid policies or tiny memory remain failures', async ({ page, request }) => {
  await page.goto('/?mode=experiment');
  await page.locator('#comparison-axis').selectOption('context_policy');
  await page.locator('#context-mode').selectOption('memory');
  await page.locator('#context-window').fill('1');
  await page.getByRole('button', { name: '清空', exact: true }).click();
  await page.locator('#task-checkbox-list label').filter({ hasText: 'order-status-007' }).getByRole('checkbox').check();
  await page.locator('#run-exp-button').click();
  await expect(page).toHaveURL(/experiment_id=/);
  const id = new URL(page.url()).searchParams.get('experiment_id')!;
  const saved = parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${id}`)).json()).experiment;
  expect(saved.metrics.baseline_success_count).toBe(1);
  expect(saved.metrics.recovery_success_count).toBe(1);
  expect(saved.metrics.retry_recovery_rate).toBeNull();
  await expect(page.getByLabel('已保存上下文对照')).toContainText('工具记忆');
  await expect(page.getByLabel('上下文实验解读')).toContainText('不能单独证明记忆的收益');
  const downloading = page.waitForEvent('download');
  await page.locator('#btn-export-experiment-csv').click();
  const download = await downloading;
  const csv = await readFile((await download.path())!, 'utf8');
  expect(csv).toContain('"context_algorithm_version","context_memory_max_bytes"');
  expect(csv).toContain('"tool-round-window-memory-v1","8192"');
  const posts: string[] = [];
  page.on('request', event => { if (event.url().includes('/api/') && event.method() !== 'GET') posts.push(event.url()); });
  await page.reload();
  await expect(page.getByLabel('已保存上下文对照')).toContainText('工具记忆');
  expect(posts).toEqual([]);
  const policy = saved.config.recovery_agent!.context_policy!;
  const invalid = await request.post('/api/v1/episodes', { data: { provider: 'fake', model: 'fake-model',
    context_policy: { ...policy, schema_version: '1.0' } } });
  expect(invalid.status()).toBe(422);
  const tiny = parseApi(episodeResponseSchema, await (await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', task_id: 'order-status-007', context_policy: { ...policy, memory_max_bytes: 256 },
  } })).json()).artifact;
  expect(tiny.evaluation.success).toBe(false);
  expect(tiny.episode.termination_reason).toBe('MAX_STEPS');
});
