import assert from 'node:assert/strict';
import test from 'node:test';
import { comparableHistory, summarizeEpisode } from '../src/historySummary.ts';

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

test('comparable history excludes old and mismatched records and sorts without mutating input', () => {
  const items = [
    { experiment_id: 'old', created_at: '2026-09-28T00:00:00Z', comparison_key: 'same' },
    { experiment_id: 'legacy', created_at: '2026-09-30T00:00:00Z' },
    { experiment_id: 'different', created_at: '2026-09-30T00:00:00Z', comparison_key: 'other' },
    { experiment_id: 'new', created_at: '2026-09-29T00:00:00Z', comparison_key: 'same' },
    { experiment_id: 'invalid-date', created_at: 'invalid', comparison_key: 'same' },
  ];
  assert.deepEqual(comparableHistory(items, 'same').map((item) => item.experiment_id), ['new', 'old']);
  assert.equal(items[0].experiment_id, 'old');
  assert.deepEqual(comparableHistory(items, ''), []);
});
