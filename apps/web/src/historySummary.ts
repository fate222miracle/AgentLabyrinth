export interface EpisodeHistorySummary {
  status: 'loading' | 'ready' | 'error';
  taskName?: string;
  modelId?: string;
  timestamp?: string;
  success?: boolean;
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
