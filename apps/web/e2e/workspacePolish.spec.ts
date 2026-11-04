import { expect, test } from '@playwright/test';

test('task preview keeps keyboard focus, adapts to narrow screens and never executes on browse', async ({ page }, testInfo) => {
  const writes: string[] = [];
  page.on('request', request => { if (request.url().includes('/api/') && request.method() !== 'GET') writes.push(request.url()); });
  await page.goto('/tasks');
  const first = page.locator('.library-task').first();
  const trigger = first.getByRole('button', { name: '查看任务', exact: true });
  await expect(first).toBeVisible();
  await expect(page.locator('.model-catalog-caution')).toHaveCount(0);
  await trigger.click();
  const preview = page.getByLabel('任务详情', { exact: true });
  await expect(preview.locator('h2')).toBeFocused();
  await expect(preview).toContainText('任务目标与交付要求');
  await expect(trigger).toHaveAttribute('aria-expanded', 'true');
  for (const [width, height] of [[1440, 900], [1280, 720], [768, 1024], [640, 450], [390, 844]]) {
    await page.setViewportSize({ width, height });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (width >= 1024) {
      const [list, detail] = await Promise.all([first.boundingBox(), preview.boundingBox()]);
      expect(list!.x + list!.width).toBeLessThan(detail!.x);
    }
    await preview.getByRole('button', { name: '配置此任务', exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath(`task-preview-${width}.png`), fullPage: false });
  }
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await preview.getByRole('button', { name: '关闭详情', exact: true }).click();
  await expect(trigger).toBeFocused();
  await page.getByLabel('查找任务', { exact: true }).fill('no-such-task-ui-check');
  await expect(page.getByRole('heading', { name: '没有找到匹配任务', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '清除筛选', exact: true }).click();
  await expect(first).toBeVisible();
  await page.getByRole('combobox', { name: '任务来源', exact: true }).selectOption('bfcl_adapted');
  await expect(page.locator('.library-task').first()).toContainText('bfcl-simple_python_');
  await page.locator('.library-task').first().getByRole('button', { name: '查看任务', exact: true }).click();
  await expect(preview).toContainText('BFCL Python 改编');
  await page.getByRole('combobox', { name: '任务来源', exact: true }).selectOption('all');
  await expect(preview).toHaveCount(0);
  expect(writes).toEqual([]);
});

test('failed task metadata has a retry state instead of an endless loader or a false empty search', async ({ page, request }) => {
  const meta = await (await request.get('/api/v1/meta')).json();
  let failed = true;
  await page.route('**/api/v1/meta', route => route.fulfill(failed
    ? { status: 503, json: { detail: 'Metadata unavailable' } } : { json: meta }));
  await page.goto('/tasks');
  await expect(page.getByText('任务目录未载入，请使用上方的重新读取按钮重试。', { exact: true })).toBeVisible();
  await expect(page.locator('.library-toolbar [role="status"]')).toHaveText('目录未载入');
  await expect(page.locator('.library-loading')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '清除筛选', exact: true })).toHaveCount(0);
  failed = false;
  await page.getByRole('button', { name: '重新读取模型目录', exact: true }).click();
  await expect(page.locator('.library-task').first()).toBeVisible();
  await expect(page.getByText('任务目录未载入，请使用上方的重新读取按钮重试。', { exact: true })).toHaveCount(0);
});

test('standby uses content height and experiment charts precede ID utilities', async ({ page }, testInfo) => {
  const writes: string[] = [];
  page.on('request', request => { if (request.url().includes('/api/') && request.method() !== 'GET') writes.push(request.url()); });
  await page.goto('/workbench');
  await expect(page.locator('.single-launch-summary')).toContainText('order-status-001');
  const stage = page.getByLabel('执行舞台准备状态', { exact: true });
  await expect(stage).toContainText('尚未开始');
  await expect(page.locator('.stage-ready-zones')).toHaveCount(0);
  for (const [width, height] of [[1440, 900], [1280, 720], [768, 1024], [640, 450], [390, 844]]) {
    await page.setViewportSize({ width, height });
    expect((await stage.boundingBox())!.height).toBeLessThan(360);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`standby-${width}.png`), fullPage: false });
  }
  await page.locator('#tab-experiment').click();
  await expect(page.locator('.experiment-dashboard')).toBeVisible();
  const positions = await page.evaluate(() => ({
    charts: document.querySelector('.experiment-dashboard')!.getBoundingClientRect().top + scrollY,
    archive: document.querySelector('.experiment-archive')!.getBoundingClientRect().top + scrollY,
  }));
  expect(positions.charts).toBeLessThan(positions.archive);
  await expect(page.getByLabel('历史 Experiment ID', { exact: true })).toBeAttached();
  expect(writes).toEqual([]);
});
