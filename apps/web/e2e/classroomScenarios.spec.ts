import { readFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { episodeResponseSchema, experimentResponseSchema, metaSchema, parseApi } from '../src/apiContracts';

test('scenario setup preserves a chosen model and saved history, without automatic execution', async ({ page, request }, testInfo) => {
  const meta = parseApi(metaSchema, await (await request.get('/api/v1/meta')).json());
  await page.route('**/api/v1/meta', route => route.fulfill({ json: { ...meta,
    models: [...meta.models, { ...meta.models[0], id: 'classroom-candidate', name: 'Classroom candidate', provider: 'aihubmix', is_default: false }],
  } }));
  const artifact = parseApi(episodeResponseSchema, await (await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', task_id: 'order-status-001',
  } })).json()).artifact;
  const mutations: string[] = [];
  page.on('request', value => {
    if (value.url().includes('/api/') && value.method() !== 'GET') mutations.push(value.url());
  });
  await page.goto(`/?episode_id=${artifact.episode.episode_id}`);
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
  await page.locator('#config-panel > summary').click();
  await page.locator('#model-select').selectOption('classroom-candidate');
  await page.locator('.classroom-scenarios > summary').click();
  await page.getByRole('button', { name: '配置退款审批实时演示' }).click();
  await expect(page.locator('#model-select')).toHaveValue('classroom-candidate');
  await expect(page.locator('input[name="single-runtime-backend"][value="langgraph"]')).toBeChecked();
  await page.locator('.advanced-settings > summary').click();
  await expect(page.locator('#steps-input')).toHaveValue('10');
  await expect(page.locator('#single-token-budget')).toHaveValue('20000');
  await expect(page).toHaveURL(new RegExp(`episode_id=${artifact.episode.episode_id}`));
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
  await page.locator('.classroom-scenarios > summary').click();
  await page.getByRole('button', { name: '配置退货审核上下文对照' }).click();
  await expect(page.locator('#exp-model-select')).toHaveValue('classroom-candidate');
  await expect(page.locator('#comparison-axis')).toHaveValue('context_policy');
  await expect(page.locator('#context-window')).toHaveValue('1');
  await expect(page.locator('#task-checkbox-list input:checked')).toHaveCount(1);
  const selected = meta.tasks.find(task => task.name === 'return-evidence-chain-001')!;
  await expect(page.locator('#task-checkbox-list label').filter({ hasText: selected.name }).getByRole('checkbox')).toBeChecked();
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.locator('.classroom-scenarios > summary').click();
    await page.locator('.classroom-scenarios').scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath(`classroom-${width}.png`) });
    await page.locator('.classroom-scenarios > summary').click();
  }
  expect(mutations).toEqual([]);
  expect(parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${artifact.episode.episode_id}`)).json()).artifact).toEqual(artifact);
});

test('classroom refund runs live, then creates a frozen context pair with CSV and read-only refresh', async ({ page, request }, testInfo) => {
  await page.goto('/?mode=single');
  await page.getByRole('button', { name: '配置退款审批实时演示' }).click();
  await page.locator('#run-button').click();
  await expect(page).toHaveURL(/episode_id=/);
  const episodeId = new URL(page.url()).searchParams.get('episode_id')!;
  const episode = parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${episodeId}`)).json()).artifact;
  expect(episode.task.name).toBe('refund-evidence-chain-003');
  expect(episode.evaluation.success).toBe(true);
  expect(episode.episode.tool_call_count).toBe(7);
  await expect(page.getByRole('region', { name: '本次工具执行过程' }).getByRole('slider')).toHaveCount(0);
  await page.locator('.classroom-scenarios > summary').click();
  await page.getByRole('button', { name: '配置退款审批上下文对照' }).click();
  await page.locator('#run-exp-button').click();
  await expect(page).toHaveURL(/experiment_id=/);
  const id = new URL(page.url()).searchParams.get('experiment_id')!;
  const original = parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${id}`)).json()).experiment;
  expect(original.pairs).toHaveLength(1);
  expect(original.metrics.baseline_success_count).toBe(1);
  expect(original.metrics.recovery_success_count).toBe(0);
  expect(original.metrics.retry_recovery_rate).toBeNull();
  expect(original.config.seeds).toEqual([1]);
  expect(original.config.repeat_count).toBe(1);
  expect(original.config.max_total_tokens).toBe(40000);
  await expect(page.getByLabel('上下文实验解读')).toContainText('Fake 结果只验证机制');
  const downloading = page.waitForEvent('download');
  await page.locator('#btn-export-experiment-csv').click();
  const download = await downloading;
  const csv = await readFile((await download.path())!, 'utf8');
  expect(csv).toContain('refund-evidence-chain-003');
  expect(csv).toContain('"recent_tool_rounds","1"');
  expect(csv).toContain('"model_id","provider","task_name"');
  expect(csv).toContain('"fake-model","fake","refund-evidence-chain-003"');
  await download.saveAs(testInfo.outputPath('classroom-context.csv'));
  await page.screenshot({ path: testInfo.outputPath('classroom-context-result.png') });
  const posts: string[] = [];
  page.on('request', value => { if (value.url().includes('/api/') && value.method() !== 'GET') posts.push(value.url()); });
  await page.reload();
  await expect(page.getByLabel('已保存上下文对照')).toContainText('最近 1 轮');
  await expect(page.getByLabel('上下文实验解读')).toContainText('完整历史通过 1 / 1');
  expect(posts).toEqual([]);
  expect(parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${id}`)).json()).experiment).toEqual(original);
});

test('an older catalog cannot configure unavailable classroom tasks', async ({ page, request }) => {
  const meta = parseApi(metaSchema, await (await request.get('/api/v1/meta')).json());
  await page.route('**/api/v1/meta', route => route.fulfill({ json: { ...meta,
    tasks: meta.tasks.filter(task => task.category !== 'evidence_chain'),
  } }));
  const posts: string[] = [];
  page.on('request', value => { if (value.url().includes('/api/') && value.method() !== 'GET') posts.push(value.url()); });
  await page.goto('/?mode=single');
  await expect(page.getByText('当前任务目录未提供此场景')).toHaveCount(3);
  for (const button of await page.locator('.classroom-actions button').all()) await expect(button).toBeDisabled();
  expect(posts).toEqual([]);
});
