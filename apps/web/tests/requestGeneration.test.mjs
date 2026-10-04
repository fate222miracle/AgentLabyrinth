import assert from 'node:assert/strict';
import test from 'node:test';
import { RequestGeneration } from '../src/requestGeneration.ts';

test('a late accepted job cannot replace history or finish a newer loading state', async () => {
  const page = new RequestGeneration();
  const jobRequest = page.begin();
  let accept;
  const response = new Promise((resolve) => { accept = resolve; });
  let visible = 'loading-job';
  const completion = response.then(() => {
    if (page.isCurrent(jobRequest)) visible = 'job-result';
  }).finally(() => {
    if (page.isCurrent(jobRequest)) visible = 'job-finished';
  });
  page.begin(); // browser Back or opening history
  visible = 'loading-history';
  accept();
  await completion;
  assert.equal(visible, 'loading-history');
});

test('control replies require both the current page and latest control request', () => {
  const page = new RequestGeneration();
  const controls = new RequestGeneration();
  const owner = page.begin();
  const pause = controls.begin();
  const cancel = controls.begin();
  assert.equal(controls.isCurrent(pause), false);
  assert.equal(page.isCurrent(owner) && controls.isCurrent(cancel), true);
  page.begin(); // navigate while resume/cancel is pending
  assert.equal(page.isCurrent(owner) && controls.isCurrent(cancel), false);
  assert.equal(page.isCurrent(page.capture()), true);
});
