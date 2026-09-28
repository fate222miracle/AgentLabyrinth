/** Consume one Episode SSE response, including events split across network chunks. */
export async function readEpisodeStream(
  response: Response,
  onTrace: (value: unknown) => void,
): Promise<unknown> {
  if (!response.body) throw new Error('浏览器未提供实时传输。');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let completed: unknown;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let end = buffer.indexOf('\n\n');
      while (end >= 0) {
        const block = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        const type = block.match(/^event: (.+)$/m)?.[1];
        const data = block.match(/^data: (.+)$/m)?.[1];
        if (data) {
          const parsed: unknown = JSON.parse(data);
          if (type === 'trace') onTrace(parsed);
          if (type === 'complete') completed = parsed;
          if (type === 'error') {
            const message = parsed && typeof parsed === 'object' && 'message' in parsed
              && typeof parsed.message === 'string' ? parsed.message : '运行失败';
            throw new Error(message);
          }
        }
        end = buffer.indexOf('\n\n');
      }
      if (done) break;
    }
  } finally {
    reader.releaseLock();
  }
  if (!completed) throw new Error('实时连接中断；运行可能仍在后端继续。');
  return completed;
}
