import { expect, test } from '@playwright/test';

for (const hasFake of [true, false]) {
  test(`first use requires deliberate real model selection (Fake available: ${hasFake})`, async ({ page, request }) => {
    const original = await (await request.get('/api/v1/meta')).json();
    const fake = original.models.find((model: { provider: string }) => model.provider === 'fake');
    const real = { ...fake, id: 'real-test-entry', name: 'Real catalog fixture', provider: 'aihubmix', scenarios: [] };
    await page.route('**/api/v1/meta', route => route.fulfill({ json: { ...original,
      model_catalog_status: 'unavailable', default_model: real.id, models: [...(hasFake ? [fake] : []), real],
    } }));
    const mutations: string[] = [];
    page.on('request', r => { if (r.url().includes('/api/') && r.method() !== 'GET') mutations.push(r.url()); });
    await page.goto('/?mode=single');
    await expect(page.locator('#model-select')).toHaveValue(hasFake ? 'fake' : '');
    if (!hasFake) {
      await expect(page.locator('#model-select option:checked')).toHaveText('请选择评测模型');
      await expect(page.locator('#run-button')).toBeDisabled();
    }
    await page.locator('#model-select').selectOption(real.id);
    await page.getByRole('button', { name: '重新读取模型目录', exact: true }).click();
    await expect(page.locator('#model-select')).toHaveValue(real.id);
    await page.locator('#tab-experiment').click();
    await expect(page.locator('#exp-model-select')).toHaveValue(hasFake ? 'fake' : '');
    await expect(page.locator('.experiment-launch-summary')).toContainText('1 个任务');
    await expect(page.locator('#run-exp-button')).toContainText('2 次执行');
    await page.locator('.experiment-settings > summary').click();
    await expect(page.locator('#exp-global-token-budget')).toHaveValue('16000');
    await page.locator('#exp-global-token-budget').fill('12345');
    await page.locator('#exp-model-select').selectOption(real.id);
    await page.getByRole('button', { name: '重新读取模型目录', exact: true }).click();
    await expect(page.locator('#exp-model-select')).toHaveValue(real.id);
    await expect(page.locator('#exp-global-token-budget')).toHaveValue('12345');
    expect(mutations).toEqual([]);
  });
}

test('an explicit tested candidate stays selectable during discovery failure without claiming health', async ({ page, request }) => {
  const original = await (await request.get('/api/v1/meta')).json();
  const fake = original.models.find((model: { provider: string }) => model.provider === 'fake');
  await page.route('**/api/v1/meta', (route) => route.fulfill({ json: {
    ...original, model_catalog_status: 'unavailable', default_model: 'fake',
    models: [fake, { id: 'coding-glm-5.3-flash-free', name: 'GLM Flash tested candidate',
      provider: 'aihubmix', is_default: false, is_experimental: true, scenarios: [],
      notes: '当前目录未确认此 ID；仅依据带日期实测允许尝试。可用性以实际运行结果为准。' }],
  } }));
  const mutations: string[] = [];
  page.on('request', (reply) => { if (reply.url().includes('/api/') && reply.method() !== 'GET') mutations.push(reply.url()); });
  await page.goto('/?mode=single');
  await expect(page.getByText('模型目录暂不可用', { exact: true })).toBeVisible();
  await page.locator('#model-select').selectOption('coding-glm-5.3-flash-free');
  await page.locator('.model-note-disclosure > summary').click();
  await expect(page.getByText('当前目录未确认此 ID', { exact: false })).toBeVisible();
  await expect(page.locator('#run-button')).toBeEnabled();
  await expect(page.getByRole('button', { name: '重新读取模型目录', exact: true })).toBeVisible();
  expect(mutations).toEqual([]);
});

for (const failure of ['catalog', 'http']) {
  test(`metadata ${failure} failure can recover without execution or resetting the draft`, async ({ page, request }) => {
    const original = await (await request.get('/api/v1/meta')).json();
    const unavailable = { ...original, model_catalog_status: 'unavailable', default_model: 'fake',
      models: original.models.filter((model: { provider: string }) => model.provider === 'fake') };
    const restored = { ...original, model_catalog_status: 'live', default_model: 'coding-glm-5.3-free', models: [...original.models, { ...original.models[0], id: 'coding-glm-5.3-free', name: 'GLM test catalog entry', provider: 'aihubmix', is_default: true, scenarios: [] }] };
    let recover = false;
    let reads = 0;
    let releaseOld!: () => void;
    const oldRead = new Promise<void>((resolve) => { releaseOld = resolve; });
    await page.route('**/api/v1/meta', async (route) => {
      const isOld = ++reads === 1;
      if (isOld) await oldRead;
      if ((!recover || isOld) && failure === 'http') {
        await route.fulfill({ status: 503, json: { detail: 'Metadata service unavailable' } });
      } else {
        await route.fulfill({ json: !recover || isOld ? unavailable : restored });
      }
    });
    const mutations: string[] = [];
    page.on('request', (reply) => { if (reply.url().includes('/api/') && reply.method() !== 'GET') mutations.push(reply.url()); });
    await page.goto('/?mode=single');
    const retry = page.getByRole('button', { name: '重新读取模型目录', exact: true });
    await expect(retry).toBeVisible();
    if (failure === 'catalog') {
      await page.locator('.advanced-settings > summary').click();
      await page.getByLabel('步数上限 (Max Steps)').fill('4');
    }
    const initialReads = reads;
    recover = true;
    await retry.click();
    await expect(retry).toHaveCount(0);
    await expect(page.locator('#model-select option[value="coding-glm-5.3-free"]')).toHaveCount(1);
    if (failure === 'catalog') {
      await expect(page.locator('#model-select')).toHaveValue('fake');
      await expect(page.getByLabel('步数上限 (Max Steps)')).toHaveValue('4');
    } else {
      await expect(page.locator('#model-select')).toHaveValue('fake');
      await expect(page.locator('#run-button')).toBeEnabled();
    }
    const oldResponse = page.waitForResponse((reply) => reply.url().endsWith('/api/v1/meta'));
    releaseOld();
    await oldResponse;
    await expect(retry).toHaveCount(0);
    await expect(page.locator('#model-select option[value="coding-glm-5.3-free"]')).toHaveCount(1);
    expect(reads).toBe(initialReads + 1);
    expect(mutations).toEqual([]);
  });
}
