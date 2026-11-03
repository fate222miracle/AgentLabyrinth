import assert from 'node:assert/strict';
import test from 'node:test';
import { areaFor, canonicalLocation, routeParams, sectionFor, workspaceFor } from '../src/workspaceNavigation.ts';

const base = 'http://127.0.0.1:5173';
const episode = '10000000-0000-4000-8000-000000000001';
const experiment = '10000000-0000-4000-8000-000000000002';

test('legacy bookmarks and new page URLs resolve to the same saved identity and workspace', () => {
  for (const [old, next, workspace, key, id] of [
    [`/?episode_id=${episode}`, `/runs/${episode}`, 'episode', 'episode_id', episode],
    [`/?experiment_id=${experiment}`, `/experiments/${experiment}`, 'experiment', 'experiment_id', experiment],
    [`/?experiment_job_id=${experiment}`, `/experiments/jobs/${experiment}`, 'experiment', 'experiment_job_id', experiment],
  ]) {
    assert.equal(workspaceFor(new URL(old, base)), workspace);
    assert.equal(workspaceFor(new URL(next, base)), workspace);
    assert.equal(routeParams(new URL(next, base)).get(key), id);
    const canonical = canonicalLocation(new URL(old, base));
    assert.equal(canonical.pathname, next);
    assert.equal(canonical.searchParams.get(key), id);
    assert.equal(canonicalLocation(canonical).href, canonical.href);
  }
});

test('page navigation cannot inherit a different area or silently restore a run', () => {
  for (const [path, expected] of [['/tasks', 'tasks'], ['/runs', 'runs'], ['/workbench', 'workbench'],
    ['/experiments', 'experiments'], ['/experiments/new', 'experiment-new']]) {
    const url = new URL(path, base);
    assert.equal(workspaceFor(url), expected);
    assert.equal(routeParams(url).get('episode_id'), null);
    assert.equal(routeParams(url).get('experiment_id'), null);
  }
  const navigating = new URL(`/tasks?page=tasks&episode_id=${episode}`, base);
  const canonical = canonicalLocation(navigating);
  assert.equal(canonical.pathname, `/runs/${episode}`);
  assert.equal(canonical.searchParams.has('page'), false);
  assert.equal(workspaceFor(canonical), 'episode');
  assert.equal(workspaceFor(new URL('/?mode=single', base)), 'workbench');
  assert.equal(areaFor('experiment-new'), 'experiments');
  assert.equal(areaFor('episode'), 'runs');
  assert.equal(workspaceFor(new URL('/', base)), 'tasks');
  assert.equal(canonicalLocation(new URL('/', base)).pathname, '/tasks');
  assert.equal(workspaceFor(new URL('/?mode=experiment', base)), 'experiment-new');
  assert.equal(canonicalLocation(new URL(`/runs/${episode}?mode=single`, base)).pathname, '/workbench');
});

test('detail sections deep-link without changing the saved identity', () => {
  for (const section of ['results', 'review', 'unknown']) {
    const url = new URL(`/?episode_id=${episode}&section=${section}`, base);
    assert.equal(sectionFor(url), section === 'unknown' ? 'process' : section);
    assert.equal(canonicalLocation(url).searchParams.get('episode_id'), episode);
    const direct = new URL(`/runs/${episode}?section=${section}`, base);
    assert.equal(canonicalLocation(direct).pathname, `/runs/${episode}`);
  }
});
