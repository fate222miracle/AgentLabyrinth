import { randomUUID } from 'node:crypto';
import { expect, test } from '@playwright/test';
import { episodeResponseSchema, parseApi } from '../src/apiContracts';

test('saved usage shows partial and unknown totals without changing history or calling a model', async ({ page, request }, testInfo) => {
  const response = await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'success', task_id: 'order-status-001',
  } });
  expect(response.ok()).toBeTruthy();
  const original = parseApi(episodeResponseSchema, await response.json());
  let fixture = structuredClone(original);
  const id = original.artifact.episode.episode_id;
  const mutations: string[] = [];
  page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  await page.route(`**/api/v1/episodes/${id}`, route => route.fulfill({ json: fixture }));
  await page.goto(`/?episode_id=${id}`);
  const box = page.locator('.metric-box').filter({ has: page.locator('#metric-tokens') });
  await expect(box).toContainText('Token 消耗');
  await expect(box).not.toContainText('总用量未知');

  fixture = structuredClone(original);
  const artifact = fixture.artifact;
  // Model a saved network interruption: one reported response followed by an unanswered request.
  artifact.episode.termination_reason = 'RUNTIME_ERROR';
  artifact.episode.detail = 'provider_error: NETWORK_CONNECTION_FAILED';
  artifact.evaluation.success = false;
  artifact.events = artifact.events.filter(event => !['MODEL_REQUESTED', 'MODEL_RESPONDED'].includes(event.event_type));
  const requested = original.artifact.events.find(event => event.event_type === 'MODEL_REQUESTED')!;
  const responded = original.artifact.events.find(event => event.event_type === 'MODEL_RESPONDED')!;
  artifact.episode.model_call_count = 2;
  artifact.episode.token_usage = { prompt_tokens: 3280, completion_tokens: 84, simulated: false };
  artifact.events.splice(1, 0, { ...requested, event_id: randomUUID() },
    { ...responded, event_id: randomUUID(), token_usage: artifact.episode.token_usage },
    { ...requested, event_id: randomUUID() });
  const saved = JSON.stringify(fixture);
  await page.reload();
  await expect(box).toContainText('已报告 Token');
  await expect(page.locator('#metric-tokens')).toHaveText('3364');
  await expect(box).toContainText('总用量未知');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const width of [1440, 1280, 720, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await box.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    expect(await page.locator('.episode-metrics .metric-box').evaluateAll(elements =>
      elements.every(element => element.scrollWidth <= element.clientWidth + 1))).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(`usage-${width}.png`) });
  }
  expect(JSON.stringify(fixture)).toBe(saved);
  artifact.events = artifact.events.filter(event => event.event_type !== 'MODEL_RESPONDED');
  artifact.episode.token_usage = { prompt_tokens: 0, completion_tokens: 0, simulated: false };
  await page.reload();
  await expect(page.locator('#metric-tokens')).toHaveText('未知');
  await expect(box).toContainText('总用量未知');
  expect(mutations).toEqual([]);
  expect(parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact).toEqual(original.artifact);
});
