import assert from 'node:assert/strict';
import test from 'node:test';
import { changedStateFields, groupTraceByStep, keyFields, stepOutcome, stepTitle } from '../src/traceSteps.ts';

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
