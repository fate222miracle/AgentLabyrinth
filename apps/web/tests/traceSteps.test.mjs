import assert from 'node:assert/strict';
import test from 'node:test';
import { changedStateFields, groupTraceByStep, keyFields, stepOutcome, stepTitle, toolFeedbackFields, latestDeclaredPlan } from '../src/traceSteps.ts';

test('A declaration follows the arrived prefix and never uses a proposed or future plan', () => {
  const events = [
    { event_type: 'TOOL_CALL_PROPOSED', step_index: 1, payload: { name: 'update_plan', arguments: { plan: [{ id: 'future' }] } } },
    { event_type: 'PLAN_UPDATED', step_index: 1, payload: { items: [{ id: 'first', status: 'pending' }] } },
    { event_type: 'PLAN_UPDATED', step_index: 3, payload: { items: [{ id: 'later', status: 'done' }] } },
  ];
  assert.equal(latestDeclaredPlan(events, 0), undefined);
  assert.equal(latestDeclaredPlan(events, 1)?.payload.items[0].id, 'first');
  assert.equal(latestDeclaredPlan(events, 2)?.payload.items[0].id, 'later');
});

test('Search feedback shows recorded matching and guidance without inventing legacy fields', () => {
  const event = result => ({ step_index: 1, event_type: 'TOOL_SUCCEEDED', payload: { observation: { result } } });
  assert.deepEqual(toolFeedbackFields(event({ documents: [], search_mode: 'none', hint: '使用原文片段' }), 'search_documents'),
    [['documents', []], ['search_mode', '无匹配'], ['hint', '使用原文片段']]);
  assert.deepEqual(toolFeedbackFields(event({ documents: [] }), 'search_documents'), [['documents', []]]);
  assert.equal(toolFeedbackFields(event({ documents: [{ document_id: 'INSPECTION' }], search_mode: 'exact_id' }), 'search_documents')[1][1], '文档 ID 精确匹配');
  assert.deepEqual(toolFeedbackFields(undefined, 'search_documents'), []);
});

test('A model round with several calls has an explicit multi-tool title', () => {
  assert.equal(stepTitle([
    { step_index: 3, event_type: 'TOOL_CALL_PROPOSED', payload: { name: 'read_document', call_id: 'a' } },
    { step_index: 3, event_type: 'TOOL_CALL_PROPOSED', payload: { name: 'read_document', call_id: 'b' } },
  ]), '多工具调用 · 2 个');
});

test('Replay groups saved actions and reports observed failures', () => {
  const events = [
    { step_index: 0, event_type: 'OBSERVATION_CREATED', payload: {} },
    { step_index: 1, event_type: 'TOOL_CALL_PROPOSED', payload: { name: 'read_document' } },
    { step_index: 1, event_type: 'TOOL_CALL_VALIDATED', payload: { arguments_valid: false } },
    { step_index: 2, event_type: 'TOOL_CALL_PROPOSED', payload: { name: 'read_document' } },
    { step_index: 2, event_type: 'TOOL_SUCCEEDED', payload: { observation: { id: 'DOC-007' } } },
  ];
  const steps = groupTraceByStep(events);
  assert.deepEqual(steps.map((group) => group.events.length), [1, 2, 2]);
  assert.equal(stepTitle(steps[1].events), 'read_document');
  assert.equal(stepOutcome(steps[1].events), '参数错误');
  assert.equal(stepOutcome(steps[2].events), '工具成功');
  assert.equal(groupTraceByStep([]).length, 0);
});

test('Replay reports only changes present in saved snapshots', () => {
  const initial = { orders: [{ status: 'shipped' }], acquired_evidence: [], done: false };
  const afterError = { ...initial };
  const afterQuery = { ...initial, acquired_evidence: ['order:ORD-001'] };
  assert.deepEqual(changedStateFields(initial, afterError), []);
  assert.deepEqual(changedStateFields(afterError, afterQuery), [['acquired_evidence', ['order:ORD-001']]]);
  assert.deepEqual(changedStateFields(null, afterQuery), []);
});

test('Replay selects decisive saved fields, including MCP tool failure', () => {
  const error = { schema_version: '1.0', code: 'TOOL_EXECUTION_ERROR', message: 'Tool execution failed.', retryable: false };
  assert.deepEqual(keyFields(error, ['code', 'message', 'retryable']), [
    ['code', 'TOOL_EXECUTION_ERROR'], ['message', 'Tool execution failed.'], ['retryable', false],
  ]);
  assert.deepEqual(keyFields({ feedback: 'Answer submitted.', submission: { answer: 'shipped' } }, ['feedback']),
    [['feedback', 'Answer submitted.']]);
  assert.equal(stepOutcome([
    { step_index: 2, event_type: 'TOOL_SUCCEEDED', payload: {} },
    { step_index: 2, event_type: 'EPISODE_FINISHED', payload: { success: false, termination_reason: 'FAILED' } },
  ]), 'FAILED');
});

test('Replay never labels rejected or failed actions as successful', () => {
  for (const [code, arguments_valid, permitted, expected] of [
    ['INVALID_ARGUMENTS', false, true, '参数错误'],
    ['UNKNOWN_TOOL', true, true, '未知工具'],
    ['FORBIDDEN_TOOL', true, false, '禁止工具'],
  ]) {
    assert.equal(stepOutcome([
      { step_index: 1, event_type: 'TOOL_CALL_VALIDATED', payload: { error_code: code, arguments_valid, permitted } },
      { step_index: 1, event_type: 'EPISODE_FINISHED', payload: { success: false, termination_reason: 'FAILED' } },
    ]), expected);
  }
  assert.equal(stepOutcome([
    { step_index: 1, event_type: 'TOOL_FAILED', payload: { error: { code: 'TOOL_TIMEOUT' } } },
    { step_index: 1, event_type: 'EPISODE_FINISHED', payload: { success: false } },
  ]), '工具失败');
  assert.equal(stepOutcome([
    { step_index: 1, event_type: 'EPISODE_FINISHED', payload: { success: false, termination_reason: 'MAX_STEPS' } },
  ]), 'MAX_STEPS');
});
