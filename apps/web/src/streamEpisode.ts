import { episodeResponseSchema, traceEventSchema, errorSchema, parseApi,
  requireIdentity, type TraceEvent } from './apiContracts.ts';

/** Consume one Episode SSE response, including events split across network chunks. */
export async function readEpisodeStream(
  response: Response,
  onTrace: (value: TraceEvent) => void,
) {
  if (!response.body) throw new Error('浏览器未提供实时传输。');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let completed: ReturnType<typeof episodeResponseSchema.parse> | undefined;
  let episodeId: string | undefined;
  const events: string[] = [];
  const seen = new Set<string>();
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, '\n');
      let end = buffer.indexOf('\n\n');
      while (end >= 0) {
        const block = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        const type = block.match(/^event:\s?(.+)$/m)?.[1];
        const data = block.split('\n').filter((line) => line.startsWith('data:'))
          .map((line) => line.slice(5).replace(/^ /, '')).join('\n');
        if (data && ['trace', 'complete', 'error'].includes(type ?? '')) {
          let parsed: unknown;
          try { parsed = JSON.parse(data); }
          catch { throw new Error('实时接口返回的 JSON 无效。'); }
          if (completed) throw new Error('完成后收到了重复或异常实时事件。');
          if (type === 'trace') {
            const event = parseApi(traceEventSchema, parsed);
            if (episodeId) requireIdentity(event.episode_id, episodeId);
            episodeId = event.episode_id;
            if (seen.has(event.event_id)) throw new Error('实时 Trace 出现重复事件。');
            seen.add(event.event_id);
            events.push(event.event_id);
            onTrace(event);
          }
          if (type === 'complete') {
            completed = parseApi(episodeResponseSchema, parsed);
            if (episodeId) requireIdentity(completed.artifact.episode.episode_id, episodeId);
            if (events.some((id, index) => completed?.artifact.events[index]?.event_id !== id)) {
              throw new Error('完成产物与实时 Trace 顺序不一致。');
            }
          }
          if (type === 'error') {
            throw new Error(parseApi(errorSchema, parsed).message);
          }
        }
        end = buffer.indexOf('\n\n');
      }
      if (done) break;
    }
  } catch (error) {
    await reader.cancel().catch(() => {});
    throw error;
  } finally {
    reader.releaseLock();
  }
  if (!completed) throw new Error('实时连接中断；运行可能仍在后端继续。');
  return completed;
}
