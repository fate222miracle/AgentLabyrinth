export const episodeId = '10000000-0000-4000-8000-000000000001';
export const eventId = '10000000-0000-4000-8000-000000000002';
export const requestId = '10000000-0000-4000-8000-000000000003';
export const usage = () => ({ prompt_tokens: 0, completion_tokens: 0, simulated: true });
export const cost = () => ({ amount: '0', currency: 'USD', price_table_version: 'fake-zero-v1', is_known: false });
export const trace = () => ({ schema_version: '1.0', event_id: eventId, episode_id: episodeId,
  step_index: 0, event_type: 'EPISODE_STARTED', timestamp: '2026-10-03T00:00:00Z',
  duration_ms: 0, payload: {}, token_usage: usage(), estimated_cost: cost(), parent_event_id: null });
export const episodeResponse = () => ({ schema_version: '1.0', request_id: requestId, artifact: {
  schema_version: '1.0', task: { name: '订单状态', max_steps: 6, evaluator_config: {} },
  agent: { model: { model: 'fake-model', provider: 'fake' } }, run_config: {},
  episode: { episode_id: episodeId, termination_reason: 'SUCCESS', detail: 'submitted',
    step_count: 1, model_call_count: 1, tool_call_count: 1, duration_ms: 1,
    token_usage: usage(), estimated_cost: cost(), final_state: {} },
  evaluation: { success: true, reason: 'goal_met', metrics: {} }, events: [trace()],
} });
export const job = () => ({ schema_version: '1.0', experiment_id: episodeId, status: 'queued',
  requested_action: null, error_code: null, updated_at: '2026-10-03T00:00:00Z' });
