import assert from 'node:assert/strict';
import test from 'node:test';
import { readEpisodeStream } from '../src/streamEpisode.ts';
import { episodeId, episodeResponse, requestId, trace } from './apiFixtures.mjs';

const response = (chunks) => new Response(new ReadableStream({
  start(controller) {
    for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk));
    controller.close();
  },
}));
const block = (type, data) => `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`;

test('fragmented CRLF live Trace ends with matching saved artifact', async () => {
  const seen = [];
  const stream = (block('trace', trace()) + block('complete', episodeResponse())).replaceAll('\n', '\r\n');
  const result = await readEpisodeStream(response([...stream]), (event) => seen.push(event));
  assert.deepEqual(seen, [trace()]);
  assert.equal(result.artifact.episode.episode_id, episodeId);
});

test('stream failure or missing completion never claims a finished run', async () => {
  const error = { schema_version: '1.0', request_id: requestId, error_code: 'INTERNAL_ERROR', message: 'bad model' };
  await assert.rejects(readEpisodeStream(response([block('error', error)]), () => {}), /bad model/);
  await assert.rejects(readEpisodeStream(response([block('trace', trace())]), () => {}), /连接中断/);
});

test('invalid Trace is rejected before calling the UI callback and cancels reader', async () => {
  let called = false;
  let cancelled = false;
  const stream = new ReadableStream({ start(controller) {
    controller.enqueue(new TextEncoder().encode(block('trace', { ...trace(), payload: [] })));
  }, cancel() { cancelled = true; } });
  await assert.rejects(readEpisodeStream(new Response(stream), () => { called = true; }), /校验失败/);
  assert.equal(called, false);
  assert.equal(cancelled, true);
});

test('duplicate or wrong-owner events and inconsistent completion cannot be trusted', async () => {
  await assert.rejects(readEpisodeStream(response([block('trace', trace()), block('trace', trace())]), () => {}), /重复事件/);
  const alien = { ...trace(), episode_id: '10000000-0000-4000-8000-000000000004' };
  await assert.rejects(readEpisodeStream(response([block('trace', trace()), block('trace', alien)]), () => {}), /ID 与请求不一致/);
  const complete = episodeResponse();
  complete.artifact.events = [];
  await assert.rejects(readEpisodeStream(response([block('trace', trace()), block('complete', complete)]), () => {}), /顺序不一致/);
  await assert.rejects(readEpisodeStream(response([block('complete', episodeResponse()), block('trace', trace())]), () => {}), /完成后/);
});
