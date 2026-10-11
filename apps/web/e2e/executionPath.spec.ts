import { expect, test } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { episodeResponseSchema, parseApi } from '../src/apiContracts';
import { flowFrames } from '../src/flowFrames';

test('incremental live events remain visible on completion without an automatic replay', async ({ page, request }, testInfo) => {
  const reply = await request.post('/api/v1/episodes',{data:{provider:'fake',model:'fake-model',scenario:'success',task_id:'order-status-007'}});
  const saved = parseApi(episodeResponseSchema,await reply.json());
  const artifact = saved.artifact;
  // Feed an actual saved Fake trace in controlled network chunks; this checks UI transport, not real-model latency.
  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window);
    const controls = window as Window & { pushTrace?: (chunk: {block:string;done?:boolean}) => void; streamCalls?: number };
    window.fetch = async (input, init) => {
      const url = new URL(input instanceof Request ? input.url : String(input), location.href);
      if (url.pathname !== '/api/v1/episodes/stream') return originalFetch(input,init);
      controls.streamCalls = (controls.streamCalls ?? 0) + 1;
      return new Response(new ReadableStream<Uint8Array>({start(controller) {
        controls.pushTrace = ({block,done}) => {
          if (block) controller.enqueue(new TextEncoder().encode(block));
          if (done) controller.close();
        };
      }}),{headers:{'Content-Type':'text/event-stream'}});
    };
  });
  await page.goto('/?mode=single');
  await page.getByLabel('搜索任务',{exact:true}).fill('order-status-007');
  await page.getByRole('button',{name:/order-status-007 多步规划/}).click();
  await page.getByRole('button',{name:'开始运行 Episode',exact:true}).click();
  await expect.poll(() => page.evaluate(() => typeof (window as Window & {pushTrace?:unknown}).pushTrace)).toBe('function');
  const send = async (block: string, done = false) => page.evaluate(chunk => {
    (window as Window & {pushTrace?: (chunk:{block:string;done:boolean}) => void}).pushTrace!(chunk);
  },{block,done});
  let sent = 0;
  const through = async (index: number) => {
    await send(artifact.events.slice(sent,index+1).map(event => `event: trace\ndata: ${JSON.stringify(event)}\n\n`).join(''));
    sent = index+1;
  };
  const live = page.getByRole('region',{name:'实时工具调用流程'});
  await through(artifact.events.findIndex(event => event.event_type === 'MODEL_REQUESTED'));
  await expect(live.locator('.react-flow__node')).toHaveCount(2);
  await expect(live.getByLabel('当前阶段摘要')).toContainText('等待模型响应');
  await expect(live.getByLabel('最终输出')).toContainText('运行完成后显示评测结果');
  await expect(live.getByRole('slider',{name:'动画进度'})).toHaveCount(0);
  await expect(page.locator('#trace-panel')).toBeFocused();
  await through(artifact.events.findIndex(event => event.event_type === 'TOOL_CALL_PROPOSED'));
  await expect(live.locator('.react-flow__node')).toHaveCount(3);
  await expect(live.getByLabel('当前阶段摘要')).not.toContainText('工具返回');
  await expect(live.locator('animateMotion')).toHaveCount(1);
  await page.emulateMedia({reducedMotion:'reduce'});
  await expect(live.locator('animateMotion')).toHaveCount(0);
  await live.screenshot({path:testInfo.outputPath('incremental-live.png')});
  await through(artifact.events.length-1);
  await expect(live.locator('.flow-node.current')).toContainText('任务答案');
  const nodeId = await live.locator('.flow-node.current').locator('..').getAttribute('data-id');
  await send(`event: complete\ndata: ${JSON.stringify(saved)}\n\n`,true);
  const completed = page.getByRole('region',{name:'本次工具执行过程'});
  await expect(completed).toBeVisible();
  await expect(completed.locator('.flow-node.current').locator('..')).toHaveAttribute('data-id',nodeId!);
  await expect(completed.getByLabel('最终输出')).toContainText('approved');
  await expect(completed.getByRole('slider',{name:'动画进度'})).toHaveCount(0);
  await expect(completed.getByRole('button',{name:'播放全过程',exact:true})).toHaveCount(0);
  await expect(completed.locator('animateMotion')).toHaveCount(0);
  await completed.screenshot({path:testInfo.outputPath('live-completed-no-replay.png')});
  await page.getByRole('button',{name:'查看保存详情与回放',exact:true}).click();
  await expect(page.getByRole('region',{name:'工具调用动画回放'})).toBeVisible();
  expect(await page.evaluate(() => (window as Window & {streamCalls?:number}).streamCalls)).toBe(1);
  const mutations: string[] = [];
  page.on('request', r => {if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url());});
  await page.reload();
  await expect(page.getByRole('region',{name:'工具调用动画回放'})).toBeVisible();
  expect(mutations).toEqual([]);
  expect(parseApi(episodeResponseSchema,await (await request.get(`/api/v1/episodes/${artifact.episode.episode_id}`)).json()).artifact).toEqual(artifact);
});

test('BFCL output presents the accepted proposal, never an invented calculation or future answer', async ({ page, request }, testInfo) => {
  const reply = await request.post('/api/v1/episodes', {data:{provider:'fake',model:'fake-model',scenario:'success',task_id:'bfcl-simple_python_1',suite:'bfcl_adapted'}});
  const response = parseApi(episodeResponseSchema, await reply.json());
  // Display-only fixture: the generic Fake provider cannot solve BFCL. No artifact or score is rewritten.
  const fixture = structuredClone(response.artifact);
  const proposal = {name:'math.factorial',arguments:{number:5}};
  const entries = [
    ['EPISODE_STARTED',{seed:1}],
    ['OBSERVATION_CREATED',{observation:{question:'Calculate the factorial of 5.'}}],
    ['MODEL_REQUESTED',{}], ['MODEL_RESPONDED',{action_kind:'tool_call'}],
    ['TOOL_CALL_PROPOSED',{call_id:'display-call',...proposal}],
    ['TOOL_STARTED',{call_id:'display-call',name:proposal.name}],
    ['TOOL_SUCCEEDED',{call_id:'display-call',observation:{accepted:true}}],
    ['ENVIRONMENT_UPDATED',{state:{proposed_call:proposal}}],
    ['EPISODE_FINISHED',{termination_reason:'SUCCESS',success:true,detail:'submitted'}],
  ] as const;
  fixture.events = entries.map(([event_type,payload],i) => ({...fixture.events[0],
    event_id:randomUUID(),event_type,payload,step_index:i < 2 ? 0 : 1}));
  fixture.episode.final_state = {proposed_call:proposal};
  fixture.episode.termination_reason = 'SUCCESS';
  fixture.episode.detail = 'submitted';
  fixture.evaluation = {...fixture.evaluation,success:true,reason:'call_matches_ground_truth'};
  await page.route(`**/api/v1/episodes/${fixture.episode.episode_id}`, route => route.fulfill({json:{...response,artifact:fixture}}));
  const mutations: string[] = [];
  page.on('request', r => {if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url());});
  await page.goto(`/?episode_id=${fixture.episode.episode_id}`);
  const slider = page.getByRole('slider',{name:'动画进度'});
  await slider.press('Home');
  await expect(page.getByLabel('当前阶段摘要')).not.toContainText('math.factorial');
  await expect(page.locator('.flow-node').filter({hasText:'函数调用输出'})).toHaveCount(0);
  await slider.press('End');
  const inspector = page.getByLabel('当前阶段摘要');
  await expect(inspector).toContainText('math.factorial(number=5)');
  await expect(inspector).toContainText('未产生数值计算结果');
  await expect(page.locator('.flow-node.current')).toContainText('函数调用输出');
  await expect(page.getByLabel('最终输出')).toContainText('评测结论：通过');
  for (const [width,height] of [[1440,1000],[390,844]]) {
    await page.setViewportSize({width,height});
    await inspector.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.locator('.flow-replay').screenshot({path:testInfo.outputPath(`bfcl-output-${width}.png`)});
  }
  fixture.evaluation = {...fixture.evaluation,success:false,reason:'call_does_not_match_ground_truth'};
  await page.reload();
  await expect(page.getByLabel('最终输出')).toHaveClass(/failed/);
  await expect(page.getByLabel('最终输出')).toContainText('评测结论：未通过');
  fixture.events = fixture.events.filter(event => event.event_type !== 'ENVIRONMENT_UPDATED');
  await page.reload();
  await page.getByRole('slider',{name:'动画进度'}).press('End');
  await expect(inspector).toContainText('当前轨迹未保存已接收的函数调用');
  await expect(inspector).not.toContainText('math.factorial(number=5)');
  expect(mutations).toEqual([]);
  expect(parseApi(episodeResponseSchema,await (await request.get(`/api/v1/episodes/${fixture.episode.episode_id}`)).json()).artifact).toEqual(response.artifact);
});

test('order and document deliveries show answers, evidence and verdict; failure never fabricates a delivery', async ({ page, request }) => {
  for (const options of [
    {task_id:'order-status-001',scenario:'success'},
    {task_id:'order-status-007',scenario:'success'},
    {task_id:'order-status-001',scenario:'invalid-arguments'},
  ]) {
    const reply = await request.post('/api/v1/episodes',{data:{provider:'fake',model:'fake-model',...options}});
    const artifact = parseApi(episodeResponseSchema,await reply.json()).artifact;
    await page.goto(`/?episode_id=${artifact.episode.episode_id}`);
    await page.getByRole('slider',{name:'动画进度'}).press('End');
    const output = page.getByLabel('最终输出');
    const inspector = page.getByLabel('当前阶段摘要');
    await expect(output).toContainText('交付要求：提交任务结论，并引用实际获取的证据');
    await expect(output).toContainText(`评测结论：${artifact.evaluation.success ? '通过' : '未通过'}`);
    if (options.scenario === 'success') {
      const submission = artifact.episode.final_state.submission as {answer:string;evidence:string[]};
      await expect(output).toContainText(submission.answer);
      await expect(inspector).toContainText(submission.answer);
      for (const evidence of submission.evidence) {
        await expect(output).toContainText(evidence);
        await expect(inspector).toContainText(evidence);
      }
      await expect(page.locator('.flow-node.current')).toContainText('任务答案');
    } else {
      await expect(output).toContainText('未保存已提交的答案');
      await expect(inspector).toContainText('当前轨迹未保存已提交的答案');
      await expect(page.locator('.flow-node.current')).toContainText('运行结束');
    }
  }
});

test('repeated invocations retain rejection, current evidence and read-only navigation', async ({ page, request }, testInfo) => {
  const reply = await request.post('/api/v1/episodes', { data: {
    provider: 'fake', model: 'fake-model', scenario: 'invalid-then-success',
    task_id: 'order-status-001', runtime_strategy: 'handwritten_recovery',
  } });
  expect(reply.ok()).toBeTruthy();
  const artifact = parseApi(episodeResponseSchema, await reply.json()).artifact;
  const frames = flowFrames(artifact.events, artifact.run_config.environment_version ?? '');
  const mutations: string[] = [];
  const errors: string[] = [];
  page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(`/?episode_id=${artifact.episode.episode_id}`);
  const slider = page.getByRole('slider', { name: '动画进度' });
  const nodes = page.locator('.react-flow__node');
  const inspector = page.getByLabel('当前阶段摘要');
  const move = async (index: number) => {
    await slider.press('Home');
    for (let i = 0; i < index; i++) await slider.press('ArrowRight');
  };
  const rejected = frames.findIndex(f => f.phase === 'reject');
  await move(rejected);
  await expect(nodes.locator('.flow-node.failed')).toHaveCount(1);
  await expect(nodes.filter({hasText:'query_records'})).toHaveCount(1);
  await expect(inspector).toContainText('INVALID_ARGUMENTS');
  await expect(inspector).not.toContainText('查询记录');
  const firstId = await nodes.filter({hasText:'query_records'}).getAttribute('data-id');
  const executed = frames.findIndex(f => f.phase === 'execute');
  await move(executed);
  await expect(nodes.filter({hasText:'query_records'})).toHaveCount(2);
  await expect(nodes.filter({hasText:'query_records'}).first()).toHaveAttribute('data-id', firstId!);
  await expect(inspector.getByRole('heading',{name:'工具返回',exact:true})).toHaveCount(0);
  await slider.press('End');
  await expect(nodes.filter({hasText:'query_records'})).toHaveCount(2);
  const trail = page.getByLabel('已记录执行节点');
  await trail.getByRole('button', {name:'查询记录',exact:true}).focus();
  await page.keyboard.press('Enter');
  await expect(inspector).toContainText('已获取证据');
  await expect(inspector).toContainText('order:ORD-001');
  await expect(inspector).not.toContainText('提交内容');
  for (const [width,height] of [[1440,1000],[1280,900],[768,1000],[390,844]]) {
    await page.setViewportSize({width,height});
    await page.locator('.flow-canvas').scrollIntoViewIfNeeded();
    await expect.poll(() => page.locator('.flow-node.current').evaluate(node => {
      const box = node.getBoundingClientRect(), canvas = node.closest('.flow-canvas')!.getBoundingClientRect();
      const text = node.querySelector('.flow-node-status')!;
      return box.left >= canvas.left - 2 && box.right <= canvas.right + 2
        && box.top >= canvas.top - 2 && box.bottom <= canvas.bottom + 2
        && parseFloat(getComputedStyle(text).fontSize) * box.width / 224 >= 11;
    })).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.locator('.flow-replay').screenshot({path:testInfo.outputPath(`execution-${width}.png`)});
  }
  await page.emulateMedia({reducedMotion:'reduce'});
  await move(rejected);
  await expect.poll(() => page.locator('.flow-node').evaluateAll(items => items.flatMap(item => item.getAnimations()).length)).toBe(0);
  await expect(inspector).toContainText('INVALID_ARGUMENTS');
  await page.getByRole('button',{name:'技术 Trace',exact:true}).click();
  await page.getByRole('button',{name:'流程动画',exact:true}).click();
  await expect(inspector).toContainText('INVALID_ARGUMENTS');
  await page.reload();
  await expect(page.getByText('评测通过 (SUCCESS)',{exact:true})).toBeVisible();
  expect(mutations).toEqual([]);
  expect(errors).toEqual([]);
  const reread = parseApi(episodeResponseSchema, await (await request.get(`/api/v1/episodes/${artifact.episode.episode_id}`)).json()).artifact;
  expect(reread).toEqual(artifact);
});

test('an interrupted real-event prefix only creates arrived nodes and preserves unknown status', async ({ page, request }, testInfo) => {
  const reply = await request.post('/api/v1/episodes', {data:{provider:'fake',model:'fake-model',scenario:'success',task_id:'order-status-001'}});
  const artifact = parseApi(episodeResponseSchema, await reply.json()).artifact;
  const proposed = artifact.events.findIndex(event => event.event_type === 'TOOL_CALL_PROPOSED');
  const prefix = artifact.events.slice(0,proposed+1);
  await page.route('**/api/v1/episodes/stream', route => route.fulfill({contentType:'text/event-stream',
    body:prefix.map(event => `event: trace\ndata: ${JSON.stringify(event)}\n\n`).join('')}));
  await page.goto('/?mode=single');
  await page.getByRole('button',{name:'开始运行 Episode',exact:true}).click();
  const live = page.getByRole('region',{name:'实时工具调用流程'});
  await expect(live).toBeVisible();
  await expect(page.getByText('实时连接已中断，后端运行状态未知。',{exact:false})).toBeVisible();
  await expect(live.locator('.react-flow__node')).toHaveCount(3);
  await expect(live.locator('.flow-node-status').filter({hasText:'已提议'})).toHaveCount(1);
  await expect(live.getByLabel('当前阶段摘要')).not.toContainText('工具返回');
  await expect(live.getByLabel('最终输出')).toContainText('请稍后按 Episode ID 回读最终产物');
  await expect(live.getByLabel('动画进度')).toHaveCount(0);
  await expect(live.getByLabel('已记录执行节点').getByRole('button').first()).toBeDisabled();
  await live.screenshot({path:testInfo.outputPath('live-prefix-interrupted.png')});
});

test('timeout and BFCL provider failure never invent tool execution or a successful result', async ({ page, request }, testInfo) => {
  for (const options of [
    {task_id:'order-status-001',fault_profile:'tool_timeout'},
    {task_id:'bfcl-simple_python_1',suite:'bfcl_adapted'},
  ]) {
    const reply = await request.post('/api/v1/episodes',{data:{provider:'fake',model:'fake-model',scenario:'success',...options}});
    expect(reply.ok()).toBeTruthy();
    const artifact = parseApi(episodeResponseSchema, await reply.json()).artifact;
    const frames = flowFrames(artifact.events,artifact.run_config.environment_version ?? '');
    await page.goto(`/?episode_id=${artifact.episode.episode_id}`);
    if ('suite' in options) {
      // The generic Fake provider has no BFCL answer program; keep its actual failure visible.
      expect(artifact.episode.termination_reason).toBe('RUNTIME_ERROR');
      expect(frames.some(frame => frame.tool)).toBe(false);
      await expect(page.getByText('评测未通过 (FAILED)',{exact:true})).toBeVisible();
      await page.getByRole('slider',{name:'动画进度'}).press('End');
      await expect(page.locator('.flow-node.current')).toContainText('RUNTIME_ERROR');
      await expect(page.getByLabel('最终输出')).toContainText('未保存函数调用提议');
      await expect(page.locator('.flow-node-kind').filter({hasText:'工具调用'})).toHaveCount(0);
      await page.locator('.flow-workspace').screenshot({path:testInfo.outputPath('bfcl-provider-failure.png')});
      continue;
    }
    const slider = page.getByRole('slider',{name:'动画进度'});
    const returned = frames.findIndex(f => f.phase === 'return');
    expect(returned).toBeGreaterThan(0);
    await slider.press('Home');
    for (let i = 0; i < returned; i++) await slider.press('ArrowRight');
    const inspector = page.getByLabel('当前阶段摘要');
    await expect(inspector).toContainText('TOOL_TIMEOUT');
    await expect(page.locator('.flow-node.current')).toHaveClass(/failed/);
    await expect(page.locator('.flow-node.current')).toContainText('已记录失败');
    await page.locator('.flow-workspace').screenshot({path:testInfo.outputPath('tool-timeout.png')});
  }
});
