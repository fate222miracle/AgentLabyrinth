import { expect, test } from '@playwright/test';
import { episodeResponseSchema, metaSchema, parseApi } from '../src/apiContracts';

test('advanced settings occupy a separate row, keeping task and model columns compact at all viewports', async ({ page, request }, testInfo) => {
  const meta = parseApi(metaSchema, await (await request.get('/api/v1/meta')).json());
  await page.route('**/api/v1/meta', route => route.fulfill({ json: { ...meta, models: [...meta.models,
    { ...meta.models[0], id: 'layout-candidate', name: '配置布局检查候选', provider: 'aihubmix', is_default: false,
      notes: '仅用于展示真实模型的预算控件，本测试不发起推理。' }],
  } }));
  const posts: string[] = [];
  page.on('request', event => { if (event.url().includes('/api/') && event.method() !== 'GET') posts.push(event.url()); });
  await page.goto('/?mode=single');
  await page.getByRole('button', { name: '配置配送争议实时演示' }).click();
  await page.locator('#model-select').selectOption('layout-candidate');
  const taskBefore = await page.locator('.task-picker').boundingBox();
  const optionsBefore = await page.locator('.single-run-options').boundingBox();
  await page.locator('.single-advanced-settings > summary').click();
  await page.locator('#single-context-mode').selectOption('memory');
  await page.locator('#single-context-window').fill('2');
  await expect(page.locator('#single-token-budget')).toHaveValue('20000');
  await expect(page.locator('.single-launch-summary')).toContainText('记忆 8192 字节');
  await expect(page.locator('.single-run-options .advanced-settings')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '工具与容错', exact: true })).toBeVisible();
  const taskAfter = await page.locator('.task-picker').boundingBox();
  const optionsAfter = await page.locator('.single-run-options').boundingBox();
  expect(Math.abs(taskAfter!.height - taskBefore!.height)).toBeLessThan(2);
  expect(Math.abs(optionsAfter!.height - optionsBefore!.height)).toBeLessThan(70);
  const advanced = await page.locator('.single-advanced-settings').boundingBox();
  expect(advanced!.y).toBeGreaterThanOrEqual(Math.max(taskAfter!.y + taskAfter!.height, optionsAfter!.y + optionsAfter!.height));
  expect(advanced!.width).toBeGreaterThan(taskAfter!.width);
  await page.locator('.context-help > summary').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('.context-help')).toHaveAttribute('open', '');
  await expect(page.locator('.context-help')).toContainText('字节上限不是 Token 预算');
  await page.keyboard.press('Enter');
  await expect(page.locator('.context-help')).not.toHaveAttribute('open');
  for (const [width, height] of [[1440, 1000], [1280, 900], [768, 1024], [640, 450], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await page.locator('.single-advanced-settings').scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.locator('#single-context-bytes')).toHaveValue('8192');
    await expect(page.locator('#steps-input')).toHaveValue('10');
    if (width > 640) {
      const rounds = await page.locator('#single-context-window').boundingBox();
      const bytes = await page.locator('#single-context-bytes').boundingBox();
      expect(Math.abs(rounds!.y - bytes!.y)).toBeLessThan(2);
    }
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    await page.screenshot({ path: testInfo.outputPath(`compact-settings-${width}.png`), fullPage: true });
  }
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.locator('.single-advanced-settings > summary').press('Enter');
  await expect(page.locator('.single-advanced-settings')).not.toHaveAttribute('open');
  await page.locator('.single-advanced-settings > summary').press('Enter');
  await expect(page.locator('#single-context-mode')).toHaveValue('memory');
  expect(posts).toEqual([]);
});

test('grouped controls preserve explicit limits, rejected tools and read-only history', async ({ page, request }) => {
  await page.goto('/?mode=single');
  await page.locator('#single-task-search').fill('order-status-001');
  await page.getByRole('button', { name: /order-status-001/ }).click();
  await page.locator('input[name="single-runtime-backend"][value="langgraph"]').check();
  await page.locator('.single-advanced-settings > summary').focus();
  await page.keyboard.press('Enter');
  await page.locator('#steps-input').fill('5');
  await page.locator('#single-time-limit').fill('120');
  await page.locator('#single-context-mode').selectOption('memory');
  await page.locator('#single-context-window').fill('1');
  await page.locator('#single-context-bytes').fill('2048');
  await page.locator('#scenario-select').selectOption('invalid-arguments');
  await page.locator('.single-advanced-settings > summary').click();
  await expect(page.locator('.single-launch-summary')).toContainText('记忆 2048 字节');
  const sent = page.waitForRequest(value => value.method() === 'POST' && value.url().endsWith('/api/v1/episodes/stream'));
  await page.locator('#run-button').click();
  expect((await sent).postDataJSON()).toMatchObject({ max_steps: 5, max_execution_time_ms: 120000,
    runtime_backend: 'langgraph', scenario: 'invalid-arguments', context_policy: { memory_max_bytes: 2048, max_tool_rounds: 1 } });
  await expect(page).toHaveURL(/episode_id=/);
  const id = new URL(page.url()).searchParams.get('episode_id')!;
  const original = parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact;
  expect(original.evaluation.success).toBe(false);
  expect(original.events.some(event => event.event_type === 'TOOL_STARTED')).toBe(false);
  await expect(page.locator('#eval-badge')).toContainText('评测未通过');
  const posts: string[] = [];
  page.on('request', value => { if (value.url().includes('/api/') && value.method() !== 'GET') posts.push(value.url()); });
  await page.locator('#config-panel > summary').click();
  await page.locator('.single-advanced-settings > summary').click();
  await expect(page.locator('#single-context-bytes')).toHaveValue('2048');
  await page.locator('#single-context-mode').selectOption('full');
  await expect(page.locator('.episode-runtime')).toContainText('工具记忆（最多 2048 字节）');
  await page.reload();
  await expect(page.locator('#eval-badge')).toContainText('评测未通过');
  await expect(page.locator('.episode-runtime')).toContainText('工具记忆（最多 2048 字节）');
  expect(posts).toEqual([]);
  expect(parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact).toEqual(original);
});
