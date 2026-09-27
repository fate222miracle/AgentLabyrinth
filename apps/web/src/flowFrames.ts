import type { TraceStepEvent } from './traceSteps';

export interface FlowFrame {
  step: number;
  phase: 'observe' | 'choose' | 'execute' | 'return' | 'reject' | 'finish';
  tool: string | null;
  transport: 'mcp' | 'local' | 'unknown';
  failed: boolean;
  payload: Record<string, unknown>;
}

/** Derive ordered visual beats from recorded calls, never invent tool execution. */
export function flowFrames(events: TraceStepEvent[], environmentVersion: string): FlowFrame[] {
  const calls = new Map<string, { tool: string; transport: FlowFrame['transport'] }>();
  const frames: FlowFrame[] = [];
  for (const event of events) {
    const id = String(event.payload.call_id ?? '');
    if (event.event_type === 'TOOL_CALL_PROPOSED') {
      calls.set(id, { tool: String(event.payload.name ?? '未知工具'), transport: 'unknown' });
    }
    const call = calls.get(id);
    if (event.event_type === 'TOOL_STARTED' && call) {
      call.transport = event.payload.transport === 'mcp' ? 'mcp'
        : environmentVersion === 'tool-lab-m0-v1' || (environmentVersion === 'tool-lab-mcp-v1' && call.tool === 'submit_answer')
          ? 'local' : 'unknown';
    }
    let phase: FlowFrame['phase'] | null = null;
    if (event.event_type === 'OBSERVATION_CREATED') phase = 'observe';
    if (event.event_type === 'TOOL_CALL_PROPOSED') phase = 'choose';
    if (event.event_type === 'TOOL_STARTED' && call) phase = 'execute';
    if (['TOOL_SUCCEEDED', 'TOOL_FAILED'].includes(event.event_type) && call) phase = 'return';
    if (event.event_type === 'TOOL_CALL_VALIDATED' && (event.payload.error_code
      || event.payload.arguments_valid === false || event.payload.permitted === false)) phase = 'reject';
    if (event.event_type === 'EPISODE_FINISHED') phase = 'finish';
    if (phase) frames.push({ step: event.step_index, phase, tool: call?.tool ?? null,
      transport: call?.transport ?? 'unknown', failed: phase === 'reject'
        || event.event_type === 'TOOL_FAILED' || event.payload.success === false, payload: event.payload });
  }
  return frames;
}
