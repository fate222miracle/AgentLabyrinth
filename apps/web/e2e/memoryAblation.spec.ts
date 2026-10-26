import { readFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { experimentResponseSchema, episodeResponseSchema, parseApi } from '../src/apiContracts';
import { flowFrames } from '../src/flowFrames';

test('same-window memory ablation runs from Web and preserves history, CSV and request diagnostics', async ({ page, request }, testInfo) => {
  await page.goto('/');
  await page.getByLabel('对照变量', { exact: true }).selectOption('memory_ablation');
  await page.getByLabel('评测模型', { exact: true }).selectOption('fake');
  await page.locator('#exp-scenario-select').selectOption('clean');
  await page.getByRole('button', { name: '清空', exact: true }).click();
  await page.locator('#task-checkbox-list label').filter({ hasText: 'order-status-007' }).getByRole('checkbox').check();
  await page.getByLabel('相同窗口轮次 N（两侧共用）', { exact: true }).fill('0');
  await page.locator('#run-exp-button').click();
  await expect(page.getByText('相同窗口轮次须为 1–100 的整数', { exact: true })).toBeVisible();
  await page.getByLabel('相同窗口轮次 N（两侧共用）', { exact: true }).fill('1');
  await page.getByLabel('右侧记忆上限 M（字节）', { exact: true }).fill('255');
  await page.locator('#run-exp-button').click();
  await expect(page.getByText('记忆大小须为 256–32768 的整数字节', { exact: true })).toBeVisible();
  await page.getByLabel('右侧记忆上限 M（字节）', { exact: true }).fill('8192');
  await page.locator('#run-exp-button').click();
  await expect(page).toHaveURL(/experiment_id=/);
  const experimentId = new URL(page.url()).searchParams.get('experiment_id')!;
  const original = parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${experimentId}`)).json()).experiment;
  expect(original.schema_version).toBe('1.5');
  expect(original.config.comparison_axis).toBe('memory_ablation');
  expect(original.metrics.baseline_success_count).toBe(0);
  expect(original.metrics.recovery_success_count).toBe(1);
  expect(original.metrics.retry_recovery_rate).toBeNull();
  const savedNote = page.getByLabel('已保存工具记忆对照');
  await expect(savedNote).toContainText('最近 1 轮工具交互 + 工具记忆');
  await expect(page.getByText('仅带记忆窗口通过', { exact: true })).toBeVisible();
  await page.locator('.experiment-draft > summary').click();
  await page.getByLabel('相同窗口轮次 N（两侧共用）', { exact: true }).fill('2');
  await expect(savedNote).toContainText('最近 1 轮工具交互');
  const mutations: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.reload();
  await expect(savedNote).toContainText('最近 1 轮工具交互');
  const review = page.getByRole('region', { name: '工具记忆执行差异', exact: true });
  const episodeGets: string[] = [];
  page.on('request', r => { if (/\/api\/v1\/episodes\/[^/?]+$/.test(r.url())) episodeGets.push(r.url()); });
  await expect(review.getByText('按需读取两条记录，不批量加载全部 Trace。')).toBeVisible();
  expect(episodeGets).toEqual([]);
  await review.getByRole('button', { name: '读取两侧执行记录', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(review.getByRole('status')).toContainText('已读取 2 / 2 侧');
  expect(episodeGets).toHaveLength(2);
  const left = review.getByRole('region', { name: '近期窗口（无记忆）执行记录', exact: true });
  const right = review.getByRole('region', { name: '近期窗口 + 工具记忆执行记录', exact: true });
  await expect(left).toContainText('评测未通过');
  await expect(right).toContainText('评测通过');
  // The last read is only proposed before MAX_STEPS: it must not count as returned evidence.
  await expect(left.locator('dl > div').filter({ hasText: '成功阅读' }).locator('dd')).toHaveText('2 次');
  await expect(left.locator('dl > div').filter({ hasText: '重复阅读' }).locator('dd')).toHaveText('1 次');
  await expect(right.locator('dl > div').filter({ hasText: '成功阅读' }).locator('dd')).toHaveText('1 次');
  await expect(right.locator('dl > div').filter({ hasText: '重复阅读' }).locator('dd')).toHaveText('0 次');
  await right.getByText('查看实际阅读的文档', { exact: true }).click();
  await expect(right.locator('.memory-read-documents li')).toHaveCount(1);
  const downloadEvent = page.waitForEvent('download');
  await page.locator('#btn-export-experiment-csv').click();
  const download = await downloadEvent;
  const csv = await readFile((await download.path())!, 'utf8');
  expect(csv).toContain('context_memory_max_bytes');
  expect(csv).toContain('"recent_window"');
  expect(csv).toContain('"recent_window_with_memory"');
  const rows = csv.trim().split('\r\n').slice(1);
  expect(rows[0].split(',').slice(21, 23)).toEqual(['"recent_tool_rounds"', '"1"']);
  expect(rows[1].split(',').slice(21, 23)).toEqual(['"recent_tool_rounds"', '"1"']);
  expect(rows[0].split(',')[27]).toBe('');
  expect(rows[1].split(',')[27]).toBe('"8192"');
  await download.saveAs(testInfo.outputPath('memory-ablation.csv'));
  for (const [width, height] of [[1440, 900], [1280, 800], [768, 1024], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await review.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(`memory-result-${width}.png`) });
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole('button', { name: '查看 order-status-007 的 近期窗口 + 工具记忆 Trace', exact: true }).click();
  const episodeId = new URL(page.url()).searchParams.get('episode_id')!;
  const artifact = parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${episodeId}`)).json()).artifact;
  const frames = flowFrames(artifact.events, artifact.run_config.environment_version ?? '');
  const projected = frames.findIndex((frame) => frame.phase === 'request' && Number((frame.payload.context as Record<string, unknown>)?.memory_entries_count) > 0);
  expect(projected).toBeGreaterThan(0);
  const slider = page.getByRole('slider', { name: '动画进度' });
  await slider.fill(String(projected));
  await slider.dispatchEvent('input');
  const diagnostic = page.getByLabel('已保存模型输入诊断');
  await expect(diagnostic).toContainText('记忆条数');
  await expect(diagnostic).toContainText('不是 Token');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.screenshot({ path: testInfo.outputPath('memory-request.png') });
  await page.goBack();
  await expect(savedNote).toContainText('最近 1 轮工具交互');
  await page.goForward();
  await expect(page).toHaveURL(new RegExp(`episode_id=${episodeId}`));
  expect(mutations).toEqual([]);
  expect(parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${experimentId}`)).json()).experiment).toEqual(original);
});

test('saved pair review isolates failed or mismatched records, missing traces and late task responses', async ({ page, request }, testInfo) => {
  const original = parseApi(experimentResponseSchema, await (await request.post('/api/v1/experiments', { data: {
    schema_version: '1.6', provider: 'fake', model: 'fake-model', scenario: 'clean', task_ids: ['order-status-007'], seeds: [1, 2],
    comparison_axis: 'memory_ablation', context_policy: { schema_version: '1.1', algorithm_version: 'tool-round-window-memory-v1',
      mode: 'recent_tool_rounds', max_tool_rounds: 1, memory_max_bytes: 8192 },
  } })).json()).experiment;
  const [first, second] = original.pairs;
  const mutations: string[] = [];
  page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.goto(`/?experiment_id=${original.experiment_id}`);
  const review = page.getByRole('region', { name: '工具记忆执行差异', exact: true });
  const leftRoute = `**/api/v1/episodes/${first.baseline_episode_id}`;
  await page.route(leftRoute, route => route.fulfill({ status: 404, json: { detail: 'unavailable' } }));
  await review.getByRole('button', { name: '读取两侧执行记录', exact: true }).click();
  await expect(review.getByRole('alert')).toContainText('此侧记录读取失败');
  await expect(review.getByRole('status')).toContainText('已读取 1 / 2 侧');
  await expect(review.getByText('评测通过', { exact: true })).toBeVisible();
  await page.unroute(leftRoute);
  await review.getByRole('button', { name: '重新读取两侧执行记录', exact: true }).click();
  await expect(review.getByRole('status')).toContainText('已读取 2 / 2 侧');

  const rightBody = await (await request.get(`/api/v1/episodes/${first.recovery_episode_id}`)).json();
  await page.route(leftRoute, route => route.fulfill({ json: rightBody }));
  await review.getByRole('button', { name: '重新读取两侧执行记录', exact: true }).click();
  await expect(review.getByRole('alert')).toContainText('结果 ID 与请求不一致');
  await page.unroute(leftRoute);
  await page.route(`**/api/v1/episodes/${first.recovery_episode_id}`, route => route.fulfill({ json: {
    ...rightBody, artifact: { ...rightBody.artifact, events: [] },
  } }));
  await review.getByRole('button', { name: '重新读取两侧执行记录', exact: true }).click();
  const right = review.getByRole('region', { name: '近期窗口 + 工具记忆执行记录', exact: true });
  await expect(right).toContainText('未保存完整起止 Trace');
  await expect(right.locator('dd').filter({ hasText: '未知' })).toHaveCount(2);
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
  await page.screenshot({ path: testInfo.outputPath('memory-review-reduce.png') });
  expect(mutations).toEqual([]);
  expect(parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${original.experiment_id}`)).json()).experiment).toEqual(original);
});
