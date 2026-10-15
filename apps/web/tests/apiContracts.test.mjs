import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { dashboardSchema, episodeResponseSchema, experimentArtifactSchema, jobSchema,
  parseApi, requireIdentity, resumableIdsSchema, traceEventSchema } from '../src/apiContracts.ts';
import { readApi, readEpisode } from '../src/apiClient.ts';
import { episodeId, episodeResponse, job, trace } from './apiFixtures.mjs';

test('legacy unknown metrics stay unknown and extra provenance survives export', () => {
  const legacy = JSON.parse(readFileSync(new URL('../../../tests/fixtures/legacy_experiment.json', import.meta.url)));
  const parsed = parseApi(experimentArtifactSchema, legacy);
  assert.equal(parsed.metrics.retry_eligible_count, undefined);
  assert.equal(parsed.pairs[0].baseline_model_calls, undefined);
  assert.deepEqual(parsed.config, legacy.config);
  const response = episodeResponse();
  response.artifact.agent.model.version = 'preserved';
  assert.equal(parseApi(episodeResponseSchema, response).artifact.agent.model.version, 'preserved');
  assert.equal(parseApi(episodeResponseSchema, response).artifact.episode.estimated_cost.is_known, false);
});

for (const [name, corrupt] of [
  ['string success', (value) => { value.artifact.evaluation.success = 'true'; }],
  ['negative tokens', (value) => { value.artifact.episode.token_usage.prompt_tokens = -1; }],
  ['fractional duration', (value) => { value.artifact.events[0].duration_ms = 1.2; }],
  ['wrong event owner', (value) => { value.artifact.events[0].episode_id = '10000000-0000-4000-8000-000000000004'; }],
  ['duplicate event', (value) => { value.artifact.events.push(value.artifact.events[0]); }],
  ['unknown version', (value) => { value.artifact.schema_version = '9.0'; }],
  ['nondecimal cost', (value) => { value.artifact.episode.estimated_cost.amount = 'secret-not-a-number'; }],
  ['number cost', (value) => { value.artifact.episode.estimated_cost.amount = 0; }],
  ['nonUTC timestamp', (value) => { value.artifact.events[0].timestamp = '2026-10-03T08:00:00+08:00'; }],
]) {
  test(`bad Episode rejected: ${name}`, () => {
    const value = episodeResponse();
    corrupt(value);
    assert.throws(() => parseApi(episodeResponseSchema, value), (error) =>
      /接口数据校验失败/.test(error.message) && !error.message.includes('secret-not-a-number'));
  });
}

test('bad Job, lists, payloads and dashboard never masquerade as empty success', () => {
  assert.throws(() => parseApi(jobSchema, { ...job(), status: 'finished' }), /校验失败/);
  assert.throws(() => parseApi(resumableIdsSchema, ['not-an-id']), /校验失败/);
  assert.throws(() => parseApi(traceEventSchema, { ...trace(), payload: [] }), /校验失败/);
  assert.throws(() => parseApi(dashboardSchema, { schema_version: '1.1', items: {}, skipped_count: 0 }), /校验失败/);
});

test('duplicate pair ownership cannot reuse an Episode or leave an orphan result', () => {
  const legacy = JSON.parse(readFileSync(new URL('../../../tests/fixtures/legacy_experiment.json', import.meta.url)));
  legacy.pairs[0].recovery_episode_id = legacy.pairs[0].baseline_episode_id;
  assert.throws(() => parseApi(experimentArtifactSchema, legacy), /校验失败/);
});

test('global Token budget requires the new artifact revision and remains distinct from legacy', () => {
  const legacy = JSON.parse(readFileSync(new URL('../../../tests/fixtures/legacy_experiment.json', import.meta.url)));
  assert.equal(parseApi(experimentArtifactSchema, legacy).config.max_total_tokens, undefined);
  const current = { ...legacy, schema_version: '1.3', config: { ...legacy.config, max_total_tokens: 121 } };
  assert.equal(parseApi(experimentArtifactSchema, current).config.max_total_tokens, 121);
  for (const corrupt of [
    { ...current, schema_version: '1.2' },
    { ...current, config: { ...current.config, max_total_tokens: 0 } },
    { ...current, config: { ...current.config, max_total_tokens: '121' } },
  ]) assert.throws(() => parseApi(experimentArtifactSchema, corrupt), /校验失败/);
});

test('HTTP errors and wrong identity cannot populate a result', async () => {
  await assert.rejects(readApi(new Response('private raw upstream text', { status: 502 }), jobSchema), /^Error: 接口请求失败 \(502\)$/);
  await assert.rejects(readApi(new Response('{secret'), jobSchema), /JSON 无效/);
  await assert.rejects(readEpisode(new Response(JSON.stringify(episodeResponse())), '10000000-0000-4000-8000-000000000004'), /ID 与请求不一致/);
  requireIdentity(episodeId.toUpperCase(), episodeId);
});

test('versioned context policy survives read-only replay and malformed windows are rejected', () => {
  const value = episodeResponse();
  value.artifact.agent.schema_version = '1.2';
  value.artifact.agent.context_policy = { schema_version: '1.0', algorithm_version: 'tool-round-window-v1',
    mode: 'recent_tool_rounds', max_tool_rounds: 1 };
  assert.equal(parseApi(episodeResponseSchema, value).artifact.agent.context_policy.max_tool_rounds, 1);
  for (const mutate of [
    (agent) => { agent.schema_version = '1.1'; },
    (agent) => { agent.context_policy.max_tool_rounds = 0; },
    (agent) => { agent.context_policy.max_tool_rounds = '1'; },
    (agent) => { agent.context_policy.max_tool_rounds = null; },
    (agent) => { agent.context_policy.mode = 'full'; },
    (agent) => { agent.context_policy.algorithm_version = 'future'; },
  ]) {
    const corrupt = structuredClone(value);
    mutate(corrupt.artifact.agent);
    assert.throws(() => parseApi(episodeResponseSchema, corrupt), /校验失败/);
  }
});


test('context result validates policies, revision and inapplicable recovery metrics', () => {
  const legacy = JSON.parse(readFileSync(new URL('../../../tests/fixtures/legacy_experiment.json', import.meta.url)));
  legacy.schema_version = '1.4';
  legacy.config.comparison_axis = 'context_policy';
  legacy.config.baseline_agent = { runtime_backend: 'handwritten', runtime_strategy: 'handwritten', context_policy: {
    schema_version: '1.0', algorithm_version: 'tool-round-window-v1', mode: 'full', max_tool_rounds: null,
  } };
  legacy.config.recovery_agent = { ...legacy.config.baseline_agent, context_policy: {
    ...legacy.config.baseline_agent.context_policy, mode: 'recent_tool_rounds', max_tool_rounds: 1,
  } };
  for (const pair of legacy.pairs) { pair.retry_eligible = null; pair.recovered = false; }
  legacy.metrics.retry_eligible_count = null;
  legacy.metrics.retry_recovery_count = null;
  legacy.metrics.retry_recovery_rate = null;
  assert.equal(parseApi(experimentArtifactSchema, legacy).config.recovery_agent.context_policy.max_tool_rounds, 1);
  for (const corrupt of [
    (v) => { v.schema_version = '1.3'; },
    (v) => { v.config.recovery_agent.context_policy.max_tool_rounds = 0; },
    (v) => { v.config.recovery_agent.runtime_backend = 'langgraph'; },
    (v) => { v.metrics.retry_recovery_rate = 0; },
    (v) => { v.pairs[0].recovered = true; },
  ]) {
    const invalid = structuredClone(legacy); corrupt(invalid);
    assert.throws(() => parseApi(experimentArtifactSchema, invalid));
  }
});

test('bounded memory sub-version survives history and cannot silently become an old window', () => {
  const value = episodeResponse();
  value.artifact.agent.schema_version = '1.2';
  value.artifact.agent.context_policy = { schema_version: '1.1', algorithm_version: 'tool-round-window-memory-v1',
    mode: 'recent_tool_rounds', max_tool_rounds: 1, memory_max_bytes: 8192 };
  assert.equal(parseApi(episodeResponseSchema, value).artifact.agent.context_policy.memory_max_bytes, 8192);
  for (const change of [{ schema_version: '1.0' }, { algorithm_version: 'tool-round-window-v1' },
    { memory_max_bytes: 255 }, { memory_max_bytes: '8192' }, { memory_max_bytes: undefined }, { mode: 'full' }]) {
    const corrupt = structuredClone(value);
    Object.assign(corrupt.artifact.agent.context_policy, change);
    assert.throws(() => parseApi(episodeResponseSchema, corrupt), /校验失败/);
  }
});

test('memory ablation result requires revision 1.5, a same-window switch and no recovery metrics', () => {
  const legacy = JSON.parse(readFileSync(new URL('../../../tests/fixtures/legacy_experiment.json', import.meta.url)));
  legacy.schema_version = '1.5';
  legacy.config.comparison_axis = 'memory_ablation';
  legacy.config.baseline_agent = { runtime_backend: 'handwritten', runtime_strategy: 'handwritten',
    runtime_version: 'reference-v2', recovery_policy: 'none', context_policy: {
    schema_version: '1.0', algorithm_version: 'tool-round-window-v1', mode: 'recent_tool_rounds', max_tool_rounds: 1,
  } };
  legacy.config.recovery_agent = { ...legacy.config.baseline_agent, context_policy: {
    schema_version: '1.1', algorithm_version: 'tool-round-window-memory-v1', mode: 'recent_tool_rounds',
    max_tool_rounds: 1, memory_max_bytes: 8192,
  } };
  for (const pair of legacy.pairs) { pair.retry_eligible = null; pair.recovered = false; }
  legacy.metrics.retry_eligible_count = null;
  legacy.metrics.retry_recovery_count = null;
  legacy.metrics.retry_recovery_rate = null;
  const parsed = parseApi(experimentArtifactSchema, legacy);
  assert.equal(parsed.config.recovery_agent.context_policy.memory_max_bytes, 8192);
  assert.equal(parsed.config.baseline_agent.context_policy.memory_max_bytes, undefined);
  for (const corrupt of [
    (v) => { v.schema_version = '1.4'; },
    (v) => { v.config.comparison_axis = 'recovery_policy'; },
    (v) => { delete v.config.comparison_axis; },
    (v) => { v.config.baseline_agent.context_policy = structuredClone(v.config.recovery_agent.context_policy); },
    (v) => { v.config.recovery_agent.context_policy.memory_max_bytes = undefined; },
    (v) => { v.config.recovery_agent.context_policy.max_tool_rounds = 2; },
    (v) => { v.config.recovery_agent.runtime_backend = 'langgraph'; },
    (v) => { v.config.recovery_agent.runtime_version = 'changed'; },
    (v) => { v.config.baseline_agent.runtime_version = ''; v.config.recovery_agent.runtime_version = ''; },
    (v) => { v.config.recovery_agent.recovery_policy = 'invalid_arguments_once'; },
    (v) => { v.config.baseline_agent.recovery_policy = 'invalid_arguments_once'; v.config.recovery_agent.recovery_policy = 'invalid_arguments_once'; },
    (v) => { delete v.config.baseline_agent.runtime_backend; delete v.config.recovery_agent.runtime_backend; },
    (v) => { v.metrics.retry_recovery_rate = 0; },
    (v) => { v.pairs[0].recovered = true; },
  ]) {
    const invalid = structuredClone(legacy); corrupt(invalid);
    assert.throws(() => parseApi(experimentArtifactSchema, invalid));
  }
});
