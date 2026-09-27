import assert from 'node:assert/strict';
import test from 'node:test';
import { flowFrames } from '../src/flowFrames.ts';

const event = (event_type, payload, step_index = 1) => ({ event_type, payload, step_index });
test('MCP beats preserve recorded order and distinguish local submission', () => {
  const frames = flowFrames([
    event('TOOL_CALL_PROPOSED', {call_id:'a', name:'search_documents'}),
    event('TOOL_STARTED', {call_id:'a', name:'search_documents', transport:'mcp'}),
    event('TOOL_SUCCEEDED', {call_id:'a', observation:{documents:[]}}),
    event('TOOL_CALL_PROPOSED', {call_id:'b', name:'submit_answer'}, 2),
    event('TOOL_STARTED', {call_id:'b', name:'submit_answer'}, 2),
  ], 'tool-lab-mcp-v1');
  assert.deepEqual(frames.map(f => f.phase), ['choose','execute','return','choose','execute']);
  assert.equal(frames[1].transport, 'mcp');
  assert.equal(frames[2].transport, 'mcp');
  assert.equal(frames[4].transport, 'local');
});
test('rejection never animates execution and missing transport stays unknown', () => {
  const frames = flowFrames([
    event('TOOL_CALL_PROPOSED', {call_id:'a', name:'read_document'}),
    event('TOOL_CALL_VALIDATED', {call_id:'a', permitted:false, error_code:'FORBIDDEN_TOOL'}),
    event('EPISODE_FINISHED', {success:false, termination_reason:'FAILED'}),
  ], '');
  assert.deepEqual(frames.map(f => f.phase), ['choose','reject','finish']);
  assert.equal(frames[1].failed, true);
  assert.equal(frames[2].failed, true);
  const unknown = flowFrames([event('TOOL_CALL_PROPOSED', {call_id:'x', name:'read_document'}),
    event('TOOL_STARTED', {call_id:'x'})], '');
  assert.equal(unknown[1].transport, 'unknown');
});
test('parallel call IDs keep tool results associated and failure intact', () => {
  const frames = flowFrames([
    event('TOOL_CALL_PROPOSED', {call_id:'a', name:'search_documents'}),
    event('TOOL_CALL_PROPOSED', {call_id:'b', name:'read_document'}),
    event('TOOL_STARTED', {call_id:'a', transport:'mcp'}),
    event('TOOL_FAILED', {call_id:'a', error:{code:'TOOL_EXECUTION_ERROR'}}),
  ], 'tool-lab-mcp-v1');
  assert.equal(frames.at(-1).tool, 'search_documents');
  assert.equal(frames.at(-1).failed, true);
  assert.deepEqual(flowFrames([], ''), []);
});
