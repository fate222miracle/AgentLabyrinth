import { expect, test } from '@playwright/test';
import { episodeResponseSchema, parseApi } from '../src/apiContracts';
import { flowFrames } from '../src/flowFrames';

test('a completed live run leads with its real delivery and analysis retains the same saved answer', async ({ page, request }, testInfo) => {
  await page.goto('/workbench');
  await page.getByRole('button', { name: '修改任务与配置', exact: true }).click();
  await page.getByRole('button', { name: '配置退货审核实时演示', exact: true }).click();
  await page.locator('#run-button').click();
  const flow = page.getByRole('region', { name: '本次工具执行过程', exact: true });
  const output = flow.getByLabel('最终输出', { exact: true });
  await expect(output).toBeFocused();
  await expect(output).toContainText('Fake 离线模拟');
  const id = await page.locator('.persistence-value').innerText();
  const source = parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact;
  const submission = source.episode.final_state.submission as { answer: string; evidence: string[] };
  await expect(output.locator('.delivery-answer')).toHaveText(submission.answer);
  for (const evidence of submission.evidence) await expect(output).toContainText(evidence);
  expect(await flow.evaluate(element => element.querySelector('.run-delivery')!.getBoundingClientRect().top
    < element.querySelector('.flow-canvas')!.getBoundingClientRect().top)).toBe(true);
  await expect(flow.locator('.flow-task-brief')).not.toHaveAttribute('open');
  await expect(flow.getByRole('button', { name: '播放全过程', exact: true })).toHaveCount(0);
  for (const [width, height] of [[1440, 900], [1280, 720], [768, 1024], [640, 450], [390, 844]]) {
    await page.setViewportSize({ width, height });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const positions = await flow.evaluate(element => ({
      current: element.querySelector('.flow-inspector')!.getBoundingClientRect().top,
      canvas: element.querySelector('.flow-canvas')!.getBoundingClientRect().top,
    }));
    if (width <= 900) expect(positions.current).toBeLessThan(positions.canvas);
    await output.scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath(`delivery-${width}.png`), fullPage: false });
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await flow.getByRole('button', { name: '专注查看', exact: true }).click();
  await expect.poll(() => page.evaluate(() => document.fullscreenElement?.classList.contains('flow-replay'))).toBe(true);
  await flow.locator('.flow-canvas').scrollIntoViewIfNeeded();
  await expect.poll(() => flow.locator('.flow-node.current').evaluate(node => {
    const box = node.getBoundingClientRect(), canvas = node.closest('.flow-canvas')!.getBoundingClientRect();
    return box.left >= canvas.left - 2 && box.right <= canvas.right + 2 && box.top >= canvas.top - 2 && box.bottom <= canvas.bottom + 2;
  })).toBe(true);
  await flow.getByRole('button', { name: '退出专注查看', exact: true }).click();
  await expect.poll(() => page.evaluate(() => document.fullscreenElement === null)).toBe(true);
  const writes: string[] = [];
  page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') writes.push(r.url()); });
  await page.getByRole('button', { name: '结果分析', exact: true }).click();
  const analysis = page.getByLabel('结果交付摘要', { exact: true });
  await expect(analysis.locator('.delivery-answer')).toHaveText(submission.answer);
  expect(await page.evaluate(() => document.querySelector('.episode-summary .run-delivery')!.getBoundingClientRect().top
    < document.querySelector('.episode-metrics')!.getBoundingClientRect().top)).toBe(true);
  await page.reload();
  await expect(analysis.locator('.delivery-answer')).toHaveText(submission.answer);
  expect(writes).toEqual([]);
  expect(parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${id}`)).json()).artifact).toEqual(source);
});

test('an empty document return keeps its raw feedback instead of announcing that body text arrived', async ({ page, request }) => {
  const saved = parseApi(episodeResponseSchema, await (await request.post('/api/v1/episodes', {
    data: { provider: 'fake', model: 'fake-model', task_id: 'return-evidence-chain-001' },
  })).json());
  const fixture = structuredClone(saved);
  const frames = flowFrames(fixture.artifact.events, fixture.artifact.run_config.environment_version ?? '');
  const target = frames.findIndex(frame => frame.phase === 'return' && frame.tool === 'read_document');
  const event = fixture.artifact.events[frames[target].eventIndex];
  event.payload = { ...event.payload, observation: { result: { document: { document_id: 'empty-display-fixture', content: '' } } } };
  await page.route(`**/api/v1/episodes/${fixture.artifact.episode.episode_id}`, route => route.fulfill({ json: fixture }));
  await page.goto(`/runs/${fixture.artifact.episode.episode_id}`);
  await page.getByRole('slider', { name: '动画进度', exact: true }).fill(String(target));
  const feedback = page.getByLabel('当前阶段摘要', { exact: true });
  await expect(feedback).toContainText('empty-display-fixture');
  await expect(feedback).not.toContainText('正文已返回，完整内容见关联资料。');
});

test('long saved delivery remains readable and failure does not erase the submitted answer or become success', async ({ page, request }) => {
  const source = parseApi(episodeResponseSchema, await (await request.post('/api/v1/episodes', {
    data: { provider: 'fake', model: 'fake-model', task_id: 'order-status-001' },
  })).json());
  // A display fixture checks long text; it never overwrites the source Episode or its score.
  const fixture = structuredClone(source);
  const answer = '保留原始提交，不改写评测结论。\n'.repeat(24) + '完整答案的末尾';
  fixture.artifact.episode.final_state.submission = { answer, evidence: ['document:long-evidence-id'] };
  fixture.artifact.evaluation.success = false;
  fixture.artifact.evaluation.reason = 'submission_does_not_match_target';
  await page.route(`**/api/v1/episodes/${source.artifact.episode.episode_id}`, route => route.fulfill({ json: fixture }));
  const writes: string[] = [];
  page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') writes.push(r.url()); });
  await page.goto(`/runs/${source.artifact.episode.episode_id}?section=results`);
  const delivery = page.getByLabel('结果交付摘要', { exact: true });
  await expect(delivery).toHaveClass(/failed/);
  await expect(delivery).toContainText('评测结论：未通过');
  await expect(delivery).toContainText('已保存提交，但未通过任务规则检查');
  expect(await delivery.locator('.delivery-answer').textContent()).toBe(answer);
  expect(await delivery.locator('.delivery-answer').evaluate(element => element.scrollHeight <= element.clientHeight + 1)).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: '执行过程', exact: true }).click();
  await expect(page.getByLabel('最终输出', { exact: true })).toContainText('整次运行的最终结果');
  await expect(page.getByLabel('当前阶段摘要', { exact: true })).not.toContainText('完整答案的末尾');
  expect(writes).toEqual([]);
  expect(parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${source.artifact.episode.episode_id}`)).json()).artifact).toEqual(source.artifact);
});
