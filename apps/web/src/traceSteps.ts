export interface TraceStepEvent {
  step_index: number;
  event_type: string;
  payload: Record<string, unknown>;
}

/** Keep adjacent saved events together without rewriting their order. */
export function groupTraceByStep<T extends TraceStepEvent>(events: T[]): { step: number; events: T[] }[] {
  const groups: { step: number; events: T[] }[] = [];
  for (const event of events) {
    const current = groups[groups.length - 1];
    if (current?.step === event.step_index) current.events.push(event);
    else groups.push({ step: event.step_index, events: [event] });
  }
  return groups;
}

/** Label a step from observed events, never from the task's expected answer. */
export function stepTitle(events: TraceStepEvent[]): string {
  const proposed = events.find((event) => event.event_type === 'TOOL_CALL_PROPOSED');
  if (proposed && typeof proposed.payload.name === 'string') return proposed.payload.name;
  if (events.some((event) => event.event_type === 'EPISODE_FINISHED')) return '运行结束';
  return '初始观察';
}

/** Label the observed step outcome, prioritizing failures. */
export function stepOutcome(events: TraceStepEvent[]): string {
  if (events.some((event) => event.event_type === 'TOOL_FAILED')) return '工具失败';
  const rejected = events.find((event) => event.event_type === 'TOOL_CALL_VALIDATED'
    && (event.payload.error_code || event.payload.arguments_valid === false || event.payload.permitted === false));
  if (rejected) {
    if (rejected.payload.error_code === 'INVALID_ARGUMENTS' || rejected.payload.arguments_valid === false) return '参数错误';
    if (rejected.payload.error_code === 'UNKNOWN_TOOL') return '未知工具';
    if (rejected.payload.error_code === 'FORBIDDEN_TOOL' || rejected.payload.permitted === false) return '禁止工具';
    return String(rejected.payload.error_code ?? '校验失败');
  }
  const finished = events.find((event) => event.event_type === 'EPISODE_FINISHED');
  if (finished?.payload.success === false) return String(finished.payload.termination_reason ?? '失败');
  if (events.some((event) => event.event_type === 'TOOL_SUCCEEDED')) return '工具成功';
  if (finished) return String(finished.payload.termination_reason ?? '已结束');
  return '已记录';
}

/** Compare only snapshots actually saved at or before each Replay step. */
export function changedStateFields(
  previous: Record<string, unknown> | null,
  current: Record<string, unknown> | null,
): [string, unknown][] {
  if (!previous || !current) return [];
  return Object.entries(current).filter(([key, value]) =>
    JSON.stringify(value) !== JSON.stringify(previous[key]));
}

/** Keep recorded values, but prefer the fields that explain a step. */
export function keyFields(
  source: Record<string, unknown>,
  preferred: string[],
): [string, unknown][] {
  const selected = preferred.filter((key) => Object.prototype.hasOwnProperty.call(source, key));
  return (selected.length ? selected : Object.keys(source).slice(0, 4))
    .map((key) => [key, source[key]]);
}
