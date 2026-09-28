import assert from 'node:assert/strict';
import test from 'node:test';
import { readEpisodeStream } from '../src/streamEpisode.ts';

const response = (chunks) => new Response(new ReadableStream({
  start(controller) {
    for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk));
    controller.close();
  },
}));

test('fragmented live trace ends with the saved artifact', async () => {
  const seen = [];
  const result = await readEpisodeStream(response([
    'event: trace\ndata: {"event_id":"a"}\n',
    '\nevent: complete\ndata: {"artifact":{"episode":{"episode_id":"a"}}}\n\n',
  ]), (event) => seen.push(event));
  assert.deepEqual(seen, [{ event_id: 'a' }]);
  assert.equal(result.artifact.episode.episode_id, 'a');
});

test('stream failure or missing completion never claims a finished run', async () => {
  await assert.rejects(readEpisodeStream(response(['event: error\ndata: {"message":"bad model"}\n\n']), () => {}), /bad model/);
  await assert.rejects(readEpisodeStream(response(['event: trace\ndata: {}\n\n']), () => {}), /连接中断/);
});
