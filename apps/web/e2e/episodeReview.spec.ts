import { readFile } from 'node:fs/promises';

import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

import {
  episodeResponseSchema, episodeReviewResponseSchema, experimentResponseSchema, parseApi,
} from '../src/apiContracts';

const MODEL = 'coding-minimax-m2.7-free';

async function showRealModel(page: Page) {
  await page.route('**/api/v1/meta', async route => {
    const data = await (await route.fetch()).json();
    data.models = data.models.filter((model: { id: string }) => model.id !== MODEL);
    data.models.push({ id: MODEL, name: '离线评审模型', provider: 'aihubmix', is_default: false,
      is_experimental: false, notes: '仅浏览器夹具', scenarios: [] });
    await route.fulfill({ json: data });
  });
}

async function savedEpisode(request: APIRequestContext, scenario = 'success') {
  return parseApi(episodeResponseSchema, await (await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', scenario, task_id: 'order-status-001',
  } })).json()).artifact;
}

async function fakeReview(request: APIRequestContext, id: string) {
  return parseApi(episodeReviewResponseSchema, await (await request.post('/api/v1/episode-reviews', {
    data: { episode_id: id, method: 'llm_judge' },
  })).json());
}

test('real Judge requires explicit selection and exactly one click; refresh only reads history', async ({ page, request }) => {
  const artifact = await savedEpisode(request);
  const id = artifact.episode.episode_id;
  const seed = await fakeReview(request, id);
  const result = parseApi(episodeReviewResponseSchema, { ...seed, review: {
    ...seed.review, review_id: '10000000-0000-4000-8000-000000000011', provider: 'aihubmix', model: MODEL,
    verdict: 'pass', answer_correctness: 'pass', evidence_support: 'pass', process_safety: 'pass',
    rationale: '离线夹具：实际查询记录支持本次答案。', event_ids: [artifact.events[0].event_id],
    token_usage: { schema_version: '1.0', prompt_tokens: 11, completion_tokens: 7, simulated: false },
    estimated_cost: { ...seed.review.estimated_cost!, amount: '0', is_known: false, price_table_version: 'unverified' },
  } });
  const history = [seed.review];
  await showRealModel(page);
  await page.route(`**/api/v1/episodes/${id}/reviews`, route => route.fulfill({
    json: { schema_version: '1.0', request_id: seed.request_id, episode_id: id, reviews: history },
  }));
  const posts: unknown[] = [];
  let releaseReply: () => void = () => { throw new Error('No pending request'); };
  await page.route('**/api/v1/episode-reviews', async route => {
    posts.push(route.request().postDataJSON());
    await new Promise<void>(resolve => { releaseReply = resolve; });
    history.push(result.review);
    await route.fulfill({ json: result });
  });
  await page.goto(`/?episode_id=${id}`);
  const panel = page.locator('.episode-review-card');
  await expect(panel.getByRole('heading', { name: '大模型评审' })).toBeVisible();
  await expect(panel.getByRole('button', { name: '评审本次结果' })).toBeDisabled();
  await expect(panel.getByRole('button', { name: /保存检查|模拟/ })).toHaveCount(0);
  await page.getByLabel('评审模型').selectOption(MODEL);
  expect(posts).toEqual([]);
  await panel.getByRole('button', { name: '评审本次结果' }).click();
  await expect.poll(() => posts.length).toBe(1);
  await expect(panel.getByRole('button', { name: '正在评审…' })).toBeDisabled();
  releaseReply();
  await expect(panel.getByText('离线夹具：实际查询记录支持本次答案。')).toBeVisible();
  await expect(panel.getByText('与规则评分一致', { exact: true })).toBeVisible();
  expect(posts).toEqual([{ schema_version: '1.1', episode_id: id, method: 'llm_judge',
    judge_provider: 'aihubmix', judge_model: MODEL }]);
  await panel.locator('.review-citations > summary').focus();
  await page.keyboard.press('Enter');
  await expect(panel.locator('.review-citations')).toContainText(artifact.events[0].event_id);
  const downloading = page.waitForEvent('download');
  await panel.getByRole('button', { name: '导出全部记录 CSV' }).click();
  const csv = await readFile((await (await downloading).path())!, 'utf8');
  expect(csv).toContain('fake-judge-v1');
  expect(csv).toContain(`"aihubmix","${MODEL}"`);
  expect(csv).toContain('"11","7","false","false","","USD","unverified"');
  await page.reload();
  await expect(panel.getByText('离线夹具：实际查询记录支持本次答案。')).toBeVisible();
  expect(posts).toHaveLength(1);
  expect(parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact).toEqual(artifact);
});

test('saved model versions, unknown usage and legacy CSV remain readable without product demo actions', async ({ page, request }, testInfo) => {
  const artifact = await savedEpisode(request);
  const id = artifact.episode.episode_id;
  const seed = await fakeReview(request, id);
  const base = seed.review;
  const reviews = [
    { ...base, review_id: '10000000-0000-4000-8000-000000000021', provider: 'aihubmix',
      created_at: '2026-10-22T10:00:00Z',
      model: 'saved-real-model', prompt_version: 'episode-review-v1', status: 'failed',
      verdict: null, answer_correctness: null, evidence_support: null, process_safety: null,
      rationale: null, failure_code: 'INVALID_JUDGE_OUTPUT',
      token_usage: { schema_version: '1.0', prompt_tokens: 2711, completion_tokens: 252, simulated: false },
      estimated_cost: { ...base.estimated_cost!, amount: '0', is_known: false, price_table_version: 'unverified' } },
    { ...base, review_id: '10000000-0000-4000-8000-000000000022', provider: 'aihubmix',
      model: 'saved-real-model', prompt_version: 'episode-review-v2', verdict: 'fail',
      rationale: '离线夹具：证据存在疑点，需查看实际返回。', token_usage: null,
      estimated_cost: { ...base.estimated_cost!, amount: '0.002', is_known: true } },
    { ...base, review_id: '10000000-0000-4000-8000-000000000023', token_usage: null, estimated_cost: null },
    { ...base, review_id: '10000000-0000-4000-8000-000000000024' },
    { ...base, review_id: '10000000-0000-4000-8000-000000000025', method: 'human',
      provider: null, model: null, prompt_version: null, token_usage: null, estimated_cost: null,
      reviewer_label: '=SUM(1,2)', rationale: '说明含"引号"\n第二行' },
  ];
  await showRealModel(page);
  await page.route(`**/api/v1/episodes/${id}/reviews`, route => route.fulfill({
    json: { schema_version: '1.0', request_id: seed.request_id, episode_id: id, reviews },
  }));
  const writes: string[] = [];
  page.on('request', value => {
    if (value.url().includes('/api/') && value.method() !== 'GET') writes.push(value.url());
  });
  await page.goto(`/?episode_id=${id}`);
  const panel = page.locator('.episode-review-card');
  await expect(panel.locator('.review-item')).toHaveCount(2);
  await expect(panel.locator('.review-item').first()).toContainText('证据存在疑点');
  await expect(panel.getByText('与规则评分存在分歧，请检查下方理由')).toBeVisible();
  const failed = panel.locator('.review-item').filter({ hasText: 'episode-review-v1' });
  await expect(failed.getByText('输入 2711 / 输出 252')).not.toBeVisible();
  await failed.locator('.review-technical > summary').click();
  await expect(failed.getByText('输入 2711 / 输出 252')).toBeVisible();
  await expect(failed).toContainText('未知（未验证）');
  await expect(failed).not.toContainText('$0');
  const completed = panel.locator('.review-item').filter({ hasText: '证据存在疑点' });
  await completed.locator('.review-technical > summary').click();
  await expect(completed).toContainText('未知（未报告）');
  await expect(completed).toContainText('$0.002 USD');
  await panel.locator('.review-archive > summary').click();
  await expect(panel.locator('.review-archive')).toContainText('3 条');
  const downloading = page.waitForEvent('download');
  await panel.getByRole('button', { name: '导出全部记录 CSV' }).click();
  const csv = await readFile((await (await downloading).path())!, 'utf8');
  expect(csv.charCodeAt(0)).toBe(0xfeff);
  expect(csv).toContain('prompt_version,rubric_version,prompt_tokens,completion_tokens,simulated,cost_is_known,estimated_cost,currency,price_table_version');
  expect(csv).toContain('"episode-review-v1","tool-lab-review-v1","2711","252","false","false","","USD","unverified"');
  expect(csv).toContain('"episode-review-v2","tool-lab-review-v1","","","","true","0.002"');
  expect(csv).toContain('"\'=SUM(1,2)"');
  expect(csv).toContain('"说明含""引号""\n第二行"');
  await failed.locator('.review-technical > summary').click();
  await completed.locator('.review-technical > summary').click();
  await panel.locator('.review-archive > summary').click();
  for (const width of [1440, 1280, 768, 720, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await panel.screenshot({ path: testInfo.outputPath(`judge-${width}.png`) });
  }
  await page.reload();
  await expect(failed).toContainText('episode-review-v1');
  expect(writes).toEqual([]);
});

test('experiment review summary counts only saved real model reviews and stays read-only', async ({ page, request }) => {
  await page.goto('/?mode=experiment');
  await page.getByRole('button', { name: '清空', exact: true }).click();
  await page.locator('#task-checkbox-list label').filter({ hasText: 'order-status-001' }).getByRole('checkbox').check();
  await page.locator('#run-exp-button').click();
  await expect(page).toHaveURL(/experiment_id=/);
  const id = new URL(page.url()).searchParams.get('experiment_id')!;
  const experiment = parseApi(experimentResponseSchema, await (await request.get(`/api/v1/experiments/${id}`)).json()).experiment;
  const pair = experiment.pairs[0];
  const reviewedId = pair.recovery_success ? pair.recovery_episode_id : pair.baseline_episode_id;
  const seed = await fakeReview(request, reviewedId);
  await page.route(`**/api/v1/episodes/${reviewedId}/reviews`, route => route.fulfill({ json: {
    schema_version: '1.0', request_id: seed.request_id, episode_id: reviewedId,
    reviews: [seed.review, { ...seed.review, review_id: '10000000-0000-4000-8000-000000000029',
      provider: 'aihubmix', model: MODEL, verdict: 'pass' }],
  } }));
  const writes: string[] = [];
  page.on('request', value => { if (value.url().includes('/api/') && value.method() !== 'GET') writes.push(value.url()); });
  await page.locator('.experiment-review-summary > summary').click();
  await expect(page.locator('.experiment-review-summary')).toContainText(`1 / ${experiment.episode_ids.length}`);
  await expect(page.locator('.review-summary-grid > div').nth(1).locator('strong')).toHaveText('1');
  expect(writes).toEqual([]);
});

test('no final submission or real model never falls back to a simulated Judge', async ({ page, request }) => {
  const artifact = await savedEpisode(request, 'invalid-arguments');
  const writes: string[] = [];
  page.on('request', value => { if (value.url().includes('/api/') && value.method() !== 'GET') writes.push(value.url()); });
  await page.goto(`/?episode_id=${artifact.episode.episode_id}`);
  const panel = page.locator('.episode-review-card');
  await expect(panel.getByRole('button', { name: '评审本次结果' })).toBeDisabled();
  await expect(panel.getByText('本次没有已保存的最终提交，暂不能进行模型评审。')).toBeVisible();
  await expect(panel.getByText('暂无可选的真实模型，请先恢复模型目录。')).toBeVisible();
  await expect(panel.locator('.review-item')).toHaveCount(0);
  await expect(panel.getByRole('button', { name: /模拟|人工/ })).toHaveCount(0);
  expect(writes).toEqual([]);
});

test('Judge network and strict-output failures never retry or become task failure', async ({ page, request }) => {
  const artifact = await savedEpisode(request);
  const id = artifact.episode.episode_id;
  const seed = await fakeReview(request, id);
  await showRealModel(page);
  let calls = 0;
  await page.route('**/api/v1/episode-reviews', route => {
    calls++;
    return calls === 1 ? route.fulfill({ status: 503, json: { detail: 'Offline network failure' } })
      : route.fulfill({ json: { ...seed, review: { ...seed.review,
        review_id: '10000000-0000-4000-8000-000000000031', provider: 'aihubmix', model: MODEL,
        status: 'failed', verdict: null, answer_correctness: null, evidence_support: null,
        process_safety: null, rationale: null, failure_code: 'INVALID_JUDGE_OUTPUT' } } });
  });
  await page.goto(`/?episode_id=${id}`);
  const panel = page.locator('.episode-review-card');
  await page.getByLabel('评审模型').selectOption(MODEL);
  await panel.getByRole('button', { name: '评审本次结果' }).click();
  await expect(panel.getByRole('alert')).toBeVisible();
  expect(calls).toBe(1);
  await panel.getByRole('button', { name: '评审本次结果' }).click();
  await expect(panel.locator('.review-item')).toContainText('复核失败：INVALID_JUDGE_OUTPUT');
  await expect(panel.getByText('规则评分：通过')).toBeVisible();
  await expect(panel.locator('.review-agreement')).toHaveCount(0);
  expect(calls).toBe(2);
});
