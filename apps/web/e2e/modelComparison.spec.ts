import { expect, test } from '@playwright/test';

test('model comparison selects two matching records and opens saved routes using GET', async ({ page, request }, testInfo) => {
  const response = await request.post('/api/v1/episodes', { data: {
    schema_version: '1.3', provider: 'fake', model: 'fake-model', scenario: 'success',
    suite: 'gridworld', task_id: 'key-door-002-v1', max_steps: 20, token_budget: 16000,
  } });
  expect(response.status()).toBe(201);
  const { artifact } = await response.json();
  const base = {
    started_at: artifact.events[0].timestamp, comparison_key: 'a'.repeat(64),
    task_name: artifact.task.name, task_version: artifact.task.version, seed: 1,
    model_id: 'model-alpha', provider: 'aihubmix', context_rounds: 2, max_steps: 24,
    token_budget: 160000, max_execution_time_ms: 330000, success: true, termination: 'SUCCESS',
    detail: 'submitted', actions: 14, illegal_actions: 0, duration_ms: 94000,
    input_tokens: 26000, output_tokens: 500, usage_complete: true,
  };
  const ids = [artifact.episode.episode_id, crypto.randomUUID(), crypto.randomUUID()];
  await page.route('**/api/v1/episodes/gridworld-comparison', route => route.fulfill({ json: {
    schema_version: '1.0', skipped_count: 0, items: [
      { ...base, episode_id: ids[0] },
      { ...base, episode_id: ids[1], model_id: 'model-beta', success: false,
        termination: 'RUNTIME_ERROR', detail: 'provider_error: REQUEST_TIMEOUT', input_tokens: null,
        output_tokens: null, usage_complete: false, duration_ms: 61000 },
      { ...base, episode_id: ids[2], model_id: 'model-gamma', comparison_key: 'b'.repeat(64), context_rounds: null },
    ],
  } }));
  await page.route(`**/api/v1/episodes/${ids[1]}`, route => route.fulfill({ json: {
    schema_version: '1.0', request_id: crypto.randomUUID(), artifact: {
      ...artifact, episode: { ...artifact.episode, episode_id: ids[1] },
      events: artifact.events.map((event: object) => ({ ...event, episode_id: ids[1] })),
    },
  } }));
  const writes: string[] = [];
  page.on('request', value => { if (value.method() === 'POST') writes.push(value.url()); });
  await page.goto('/experiments');
  await page.getByRole('checkbox', { name: '选择 model-alpha' }).check();
  await page.getByRole('checkbox', { name: '选择 model-beta' }).check();
  const pair = page.getByRole('region', { name: '两局并排对比' });
  await expect(pair.getByRole('img')).toHaveCount(2);
  await expect(pair.getByText('未知', { exact: true })).toBeVisible();
  await expect(pair.getByRole('link', { name: /查看 3D 回放/ }).first()).toHaveAttribute('href', `/gridworld/${[ids[0], ids[1]].sort()[0]}`);
  await page.screenshot({ path: testInfo.outputPath('model-comparison.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('combobox', { name: '运行配置' }).selectOption('b'.repeat(64));
  await expect(pair).toHaveCount(0);
  await expect(page.getByRole('checkbox', { name: '选择 model-gamma' })).toBeDisabled();
  await page.getByText('策略实验', { exact: true }).click();
  await expect(page.getByRole('button', { name: '新建对照实验' })).toBeVisible();
  expect(writes).toEqual([]);

  const judge = 'model-judge';
  await page.route('**/api/v1/meta', async route => {
    const response = await route.fetch();
    const json = await response.json();
    const model = { provider: 'aihubmix', is_default: false, is_experimental: false, notes: '', scenarios: [] };
    json.models.push({ ...model, id: 'model-alpha', name: 'Alpha' }, { ...model, id: judge, name: '独立评审模型' });
    await route.fulfill({ json });
  });
  const pairIds = [ids[0], ids[1]].sort();
  const sourceEvent = artifact.events.find((event: { event_type: string }) => event.event_type === 'ENVIRONMENT_UPDATED');
  const review = {
    schema_version: '1.0', review_id: crypto.randomUUID(), episode_ids: pairIds,
    source_hashes: ['c'.repeat(64), 'd'.repeat(64)], comparison_key: base.comparison_key,
    review_input_hash: 'e'.repeat(64), created_at: base.started_at, judge_model: judge,
    prompt_version: 'gridworld-pair-review-v2', output: {
      assessment: 'tradeoff', rationale: '两局探索路线各有取舍。\n\n仅凭这两局还不能判断模型的总体导航能力。',
      citations: [{ side: 'a', event_id: sourceEvent.event_id }, { side: 'b', event_id: sourceEvent.event_id }],
    }, failure_code: null, token_usage: { prompt_tokens: 300, completion_tokens: 80, simulated: false },
    estimated_cost: null,
  };
  const failedReview = { ...review, review_id: crypto.randomUUID(), output: null,
    prompt_version: 'gridworld-pair-review-v1',
    failure_code: 'JUDGE_REQUEST_TIMEOUT', token_usage: null };
  const previousReview = { ...review, review_id: crypto.randomUUID(), prompt_version: 'gridworld-pair-review-v1',
    output: { ...review.output, assessment: 'a', rationale: '这是上一次评审的结论。' } };
  let finishReview!: () => void;
  const pendingReview = new Promise<void>(resolve => { finishReview = resolve; });
  let failReview!: () => void;
  const pendingFailure = new Promise<void>(resolve => { failReview = resolve; });
  let posts = 0;
  await page.route('**/api/v1/gridworld-comparison-reviews*', async route => {
    if (route.request().method() === 'GET') {
      const query = new URL(route.request().url()).searchParams;
      expect([query.get('episode_a'), query.get('episode_b')]).toEqual(pairIds);
      return route.fulfill({ json: {
        schema_version: '1.0', reviews: posts ? [review, failedReview, previousReview] : [previousReview], skipped_count: 0,
      } });
    }
    posts++;
    expect(route.request().postDataJSON()).toEqual({ schema_version: '1.0', episode_ids: pairIds, judge_model: judge });
    if (posts === 2) {
      await pendingFailure;
      return route.abort('failed');
    }
    await pendingReview;
    return route.fulfill({ status: 201, json: review });
  });
  await page.reload();
  const openReview = async () => {
    await page.getByRole('checkbox', { name: '选择 model-beta' }).check();
    await page.getByRole('checkbox', { name: '选择 model-alpha' }).check();
    await page.getByText('双局模型评审', { exact: true }).press('Enter');
  };
  await openReview();
  const submit = page.getByRole('button', { name: '评审这两局' });
  const select = page.getByRole('combobox', { name: '评审模型' });
  await expect(submit).toBeDisabled();
  await expect(select.locator('option[value="model-alpha"]')).toHaveCount(0);
  await select.selectOption(judge);
  const previousConclusion = pair.getByText('这是上一次评审的结论。');
  const waiting = pair.getByRole('status').filter({ hasText: '正在等待评审模型返回。' });
  await expect(previousConclusion).toBeVisible();
  expect(posts).toBe(0);
  await submit.click();
  try {
    await expect(waiting).toBeVisible();
    await expect(previousConclusion).toBeHidden({ timeout: 1500 });
    const logo = waiting.locator('img');
    await expect(logo).toHaveAttribute('src', '/brand/fox-loading.svg');
    await expect.poll(() => logo.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
    await page.screenshot({ path: testInfo.outputPath('pair-judge-loading.png'), fullPage: true });
  } finally {
    finishReview();
  }
  await expect(pair.getByText('两局探索路线各有取舍。', { exact: false })).toBeVisible();
  await expect(pair.getByRole('listitem').filter({ hasText: `A 局 · 第 ${sourceEvent.step_index} 步 · 公开动作` })).toBeVisible();
  await expect(waiting).toHaveCount(0);
  await expect(previousConclusion).toBeHidden();
  expect(posts).toBe(1);
  await page.screenshot({ path: testInfo.outputPath('pair-judge-mobile.png'), fullPage: true });
  await page.reload();
  await openReview();
  await expect(pair.getByText('两局探索路线各有取舍。', { exact: false })).toBeVisible();
  const history = pair.getByText(/^历史评审（\d+）$/);
  await expect(previousConclusion).toBeHidden();
  await history.click();
  await expect(pair.getByText('历史评审 · 初版提示')).toHaveCount(2);
  await expect(pair.getByText('评审模型请求超时。', { exact: false })).toBeVisible();
  await expect(previousConclusion).toBeVisible();
  await expect(pair.getByText('评审 Token 未知', { exact: false })).toBeVisible();
  expect(posts).toBe(1);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await select.selectOption(judge);
  await submit.click();
  try {
    await expect.poll(() => waiting.locator('img').evaluate((img: HTMLImageElement) => img.currentSrc))
      .toMatch(/\/brand\/fox-mark\.svg$/);
    const motion = await page.context().newPage();
    try {
      await motion.goto('/brand/fox-loading.svg');
      await expect(motion.locator('.route')).toHaveCSS('animation-name', 'loading-trace');
      await expect(motion.locator('.route')).toHaveCSS('animation-iteration-count', 'infinite');
      await motion.emulateMedia({ reducedMotion: 'reduce' });
      await expect(motion.locator('.route')).toHaveCSS('animation-name', 'none');
    } finally {
      await motion.close();
    }
    await expect(previousConclusion).toBeHidden();
  } finally {
    failReview();
  }
  await expect(waiting).toHaveCount(0);
  await expect(pair.getByRole('alert')).toContainText('评审请求未确认完成');
  await expect(previousConclusion).toBeHidden();
  await history.click();
  await expect(previousConclusion).toBeVisible();
  expect(posts).toBe(2);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: testInfo.outputPath('pair-judge-desktop.png'), fullPage: true });
  await page.getByRole('checkbox', { name: '选择 model-beta' }).uncheck();
  await expect(pair).toHaveCount(0);

  const batchId = crypto.randomUUID();
  const batchRows = [
    { ...base, episode_id: ids[0] },
    { ...base, episode_id: ids[1], model_id: 'model-beta', success: false,
      termination: 'RUNTIME_ERROR', detail: 'provider_error: REQUEST_TIMEOUT' },
  ];
  const finished = {
    schema_version: '1.0', batch_id: batchId, created_at: base.started_at,
    task: base.task_name, task_version: base.task_version, seed: 1, max_steps: 24,
    input_threshold: 160000, output_per_call: 2048, timeout_ms: 330000, context_rounds: 2,
    running: false, runs: [
      { model: 'model-alpha', episode_id: ids[0], status: 'completed', row: batchRows[0] },
      { model: 'model-beta', episode_id: ids[1], status: 'failed', row: batchRows[1] },
      { model: 'model-delta', episode_id: crypto.randomUUID(), status: 'unavailable', row: null },
      { model: 'model-epsilon', episode_id: crypto.randomUUID(), status: 'not_started', row: null },
    ],
  };
  let batchPosts = 0;
  await page.route('**/api/v1/gridworld-batches', route => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ json: { schema_version: '1.0', skipped_count: 0, items: batchPosts ? [finished] : [] } });
    }
    batchPosts++;
    expect(route.request().postDataJSON()).toEqual({ schema_version: '1.0' });
    return route.fulfill({ status: 202, json: {
      ...finished, running: true, runs: finished.runs.map(run => ({ ...run, status: 'queued', row: null })),
    } });
  });
  await page.getByText('同配置四模型批次', { exact: true }).press('Enter');
  await page.getByRole('button', { name: '启动四模型实测' }).click();
  await expect(page.getByText('模型不可用', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '在下方对比本批结果' }).click();
  await expect(page.getByText(/当前查看 .* 批次的已保存结果/)).toBeVisible();
  await expect(page.getByRole('checkbox', { name: '选择 model-alpha' })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('gridworld-batch.png'), fullPage: true });
  await page.reload();
  await page.getByText('同配置四模型批次', { exact: true }).click();
  await expect(page.getByText('未开始', { exact: true })).toBeVisible();
  expect(batchPosts).toBe(1);
});
