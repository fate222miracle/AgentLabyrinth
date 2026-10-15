import { expect, test } from '@playwright/test';
import { episodeResponseSchema, parseApi } from '../src/apiContracts';

test('fox brand opens a keyboard-accessible preview without changing saved history or the draft', async ({ page, request }, testInfo) => {
  const response = await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'success', task_id: 'order-status-007',
  } });
  expect(response.ok()).toBeTruthy();
  const artifact = parseApi(episodeResponseSchema, await response.json()).artifact;
  const mutations: string[] = [];
  page.on('request', value => {
    if (value.url().includes('/api/') && value.method() !== 'GET') mutations.push(value.url());
  });
  await page.goto(`/?episode_id=${artifact.episode.episode_id}`);
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
  await page.locator('#config-panel > summary').click();
  const search = page.getByLabel('搜索任务', { exact: true });
  await search.fill('order-status-007');
  const originalUrl = page.url();
  const brand = page.getByRole('link', { name: 'AgentLabyrinth · 查看标志动态展示' });
  await expect(brand.locator('img')).toHaveAttribute('src', '/brand/fox-motion.svg');
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href', '/brand/fox-icon.svg');
  const opened = page.waitForEvent('popup');
  await brand.press('Enter');
  const preview = await opened;
  await expect(preview.getByRole('heading', { name: 'AgentLabyrinth', exact: true })).toBeVisible();
  await expect(preview.locator('#motion')).toHaveAttribute('src', /^fox-motion.svg\?play=\d+$/);
  await preview.close();
  expect(page.url()).toBe(originalUrl);
  await expect(search).toHaveValue('order-status-007');
  await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const width of [390, 640, 800, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(brand).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`fox-nav-${width}.png`) });
  }
  expect(mutations).toEqual([]);
  const saved = parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${artifact.episode.episode_id}`)).json());
  expect(saved.artifact).toEqual(artifact);
});

test('failed motion assets fall back to static and preview replay respects a changing reduced-motion preference', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/brand/fox-motion.svg*', route => route.abort());
  await page.goto('/?mode=single');
  const navMark = page.locator('.brand-mark img');
  await expect(navMark).toHaveAttribute('src', '/brand/fox-mark.svg');
  await expect.poll(() => navMark.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
  await expect(page.locator('#run-button')).toBeVisible();
  await page.goto('/brand/fox-preview.html');
  const mark = page.locator('#motion');
  await expect(mark).toHaveAttribute('src', 'fox-mark.svg');
  await expect(page.getByRole('status')).toContainText('动画暂不可用');
  await page.unroute('**/brand/fox-motion.svg*');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  const replay = page.getByRole('button', { name: '重播动画' });
  for (let index = 0; index < 5; index++) await replay.click();
  await expect(mark).toHaveAttribute('src', /^fox-motion.svg\?play=\d+$/);
  await replay.press('Enter');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(mark).toHaveAttribute('src', 'fox-mark.svg');
  await expect(page.getByRole('status')).toContainText('减少动效');
  await replay.click();
  await expect(mark).toHaveAttribute('src', 'fox-mark.svg');
  expect(errors).toEqual([]);
});
