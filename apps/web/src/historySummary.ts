export interface EpisodeHistorySummary {
  status: 'loading' | 'ready' | 'error';
  taskName?: string;
  modelId?: string;
  timestamp?: string;
  success?: boolean;
}

import type { EpisodeArtifact, ExperimentDashboardItem } from './apiContracts.ts';
export type { ExperimentDashboardItem } from './apiContracts.ts';

/** Reconcile saved reports; absent responses must never imply zero total usage. */
export function savedUsage(artifact: EpisodeArtifact) {
  const { events, episode } = artifact;
  const requests = events.filter(event => event.event_type === 'MODEL_REQUESTED');
  const responses = events.filter(event => event.event_type === 'MODEL_RESPONDED');
  const total = episode.token_usage.prompt_tokens + episode.token_usage.completion_tokens;
  const prompt = responses.reduce((sum, event) => sum + event.token_usage.prompt_tokens, 0);
  const completion = responses.reduce((sum, event) => sum + event.token_usage.completion_tokens, 0);
  const complete = events[0]?.event_type === 'EPISODE_STARTED' && events.at(-1)?.event_type === 'EPISODE_FINISHED'
    && requests.length === episode.model_call_count && responses.length === requests.length
    && prompt === episode.token_usage.prompt_tokens && completion === episode.token_usage.completion_tokens;
  return { complete, reportedTotal: complete || responses.length > 0 || total > 0 ? total : null };
}

export function comparableHistory(items: ExperimentDashboardItem[], key: string): ExperimentDashboardItem[] {
  if (!key) return [];
  return items.filter((item) => item.comparison_key === key && Number.isFinite(Date.parse(item.created_at)))
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}

interface SummarySource {
  task?: { name?: string };
  agent?: { model?: { model?: string } };
  events?: Array<{ timestamp?: string }>;
  evaluation?: { success?: boolean };
}

export function summarizeEpisode(value: SummarySource): EpisodeHistorySummary {
  return {
    status: 'ready',
    taskName: value.task?.name || '任务未记录',
    modelId: value.agent?.model?.model || '模型未记录',
    timestamp: value.events?.[0]?.timestamp,
    success: typeof value.evaluation?.success === 'boolean' ? value.evaluation.success : undefined,
  };
}
