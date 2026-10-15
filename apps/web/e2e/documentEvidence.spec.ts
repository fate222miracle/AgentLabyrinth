import { expect, test } from '@playwright/test';
import { episodeResponseSchema, parseApi } from '../src/apiContracts';

test('live document shelf follows actual reads and citations; previews and refresh never execute tools', async ({ page, request }, testInfo) => {
  const saved = parseApi(episodeResponseSchema, await (await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', task_id: 'return-evidence-chain-001', scenario: 'success',
  } })).json());
  const artifact = saved.artifact;
  // Stream actual Fake events in controlled chunks to inspect intermediate UI states, not model latency.
  await page.addInitScript(() => {
    const fetchOriginal = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const url = new URL(input instanceof Request ? input.url : String(input), location.href);
      if (url.pathname !== '/api/v1/episodes/stream') return fetchOriginal(input, init);
      return new Response(new ReadableStream<Uint8Array>({ start(controller) {
        (window as Window & { pushDocumentTrace?: (chunk: { block: string; done: boolean }) => void }).pushDocumentTrace = ({ block, done }) => {
          if (block) controller.enqueue(new TextEncoder().encode(block));
          if (done) controller.close();
        };
      } }), { headers: { 'Content-Type': 'text/event-stream' } });
    };
  });
  await page.goto('/?mode=single');
  await page.getByRole('button', { name: '配置退货审核实时演示' }).click();
  await page.locator('#run-button').click();
  await expect.poll(() => page.evaluate(() => typeof (window as Window & { pushDocumentTrace?: unknown }).pushDocumentTrace)).toBe('function');
  const send = (block: string, done = false) => page.evaluate(chunk => {
    (window as Window & { pushDocumentTrace?: (chunk: { block: string; done: boolean }) => void }).pushDocumentTrace!(chunk);
  }, { block, done });
  let cursor = 0;
  const through = async (index: number) => {
    await send(artifact.events.slice(cursor, index + 1).map(event => `event: trace\ndata: ${JSON.stringify(event)}\n\n`).join(''));
    cursor = index + 1;
  };
  await through(artifact.events.findIndex(event => event.event_type === 'MODEL_REQUESTED'));
  const shelf = page.getByLabel('关联资料与实际引用');
  await expect(shelf).toContainText('0 / 5 已读取');
  await expect(shelf.getByLabel('当前过程阅读统计')).toContainText('成功阅读 0 次 · 重复阅读 0 次');
  await expect(shelf.getByRole('button')).toHaveCount(5);
  const mutations: string[] = [];
  page.on('request', value => { if (value.url().includes('/api/') && value.method() !== 'GET') mutations.push(value.url()); });
  await shelf.getByRole('button', { name: /退货政策 2025-A/ }).focus();
  await page.keyboard.press('Enter');
  await expect(shelf.getByLabel('资料正文预览')).toContainText('Archived policy');
  await expect(shelf).toContainText('0 / 5 已读取');
  const reads = artifact.events.flatMap((event, index) => event.event_type === 'TOOL_CALL_PROPOSED' && event.payload.name === 'read_document'
    ? [{ index, callId: event.payload.call_id }] : []);
  const started = (callId: unknown) => artifact.events.findIndex(event => event.event_type === 'TOOL_STARTED' && event.payload.call_id === callId);
  const succeeded = (callId: unknown) => artifact.events.findIndex(event => event.event_type === 'TOOL_SUCCEEDED' && event.payload.call_id === callId);
  await through(started(reads[0].callId));
  await expect(shelf.getByLabel('资料正文预览')).toContainText('RET-ENTRY');
  await expect(shelf.getByLabel('资料正文预览')).toContainText('Agent 正在读取');
  await expect(shelf).toContainText('0 / 5 已读取');
  await expect(shelf.getByLabel('当前过程阅读统计')).toContainText('成功阅读 0 次');
  await through(succeeded(reads[0].callId));
  await expect(shelf).toContainText('1 / 5 已读取');
  await expect(shelf.getByRole('button', { name: /CASE-314 intake/ })).not.toContainText('已提交引用');
  await through(started(reads[1].callId));
  await expect(shelf.getByLabel('资料正文预览')).toContainText('RET-POLICY');
  await expect(shelf.getByLabel('资料正文预览')).toContainText('Agent 正在读取');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.locator('.flow-workspace').screenshot({ path: testInfo.outputPath('live-reading.png') });
  await through(artifact.events.length - 1);
  await send(`event: complete\ndata: ${JSON.stringify(saved)}\n\n`, true);
  await expect(page.getByRole('region', { name: '本次工具执行过程' })).toBeVisible();
  await expect(shelf).toContainText('3 / 5 已读取');
  await expect(shelf.getByLabel('当前过程阅读统计')).toContainText('成功阅读 3 次 · 重复阅读 0 次');
  await expect(shelf.getByRole('button').filter({ hasText: '已提交引用' })).toHaveCount(3);
  await expect(shelf.getByRole('button', { name: /CASE-315/ })).toContainText('尚未读取');
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.locator('.flow-workspace').screenshot({ path: testInfo.outputPath(`documents-${width}.png`) });
  }
  await page.reload();
  await page.getByRole('slider', { name: '动画进度' }).press('Home');
  await expect(shelf).toHaveCount(0); // No future snapshot at EPISODE_STARTED.
  await page.getByRole('slider', { name: '动画进度' }).press('End');
  await expect(shelf).toContainText('3 / 5 已读取');
  expect(mutations).toEqual([]);
  expect(parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${artifact.episode.episode_id}`)).json()).artifact).toEqual(artifact);
});

test('failed search does not mark initial documents read; absent snapshots do not borrow final documents', async ({ page, request }) => {
  const response = parseApi(episodeResponseSchema, await (await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', task_id: 'return-evidence-chain-001', fault_profile: 'tool_timeout',
  } })).json());
  expect(response.artifact.evaluation.success).toBe(false);
  await page.goto(`/?episode_id=${response.artifact.episode.episode_id}`);
  await page.getByRole('slider', { name: '动画进度' }).press('End');
  const shelf = page.getByLabel('关联资料与实际引用');
  await expect(shelf).toContainText('0 / 5 已读取');
  await expect(shelf.getByRole('button').filter({ hasText: '已提交引用' })).toHaveCount(0);
  await expect(page.getByLabel('最终输出')).toContainText('未保存已提交的答案');
  const fixture = structuredClone(response);
  fixture.artifact.events = fixture.artifact.events.map(event => ({ ...event, payload: { ...event.payload, initial_state: null } }));
  await page.route(`**/api/v1/episodes/${response.artifact.episode.episode_id}`, route => route.fulfill({ json: fixture }));
  await page.reload();
  await page.getByRole('slider', { name: '动画进度' }).press('End');
  await expect(shelf).toHaveCount(0);
});

test('an interrupted read retains the document preview with an unconfirmed outcome', async ({ page, request }) => {
  const saved = parseApi(episodeResponseSchema, await (await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', task_id: 'return-evidence-chain-001',
  } })).json());
  const proposed = saved.artifact.events.find(event => event.event_type === 'TOOL_CALL_PROPOSED' && event.payload.name === 'read_document')!;
  const started = saved.artifact.events.findIndex(event => event.event_type === 'TOOL_STARTED' && event.payload.call_id === proposed.payload.call_id);
  await page.route('**/api/v1/episodes/stream', route => route.fulfill({ contentType: 'text/event-stream',
    body: saved.artifact.events.slice(0, started + 1).map(event => `event: trace\ndata: ${JSON.stringify(event)}\n\n`).join('') }));
  await page.goto('/?mode=single');
  await page.getByRole('button', { name: '配置退货审核实时演示' }).click();
  await page.locator('#run-button').click();
  await expect(page.getByText('实时连接已中断，后端运行状态未知。', { exact: false })).toBeVisible();
  const shelf = page.getByLabel('关联资料与实际引用');
  await expect(shelf).toContainText('0 / 5 已读取');
  await expect(shelf.getByLabel('资料正文预览')).toContainText('RET-ENTRY');
  await expect(shelf.getByLabel('资料正文预览')).toContainText('读取已发起 · 结果未确认');
  await expect(shelf).not.toContainText('Agent 正在读取');
  await expect(shelf.getByRole('button').filter({ hasText: '已提交引用' })).toHaveCount(0);
});
