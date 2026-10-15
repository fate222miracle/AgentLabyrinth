import { changedStateFields, toolFeedbackFields, type TraceStepEvent } from './traceSteps.ts';

export interface FlowFrame {
  step: number;
  phase: 'observe' | 'request' | 'respond' | 'choose' | 'execute' | 'return' | 'reject' | 'update' | 'finish';
  eventIndex: number;
  durationMs: number | null;
  arguments: Record<string, unknown> | null;
  feedback: [string, unknown][];
  stateChanges: [string, unknown][];
  tool: string | null;
  transport: 'mcp' | 'local' | 'unknown';
  failed: boolean;
  payload: Record<string, unknown>;
}

/** Derive ordered visual beats from recorded calls, never invent tool execution. */
export function flowFrames(events: TraceStepEvent[], environmentVersion: string): FlowFrame[] {
  const calls = new Map<string, { tool: string; transport: FlowFrame['transport']; arguments: FlowFrame['arguments'] }>();
  const frames: FlowFrame[] = [];
  const record = (value: unknown): value is Record<string, unknown> =>
    typeof value === 'object' && value !== null && !Array.isArray(value);
  let previousState: Record<string, unknown> | null = null;
  for (const [eventIndex, event] of events.entries()) {
    const id = String(event.payload.call_id ?? '');
    if (event.event_type === 'TOOL_CALL_PROPOSED') {
      calls.set(id, { tool: String(event.payload.name ?? '未知工具'), transport: 'unknown',
        arguments: record(event.payload.arguments) ? event.payload.arguments : null });
    }
    const call = calls.get(id);
    if (event.event_type === 'TOOL_STARTED' && call) {
      call.transport = event.payload.transport === 'mcp' ? 'mcp'
        : environmentVersion === 'tool-lab-m0-v1' || (environmentVersion === 'tool-lab-mcp-v1' && call.tool === 'submit_answer')
          ? 'local' : 'unknown';
    }
    let phase: FlowFrame['phase'] | null = null;
    let stateChanges: FlowFrame['stateChanges'] = [];
    if (record(event.payload.initial_state)) previousState = event.payload.initial_state;
    if (event.event_type === 'ENVIRONMENT_UPDATED' && record(event.payload.state)) {
      stateChanges = changedStateFields(previousState, event.payload.state)
        .filter(([key]) => ['acquired_evidence', 'submission', 'done', 'proposed_call'].includes(key));
      previousState = event.payload.state;
      phase = 'update';
    }
    if (['EPISODE_STARTED', 'OBSERVATION_CREATED'].includes(event.event_type)) phase = 'observe';
    if (event.event_type === 'MODEL_REQUESTED') phase = 'request';
    if (event.event_type === 'MODEL_RESPONDED') phase = 'respond';
    if (event.event_type === 'TOOL_CALL_PROPOSED') phase = 'choose';
    if (event.event_type === 'TOOL_STARTED' && call) phase = 'execute';
    if (['TOOL_SUCCEEDED', 'TOOL_FAILED'].includes(event.event_type) && call) phase = 'return';
    if (event.event_type === 'TOOL_CALL_VALIDATED' && (event.payload.error_code
      || event.payload.arguments_valid === false || event.payload.permitted === false)) phase = 'reject';
    if (event.event_type === 'EPISODE_FINISHED') phase = 'finish';
    if (phase) frames.push({ step: event.step_index, phase, eventIndex,
      durationMs: typeof event.duration_ms === 'number' && event.duration_ms > 0 ? event.duration_ms : null,
      arguments: call?.arguments ?? null,
      feedback: phase === 'return' ? toolFeedbackFields(event, call?.tool ?? '') : [],
      stateChanges, tool: call?.tool ?? null,
      transport: call?.transport ?? 'unknown', failed: phase === 'reject'
        || event.event_type === 'TOOL_FAILED' || event.payload.success === false, payload: event.payload });
  }
  return frames;
}

/** Unmapped events retain their source cursor; show the nearest preceding visual phase. */
export function frameIndexAt(frames: FlowFrame[], eventIndex: number): number {
  let index = 0;
  for (const [i, frame] of frames.entries()) {
    if (frame.eventIndex > eventIndex) break;
    index = i;
  }
  return index;
}

export interface FlowPathNode {
  id: string;
  kind: 'task' | 'model' | 'tool' | 'finish';
  frame: FlowFrame;
  frameIndex: number;
}

/** Expand each observed invocation, using only the selected event prefix. */
export function flowPath(frames: FlowFrame[], eventIndex: number): FlowPathNode[] {
  const nodes: FlowPathNode[] = [];
  const calls = new Map<string, FlowPathNode>();
  let model: FlowPathNode | undefined;
  let current: FlowPathNode | undefined;
  const append = (kind: FlowPathNode['kind'], frame: FlowFrame, frameIndex: number) => {
    const node = { id: `${kind}:${frame.eventIndex}`, kind, frame, frameIndex };
    nodes.push(node);
    return node;
  };
  for (const [frameIndex, frame] of frames.entries()) {
    if (frame.eventIndex > eventIndex) break;
    const id = String(frame.payload.call_id ?? '');
    if (frame.phase === 'observe') {
      current = current?.kind === 'task' ? current : append('task', frame, frameIndex);
      current.frame = frame; current.frameIndex = frameIndex;
    }
    else if (frame.phase === 'request') current = model = append('model', frame, frameIndex);
    else if (frame.phase === 'respond') {
      current = model?.frame.step === frame.step ? model : append('model', frame, frameIndex);
      current.frame = frame; current.frameIndex = frameIndex;
    } else if (frame.phase === 'choose') {
      current = append('tool', frame, frameIndex);
      calls.set(id, current);
    } else if (['execute', 'return', 'reject'].includes(frame.phase)) {
      current = calls.get(id) ?? append('tool', frame, frameIndex);
      calls.set(id, current);
      current.frame = frame; current.frameIndex = frameIndex;
    } else if (frame.phase === 'update' && current) {
      // A snapshot adds detail to the call, without turning it into another invocation.
      current.frameIndex = frameIndex;
    } else if (frame.phase === 'finish') current = append('finish', frame, frameIndex);
  }
  return nodes;
}

export interface EvidenceDocument {
  id: string;
  title: string;
  content: string | null;
  evidenceId: string | null;
  status: 'unread' | 'found' | 'reading' | 'read' | 'failed';
  read: boolean;
  readCount: number;
  cited: boolean;
  readStep: number | null;
}

/** Project source documents and actual tool outcomes at the current Trace cursor. */
export function documentEvidence(events: TraceStepEvent[], cutoff: number) {
  const record = (value: unknown): Record<string, unknown> =>
    value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
  const docs = new Map<string, EvidenceDocument>();
  const calls = new Map<string, { name: string; args: Record<string, unknown> }>();
  let activeId: string | null = null;
  let readCursor = 'none';
  let citations: string[] = [];
  const add = (value: unknown) => {
    const raw = record(value);
    if (typeof raw.document_id !== 'string' || !raw.document_id) return null;
    const id = raw.document_id;
    const doc = docs.get(id) ?? { id, title: id, content: null, evidenceId: null,
      status: 'unread', read: false, readCount: 0, cited: false, readStep: null };
    if (typeof raw.title === 'string') doc.title = raw.title;
    if (typeof raw.content === 'string') doc.content = raw.content;
    if (typeof raw.evidence_id === 'string') doc.evidenceId = raw.evidence_id;
    docs.set(id, doc);
    return doc;
  };
  for (const [index, event] of events.entries()) {
    if (index > cutoff) break;
    const initial = record(event.payload.initial_state);
    if (Array.isArray(initial.documents)) initial.documents.forEach(add);
    const id = String(event.payload.call_id ?? '');
    if (event.event_type === 'TOOL_CALL_PROPOSED') {
      calls.set(id, { name: String(event.payload.name ?? ''), args: record(event.payload.arguments) });
    }
    const call = calls.get(id);
    if (!call) continue;
    const result = record(record(event.payload.observation).result ?? event.payload.observation);
    const target = typeof call.args.document_id === 'string' ? call.args.document_id : null;
    if (call.name === 'read_document' && target && event.event_type === 'TOOL_STARTED') {
      const doc = add({ document_id: target })!;
      doc.status = 'reading';
      activeId = target;
      readCursor = `${id}:${index}`;
    }
    if (call.name === 'read_document' && target && ['TOOL_FAILED', 'TOOL_CALL_VALIDATED'].includes(event.event_type)
      && (event.event_type === 'TOOL_FAILED' || event.payload.error_code
        || event.payload.arguments_valid === false || event.payload.permitted === false)) {
      const doc = add({ document_id: target })!;
      doc.status = 'failed';
    }
    if (event.event_type !== 'TOOL_SUCCEEDED') continue;
    if (call.name === 'search_documents' && Array.isArray(result.documents)) {
      for (const item of result.documents) {
        const doc = add(item);
        if (doc && doc.status === 'unread') doc.status = 'found';
      }
    }
    if (call.name === 'read_document' && target) {
      const raw = record(result.document);
      if (raw.document_id === target) {
        const doc = add(raw)!;
        doc.status = 'read'; doc.read = true; doc.readStep = event.step_index;
        doc.readCount += 1;
      } else {
        // A successful HTTP/tool event with document:null did not acquire a document.
        const doc = add({ document_id: target })!;
        doc.status = 'failed';
      }
    }
    if (call.name === 'submit_answer' && Array.isArray(call.args.evidence)) {
      citations = call.args.evidence.filter((value): value is string => typeof value === 'string');
    }
  }
  for (const doc of docs.values()) doc.cited = doc.evidenceId !== null && citations.includes(doc.evidenceId);
  return { documents: [...docs.values()], activeId, readCursor };
}
