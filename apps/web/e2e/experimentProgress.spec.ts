import { expect, test } from '@playwright/test';
import { experimentProgressSchema, parseApi } from '../src/apiContracts';

test('stopped job exposes saved work through GET without starting the missing arm', async ({ page, request }, testInfo) => {
  const accepted = await request.post('/api/v1/experiments/jobs', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'success', task_ids: ['order-status-001'], max_total_tokens: 1,
  } });
  expect(accepted.ok()).toBeTruthy();
  const { experiment_id: id } = await accepted.json();
  await expect.poll(async () => (await (await request.get(`/api/v1/experiments/jobs/${id}`)).json()).status).toBe('failed');
  const url = `/api/v1/experiments/${id}/progress`;
  const original = parseApi(experimentProgressSchema, await (await request.get(url)).json());
  expect(original.arms.map(arm => arm.state)).toEqual(['completed', 'no_saved_record']);
  expect(original.arms[1].success).toBeNull();
  expect((await request.get(`/api/v1/experiments/${id}`)).status()).toBe(404);
  const mutations: string[] = [];
  page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.goto(`/?experiment_job_id=${id}`);
  await page.getByRole('button', { name: '查看保存进度', exact: true }).click();
  const panel = page.getByRole('region', { name: '实验保存进度', exact: true });
  await expect(panel).toContainText('已保存结束记录');
  await expect(panel).toContainText('尚无保存记录');
  await expect(panel.getByRole('link', { name: '查看保存的运行' })).toHaveCount(1);
  for (const [width, height] of [[1440, 900], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await panel.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(`progress-${width}.png`) });
  }
  await panel.getByRole('link', { name: '查看保存的运行' }).click();
  await expect(page).toHaveURL(new RegExp(`episode_id=${original.arms[0].episode_id}`));
  await page.reload();
  expect(mutations).toEqual([]);
  expect(parseApi(experimentProgressSchema, await (await request.get(url)).json())).toEqual(original);
});

test('progress errors and rapid switching never replace the selected source or resume it', async ({ page }) => {
  const first = '10000000-0000-4000-8000-000000000001';
  const second = '10000000-0000-4000-8000-000000000002';
  const response = (id: string) => ({ schema_version: '1.0', experiment_id: id, comparison_axis: 'planning', arms: [{
    episode_id: '10000000-0000-4000-8000-000000000003', task_name: 'saved-task', seed: 1, repeat_index: 1,
    arm: 'baseline', state: 'invalid', success: null, termination_reason: null, detail: '保存记录损坏或来源不匹配。',
  }] });
  await page.route('**/api/v1/experiments/resumable', route => route.fulfill({ json: [first, second] }));
  await page.route(`**/api/v1/experiments/${first}/progress`, route => route.fulfill({ json: response(second) }));
  await page.route(`**/api/v1/experiments/${second}/progress`, route => route.fulfill({ json: response(second) }));
  const mutations: string[] = [];
  page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.goto('/?mode=experiment');
  await page.getByRole('button', { name: `查看 Experiment 保存进度 ${first}`, exact: true }).focus();
  await page.keyboard.press('Enter');
  const panel = page.getByRole('region', { name: '实验保存进度', exact: true });
  await expect(panel.getByRole('alert')).toContainText('结果 ID 与请求不一致');
  await page.unroute(`**/api/v1/experiments/${first}/progress`);
  await page.route(`**/api/v1/experiments/${first}/progress`, route => route.fulfill({ status: 503, json: {} }));
  await panel.getByRole('button', { name: '重新读取进度' }).click();
  await expect(panel.getByRole('alert')).toContainText('503');
  await page.unroute(`**/api/v1/experiments/${first}/progress`);
  let release!: () => void;
  let arrived!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  const received = new Promise<void>(resolve => { arrived = resolve; });
  await page.route(`**/api/v1/experiments/${first}/progress`, async route => {
    arrived(); await held;
    await route.fulfill({ json: response(first) }).catch(() => {});
  });
  await panel.getByRole('button', { name: '重新读取进度' }).click();
  await received;
  await page.getByRole('button', { name: `查看 Experiment 保存进度 ${second}`, exact: true }).click();
  await expect(panel).toContainText(second);
  await expect(panel).toContainText('保存记录不可用');
  release();
  await expect(panel).not.toContainText(first);
  await expect(panel.getByRole('link')).toHaveCount(0);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await panel.getByRole('button', { name: '关闭进度' }).click();
  await expect(panel).toHaveCount(0);
  await page.reload();
  await expect(panel).toHaveCount(0);
  expect(mutations).toEqual([]);
});
