import { expect, test, type APIRequestContext } from '@playwright/test';
import { episodeResponseSchema, parseApi } from '../src/apiContracts';

test.use({ viewport: { width: 1280, height: 800 },
  video: { mode: 'on', size: { width: 1280, height: 800 } } });

async function savedEpisode(request: APIRequestContext) {
  const response = await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'success', task_id: 'order-status-007',
  } });
  expect(response.ok()).toBeTruthy();
  const value: unknown = await response.json();
  return parseApi(episodeResponseSchema, value).artifact;
}

test.describe('continuous desktop motion', () => {
  test('rapid views, disclosures, keyboard and dynamic reduced motion preserve saved state', async ({ page, request }, testInfo) => {
    const artifact = await savedEpisode(request);
    const id = artifact.episode.episode_id;
    const errors: string[] = [];
    const mutations: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('request', (value) => {
      if (value.url().includes('/api/') && value.method() !== 'GET') mutations.push(value.url());
    });
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.goto(`/?episode_id=${id}`);
    await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
    const switcher = page.getByLabel('Replay 视图');
    const panel = page.locator('.replay-content');
    await switcher.scrollIntoViewIfNeeded();
    // Capture genuine intermediate indicator positions, then interrupt with the next view.
    const samples = await switcher.evaluate(async (element) => {
      const buttons = Array.from(element.querySelectorAll('button'));
      const values: string[] = [];
      for (const index of [1, 2, 0, 2, 1]) {
        buttons[index].click();
        await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
        values.push(getComputedStyle(element, '::before').transform);
      }
      return values;
    });
    expect(new Set(samples).size).toBeGreaterThan(1);
    await expect(switcher.getByRole('button', { name: '过程概览' })).toHaveAttribute('aria-pressed', 'true');
    await expect(panel).toHaveAttribute('data-view', 'story');
    await expect.poll(() => panel.evaluate((node) => node.getAnimations().length)).toBe(0);
    const firstStep = page.locator('.step-card').first();
    await firstStep.focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.locator('.step-card').nth(1)).toBeFocused();
    await expect(page.locator('.step-card').nth(1)).toHaveAttribute('aria-current', 'step');
    await page.screenshot({ path: testInfo.outputPath('motion-story.png') });
    await switcher.getByRole('button', { name: '技术 Trace' }).click();
    await expect(page.getByText('MODEL_REQUESTED', { exact: true }).first()).toBeVisible();
    await switcher.getByRole('button', { name: '流程动画' }).click();
    await expect(page.getByLabel('最初输入')).toContainText('搜索订单政策文档');
    await expect(page.getByLabel('最终输出')).toContainText('approved');

    const config = page.locator('#config-panel');
    await config.locator(':scope > summary').click();
    const search = page.locator('#single-task-search');
    await search.fill('order-status-007');
    const advanced = config.locator('.advanced-settings');
    await advanced.locator(':scope > summary').click();
    await expect(advanced).toHaveAttribute('open', '');
    await advanced.locator(':scope > summary').press('Enter');
    await expect(advanced).not.toHaveAttribute('open');
    await expect(advanced.locator(':scope > summary')).toBeFocused();
    await config.locator(':scope > summary').click();
    await config.locator(':scope > summary').click();
    await expect(search).toHaveValue('order-status-007');

    // Change the accessibility preference while content animation is in flight.
    await page.evaluate(() => {
      const node = document.querySelector<HTMLElement>('#tab-experiment');
      node?.click();
    });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await expect.poll(() => page.locator('main').evaluate((node) => node.getAnimations().length)).toBe(0);
    await page.locator('#tab-single').click();
    await expect(page).toHaveURL(new RegExp(`episode_id=${id}`));
    await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
    await expect.poll(() => page.locator('main').evaluate((node) => node.getAnimations().length)).toBe(0);
    await switcher.getByRole('button', { name: '技术 Trace' }).click();
    expect(await panel.evaluate((node) => node.getAnimations().length)).toBe(0);
    expect(mutations).toEqual([]);
    expect(errors).toEqual([]);
    const saved = await request.get(`/api/v1/episodes/${id}`);
    const savedValue: unknown = await saved.json();
    expect(parseApi(episodeResponseSchema, savedValue).artifact).toEqual(artifact);
  });
});

for (const support of ['missing', 'throws'] as const) {
  test(`navigation and saved replay work when animation API ${support}`, async ({ page, request }) => {
    const artifact = await savedEpisode(request);
    await page.addInitScript((mode) => {
      Object.defineProperty(Element.prototype, 'animate', { configurable: true, writable: true,
        value: mode === 'missing' ? undefined : () => { throw new Error('Animation unavailable'); },
      });
    }, support);
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(`/?episode_id=${artifact.episode.episode_id}`);
    await expect(page.getByText('评测通过 (SUCCESS)', { exact: true })).toBeVisible();
    for (const name of ['技术 Trace', '过程概览', '流程动画']) {
      await page.getByRole('button', { name, exact: true }).click();
    }
    await page.locator('#tab-experiment').click();
    await page.locator('#tab-single').click();
    await expect(page.getByLabel('最终输出')).toContainText('approved');
    expect(errors).toEqual([]);
  });
}
