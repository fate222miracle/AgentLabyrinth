import { expect, test } from '@playwright/test';

test('verify the Web API proxy targets this isolated test server before browser tests', async ({
  request,
}) => {
  const runId = process.env.AGENTLABYRINTH_E2E_RUN_ID;
  if (!runId) throw new Error('Playwright E2E run ID was not configured');

  const response = await request.get('/api/v1/meta');
  expect(response.ok()).toBeTruthy();
  expect(response.headers()['x-agentlabyrinth-test-run-id']).toBe(runId);
});
