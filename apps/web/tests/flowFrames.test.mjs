import assert from 'node:assert/strict';
import test from 'node:test';
import { flowFrames, flowPath, frameIndexAt } from '../src/flowFrames.ts';

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

test('execution path expands repeated calls and never exposes a future result or transport', () => {
  const frames = flowFrames([
    event('OBSERVATION_CREATED', {observation:{description:'Read policy'}}, 0),
    event('MODEL_REQUESTED', {}), event('MODEL_RESPONDED', {}),
    event('TOOL_CALL_PROPOSED', {call_id:'bad', name:'read_document', arguments:{document_id:3}}),
    event('TOOL_CALL_VALIDATED', {call_id:'bad', error_code:'INVALID_ARGUMENTS'}),
    event('MODEL_REQUESTED', {}, 2), event('MODEL_RESPONDED', {}, 2),
    event('TOOL_CALL_PROPOSED', {call_id:'ok', name:'read_document', arguments:{document_id:'policy'}}, 2),
    event('TOOL_STARTED', {call_id:'ok', transport:'mcp'}, 2),
    event('TOOL_SUCCEEDED', {call_id:'ok', observation:{document:{content:'secret future', evidence_id:'doc:policy'}}}, 2),
    event('ENVIRONMENT_UPDATED', {state:{acquired_evidence:['doc:policy']}}, 2),
    event('EPISODE_FINISHED', {success:true, termination_reason:'SUCCESS'}, 2),
  ], 'tool-lab-mcp-v1');
  const partial = flowPath(frames, 3);
  assert.equal(partial.length, 3);
  assert.equal(partial.at(-1).frame.transport, 'unknown');
  assert.deepEqual(partial.at(-1).frame.feedback, []);
  assert.ok(!JSON.stringify(partial).includes('secret future'));
  const complete = flowPath(frames, 100);
  const tools = complete.filter(node => node.kind === 'tool');
  assert.equal(tools.length, 2);
  assert.notEqual(tools[0].id, tools[1].id);
  assert.equal(tools[0].frame.failed, true);
  assert.equal(tools[1].frame.failed, false);
  assert.equal(tools[1].frame.phase, 'return');
  assert.equal(tools[1].frame.transport, 'mcp');
  assert.equal(frames[tools[1].frameIndex].phase, 'update');
  assert.equal(tools[0].id, partial.at(-1).id);
  assert.deepEqual(flowPath(frames.slice(0, 3), 100).map(node => node.kind), ['task','model']);
});

test('path associates out-of-order results by call ID and accepts old missing IDs', () => {
  const frames = flowFrames([
    event('TOOL_CALL_PROPOSED', {call_id:'a', name:'search_documents'}),
    event('TOOL_CALL_PROPOSED', {call_id:'b', name:'read_document'}),
    event('TOOL_FAILED', {call_id:'a', error:{code:'TOOL_TIMEOUT'}}),
    event('TOOL_SUCCEEDED', {call_id:'b', observation:{document:{title:'policy'}}}),
  ], '');
  const path = flowPath(frames, 100);
  assert.equal(path.length, 2);
  assert.equal(path[0].frame.tool, 'search_documents');
  assert.equal(path[0].frame.failed, true);
  assert.equal(path[1].frame.tool, 'read_document');
  const old = flowPath(flowFrames([
    event('TOOL_CALL_VALIDATED', {error_code:'UNKNOWN_TOOL'}),
    event('TOOL_CALL_PROPOSED', {name:'query_records'}),
    event('TOOL_FAILED', {error:{code:'TOOL_TIMEOUT'}}),
    event('EPISODE_FINISHED', {success:false}),
  ], ''), 100);
  assert.deepEqual(old.map(node => node.kind), ['tool','tool','finish']);
  assert.equal(old[0].frame.phase, 'reject');
  assert.equal(old[1].frame.transport, 'unknown');
  assert.equal(old[1].frame.failed, true);
  assert.deepEqual(flowPath([], 10), []);
});

test('episode start creates one stable task node without borrowing the next observation', () => {
  const frames = flowFrames([
    event('EPISODE_STARTED',{seed:1},0),
    event('OBSERVATION_CREATED',{observation:{description:'future observation'}},0),
    event('MODEL_REQUESTED',{}),
  ],'');
  const start = flowPath(frames,0);
  assert.equal(start.length,1);
  assert.equal(start[0].frame.eventIndex,0);
  assert.ok(!JSON.stringify(start).includes('future observation'));
  const observed = flowPath(frames,1);
  assert.equal(observed.length,1);
  assert.equal(observed[0].id,start[0].id);
  assert.equal(observed[0].frame.eventIndex,1);
  assert.equal(flowPath(frames,2).length,2);
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

test('source cursor and current feedback never borrow later execution, state or duration', () => {
  const events = [
    event('EPISODE_STARTED', {initial_state:{acquired_evidence:[]}}, 0),
    event('OBSERVATION_CREATED', {observation:{description:'Read a document'}}, 0),
    event('MODEL_REQUESTED', {}),
    {...event('MODEL_RESPONDED', {}), duration_ms:0},
    event('TOOL_CALL_PROPOSED', {call_id:'bad', name:'read_document', arguments:{document_id:3}}),
    event('TOOL_CALL_VALIDATED', {call_id:'bad', arguments_valid:false, error_code:'INVALID_ARGUMENTS'}),
    event('MODEL_REQUESTED', {}, 2),
    event('TOOL_CALL_PROPOSED', {call_id:'good', name:'read_document', arguments:{document_id:'doc-1'}}, 2),
    event('TOOL_CALL_VALIDATED', {call_id:'good', arguments_valid:true}, 2),
    event('TOOL_STARTED', {call_id:'good', transport:'mcp'}, 2),
    {...event('TOOL_SUCCEEDED', {call_id:'good', observation:{result:{document:{content:'Saved answer'}}}}, 2), duration_ms:27},
    event('ENVIRONMENT_UPDATED', {state:{acquired_evidence:['document:doc-1']}}, 2),
  ];
  const frames = flowFrames(events, 'tool-lab-mcp-v1');
  const rejected = frames.find(f => f.phase === 'reject');
  assert.deepEqual(rejected.arguments, {document_id:3});
  assert.deepEqual(rejected.feedback, []);
  assert.equal(rejected.transport, 'unknown');
  assert.equal(frames.find(f => f.phase === 'request').eventIndex, 2);
  assert.equal(frames.find(f => f.phase === 'respond').durationMs, null);
  assert.deepEqual(frames.find(f => f.phase === 'execute').feedback, []);
  assert.deepEqual(frames.find(f => f.phase === 'return').feedback, [['document',{content:'Saved answer'}]]);
  assert.equal(frames.find(f => f.phase === 'return').durationMs, 27);
  assert.deepEqual(frames.at(-1).stateChanges, [['acquired_evidence',['document:doc-1']]]);
  assert.equal(frames[frameIndexAt(frames, 8)].eventIndex, 7);
  assert.equal(frameIndexAt(frames, 100), frames.length - 1);
});
