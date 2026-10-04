import { defineConfig } from '@playwright/test';
import { randomUUID } from 'node:crypto';

const runId = process.env.AGENTLABYRINTH_E2E_RUN_ID ?? randomUUID();
if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(runId)) {
  throw new Error('E2E run ID must be a generated UUID');
}
process.env.AGENTLABYRINTH_E2E_RUN_ID = runId;
const channel = process.env.AGENTLABYRINTH_E2E_CHANNEL ?? 'chromium';
if (!['chromium', 'chrome', 'msedge'].includes(channel)) throw new Error('Unsupported E2E browser channel');
export default defineConfig({
  testDir: './e2e', fullyParallel: false, workers: 1, retries: 0,
  timeout: 30_000, expect: { timeout: 10_000 },
  outputDir: `../../artifacts/playwright/${runId}/results`,
  reporter: [['list'], ['html', { outputFolder: '../../artifacts/playwright-report', open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:5173', browserName: 'chromium', channel,
    viewport: { width: 1440, height: 1000 }, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: [
    { command: `cd ../.. && uv --cache-dir .uv-cache run --locked python -m scripts.web_test_server --artifacts-dir artifacts/playwright/${runId}/api`,
      url: 'http://127.0.0.1:8000/api/v1/meta', reuseExistingServer: false, timeout: 60_000 },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort',
      url: 'http://127.0.0.1:5173', reuseExistingServer: false, timeout: 60_000 },
  ],
});
