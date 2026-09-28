import assert from 'node:assert/strict';
import test from 'node:test';
import { summarizeEpisode } from '../src/historySummary.ts';

test('history summary keeps partial artifacts neutral and preserves explicit failure', () => {
  assert.deepEqual(summarizeEpisode({}), {
    status: 'ready', taskName: '任务未记录', modelId: '模型未记录',
    timestamp: undefined, success: undefined,
  });
  assert.deepEqual(summarizeEpisode({ task: { name: 'order-status-001' }, evaluation: { success: false } }), {
    status: 'ready', taskName: 'order-status-001', modelId: '模型未记录',
    timestamp: undefined, success: false,
  });
});
