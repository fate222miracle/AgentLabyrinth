import assert from 'node:assert/strict';
import test from 'node:test';
import { comparableHistory, savedUsage, summarizeEpisode } from '../src/historySummary.ts';
import { episodeResponse, trace } from './apiFixtures.mjs';

test('saved usage distinguishes reported fragments, missing usage and reconciled zero', () => {
  const artifact = episodeResponse().artifact;
  const event = (event_type, prompt_tokens = 0, completion_tokens = 0) => ({
    ...trace(), event_type, token_usage: { prompt_tokens, completion_tokens, simulated: false },
  });
  artifact.episode.model_call_count = 2;
  artifact.episode.token_usage = { prompt_tokens: 3280, completion_tokens: 84, simulated: false };
  artifact.events = [event('EPISODE_STARTED'), event('MODEL_REQUESTED'), event('MODEL_RESPONDED', 3280, 84),
    event('MODEL_REQUESTED'), event('EPISODE_FINISHED')];
  const saved = JSON.stringify(artifact);
  assert.deepEqual(savedUsage(artifact), { complete: false, reportedTotal: 3364 });
  assert.equal(JSON.stringify(artifact), saved);
  artifact.events.splice(3, 1);
  artifact.episode.model_call_count = 1;
  assert.deepEqual(savedUsage(artifact), { complete: true, reportedTotal: 3364 });
  artifact.events[2].token_usage = { prompt_tokens: 84, completion_tokens: 3280, simulated: false };
  assert.equal(savedUsage(artifact).complete, false);
  artifact.episode.token_usage = { prompt_tokens: 0, completion_tokens: 0, simulated: false };
  artifact.events.splice(2, 1);
  assert.deepEqual(savedUsage(artifact), { complete: false, reportedTotal: null });
  artifact.events.splice(1, 1);
  artifact.episode.model_call_count = 0;
  assert.deepEqual(savedUsage(artifact), { complete: true, reportedTotal: 0 });
  artifact.events = [];
  assert.deepEqual(savedUsage(artifact), { complete: false, reportedTotal: null });
});

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
