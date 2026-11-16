import { expect, test } from '@playwright/test';

test.use({ launchOptions: { args: ['--enable-unsafe-swiftshader'] } });

test('GridWorld displays accepted live moves and seeks history without replaying actions', async ({ page }, testInfo) => {
  const errors: string[] = [];
  const posts: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().includes('/api/v1/episodes')) posts.push(request.url());
  });
  await page.goto('/gridworld');
  await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
  await page.locator('#gridworld-scenario').selectOption('illegal-action');
  await page.evaluate(() => {
    const clips: string[] = [];
    const observer = new MutationObserver(records => {
      for (const { target } of records) {
        if (target instanceof HTMLCanvasElement && target.closest('.gridworld-stage')) {
          if (target.dataset.clip) clips.push(target.dataset.clip);
        }
      }
      document.body.dataset.observedClips = clips.join(',');
    });
    observer.observe(document.body, { subtree: true, attributes: true, attributeFilter: ['data-clip'] });
  });
  await page.locator('#run-button').click();
  const map = page.getByRole('region', { name: 'Agent 可见地图' });
  const canvas = map.locator('.gridworld-stage canvas');
  await expect(canvas).toBeInViewport({ ratio: 0.4 });
  await expect(canvas).toHaveAttribute('data-action', '9', { timeout: 15_000 });
  await expect(canvas).toBeInViewport({ ratio: 0.4 });
  await expect(canvas).toHaveAttribute('data-position', '5,2');
  const observedClips = (await page.locator('body').getAttribute('data-observed-clips'))?.split(',') ?? [];
  expect(observedClips).toEqual(expect.arrayContaining(['Walk', 'PickUp', 'OpenDoor']));
  expect(observedClips.filter(clip => clip === 'PickUp')).toHaveLength(1);
  expect(observedClips.filter(clip => clip === 'OpenDoor')).toHaveLength(1);
  await expect(map.locator('.gridworld-rejections')).toContainText('Movement blocked.');
  await map.screenshot({ path: testInfo.outputPath('gridworld-3d-completed.png') });

  await page.getByRole('button', { name: '查看保存详情与回放' }).click();
  await expect(map.locator('.gridworld-cell.kind-goal')).toHaveCount(0);
  const slider = page.getByRole('slider', { name: '动画进度' });
  await slider.fill(await slider.getAttribute('max') ?? '0');
  await expect(canvas).toHaveAttribute('data-action', '9');
  await expect(canvas).toHaveAttribute('data-clip', 'Idle');
  await slider.fill('1');
  await expect(canvas).toHaveAttribute('data-action', '0');
  await expect(map.locator('.gridworld-cell.kind-goal')).toHaveCount(0);
  const countWalks = async () =>
    ((await page.locator('body').getAttribute('data-observed-clips'))?.split(',') ?? [])
      .filter(clip => clip === 'Walk').length;
  const walksBeforePlayback = await countWalks();
  await page.getByRole('combobox', { name: '动画速度' }).selectOption('700');
  await page.getByRole('button', { name: '播放', exact: true }).click();
  await expect.poll(countWalks, { timeout: 15_000 }).toBeGreaterThan(walksBeforePlayback);
  await slider.fill('1');
  await expect(canvas).toHaveAttribute('data-action', '0');
  await expect(canvas).toHaveAttribute('data-clip', 'Idle');
  await page.getByRole('button', { name: '二维地图', exact: true }).click();
  await expect(canvas).toHaveCount(0);
  await expect(map.getByRole('img', { name: /Agent 可见地图/ })).toBeVisible();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: '三维场景', exact: true }).click();
  await slider.fill(await slider.getAttribute('max') ?? '0');
  await expect(canvas).toHaveAttribute('data-action', '9');
  await expect(canvas).toHaveAttribute('data-clip', 'Idle');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(posts).toHaveLength(1);
  expect(errors).toEqual([]);
});

test('missing Blender asset falls back to the public 2D map', async ({ page }) => {
  await page.route('**/gridworld/iuno-chibi.glb', route => route.fulfill({ status: 404 }));
  await page.goto('/gridworld');
  await page.locator('#run-button').click();
  const map = page.getByRole('region', { name: 'Agent 可见地图' });
  await expect(map.getByText('三维场景暂不可用，已切换到二维地图。')).toBeVisible();
  await expect(map.getByRole('img', { name: /Agent 可见地图/ })).toBeVisible();
  await expect(map.locator('canvas')).toHaveCount(0);
});

test('the second GridWorld task opens on a larger board and replays its exploration', async ({ page }, testInfo) => {
  await page.goto('/gridworld');
  await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
  await page.getByRole('button', { name: /回廊档案室/ }).click();
  await expect(page.locator('#single-stage-controls')).toContainText('最多 20 轮');
  const propKit = page.waitForResponse(response => response.url().endsWith('/gridworld/gallery-kit.glb'));
  await page.locator('#run-button').click();
  expect((await propKit).status()).toBe(200);
  const map = page.getByRole('region', { name: 'Agent 可见地图' });
  const canvas = map.locator('.gridworld-stage canvas');
  await expect(canvas).toHaveAttribute('data-action', '14', { timeout: 20_000 });
  await expect(canvas).toHaveAttribute('data-position', '7,3');
  await map.screenshot({ path: testInfo.outputPath('gridworld-gallery.png') });

  await page.getByRole('button', { name: '查看保存详情与回放' }).click();
  await expect(map.locator('.gridworld-cell.kind-goal')).toHaveCount(0);
  const slider = page.getByRole('slider', { name: '动画进度' });
  await slider.fill(await slider.getAttribute('max') ?? '0');
  await expect(canvas).toHaveAttribute('data-position', '7,3');
  await expect(map.locator('.gridworld-cell.kind-goal')).toHaveCount(1);
  await page.getByRole('button', { name: '二维地图', exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await map.locator('.gridworld-board').evaluate(board => board.scrollWidth <= board.clientWidth)).toBe(true);
});
