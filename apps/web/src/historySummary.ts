export interface EpisodeHistorySummary {
  status: 'loading' | 'ready' | 'error';
  taskName?: string;
  modelId?: string;
  timestamp?: string;
  success?: boolean;
}

export interface ExperimentDashboardItem {
  experiment_id: string;
  created_at: string;
  environment_version: string;
  comparison_axis: string;
  total_pairs: number;
  baseline_success_rate: number;
  recovery_success_rate: number;
  baseline_total_tokens: number;
  recovery_total_tokens: number;
  baseline_avg_duration_ms: number;
  recovery_avg_duration_ms: number;
  baseline_total_cost: string | null;
  recovery_total_cost: string | null;
  model_id?: string | null;
  provider?: string | null;
  task_ids?: string[];
  seeds?: number[];
  repeat_count?: number | null;
  scenario?: string | null;
  fault_profile?: string | null;
  comparison_key?: string | null;
  baseline_reference_cost?: string | null;
  recovery_reference_cost?: string | null;
  reference_price_version?: string | null;
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
