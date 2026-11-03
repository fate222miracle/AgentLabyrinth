import { expect, test } from '@playwright/test';
import { episodeResponseSchema, parseApi } from '../src/apiContracts';

test('task library leads to a preserved draft without starting inference', async ({ page }) => {
  const writes: string[] = [];
  page.on('request', request => { if (request.url().includes('/api/') && request.method() !== 'GET') writes.push(request.url()); });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: '选择下一项探索' })).toBeVisible();
  await page.getByLabel('查找任务', { exact: true }).fill('return-evidence-chain-001');
  const item = page.locator('.library-task').filter({ hasText: 'return-evidence-chain-001' });
  await item.getByRole('button', { name: '查看任务', exact: true }).click();
  await expect(page.getByLabel('任务详情', { exact: true })).toContainText('完整引用整条依据链');
  await page.getByRole('button', { name: '配置此任务', exact: true }).click();
  await expect(page).toHaveURL(/\/workbench\?/);
  await expect(page.locator('.single-launch-summary')).toContainText('return-evidence-chain-001');
  await expect(page.locator('#config-panel')).toBeHidden();
  await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
  await page.getByRole('radio', { name: 'LangGraph 独立图节点调度' }).check();
  await page.locator('#tab-tasks').click();
  await expect(page.getByLabel('查找任务', { exact: true })).toHaveValue('return-evidence-chain-001');
  await page.locator('#tab-single').click();
  await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
  await expect(page.getByRole('radio', { name: 'LangGraph 独立图节点调度' })).toBeChecked();
  await expect(page.locator('.single-launch-summary')).toContainText('return-evidence-chain-001');
  expect(writes).toEqual([]);
});

test('detail tabs keep the process first, preserve identity and never run a Judge on navigation', async ({ page, request }, testInfo) => {
  const source = parseApi(episodeResponseSchema, await (await request.post('/api/v1/episodes', {
    data: { provider: 'fake', model: 'fake-model', task_id: 'order-status-007', scenario: 'success' },
  })).json()).artifact;
  const id = source.episode.episode_id;
  const writes: string[] = [];
  page.on('request', value => { if (value.url().includes('/api/') && value.method() !== 'GET') writes.push(value.url()); });
  await page.goto(`/runs/${id}`);
  await expect(page.getByRole('navigation', { name: '运行详情视图' }).getByRole('button', { name: '执行过程', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#trace-panel')).toBeVisible();
  await expect(page.locator('#results-panel')).toBeHidden();
  await expect(page.locator('.episode-review-card')).toBeHidden();
  await expect(page.locator('#single-stage-controls')).toBeHidden();
  const top = await page.locator('#trace-panel').evaluate(node => node.getBoundingClientRect().top + scrollY);
  expect(top).toBeLessThan(600);
  await page.getByRole('button', { name: '结果分析', exact: true }).click();
  await expect(page.locator('#results-panel')).toBeVisible();
  await expect(page.locator('#trace-panel')).toBeHidden();
  await expect(page.locator('#metric-model')).toHaveText(source.agent.model.model);
  await page.getByRole('button', { name: '模型评审', exact: true }).click();
  await expect(page.locator('.episode-review-card')).toBeVisible();
  await expect(page).toHaveURL(/section=review/);
  await page.reload();
  await expect(page.locator('.episode-review-card')).toBeVisible();
  await page.getByRole('button', { name: '执行过程', exact: true }).click();
  for (const [width, height] of [[1440, 900], [1280, 720], [768, 1024], [640, 450], [390, 844]]) {
    await page.setViewportSize({ width, height });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`run-detail-${width}.png`), fullPage: true });
  }
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.locator('#tab-runs').click();
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`/runs/${id}`));
  await expect(page.locator('#trace-panel')).toBeVisible();
  expect(writes).toEqual([]);
  expect(parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact).toEqual(source);
});

test('recent records label their limited scope and errors cannot leave stale success', async ({ page, request }) => {
  const source = parseApi(episodeResponseSchema, await (await request.post('/api/v1/episodes', {
    data: { provider: 'fake', model: 'fake-model', task_id: 'order-status-001' },
  })).json()).artifact;
  await page.addInitScript(id => localStorage.setItem('al_recent_episodes', JSON.stringify([id])), source.episode.episode_id);
  await page.goto('/runs');
  await expect(page.getByRole('heading', { name: '运行记录', exact: true })).toBeVisible();
  await expect(page.locator('.records-scope')).toContainText('还不是数据库全部历史');
  await expect(page.locator('.record-row')).toContainText('order-status-001');
  await page.locator('.record-row').click();
  await expect(page.locator('#eval-badge')).toContainText('评测通过');
  await page.locator('#tab-runs').click();
  await page.getByLabel('历史 Episode ID', { exact: true }).fill('00000000-0000-4000-8000-000000000000');
  await page.getByLabel('历史 Episode ID', { exact: true }).press('Enter');
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.locator('#eval-badge')).toHaveCount(0);
  await expect(page.locator('.episode-review-card')).toHaveCount(0);
});
