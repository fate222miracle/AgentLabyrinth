export type Workspace = 'tasks' | 'workbench' | 'runs' | 'episode' | 'experiments' | 'experiment-new' | 'experiment';
export type WorkspaceArea = 'tasks' | 'workbench' | 'runs' | 'experiments';
export type EpisodeSection = 'process' | 'results' | 'review';

/** Read old query links and new page URLs without executing or restoring anything. */
export function routeParams(url: URL): URLSearchParams {
  const params = new URLSearchParams(url.search);
  if (!params.has('episode_id') && !params.has('experiment_id') && !params.has('experiment_job_id')) {
    const parts = url.pathname.split('/').filter(Boolean);
    if (parts[0] === 'runs' && parts.length === 2) params.set('episode_id', parts[1]);
    else if (parts[0] === 'experiments' && parts[1] === 'jobs' && parts.length === 3) params.set('experiment_job_id', parts[2]);
    else if (parts[0] === 'experiments' && parts.length === 2 && parts[1] !== 'new') params.set('experiment_id', parts[1]);
  }
  if (url.pathname === '/tasks') params.set('page', 'tasks');
  if (url.pathname === '/runs') params.set('page', 'runs');
  if (url.pathname === '/workbench') params.set('mode', 'single');
  if (url.pathname === '/experiments') params.set('page', 'experiments');
  return params;
}

export function workspaceFor(url: URL): Workspace {
  const params = routeParams(url);
  if (params.get('experiment_job_id') || params.get('experiment_id')) return 'experiment';
  if (params.get('episode_id')) return 'episode';
  const page = params.get('page');
  if (page === 'tasks' || page === 'runs' || page === 'experiments') return page;
  if (url.pathname === '/' && !params.has('mode')) return 'tasks';
  return params.get('mode') === 'single' ? 'workbench' : 'experiment-new';
}

export function areaFor(workspace: Workspace): WorkspaceArea {
  if (workspace === 'episode') return 'runs';
  if (workspace === 'experiment-new' || workspace === 'experiment') return 'experiments';
  return workspace;
}

export function sectionFor(url: URL): EpisodeSection {
  const section = url.searchParams.get('section');
  return section === 'results' || section === 'review' ? section : 'process';
}

/** Keep query IDs for old bookmarks and integrations while giving pages stable paths. */
export function canonicalLocation(input: URL): URL {
  const url = new URL(input);
  const params = url.searchParams;
  if (!params.has('mode') && !params.has('page') && !params.has('episode_id')
    && !params.has('experiment_id') && !params.has('experiment_job_id')) {
    const saved = routeParams(url);
    for (const key of ['episode_id', 'experiment_id', 'experiment_job_id']) {
      const id = saved.get(key);
      if (id) params.set(key, id);
    }
  }
  if (params.get('experiment_job_id')) url.pathname = `/experiments/jobs/${encodeURIComponent(params.get('experiment_job_id')!)}`;
  else if (params.get('experiment_id')) url.pathname = `/experiments/${encodeURIComponent(params.get('experiment_id')!)}`;
  else if (params.get('episode_id')) url.pathname = `/runs/${encodeURIComponent(params.get('episode_id')!)}`;
  else if (params.get('page') === 'tasks') url.pathname = '/tasks';
  else if (params.get('page') === 'runs') url.pathname = '/runs';
  else if (params.get('page') === 'experiments') url.pathname = '/experiments';
  else if (url.pathname === '/' && !params.has('mode') && !params.has('page')) url.pathname = '/tasks';
  else url.pathname = params.get('mode') === 'single' ? '/workbench' : '/experiments/new';
  if (params.has('episode_id') || params.has('experiment_id') || params.has('experiment_job_id')) params.delete('page');
  return url;
}
