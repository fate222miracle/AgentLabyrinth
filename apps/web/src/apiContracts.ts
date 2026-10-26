import * as z from 'zod/mini';

// Consumer projections of existing Pydantic contracts. Keep unused fields for export.
const count = z.int().check(z.nonnegative());
const nonnegative = z.number().check(z.nonnegative());
const rate = z.number().check(z.minimum(0), z.maximum(1));
const uuid = z.uuid();
const utc = z.iso.datetime({ offset: true }).check(z.regex(/(?:Z|\+00:00)$/));
const decimal = z.string().check(z.regex(/^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/));
const record = z.record(z.string(), z.unknown());
const hash = z.string().check(z.regex(/^[a-f0-9]{64}$/));
const modelConfig = z.looseObject({ provider: z.string(), model: z.string(),
  schema_version: z.optional(z.enum(['1.0', '1.1'])),
  tool_call_mode: z.optional(z.enum(['single', 'serial'])),
}).check(z.refine(value => (value.tool_call_mode !== undefined) === (value.schema_version === '1.1'), 'tool call mode revision mismatch'));
const termination = z.enum(['SUCCESS', 'FAILED', 'MAX_STEPS', 'TOKEN_BUDGET_EXCEEDED',
  'COST_BUDGET_EXCEEDED', 'RUNTIME_ERROR', 'TIME_BUDGET_EXCEEDED']);
const runtimeFields = {
  runtime_backend: z.optional(z.enum(['handwritten', 'langgraph', 'pydantic_ai'])),
  runtime_strategy: z.optional(z.enum(['handwritten', 'handwritten_recovery'])),
  runtime_version: z.optional(z.string()),
};
const contextPolicy = z.looseObject({
  schema_version: z.enum(['1.0', '1.1']), algorithm_version: z.enum(['tool-round-window-v1', 'tool-round-window-memory-v1']),
  mode: z.enum(['full', 'recent_tool_rounds']),
  max_tool_rounds: z.nullable(z.int().check(z.minimum(1), z.maximum(100))),
  memory_max_bytes: z.optional(z.int().check(z.minimum(256), z.maximum(32768))),
}).check(z.refine((value) => (value.mode === 'recent_tool_rounds') === (value.max_tool_rounds !== null),
  'context window mismatch'), z.refine((value) => value.memory_max_bytes !== undefined
    ? value.schema_version === '1.1' && value.algorithm_version === 'tool-round-window-memory-v1' && value.mode === 'recent_tool_rounds'
    : value.schema_version === '1.0' && value.algorithm_version === 'tool-round-window-v1', 'memory revision mismatch'));
const planningConfig = z.looseObject({
  schema_version: z.literal('1.0'), algorithm_version: z.literal('plan-update-v1'),
});
const usage = z.looseObject({ prompt_tokens: count, completion_tokens: count, simulated: z.boolean() });
const cost = z.looseObject({ amount: decimal, currency: z.literal('USD'),
  price_table_version: z.string(), is_known: z.boolean() });

export const metaSchema = z.looseObject({
  schema_version: z.literal('1.0'), request_id: uuid,
  models: z.array(z.looseObject({ id: z.string(), name: z.string(),
    provider: z.enum(['fake', 'aihubmix']), is_default: z.boolean(),
    is_experimental: z.boolean(), notes: z.string(), scenarios: z.array(z.string()) })),
  tasks: z.array(z.looseObject({ id: z.string(), name: z.string(), category: z.string(),
    description: z.string(), max_steps: count, token_budget: count,
    suite: z.enum(['tool_lab_core', 'bfcl_adapted', 'bfcl_java_adapted']),
    split: z.string(), supports_mcp: z.boolean(), supports_planning: z.optional(z.boolean()) })),
  default_model: z.string(), default_task: z.string(),
  model_catalog_status: z.enum(['live', 'unavailable', 'static']),
}).check(z.refine((value) => value.models.some((model) => model.id === value.default_model)
  && value.tasks.some((task) => task.id === value.default_task), 'metadata defaults unavailable'));

export const traceEventSchema = z.looseObject({
  schema_version: z.literal('1.0'), event_id: uuid, episode_id: uuid, step_index: count,
  event_type: z.enum(['EPISODE_STARTED', 'EPISODE_RESUMED', 'OBSERVATION_CREATED',
    'MODEL_REQUESTED', 'MODEL_RESPONDED', 'TOOL_CALL_PROPOSED', 'TOOL_CALL_VALIDATED',
    'TOOL_STARTED', 'TOOL_SUCCEEDED', 'TOOL_FAILED', 'ENVIRONMENT_UPDATED', 'PLAN_UPDATED', 'EPISODE_FINISHED']),
  timestamp: utc, duration_ms: count, payload: record, token_usage: usage,
  estimated_cost: cost, parent_event_id: z.optional(z.nullable(uuid)),
});

export const episodeArtifactSchema = z.looseObject({
  schema_version: z.enum(['1.0', '1.1']),
  task: z.looseObject({ name: z.string(), max_steps: count, evaluator_config: record }),
  episode: z.looseObject({ episode_id: uuid, termination_reason: termination, detail: z.string(),
    step_count: count, model_call_count: count, tool_call_count: count, duration_ms: count,
    token_usage: usage, estimated_cost: cost, final_state: record }),
  evaluation: z.looseObject({ success: z.boolean(), reason: z.string(), metrics: record }),
  run_config: z.looseObject({ runtime_version: z.nullish(z.string()), environment_version: z.optional(z.string()) }),
  agent: z.looseObject({ name: z.optional(z.string()), ...runtimeFields,
    schema_version: z.optional(z.enum(['1.0', '1.1', '1.2', '1.3', '1.4'])),
    context_policy: z.nullish(contextPolicy),
    planning: z.nullish(planningConfig),
    budget: z.optional(z.looseObject({ max_execution_time_ms: z.optional(count) })),
    model: modelConfig }),
  events: z.array(traceEventSchema), reference_cost: z.nullish(cost),
}).check(z.superRefine((value, ctx) => {
  if (value.agent.context_policy != null && !['1.2', '1.3', '1.4'].includes(value.agent.schema_version ?? '')) {
    ctx.addIssue({ code: 'custom', path: ['agent', 'schema_version'], message: 'context revision mismatch' });
  }
  if (value.agent.planning != null && !['1.3', '1.4'].includes(value.agent.schema_version ?? '')) {
    ctx.addIssue({ code: 'custom', path: ['agent', 'schema_version'], message: 'planning revision mismatch' });
  }
  if (value.agent.runtime_backend === 'pydantic_ai' && value.agent.schema_version !== '1.4') {
    ctx.addIssue({ code: 'custom', path: ['agent', 'schema_version'], message: 'third runtime revision mismatch' });
  }
  const ids = new Set<string>();
  for (const [index, event] of value.events.entries()) {
    if (event.episode_id !== value.episode.episode_id || ids.has(event.event_id)) {
      ctx.addIssue({ code: 'custom', path: ['events', index, 'episode_id'], message: 'trace identity mismatch' });
    }
    ids.add(event.event_id);
  }
}));

const armPairFields = {
  episode_id: uuid, success: z.boolean(), termination_reason: termination,
  steps: count, tokens: count, duration_ms: count, cost: z.nullish(decimal),
  reference_cost: z.nullish(decimal), model_calls: z.nullish(count), tool_calls: z.nullish(count),
  tool_selection_accuracy: z.nullish(rate), tool_argument_validity_rate: z.nullish(rate),
};
const armMetricFields = {
  success_count: count, success_rate: rate, total_tokens: count, avg_steps: nonnegative,
  avg_model_calls: z.nullish(nonnegative), avg_tool_calls: z.nullish(nonnegative),
  tool_selection_accuracy: z.nullish(rate), tool_argument_validity_rate: z.nullish(rate),
  avg_duration_ms: nonnegative, total_cost: z.nullish(decimal), total_reference_cost: z.nullish(decimal),
};
// Explicit prefixes keep inference exact without unsafe dynamic-key type assertions.
const pairSchema = z.looseObject({
  task_id: z.string(), task_name: z.string(), seed: z.int(), repeat_index: z.optional(count),
  baseline_episode_id: armPairFields.episode_id, baseline_success: armPairFields.success,
  baseline_termination_reason: armPairFields.termination_reason, baseline_steps: armPairFields.steps,
  baseline_tokens: armPairFields.tokens, baseline_duration_ms: armPairFields.duration_ms,
  baseline_cost: armPairFields.cost, baseline_reference_cost: armPairFields.reference_cost,
  baseline_model_calls: armPairFields.model_calls, baseline_tool_calls: armPairFields.tool_calls,
  baseline_tool_selection_accuracy: armPairFields.tool_selection_accuracy,
  baseline_tool_argument_validity_rate: armPairFields.tool_argument_validity_rate,
  recovery_episode_id: armPairFields.episode_id, recovery_success: armPairFields.success,
  recovery_termination_reason: armPairFields.termination_reason, recovery_steps: armPairFields.steps,
  recovery_tokens: armPairFields.tokens, recovery_duration_ms: armPairFields.duration_ms,
  recovery_cost: armPairFields.cost, recovery_reference_cost: armPairFields.reference_cost,
  recovery_model_calls: armPairFields.model_calls, recovery_tool_calls: armPairFields.tool_calls,
  recovery_tool_selection_accuracy: armPairFields.tool_selection_accuracy,
  recovery_tool_argument_validity_rate: armPairFields.tool_argument_validity_rate,
  retry_eligible: z.nullish(z.boolean()), recovered: z.boolean(),
});
const metricsSchema = z.looseObject({
  total_pairs: count, retry_eligible_count: z.nullish(count), retry_recovery_count: z.nullish(count),
  retry_recovery_rate: z.nullish(rate), is_cost_known: z.boolean(), is_reference_cost_known: z.optional(z.boolean()),
  baseline_success_count: armMetricFields.success_count, baseline_success_rate: armMetricFields.success_rate,
  baseline_total_tokens: armMetricFields.total_tokens, baseline_avg_steps: armMetricFields.avg_steps,
  baseline_avg_model_calls: armMetricFields.avg_model_calls, baseline_avg_tool_calls: armMetricFields.avg_tool_calls,
  baseline_tool_selection_accuracy: armMetricFields.tool_selection_accuracy,
  baseline_tool_argument_validity_rate: armMetricFields.tool_argument_validity_rate,
  baseline_avg_duration_ms: armMetricFields.avg_duration_ms, baseline_total_cost: armMetricFields.total_cost,
  baseline_total_reference_cost: armMetricFields.total_reference_cost,
  recovery_success_count: armMetricFields.success_count, recovery_success_rate: armMetricFields.success_rate,
  recovery_total_tokens: armMetricFields.total_tokens, recovery_avg_steps: armMetricFields.avg_steps,
  recovery_avg_model_calls: armMetricFields.avg_model_calls, recovery_avg_tool_calls: armMetricFields.avg_tool_calls,
  recovery_tool_selection_accuracy: armMetricFields.tool_selection_accuracy,
  recovery_tool_argument_validity_rate: armMetricFields.tool_argument_validity_rate,
  recovery_avg_duration_ms: armMetricFields.avg_duration_ms, recovery_total_cost: armMetricFields.total_cost,
  recovery_total_reference_cost: armMetricFields.total_reference_cost,
});
const experimentConfig = z.looseObject({
  comparison_axis: z.optional(z.enum(['recovery_policy', 'runtime_backend', 'context_policy', 'memory_ablation', 'planning'])),
  model: z.optional(z.union([z.string(), z.looseObject({ model: z.string(),
    schema_version: z.optional(z.enum(['1.0', '1.1'])), tool_call_mode: z.optional(z.enum(['single', 'serial'])),
  }).check(z.refine(value => (value.tool_call_mode !== undefined) === (value.schema_version === '1.1'), 'tool call mode revision mismatch'))])),
  provider: z.optional(z.string()), scenario: z.optional(z.nullable(z.string())),
  seeds: z.optional(z.array(z.int())), seed: z.optional(z.int()),
  repeat_count: z.optional(count), task_ids: z.optional(z.array(z.string())), evaluator: z.optional(z.string()),
  max_total_tokens: z.optional(z.int().check(z.minimum(1), z.maximum(1_000_000_000))),
  budget: z.optional(z.looseObject({ max_execution_time_ms: z.optional(count) })),
  baseline_agent: z.optional(z.looseObject({ ...runtimeFields, context_policy: z.nullish(contextPolicy), planning: z.nullish(planningConfig) })), recovery_agent: z.optional(z.looseObject({ ...runtimeFields, context_policy: z.nullish(contextPolicy), planning: z.nullish(planningConfig) })),
});
export const experimentArtifactSchema = z.looseObject({
  schema_version: z.enum(['1.0', '1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7']), experiment_id: uuid, created_at: utc,
  config: experimentConfig, config_hash: hash, episode_ids: z.array(uuid),
  pairs: z.array(pairSchema), metrics: metricsSchema,
}).check(z.refine((value) => (value.config.max_total_tokens == null || ['1.3', '1.4', '1.5', '1.6', '1.7'].includes(value.schema_version))
  && (value.schema_version !== '1.7' || value.config.comparison_axis === 'runtime_backend')
  && (value.schema_version !== '1.5' || value.config.comparison_axis === 'memory_ablation')
  && (value.schema_version !== '1.6' || value.config.comparison_axis === 'planning')
  && (value.config.comparison_axis !== 'planning' || (value.schema_version === '1.6'
    && value.config.baseline_agent?.planning == null && value.config.recovery_agent?.planning != null
    && value.config.baseline_agent?.context_policy?.mode === 'full'
    && value.config.recovery_agent?.context_policy?.mode === 'full'
    && value.config.baseline_agent.context_policy.mode === value.config.recovery_agent.context_policy.mode
    && value.config.baseline_agent.runtime_backend === value.config.recovery_agent.runtime_backend
    && value.config.baseline_agent.runtime_strategy === value.config.recovery_agent.runtime_strategy
    && value.config.baseline_agent.runtime_backend != null && value.config.baseline_agent.runtime_strategy != null
    && typeof value.config.baseline_agent.runtime_version === 'string' && value.config.baseline_agent.runtime_version.length > 0
    && value.config.baseline_agent.runtime_version === value.config.recovery_agent.runtime_version
    && value.config.baseline_agent.recovery_policy === (value.config.baseline_agent.runtime_strategy === 'handwritten_recovery' ? 'invalid_arguments_once' : 'none')
    && value.config.baseline_agent.recovery_policy === value.config.recovery_agent.recovery_policy
    && value.metrics.retry_eligible_count == null && value.metrics.retry_recovery_count == null
    && value.metrics.retry_recovery_rate == null
    && value.pairs.every((pair) => pair.retry_eligible == null && !pair.recovered)))
  && (value.config.comparison_axis !== 'context_policy' || (value.schema_version === '1.4'
    && value.config.baseline_agent?.context_policy?.mode === 'full'
    && value.config.recovery_agent?.context_policy?.mode === 'recent_tool_rounds'
    && value.config.baseline_agent.runtime_backend === value.config.recovery_agent.runtime_backend
    && value.config.baseline_agent.runtime_strategy === value.config.recovery_agent.runtime_strategy
    && value.metrics.retry_eligible_count == null && value.metrics.retry_recovery_count == null
    && value.metrics.retry_recovery_rate == null
    && value.pairs.every((pair) => pair.retry_eligible == null && !pair.recovered)))
  && (value.config.comparison_axis !== 'memory_ablation' || (value.schema_version === '1.5'
    && value.config.baseline_agent?.context_policy?.mode === 'recent_tool_rounds'
    && value.config.baseline_agent.context_policy.memory_max_bytes == null
    && value.config.recovery_agent?.context_policy?.mode === 'recent_tool_rounds'
    && value.config.recovery_agent.context_policy.memory_max_bytes != null
    && value.config.baseline_agent.context_policy.max_tool_rounds === value.config.recovery_agent.context_policy.max_tool_rounds
    && value.config.baseline_agent.runtime_backend === value.config.recovery_agent.runtime_backend
    && value.config.baseline_agent.runtime_strategy === value.config.recovery_agent.runtime_strategy
    && value.config.baseline_agent.runtime_backend != null
    && value.config.baseline_agent.runtime_strategy != null
    && typeof value.config.baseline_agent.runtime_version === 'string'
    && value.config.baseline_agent.runtime_version.length > 0
    && value.config.baseline_agent.runtime_version === value.config.recovery_agent.runtime_version
    && value.config.baseline_agent.recovery_policy === (value.config.baseline_agent.runtime_strategy === 'handwritten_recovery'
      ? 'invalid_arguments_once' : 'none')
    && value.config.baseline_agent.recovery_policy === value.config.recovery_agent.recovery_policy
    && value.metrics.retry_eligible_count == null && value.metrics.retry_recovery_count == null
    && value.metrics.retry_recovery_rate == null
    && value.pairs.every((pair) => pair.retry_eligible == null && !pair.recovered)))
  && value.pairs.length === value.metrics.total_pairs
  && value.episode_ids.length === value.pairs.length * 2
  && new Set(value.episode_ids).size === value.episode_ids.length
  && new Set(value.pairs.flatMap((pair) => [pair.baseline_episode_id, pair.recovery_episode_id])).size
    === value.episode_ids.length
  && value.pairs.every((pair) => value.episode_ids.includes(pair.baseline_episode_id)
    && value.episode_ids.includes(pair.recovery_episode_id)), 'experiment pair identity mismatch'));

const envelope = { schema_version: z.literal('1.0'), request_id: uuid };
export const episodeResponseSchema = z.looseObject({ ...envelope, artifact: episodeArtifactSchema });
export const experimentResponseSchema = z.looseObject({ ...envelope, experiment: experimentArtifactSchema });
export const episodeReviewSchema = z.looseObject({
  schema_version: z.literal('1.0'), review_id: uuid, episode_id: uuid,
  episode_content_hash: hash, review_input_hash: hash, created_at: utc,
  method: z.enum(['human', 'llm_judge']), rubric_version: z.literal('tool-lab-review-v1'),
  status: z.enum(['completed', 'failed']), verdict: z.nullable(z.enum(['pass', 'fail', 'uncertain'])),
  answer_correctness: z.nullable(z.enum(['pass', 'fail', 'unknown'])),
  evidence_support: z.nullable(z.enum(['pass', 'fail', 'unknown'])),
  process_safety: z.nullable(z.enum(['pass', 'fail', 'unknown'])),
  rationale: z.nullable(z.string()), event_ids: z.array(uuid), reviewer_label: z.nullable(z.string()),
  provider: z.nullable(z.enum(['fake', 'aihubmix'])), model: z.nullable(z.string()),
  prompt_version: z.nullable(z.enum(['episode-review-v1', 'episode-review-v2'])), token_usage: z.nullable(usage),
  estimated_cost: z.nullable(cost),
  failure_code: z.nullable(z.enum(['JUDGE_PROVIDER_ERROR', 'INVALID_JUDGE_OUTPUT', 'INVALID_EVENT_REFERENCE'])),
}).check(z.refine((value) => {
  const completed = value.verdict !== null && value.answer_correctness !== null
    && value.evidence_support !== null && value.process_safety !== null && value.rationale !== null;
  const attribution = value.method === 'human'
    ? value.reviewer_label !== null && value.provider === null && value.model === null && value.prompt_version === null
    : value.reviewer_label === null && value.provider !== null && value.model !== null && value.prompt_version !== null;
  return attribution && (value.status === 'completed'
    ? completed && value.failure_code === null
    : !completed && value.failure_code !== null);
}, 'review status or attribution mismatch'));
export const episodeReviewResponseSchema = z.looseObject({ ...envelope, review: episodeReviewSchema });
export const episodeReviewListResponseSchema = z.looseObject({
  ...envelope, episode_id: uuid, reviews: z.array(episodeReviewSchema),
});
export const jobSchema = z.looseObject({ schema_version: z.literal('1.0'), experiment_id: uuid,
  status: z.enum(['queued', 'running', 'paused', 'cancelled', 'completed', 'failed', 'interrupted']),
  requested_action: z.nullable(z.enum(['pause', 'cancel'])), error_code: z.nullable(z.string()), updated_at: utc });
export const resumableIdsSchema = z.array(uuid);
export const dashboardItemSchema = z.looseObject({ experiment_id: uuid, created_at: utc,
  environment_version: z.string(), comparison_axis: z.string(), total_pairs: count,
  baseline_success_rate: rate, recovery_success_rate: rate,
  baseline_total_tokens: count, recovery_total_tokens: count,
  baseline_avg_duration_ms: nonnegative, recovery_avg_duration_ms: nonnegative,
  baseline_total_cost: z.nullable(decimal), recovery_total_cost: z.nullable(decimal),
  model_id: z.nullish(z.string()), provider: z.nullish(z.string()), task_ids: z.optional(z.array(z.string())),
  seeds: z.optional(z.array(z.int())), repeat_count: z.nullish(count), scenario: z.nullish(z.string()),
  fault_profile: z.nullish(z.string()), comparison_key: z.nullish(hash),
  baseline_reference_cost: z.nullish(decimal), recovery_reference_cost: z.nullish(decimal),
  reference_price_version: z.nullish(z.string()),
  recovery_backend: z.nullish(z.enum(['handwritten', 'langgraph', 'pydantic_ai'])),
});
export const dashboardSchema = z.looseObject({ schema_version: z.enum(['1.0', '1.1']),
  items: z.array(dashboardItemSchema), skipped_count: count });
export const errorSchema = z.object({ ...envelope, error_code: z.string(), message: z.string() });

/** Reject invalid data without echoing sensitive response values. */
export function parseApi<T>(schema: z.ZodMiniType<T>, value: unknown): T {
  const result = schema.safeParse(value);
  if (!result.success) {
    const path = result.error.issues[0]?.path.join('.') || 'response';
    throw new Error(`接口数据校验失败 (${path})，请检查服务版本或重新读取。`);
  }
  return result.data;
}

/** Check route identity separately from response shape before updating state. */
export function requireIdentity(actual: string, expected: string): void {
  if (actual.toLowerCase() !== expected.trim().toLowerCase()) throw new Error('接口返回的结果 ID 与请求不一致。');
}

export type ModelOption = z.infer<typeof metaSchema>['models'][number];
export type TaskOption = z.infer<typeof metaSchema>['tasks'][number];
export type MetaResponse = z.infer<typeof metaSchema>;
export type TraceEvent = z.infer<typeof traceEventSchema>;
export type EpisodeArtifact = z.infer<typeof episodeArtifactSchema>;
export type EpisodeReview = z.infer<typeof episodeReviewSchema>;
export type ExperimentArtifact = z.infer<typeof experimentArtifactSchema>;
export type PairComparison = z.infer<typeof pairSchema>;
export type ExperimentJobState = z.infer<typeof jobSchema>;
export type ExperimentDashboardItem = z.infer<typeof dashboardItemSchema>;
