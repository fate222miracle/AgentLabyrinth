import { expect, test } from '@playwright/test';
import { experimentResponseSchema, parseApi } from '../src/apiContracts';

test('third Runtime is selectable, labelled honestly and exported without rewriting the saved experiment', async ({ page, request }, testInfo) => {
  const response = await request.post('/api/v1/experiments', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'success', task_ids: ['order-status-001'],
    comparison_axis: 'runtime_backend', tool_call_mode: 'single',
    schema_version: '1.10', runtime_target: 'pydantic_ai',
  } });
  expect(response.ok()).toBeTruthy();
  const original = parseApi(experimentResponseSchema, await response.json()).experiment;
  expect(original.schema_version).toBe('1.7');
  expect(original.config.recovery_agent?.runtime_backend).toBe('pydantic_ai');

  const mutations: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.goto(`/?experiment_id=${original.experiment_id}`);

  await expect(page.getByText('Reference Runtime ↔ PydanticAI Runtime', { exact: true })).toBeVisible();

  await page.locator('.experiment-draft > summary').click();
  await page.getByLabel('对照变量', { exact: true }).selectOption('runtime_backend');
  const target = page.locator('#runtime-target');
  await expect(target).toBeVisible();
  await expect(target.locator('option')).toHaveText(['LangGraph', 'PydanticAI']);
  await target.selectOption('pydantic_ai');
  const summary = page.locator('div[aria-label="Runtime 对照"]');
  await expect(summary).toContainText('PydanticAI');
  await expect(summary).toContainText('框架驱动单步节点，步间由适配器推进');
  await target.selectOption('langgraph');
  await expect(summary).toContainText('StateGraph 独立节点调度');

  const download = page.waitForEvent('download');
  await page.locator('#btn-export-experiment-csv').click();
  const file = await download;
  await file.saveAs(testInfo.outputPath('experiment.csv'));
  const stream = await file.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(chunk as Buffer);
  const csv = Buffer.concat(chunks).toString('utf8');
  const rightRow = csv.split('\r\n').find((line) => line.includes(',"pydantic_ai",'));
  expect(rightRow).toBeDefined();
  expect(rightRow).toContain('"pydantic-ai-slim-2.57.0"');
  expect(csv.split('\r\n')[0]).toContain('runtime_version');
  expect(csv).toContain('"reference-v2"');

  expect(mutations).toEqual([]);
  const saved = parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${original.experiment_id}`)).json()).experiment;
  expect(saved).toEqual(original);
});

test('single run offers the third scheduler with its step boundary disclosed', async ({ page }) => {
  await page.goto('/?mode=single');
  const option = page.getByRole('radio', { name: 'PydanticAI 框架节点驱动单步，步间由适配器推进' });
  await expect(page.locator('fieldset.execution-choice')).toContainText('PydanticAI 的步间推进仍由适配器完成');
  await expect(option).toBeEnabled();
  await option.check();
  await expect(page.locator('.single-launch-summary')).toContainText('PydanticAI');
});
