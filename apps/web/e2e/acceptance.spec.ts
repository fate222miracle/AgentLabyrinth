import { expect, test, type Page, type APIRequestContext } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { copyFileSync, mkdirSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { episodeArtifactSchema, episodeResponseSchema, experimentResponseSchema, parseApi } from '../src/apiContracts';

async function createEpisode(request: APIRequestContext) {
  const response = await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'success', task_id: 'order-status-001',
  } });
  expect(response.ok()).toBeTruthy();
  const value: unknown = await response.json();
  return parseApi(episodeResponseSchema, value);
}

async function openEpisode(page: Page, id: string) {
  await page.goto(`/?episode_id=${id}`);
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
}

test('actual context artifact → API read-only replay → rerun with original policy', async ({ page, request }, testInfo) => {
  const root = fileURLToPath(new URL('../../../', import.meta.url));
  const runId = process.env.AGENTLABYRINTH_E2E_RUN_ID;
  if (!runId) throw new Error('Missing isolated E2E run ID');
  const directory = join(root, 'artifacts', 'playwright', runId, 'context');
  const python = join(root, '.venv', process.platform === 'win32' ? 'Scripts' : 'bin',
    process.platform === 'win32' ? 'python.exe' : 'python');
  // Run the actual offline producer, then let the isolated API read its saved files.
  execFileSync(python, ['-m', 'scripts.context_ablation', '--artifacts-dir', directory], {
    cwd: root, timeout: 30_000, stdio: 'pipe', windowsHide: true,
  });
  const artifacts = readdirSync(directory).filter((name) => name.endsWith('.json') && name !== 'context-ablation.json')
    .map((name) => {
      const value: unknown = JSON.parse(readFileSync(join(directory, name), 'utf8'));
      return parseApi(episodeArtifactSchema, value);
    });
  const artifact = artifacts.find((value) => value.task.name === 'order-status-007'
    && value.agent.runtime_backend === 'handwritten' && value.agent.context_policy?.max_tool_rounds === 1);
  expect(artifact).toBeDefined();
  if (!artifact) throw new Error('Missing actual Fake context artifact');
  const id = artifact.episode.episode_id;
  const apiDirectory = join(root, 'artifacts', 'playwright', runId, 'api');
  const originalFile = join(directory, `${id}.json`);
  const originalBytes = readFileSync(originalFile);
  copyFileSync(originalFile, join(apiDirectory, `${id}.json`));
  mkdirSync(join(apiDirectory, 'episode-inputs'), { recursive: true });
  copyFileSync(join(directory, 'episode-inputs', `${id}.json`),
    join(apiDirectory, 'episode-inputs', `${id}.json`));
  const loaded = await request.get(`/api/v1/episodes/${id}`);
  expect(loaded.ok()).toBeTruthy();
  const loadedValue: unknown = await loaded.json();
  expect(parseApi(episodeResponseSchema, loadedValue).artifact).toEqual(artifact);
  const mutations: string[] = [];
  page.on('request', (value) => {
    if (value.url().includes('/api/') && value.method() !== 'GET') mutations.push(value.url());
  });
  await page.goto(`/?episode_id=${id}`);
  await expect(page.getByText('上下文：最近 1 轮工具交互', { exact: true })).toBeVisible();
  await expect(page.getByText('评测未通过 (FAILED)', { exact: true })).toBeVisible();
  await expect(page.getByText('MAX_STEPS', { exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: '工具调用动画回放' })).toBeVisible();
  await page.getByRole('button', { name: '技术 Trace', exact: true }).click();
  await expect(page.getByText('MODEL_REQUESTED', { exact: true }).first()).toBeVisible();
  expect(mutations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('context-history.png'), fullPage: true });
  await page.getByRole('button', { name: '单独重跑失败 Episode', exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get('episode_id')).not.toBe(id);
  const rerunId = new URL(page.url()).searchParams.get('episode_id');
  expect(rerunId).toMatch(/^[a-f0-9-]{36}$/);
  await expect(page.getByText('上下文：最近 1 轮工具交互', { exact: true })).toBeVisible();
  await expect(page.getByText('MAX_STEPS', { exact: true })).toBeVisible();
  const rerunResponse = await request.get(`/api/v1/episodes/${rerunId}`);
  expect(rerunResponse.ok()).toBeTruthy();
  const rerunValue: unknown = await rerunResponse.json();
  const rerun = parseApi(episodeResponseSchema, rerunValue).artifact;
  expect(rerun.agent).toEqual(artifact.agent);
  expect(rerun.config_hashes).toEqual(artifact.config_hashes);
  expect(rerun.evaluation.success).toBe(false);
  expect(mutations).toHaveLength(1);
  expect(mutations[0]).toContain(`/episodes/${id}/rerun`);
  expect(readFileSync(join(apiDirectory, `${id}.json`))).toEqual(originalBytes);
  await page.screenshot({ path: testInfo.outputPath('context-rerun.png'), fullPage: true });
});

test('new Episode → independent evaluation → saved Trace → replay with no execution', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/?mode=single');
  await page.getByRole('button', { name: '开始运行 Episode', exact: true }).click();
  await expect(page).toHaveURL(/episode_id=[a-f0-9-]+/);
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
  const id = new URL(page.url()).searchParams.get('episode_id');
  const saved = await request.get(`/api/v1/episodes/${id}`);
  const value: unknown = await saved.json();
  const data = parseApi(episodeResponseSchema, value);
  expect(data.artifact.evaluation.success).toBe(true);
  expect(data.artifact.episode.tool_call_count).toBe(2);
  expect(data.artifact.events.some((event: { event_type: string }) => event.event_type === 'TOOL_SUCCEEDED')).toBe(true);
  const mutations: string[] = [];
  page.on('request', (value) => {
    if (value.url().includes('/api/') && value.method() !== 'GET') mutations.push(value.url());
  });
  const flow = page.getByRole('region', { name: '工具调用动画回放' });
  await expect(flow.getByLabel('最初输入')).toBeVisible();
  await expect(flow.getByLabel('最终输出')).toContainText('shipped');
  await flow.getByRole('button', { name: '动画下一帧' }).click();
  await expect(flow.locator('.flow-position')).toHaveText(/^2\//);
  await flow.getByRole('button', { name: '动画上一帧' }).click();
  await flow.getByLabel('动画速度').selectOption('700');
  await flow.getByRole('button', { name: '播放全过程' }).click();
  await expect(flow.locator('.flow-position')).toHaveText(/^2\//);
  await flow.getByRole('button', { name: '暂停', exact: true }).click();
  await page.getByRole('button', { name: '技术 Trace', exact: true }).click();
  await expect(page.getByText('EPISODE_STARTED', { exact: true })).toBeVisible();
  expect(mutations).toEqual([]);
  expect(errors).toEqual([]);
});

test('saved flow stays readable across viewports and respects dynamic reduced motion', async ({ page, request }, testInfo) => {
  const response = await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'success', task_id: 'order-status-007',
  } });
  expect(response.ok()).toBeTruthy();
  const value: unknown = await response.json();
  const artifact = parseApi(episodeResponseSchema, value).artifact;
  const mutations: string[] = [];
  page.on('request', (value) => {
    if (value.url().includes('/api/') && value.method() !== 'GET') mutations.push(value.url());
  });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openEpisode(page, artifact.episode.episode_id);
  const flow = page.getByRole('region', { name: '工具调用动画回放' });
  for (const width of [390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(flow.getByLabel('最初输入')).toBeVisible();
    await expect(flow.getByLabel('最终输出')).toContainText('approved');
    const next = flow.getByRole('button', { name: '动画下一帧' });
    const before = await flow.locator('.flow-position').textContent();
    await next.focus();
    await expect(next).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(flow.locator('.flow-position')).not.toHaveText(before ?? '');
    await expect.poll(() => flow.evaluate((element) => {
      const canvas = element.querySelector('.flow-canvas')?.getBoundingClientRect();
      const nodes = Array.from(element.querySelectorAll('.react-flow__node'));
      return Boolean(canvas && nodes.length >= 3 && nodes.every((node) => {
        const box = node.getBoundingClientRect();
        return box.width > 0 && box.left >= canvas.left - 2 && box.right <= canvas.right + 2
          && box.top >= canvas.top - 2 && box.bottom <= canvas.bottom + 2;
      }));
    })).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    const header = await page.locator('.app-header').boundingBox();
    expect(header?.y).toBeGreaterThanOrEqual(0);
    expect(header?.y).toBeLessThanOrEqual(1);
    await flow.screenshot({ path: testInfo.outputPath(`flow-${width}.png`) });
  }
  await flow.getByLabel('动画速度').selectOption('2800');
  const progress = flow.getByRole('slider', { name: '动画进度' });
  await progress.focus();
  await page.keyboard.press('Home');
  await flow.getByRole('button', { name: '动画下一帧' }).click();
  await flow.getByRole('button', { name: '播放', exact: true }).click();
  await expect(flow.getByRole('button', { name: '暂停', exact: true })).toBeVisible();
  await expect(flow.locator('animateMotion')).toHaveCount(0);
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await expect(flow.locator('animateMotion')).toHaveCount(1);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(flow.locator('animateMotion')).toHaveCount(0);
  await flow.getByRole('button', { name: '暂停', exact: true }).click();
  expect(mutations).toEqual([]);
  const saved = await request.get(`/api/v1/episodes/${artifact.episode.episode_id}`);
  const savedValue: unknown = await saved.json();
  expect(parseApi(episodeResponseSchema, savedValue).artifact).toEqual(artifact);
});

test('bad historical response clears old success and reports a validation error', async ({ page, request }) => {
  const data = await createEpisode(request);
  const id = data.artifact.episode.episode_id;
  await openEpisode(page, id);
  const corrupt = { ...data, artifact: { ...data.artifact,
    evaluation: { ...data.artifact.evaluation, success: 'true' } } };
  await page.route(`**/api/v1/episodes/${id}`, (route) => route.fulfill({ json: corrupt }));
  await page.locator('#input-episode-id').fill(id);
  await page.getByRole('button', { name: '读取结果', exact: true }).click();
  await expect(page.getByText(/接口数据校验失败/)).toBeVisible();
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('region', { name: '工具调用动画回放' })).toHaveCount(0);
});

test('delayed accepted Job cannot reclaim a page opened from dashboard history', async ({ page, request }) => {
  const response = await request.post('/api/v1/experiments', { data: {
    provider: 'fake', model: 'fake-model', task_ids: ['order-status-001'], scenario: 'invalid-then-success',
  } });
  expect(response.ok()).toBeTruthy();
  const value: unknown = await response.json();
  const historical = parseApi(experimentResponseSchema, value).experiment.experiment_id;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  let accepted!: () => void;
  const acceptedGate = new Promise<void>((resolve) => { accepted = resolve; });
  let finished!: () => void;
  const finishedGate = new Promise<void>((resolve) => { finished = resolve; });
  await page.route('**/api/v1/experiments/jobs', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    const serverResponse = await route.fetch();
    accepted();
    await gate;
    await route.fulfill({ response: serverResponse });
    finished();
  });
  await page.goto('/');
  await page.locator('.history-disclosure > summary').click();
  await page.getByRole('button', { name: /开始运行对照实验/ }).click();
  await acceptedGate;
  try {
    await page.locator('.experiment-dashboard-item').filter({ hasText: historical }).getByRole('button').click();
    await expect(page).toHaveURL(new RegExp(`experiment_id=${historical}`));
    const delivered = page.waitForResponse((reply) => reply.url().endsWith('/api/v1/experiments/jobs')
      && reply.request().method() === 'POST');
    release();
    await finishedGate;
    await (await delivered).finished();
    await page.evaluate(() => new Promise<void>((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
    }));
    await expect(page.getByRole('button', { name: /开始运行对照实验/ })).toBeEnabled();
    await expect(page).toHaveURL(new RegExp(`experiment_id=${historical}`));
    expect(new URL(page.url()).searchParams.has('experiment_job_id')).toBe(false);
  } finally { release(); }
});

test('valid-shaped history for a different ID is refused', async ({ page, request }) => {
  const data = await createEpisode(request);
  const wrongId = '10000000-0000-4000-8000-000000000099';
  await page.route(`**/api/v1/episodes/${wrongId}`, (route) => route.fulfill({ json: data }));
  await page.goto(`/?episode_id=${wrongId}`);
  await expect(page.getByText('接口返回的结果 ID 与请求不一致。', { exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: '工具调用动画回放' })).toHaveCount(0);
});

test('malformed live Trace never becomes a successful animation', async ({ page }) => {
  await page.route('**/api/v1/episodes/stream', (route) => route.fulfill({
    contentType: 'text/event-stream', body: 'event: trace\ndata: {"event_id":"invalid","payload":[]}\n\n',
  }));
  await page.goto('/?mode=single');
  await page.getByRole('button', { name: '开始运行 Episode', exact: true }).click();
  await expect(page.getByText(/接口数据校验失败/)).toBeVisible();
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toHaveCount(0);
  expect(new URL(page.url()).searchParams.has('episode_id')).toBe(false);
});

test('broken recovery lists are visible rather than silently shown as empty', async ({ page }) => {
  await page.route('**/api/v1/episodes/resumable', (route) => route.fulfill({ json: ['not-an-id'] }));
  await page.goto('/?mode=single');
  await expect(page.getByText('待恢复记录读取失败，列表可能不完整。请刷新页面重新读取。', { exact: true })).toBeVisible();
});
