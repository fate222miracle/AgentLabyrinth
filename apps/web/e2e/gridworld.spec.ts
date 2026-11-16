import { expect, test } from '@playwright/test';
import { episodeResponseSchema, parseApi } from '../src/apiContracts';

test('GridWorld Fake live runs expose arrived state and history replay never posts', async ({ page, request }, testInfo) => {
  const writes: string[] = [];
  const episodeResponses: { method: string; status: number; path: string }[] = [];
  const pageErrors: string[] = [];
  page.on('request', value => {
    if (value.url().includes('/api/v1/episodes') && value.method() !== 'GET') {
      writes.push(`${value.method()} ${value.url()}`);
    }
  });
  page.on('response', response => {
    const path = new URL(response.url()).pathname;
    if (path === '/api/v1/episodes/stream' || /^\/api\/v1\/episodes\/[0-9a-f-]{36}$/.test(path)) {
      episodeResponses.push({ method: response.request().method(), status: response.status(), path });
    }
  });
  page.on('pageerror', error => pageErrors.push(error.message));

  await page.goto('/?mode=single');
  expect(writes).toEqual([]);
  await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
  await expect(page.locator('input[name="single-suite"][value="gridworld"]')).toHaveCount(0);
  await page.getByRole('button', { name: 'GridWorld', exact: true }).click();
  await expect(page).toHaveURL(/\/gridworld$/);
  await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
  await expect(page.locator('input[name="single-suite"]')).toHaveCount(0);
  await expect(page.locator('#gridworld-scenario')).toHaveValue('success');

  const runScenario = async (scenario: string) => {
    if (!await page.locator('#config-panel').evaluate(element => (element as HTMLDetailsElement).open)) {
      await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
    }
    await page.locator('#gridworld-scenario').selectOption(scenario);
    const writesBefore = writes.length;
    await page.locator('#run-button').click();
    await expect(page).toHaveURL(/\/gridworld\/[0-9a-f-]{36}/);
    await expect(page.getByRole('region', { name: 'Agent 可见地图', exact: true })).toBeVisible();
    expect(writes.length).toBe(writesBefore + 1);
    expect(writes.at(-1)).toContain('POST ');
    expect(writes.at(-1)).toContain('/api/v1/episodes/stream');
    const id = new URL(page.url()).searchParams.get('episode_id');
    if (!id) throw new Error('Completed GridWorld run did not retain its Episode ID');
    const response = await request.get(`/api/v1/episodes/${id}`);
    expect(response.status()).toBe(200);
    const artifact = parseApi(episodeResponseSchema, await response.json()).artifact;
    expect(artifact.run_config.environment_version).toBe('gridworld-key-door-v1');
    return { id, artifact };
  };

  const success = await runScenario('success');
  expect(success.artifact.evaluation.success).toBe(true);
  expect(success.artifact.episode.step_count).toBe(8);
  await expect(page.locator('.gridworld-cell.kind-goal')).toHaveCount(1);
  await page.getByRole('button', { name: '查看保存详情与回放', exact: true }).click();
  await expect(page.locator('.gridworld-cell.kind-goal')).toHaveCount(0);
  const slider = page.getByRole('slider', { name: '动画进度', exact: true });
  await slider.fill(await slider.getAttribute('max') ?? '0');
  await expect(page.locator('.gridworld-cell.kind-goal')).toHaveCount(1);
  for (const [width, height] of [[1440, 900], [1280, 720], [768, 1024], [640, 450], [390, 844]]) {
    await page.setViewportSize({ width, height });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const screenshot = await page.screenshot({
      path: testInfo.outputPath(`gridworld-${width}.png`),
      fullPage: true,
    });
    await testInfo.attach(`gridworld-${width}.png`, { body: screenshot, contentType: 'image/png' });
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole('button', { name: '结果分析', exact: true }).click();
  await expect(page).toHaveURL(/section=results/);
  await page.goBack();
  await expect(page).toHaveURL(/\/gridworld$/);
  expect(new URL(page.url()).searchParams.has('episode_id')).toBe(false);
  const forwardRead = page.waitForResponse(response =>
    response.url().endsWith(`/api/v1/episodes/${success.id}`)
    && response.request().method() === 'GET',
  );
  await page.goForward();
  await expect(page).toHaveURL(new RegExp(`episode_id=${success.id}.*section=results`));
  expect((await forwardRead).status()).toBe(200);
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
  const responsesBeforeRefresh = episodeResponses.length;
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#eval-badge')).toContainText('评测通过');
  await expect.poll(() => episodeResponses.slice(responsesBeforeRefresh)).toContainEqual({
    method: 'GET',
    status: 200,
    path: `/api/v1/episodes/${success.id}`,
  });
  expect(writes).toHaveLength(1);

  await page.getByRole('button', { name: 'GridWorld', exact: true }).click();
  await expect(page).toHaveURL(/\/gridworld$/);
  await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
  const illegal = await runScenario('illegal-action');
  expect(illegal.artifact.evaluation.success).toBe(true);
  expect(illegal.artifact.episode.final_state.illegal_action_count).toBe(1);
  await expect(page.locator('.gridworld-rejections')).toContainText('Movement blocked.');

  await page.getByRole('button', { name: 'GridWorld', exact: true }).click();
  await expect(page).toHaveURL(/\/gridworld$/);
  await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
  const budget = await runScenario('max-steps');
  expect(budget.artifact.episode.termination_reason).toBe('MAX_STEPS');
  expect(budget.artifact.episode.step_count).toBe(16);
  await expect(page.locator('.gridworld-heading')).toContainText('16 个环境动作');
  await expect(page.getByText('评测未通过 (FAILED)', { exact: true })).toBeVisible();

  const finalRead = await request.get(`/api/v1/episodes/${budget.id}`);
  expect(parseApi(episodeResponseSchema, await finalRead.json()).artifact).toEqual(budget.artifact);
  await page.reload();
  await expect(page).toHaveURL(new RegExp(`episode_id=${budget.id}`));
  expect(writes).toHaveLength(3);
  expect(pageErrors).toEqual([]);
  expect(episodeResponses.filter(response => response.method === 'POST')).toEqual([
    { method: 'POST', status: 200, path: '/api/v1/episodes/stream' },
    { method: 'POST', status: 200, path: '/api/v1/episodes/stream' },
    { method: 'POST', status: 200, path: '/api/v1/episodes/stream' },
  ]);
  expect(episodeResponses.some(response => response.method === 'GET' && response.status === 200)).toBe(true);
  await testInfo.attach('gridworld-episode-evidence.json', {
    body: JSON.stringify({
      episodes: [
        { scenario: 'success', id: success.id, eventCount: success.artifact.events.length },
        { scenario: 'illegal-action', id: illegal.id, eventCount: illegal.artifact.events.length },
        { scenario: 'max-steps', id: budget.id, eventCount: budget.artifact.events.length },
      ],
      browserResponses: episodeResponses,
      writes,
      pageErrors,
    }, null, 2),
    contentType: 'application/json',
  });
});

for (const taskId of ['key-door-001-v1', 'key-door-002-v1']) {
  test(`GridWorld sends one real request using the frozen budget for ${taskId}`, async ({ page }) => {
    const gallery = taskId === 'key-door-002-v1';
    const modelId = 'coding-glm-5.3-free';
    let capturedRequest: Record<string, unknown> | undefined;
    const writes: string[] = [];
    page.on('request', request => {
      if (request.url().includes('/api/v1/episodes') && request.method() !== 'GET') {
        writes.push(request.method());
      }
    });
    await page.route('**/api/v1/meta', async route => {
      const response = await route.fetch();
      const metadata = await response.json() as {
        models: Record<string, unknown>[];
        tasks: Record<string, unknown>[];
      };
      metadata.models.push({
        id: modelId,
        name: 'Coding GLM 5.3 Free',
        provider: 'aihubmix',
        is_default: false,
        is_experimental: true,
        notes: 'E2E metadata substitute',
        scenarios: [],
      });
      const gridworld = metadata.tasks.find(task => task.id === taskId);
      if (!gridworld) throw new Error('GridWorld task missing from metadata');
      gridworld.allowed_model_ids = [modelId];
      await route.fulfill({ response, json: metadata });
    });
    await page.route('**/api/v1/episodes/stream', async route => {
      capturedRequest = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 422,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'E2E captured request; no model request was sent' }),
      });
    });

    await page.goto('/?mode=single');
    expect(writes).toEqual([]);
    await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
    await page.getByRole('button', { name: 'GridWorld', exact: true }).click();
    await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
    if (gallery) {
      await page.getByRole('button', { name: /回廊档案室/ }).click();
      await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
    }
    await expect(page.locator('#model-select')).toHaveValue('fake');
    await expect(page.locator('#gridworld-scenario')).toBeVisible();
    await page.locator('#model-select').selectOption(modelId);
    await expect(page.locator('#gridworld-scenario')).toHaveCount(0);
    await expect(page.getByText('Coding GLM 5.3 Free · 实验性真实运行', { exact: true })).toBeVisible();
    await expect(page.getByText(/每次最多 2,048 输出 Token、累计输入 \+ 输出 160,000 Token/)).toBeVisible();
    if (gallery) await expect(page.getByRole('button', { name: /回廊档案室/ })).toContainText('最多 24 步');
    await expect(page.locator('#single-stage-controls')).toContainText(gallery ? '最多 24 轮' : '最多 16 轮');
    await expect(page.locator('#single-stage-controls')).toContainText(gallery ? '330 秒' : '300 秒');
    expect(writes).toEqual([]);

    await page.locator('#run-button').click();
    await expect.poll(() => capturedRequest).toBeDefined();
    expect(writes).toEqual(['POST']);
    expect(capturedRequest).toMatchObject({
      schema_version: '1.3',
      provider: 'aihubmix',
      model: modelId,
      scenario: null,
      task_id: taskId,
      suite: 'gridworld',
      max_steps: gallery ? null : 16,
      max_execution_time_ms: gallery ? null : 300000,
      token_budget: null,
      runtime_backend: 'handwritten',
      runtime_strategy: 'handwritten',
    });
    expect(capturedRequest).not.toHaveProperty('tool_call_mode');
  });
}
