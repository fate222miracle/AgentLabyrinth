import { useState, useEffect, useRef } from 'react';
import { changedStateFields, groupTraceByStep, keyFields, toolFeedbackFields, stepOutcome, stepTitle } from './traceSteps';
import { ReadableFields, fieldLabels } from './ReadableFields';
import { McpFlowReplay } from './McpFlowReplay';
import { summarizeEpisode, type EpisodeHistorySummary, type ExperimentDashboardItem } from './historySummary';
import { ExperimentDashboard } from './ExperimentDashboard';
import { readEpisodeStream } from './streamEpisode';
import { RequestGeneration } from './requestGeneration';
import { useContentMotion } from './useContentMotion';
import { HistoryReader } from './HistoryReader';
import { EpisodeSummary } from './EpisodeSummary';
import { EpisodeReviewPanel } from './EpisodeReviewPanel';
import { ClassroomScenarios } from './ClassroomScenarios';
import { ExperimentCharts } from './ExperimentCharts';
import { ExperimentReviewSummary } from './ExperimentReviewSummary';
import { MemoryPairReview } from './MemoryPairReview';
import { PlanningPairReview } from './PlanningPairReview';
import { ContextSettings, contextInput, contextLabel, type ContextChoice } from './ContextSettings';
import { metaSchema, dashboardSchema, resumableIdsSchema,
  type TaskOption, type MetaResponse, type TraceEvent, type EpisodeArtifact,
  type PairComparison, type ExperimentArtifact, type ExperimentJobState } from './apiContracts';
import { readApi, readEpisode, readExperiment, readJob, requireOk } from './apiClient';

const bfclDescriptions: Record<string, string> = {
  'bfcl-simple_python_0': '求底边长为 10、高为 5 的三角形面积。',
  'bfcl-simple_python_1': '使用数学函数计算 5 的阶乘。',
  'bfcl-simple_python_2': '已知直角三角形的两条直角边分别为 4 和 5，求斜边长度。',
  'bfcl-simple_python_3': '求二次方程的根，系数为 a=1、b=-3、c=2。',
  'bfcl-simple_python_4': '求解系数为 a=2、b=6、c=5 的二次方程。',
  'bfcl-simple_python_5': '求二次方程的所有根，系数为 a=3、b=-11、c=-4。',
  'bfcl-simple_python_6': '求系数为 a=2、b=5、c=3 的二次方程的根。',
  'bfcl-simple_python_7': '求半径为 4 英寸的圆的周长。',
  'bfcl-simple_java_6': '刷新数据库表格视图的元数据、追加已有数据，并保留当前状态。',
  'bfcl-simple_java_18': '查询系统角色数量的第 3 页，每页 20 条。',
  'bfcl-simple_java_53': '构造谓词：判断 Join 是否为完整主节点，且状态早于本地接受的任期 42、版本 7。',
  'bfcl-simple_java_74': '在 XML 序列化中处理高代理值 55357、低代理值 56832；内容不在 CDATA 内。',
  'bfcl-simple_java_76': '以宽 800、高 600 的尺寸更新开场动画画面。',
};

const taskCategoryLabels: Record<string, string> = {
  tool_selection: '工具选择',
  parameter_generation: '参数生成',
  multi_step_planning: '多步规划',
  evidence_chain: '跨文档证据链 · 自建仿真',
  error_recovery: '错误恢复',
  bfcl_single_call: '单次函数调用',
};

function taskDescription(task: TaskOption): string {
  return task.suite !== 'tool_lab_core' ? bfclDescriptions[task.id] ?? task.description : task.description;
}

const experimentJobLabels: Record<ExperimentJobState['status'], string> = {
  queued: '排队中', running: '运行中', paused: '已暂停', cancelled: '已取消',
  completed: '已完成', failed: '运行失败', interrupted: '进程中断',
};

function explainFailure(detail: string): string {
  const explanations: Record<string, string> = {
    RATE_LIMIT_EXCEEDED: '供应商限流：稍后再试，并检查账号当日配额。',
    AUTHENTICATION_FAILED: '后端 API Key 缺失、失效或认证失败。',
    MODEL_NOT_FOUND: '供应商返回 404：模型不存在或当前账号不可访问。',
    MODEL_RETIRED: '供应商已下线该模型，请选择其他模型。',
    UPSTREAM_CHANNEL_UNAVAILABLE: '供应商暂无可用通道，请稍后重试或手动换模型。',
    UPSTREAM_GATEWAY_ERROR: '供应商网关错误，请稍后再试。',
    NETWORK_CONNECTION_FAILED: '后端无法连接模型网关，请检查网络。',
    REQUEST_TIMEOUT: '模型请求超时。',
    OUTPUT_TRUNCATED: '模型输出达到单次上限，未形成完整行动。',
    INVALID_ARGUMENTS: '工具参数不符合 schema；Baseline 会终止，Recovery 最多纠错一次。',
    task_token_budget_exceeded: '累计输入与输出超出任务 Token 预算，可在运行前显式调整。',
    max_execution_time_exceeded: '本次运行已达到总时限，停止后续调用并保留已完成状态。',
    upstream_usage_unknown: '本次运行已达到总时限；在途模型请求的最终用量未知，不会自动重试。',
    missing_submission: '模型只返回文本，未调用工具完成提交。',
  };
  const parts = detail.split(': ');
  const code = parts[parts.length - 1] ?? detail;
  return explanations[code] ? `${explanations[code]} (${code})` : detail;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function snapshotAt(
  artifact: EpisodeArtifact,
  activeEventId: string | undefined,
): { state: Record<string, unknown> | null; source: string } {
  let state: Record<string, unknown> | null = null;
  let source = '尚无环境快照';
  for (const event of artifact.events) {
    if (isRecord(event.payload.initial_state)) {
      state = event.payload.initial_state;
      source = '初始状态';
    }
    if (isRecord(event.payload.state)) {
      state = event.payload.state;
      source = `Step ${event.step_index} 更新后`;
    }
    if (event.event_id === activeEventId) break;
  }
  const lastEvent = artifact.events[artifact.events.length - 1];
  if (activeEventId === lastEvent?.event_id && isRecord(artifact.episode.final_state)) {
    state = artifact.episode.final_state;
    source = 'Episode 最终状态';
  }
  return { state, source };
}

function downloadFile(filename: string, content: string, contentType: string): void {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadJson(filename: string, value: unknown): void {
  downloadFile(filename, `${JSON.stringify(value, null, 2)}\n`, 'application/json;charset=utf-8');
}

function csvCell(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) return '';
  const raw = String(value);
  // Task names and labels can eventually come from external suites; prevent spreadsheet formulas.
  const safe = typeof value === 'string' && /^[\s\u0000-\u001f]*[=+\-@]/.test(raw) ? `'${raw}` : raw;
  return `"${safe.replace(/"/g, '""')}"`;
}

function experimentCsv(experiment: ExperimentArtifact): string {
  const headers = [
    'experiment_id', 'config_hash', 'comparison_axis', 'task_id', 'seed', 'repeat_index',
    'arm', 'episode_id', 'success', 'termination_reason', 'steps', 'model_calls',
    'tool_calls', 'tokens', 'duration_ms', 'cost_usd', 'official_reference_cost_usd', 'tool_selection_accuracy',
    'tool_argument_validity_rate', 'pair_retry_eligible', 'pair_recovered', 'context_mode', 'context_max_tool_rounds',
    'model_id', 'provider', 'task_name',
    'context_algorithm_version', 'context_memory_max_bytes',
    'tool_call_mode', 'runtime_version', 'planning_algorithm_version',
  ];
  const axis = typeof experiment.config.comparison_axis === 'string'
    ? experiment.config.comparison_axis : 'recovery_policy';
  const savedModel = typeof experiment.config.model === 'string'
    ? experiment.config.model : experiment.config.model?.model;
  const savedCallMode = typeof experiment.config.model === 'object' ? experiment.config.model?.tool_call_mode ?? 'single' : 'single';
  type CsvValue = string | number | boolean | null | undefined;
  const rows = experiment.pairs.flatMap((pair): CsvValue[][] => [
    [experiment.experiment_id, experiment.config_hash, axis, pair.task_id, pair.seed,
      pair.repeat_index ?? 1, axis === 'context_policy' ? 'full' : axis === 'memory_ablation' ? 'recent_window' : axis === 'planning' ? 'no_plan' : axis === 'runtime_backend' ? 'reference' : 'baseline',
      pair.baseline_episode_id, pair.baseline_success,
      pair.baseline_termination_reason, pair.baseline_steps, pair.baseline_model_calls,
      pair.baseline_tool_calls, pair.baseline_tokens, pair.baseline_duration_ms,
      pair.baseline_cost, pair.baseline_reference_cost, pair.baseline_tool_selection_accuracy,
      pair.baseline_tool_argument_validity_rate,
      axis !== 'recovery_policy' ? null : pair.retry_eligible,
      axis !== 'recovery_policy' ? null : pair.recovered,
      experiment.config.baseline_agent?.context_policy?.mode, experiment.config.baseline_agent?.context_policy?.max_tool_rounds,
      savedModel, experiment.config.provider, pair.task_name,
      experiment.config.baseline_agent?.context_policy?.algorithm_version, experiment.config.baseline_agent?.context_policy?.memory_max_bytes, savedCallMode,
      experiment.config.baseline_agent?.runtime_version,
      experiment.config.baseline_agent?.planning?.algorithm_version],
    [experiment.experiment_id, experiment.config_hash, axis, pair.task_id, pair.seed,
      pair.repeat_index ?? 1, axis === 'context_policy' ? 'recent_tool_rounds' : axis === 'memory_ablation' ? 'recent_window_with_memory' : axis === 'planning' ? 'declared_plan' : axis === 'runtime_backend' ? experiment.config.recovery_agent?.runtime_backend ?? 'langgraph' : 'recovery',
      pair.recovery_episode_id, pair.recovery_success,
      pair.recovery_termination_reason, pair.recovery_steps, pair.recovery_model_calls,
      pair.recovery_tool_calls, pair.recovery_tokens, pair.recovery_duration_ms,
      pair.recovery_cost, pair.recovery_reference_cost, pair.recovery_tool_selection_accuracy,
      pair.recovery_tool_argument_validity_rate,
      axis !== 'recovery_policy' ? null : pair.retry_eligible,
      axis !== 'recovery_policy' ? null : pair.recovered,
      experiment.config.recovery_agent?.context_policy?.mode, experiment.config.recovery_agent?.context_policy?.max_tool_rounds,
      savedModel, experiment.config.provider, pair.task_name,
      experiment.config.recovery_agent?.context_policy?.algorithm_version, experiment.config.recovery_agent?.context_policy?.memory_max_bytes, savedCallMode,
      experiment.config.recovery_agent?.runtime_version,
      experiment.config.recovery_agent?.planning?.algorithm_version],
  ]);
  return `\uFEFF${[headers, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n')}\r\n`;
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  EPISODE_STARTED: '运行开始',
  OBSERVATION_CREATED: '初始观察',
  MODEL_REQUESTED: '请求模型',
  MODEL_RESPONDED: '模型返回',
  TOOL_CALL_PROPOSED: '提议工具调用',
  TOOL_CALL_VALIDATED: '校验工具调用',
  TOOL_STARTED: '开始执行工具',
  TOOL_SUCCEEDED: '工具执行成功',
  TOOL_FAILED: '工具执行失败',
  ENVIRONMENT_UPDATED: '环境状态更新',
  PLAN_UPDATED: '更新计划声明',
  EPISODE_RESUMED: '从存档恢复',
  EPISODE_FINISHED: '运行结束',
};

function formatEventTypeLabel(eventType: string): string {
  return EVENT_TYPE_LABELS[eventType] ?? eventType;
}

function formatSigned(value: number): string {
  return value > 0 ? `+${value}` : String(value);
}

function parseSeedList(value: string): number[] | null {
  const parts = value.split(',').map((part) => part.trim());
  if (parts.length === 0 || parts.length > 10 || parts.some((part) => part === '')) return null;
  const seeds = parts.map(Number);
  if (seeds.some((seed) => !Number.isSafeInteger(seed))) return null;
  return new Set(seeds).size === seeds.length ? seeds : null;
}

function comparisonLabel(pair: PairComparison, axis: 'recovery_policy' | 'runtime_backend' | 'context_policy' | 'memory_ablation' | 'planning'): string {
  if (axis === 'planning') {
    if (pair.baseline_success && pair.recovery_success) return '有无声明均通过';
    if (!pair.baseline_success && !pair.recovery_success) return '有无声明均未通过';
    return pair.baseline_success ? '仅无声明通过' : '仅声明计划通过';
  }
  if (axis === 'context_policy') {
    if (pair.baseline_success && pair.recovery_success) return '两种上下文均通过';
    if (!pair.baseline_success && !pair.recovery_success) return '两种上下文均未通过';
    return pair.baseline_success ? '仅完整历史通过' : '仅最近轮次通过';
  }
  if (axis === 'memory_ablation') {
    if (pair.baseline_success && pair.recovery_success) return '有无记忆均通过';
    if (!pair.baseline_success && !pair.recovery_success) return '有无记忆均未通过';
    return pair.baseline_success ? '仅无记忆窗口通过' : '仅带记忆窗口通过';
  }
  if (axis === 'runtime_backend') {
    if (pair.baseline_success && pair.recovery_success) return '两种 Runtime 均通过';
    if (!pair.baseline_success && !pair.recovery_success) return '两种 Runtime 均未通过';
    return pair.baseline_success ? 'Reference 通过' : '外部框架通过';
  }
  if (pair.recovered) return '挽救成功 (RECOVERED)';
  if (pair.baseline_success && pair.recovery_success) return '两组均通过 (TIED)';
  if (!pair.baseline_success && !pair.recovery_success) return '两组均未通过';
  if (pair.baseline_success) return 'Recovery 回退';
  return 'Recovery 通过（未确认挽救）';
}

async function copyTextToClipboard(value: string, label: string): Promise<string> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
      return `${label} 已复制`;
    }

    const textarea = document.createElement('textarea');
    textarea.value = value;
    textarea.setAttribute('readonly', 'true');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    if (!document.execCommand('copy')) throw new Error('copy command failed');
    document.body.removeChild(textarea);
    return `${label} 已复制`;
  } catch {
    return '复制失败：当前浏览器未授予剪贴板权限';
  }
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'single' | 'experiment'>('experiment');
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [metadataError, setMetadataError] = useState<string | null>(null);

  // Single Episode states
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedScenario, setSelectedScenario] = useState<string>('success');
  const [singleFaultProfile, setSingleFaultProfile] = useState<string>('none');
  const [selectedSingleTask, setSelectedSingleTask] = useState<string>('');
  const [selectedSuite, setSelectedSuite] = useState<TaskOption['suite']>('tool_lab_core');
  const [singleTaskQuery, setSingleTaskQuery] = useState('');
  const [maxSteps, setMaxSteps] = useState<number>(6);
  const [artifact, setArtifact] = useState<EpisodeArtifact | null>(null);
  const [liveRun, setLiveRun] = useState<{
    events: TraceEvent[]; episodeId: string | null; model: string;
    environmentVersion: string; status: 'running' | 'interrupted' | 'completed';
  } | null>(null);
  const [recentEpisodeIds, setRecentEpisodeIds] = useState<string[]>([]);
  const [episodeHistorySummaries, setEpisodeHistorySummaries] = useState<
    Record<string, EpisodeHistorySummary>
  >({});
  const [resumableEpisodeIds, setResumableEpisodeIds] = useState<string[]>([]);
  const [recoveryListError, setRecoveryListError] = useState(false);
  const [inputEpisodeId, setInputEpisodeId] = useState<string>('');
  const [expandedEvents, setExpandedEvents] = useState<Record<string, boolean>>({});
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('ALL');
  const [replayIndex, setReplayIndex] = useState<number>(0);
  const [replayPlaying, setReplayPlaying] = useState<boolean>(false);
  const [replaySpeedMs, setReplaySpeedMs] = useState<number>(1000);
  const [replayView, setReplayView] = useState<'flow' | 'story' | 'events'>('flow');
  const mainMotionRef = useRef<HTMLElement>(null);
  const tracePanelRef = useRef<HTMLElement>(null);
  const replayMotionRef = useRef<HTMLDivElement>(null);
  useContentMotion(mainMotionRef, activeTab, activeTab === 'single' ? 1 : 0);
  useContentMotion(replayMotionRef,
    activeTab === 'single' ? `${artifact?.episode.episode_id ?? ''}:${replayView}` : '',
    replayView === 'flow' ? 0 : replayView === 'story' ? 1 : 2);
  const storyStageRef = useRef<HTMLDivElement>(null);

  // Experiment states
  const [expModel, setExpModel] = useState<string>('');
  const [expScenario, setExpScenario] = useState<string>('invalid-then-success');
  const [expFaultProfile, setExpFaultProfile] = useState<string>('none');
  const [contextWindow, setContextWindow] = useState(2);
  const [contextChoice, setContextChoice] = useState<ContextChoice>('window');
  const [memoryBytes, setMemoryBytes] = useState(8192);
  const [memoryAxisWindow, setMemoryAxisWindow] = useState(1);
  const [memoryAxisBytes, setMemoryAxisBytes] = useState(8192);
  const [singleContextChoice, setSingleContextChoice] = useState<ContextChoice>('full');
  const [singlePlanning, setSinglePlanning] = useState(false);
  const [singleContextWindow, setSingleContextWindow] = useState(2);
  const [singleMemoryBytes, setSingleMemoryBytes] = useState(8192);
  const [comparisonAxis, setComparisonAxis] = useState<'recovery_policy' | 'runtime_backend' | 'context_policy' | 'memory_ablation' | 'planning'>('recovery_policy');
  const [expRuntimeBackend, setExpRuntimeBackend] = useState<'handwritten' | 'langgraph'>('handwritten');
  const [expRuntimeTarget, setExpRuntimeTarget] = useState<'langgraph' | 'pydantic_ai'>('langgraph');
  const [expRuntimeStrategy, setExpRuntimeStrategy] = useState<'handwritten' | 'handwritten_recovery'>('handwritten_recovery');
  const [singleRuntimeBackend, setSingleRuntimeBackend] = useState<'handwritten' | 'langgraph' | 'pydantic_ai'>('handwritten');
  const [singleCallMode, setSingleCallMode] = useState<'single' | 'serial'>('serial');
  const [expCallMode, setExpCallMode] = useState<'single' | 'serial'>('serial');
  const [singleToolTransport, setSingleToolTransport] = useState<'local' | 'mcp'>('local');
  const [singleRuntimeStrategy, setSingleRuntimeStrategy] = useState<'handwritten' | 'handwritten_recovery'>('handwritten');
  const [expTasks, setExpTasks] = useState<string[]>([]);
  const [expSeedsText, setExpSeedsText] = useState<string>('1');
  const [expRepeatCount, setExpRepeatCount] = useState<number>(1);
  const [expTokenBudget, setExpTokenBudget] = useState<number | null>(8000);
  const [expReferenceBudget, setExpReferenceBudget] = useState<string>('');
  const [expGlobalTokenBudget, setExpGlobalTokenBudget] = useState<string>('16000');
  const [singleTokenBudget, setSingleTokenBudget] = useState<number | null>(8000);
  const [executionSeconds, setExecutionSeconds] = useState(300);
  const [expExecutionSeconds, setExpExecutionSeconds] = useState(300);
  const [loadingActivity, setLoadingActivity] = useState<'run' | 'history'>('run');
  const [experiment, setExperiment] = useState<ExperimentArtifact | null>(null);
  const [recentExpIds, setRecentExpIds] = useState<string[]>([]);
  const [resumableExpIds, setResumableExpIds] = useState<string[]>([]);
  const [resumableJobIds, setResumableJobIds] = useState<string[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [experimentJob, setExperimentJob] = useState<ExperimentJobState | null>(null);
  const [jobWatchToken, setJobWatchToken] = useState(0);
  const [dashboardItems, setDashboardItems] = useState<ExperimentDashboardItem[]>([]);
  const [dashboardSkipped, setDashboardSkipped] = useState(0);
  const [dashboardError, setDashboardError] = useState(false);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const dashboardRequestRef = useRef<AbortController | null>(null);
  useEffect(() => () => dashboardRequestRef.current?.abort(), []);
  const [inputExpId, setInputExpId] = useState<string>('');

  // Global loading & error
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [loadingMessage, setLoadingMessage] = useState<string>('');
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copyNotice, setCopyNotice] = useState<string | null>(null);
  const metadataRequests = useRef(new RequestGeneration());
  const pageRequests = useRef(new RequestGeneration());
  const jobControlRequests = useRef(new RequestGeneration());

  useEffect(() => {
    if (!copyNotice) return;
    const timer = window.setTimeout(() => setCopyNotice(null), 1400);
    return () => window.clearTimeout(timer);
  }, [copyNotice]);

  useEffect(() => {
    if (!isLoading) return;
    const startedAt = Date.now();
    setElapsedSeconds(0);
    const timer = window.setInterval(
      () => setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [isLoading]);

  const beginLoading = (message: string, activity: 'run' | 'history' = 'run') => {
    setLoadingActivity(activity);
    setLoadingMessage(message);
    setIsLoading(true);
  };

  const finishLoading = () => {
    setIsLoading(false);
    setLoadingMessage('');
  };

  const switchTab = (next: 'single' | 'experiment') => {
    if (next === activeTab || (isLoading && loadingActivity === 'run' && !activeJobId)) return;
    pageRequests.current.begin();
    if (loadingActivity === 'history') finishLoading();
    setErrorMsg(null);
    setActiveTab(next);
    const url = new URL(window.location.href);
    url.searchParams.delete('episode_id');
    url.searchParams.delete('experiment_id');
    url.searchParams.delete('experiment_job_id');
    url.searchParams.delete('mode');
    if (next === 'single' && artifact) url.searchParams.set('episode_id', artifact.episode.episode_id);
    else if (next === 'single') url.searchParams.set('mode', 'single');
    if (next === 'experiment') {
      if (activeJobId) url.searchParams.set('experiment_job_id', activeJobId);
      else if (experiment) url.searchParams.set('experiment_id', experiment.experiment_id);
    }
    window.history.pushState({}, '', url.toString());
  };

  useEffect(() => {
    if (!activeJobId) return;
    let cancelled = false;
    let timer = 0;
    beginLoading('实验运行中；暂停与取消将在当前 Episode 结束后生效。');
    const poll = async () => {
      try {
        const response = await fetch(`/api/v1/experiments/jobs/${encodeURIComponent(activeJobId)}`);
        const job = await readJob(response, activeJobId);
        if (cancelled) return;
        setExperimentJob(job);
        if (job.status === 'completed') {
          const result = await fetch(`/api/v1/experiments/${encodeURIComponent(activeJobId)}`);
          const data = await readExperiment(result, activeJobId);
          if (cancelled) return;
          setExperiment(data.experiment);
          addRecentExpId(activeJobId);
          setResumableJobIds((ids) => ids.filter((id) => id !== activeJobId));
          refreshExperimentDashboard();
          const url = new URL(window.location.href);
          if (url.searchParams.get('experiment_job_id') === activeJobId) {
            url.searchParams.set('experiment_id', activeJobId);
            url.searchParams.delete('experiment_job_id');
            url.searchParams.delete('mode');
            window.history.replaceState({}, '', url.toString());
          }
          setActiveJobId(null);
          finishLoading();
        } else if (['paused', 'cancelled', 'failed', 'interrupted'].includes(job.status)) {
          finishLoading();
          if (job.status === 'paused' || job.status === 'interrupted') {
            setResumableJobIds((ids) => ids.includes(activeJobId) ? ids : [activeJobId, ...ids]);
          } else {
            setResumableJobIds((ids) => ids.filter((id) => id !== activeJobId));
          }
          if (job.status === 'failed') {
            const budgetErrors: Record<string, string> = {
              REFERENCE_COST_BUDGET_EXCEEDED: '已达到原厂标价参考预算；已完成的 Episode 已保存。若要提高预算，请创建新实验。',
              EXPERIMENT_TOKEN_BUDGET_EXCEEDED: '已达到整场实验 Token 预算，后续运行已停止；已完成的 Episode 已保存。提高预算须创建新实验。',
              EXPERIMENT_TOKEN_USAGE_UNKNOWN: '存在未报告或不一致的模型用量，已停止后续运行；已保存记录保留，不能按零继续累计。',
            };
            setErrorMsg(budgetErrors[job.error_code ?? ''] ?? '实验执行失败，已完成的 Episode 仍保留；请检查错误后创建新实验。');
          }
        } else {
          timer = window.setTimeout(poll, 900);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMsg(error instanceof Error ? error.message : '实验状态读取失败');
          finishLoading();
        }
      }
    };
    void poll();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [activeJobId, jobWatchToken]);

  const refreshExperimentDashboard = () => {
    dashboardRequestRef.current?.abort();
    const controller = new AbortController();
    dashboardRequestRef.current = controller;
    setDashboardLoading(true);
    fetch('/api/v1/experiments', { signal: controller.signal })
      .then((res) => {
        return readApi(res, dashboardSchema);
      })
      .then((data) => {
        if (controller.signal.aborted) return;
        setDashboardItems(data.items);
        setDashboardSkipped(data.skipped_count);
        setDashboardError(false);
      })
      .catch(() => { if (!controller.signal.aborted) setDashboardError(true); })
      .finally(() => { if (!controller.signal.aborted) setDashboardLoading(false); });
  };

  const loadMetadata = async (initialize = false) => {
    const metadataRequestId = metadataRequests.current.begin();
    const initializeDefaults = initialize || meta === null;
    setMetadataLoading(true);
    setMetadataError(null);
    try {
      const data = await readApi(await fetch('/api/v1/meta'), metaSchema);
      if (!metadataRequests.current.isCurrent(metadataRequestId)) return;
      setMeta(data);
      const initialModel = data.models.find(model => model.provider === 'fake')?.id ?? '';
      setSelectedModel((current) => !initializeDefaults && data.models.some((model) => model.id === current) ? current : initialModel);
      setExpModel((current) => !initializeDefaults && data.models.some((model) => model.id === current) ? current : initialModel);
      if (initializeDefaults && data.tasks.length > 0) {
        const initialTask = data.tasks.find((task) => task.id === data.default_task)
          ?? data.tasks.find((task) => task.suite === 'tool_lab_core') ?? data.tasks[0];
        setSelectedSuite(initialTask.suite);
        setSelectedSingleTask(initialTask.id);
        const initialExperimentTask = initialTask.suite === 'tool_lab_core' && initialTask.category !== 'evidence_chain'
          ? initialTask : data.tasks.find(task => task.suite === 'tool_lab_core' && task.category !== 'evidence_chain');
        setExpTasks(initialExperimentTask ? [initialExperimentTask.id] : []);
      }
    } catch (err: unknown) {
      if (metadataRequests.current.isCurrent(metadataRequestId)) setMetadataError(err instanceof Error ? err.message : '目录读取失败');
    } finally {
      if (metadataRequests.current.isCurrent(metadataRequestId)) setMetadataLoading(false);
    }
  };

  // 1. Fetch Metadata and parse initial query parameters
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const expId = params.get('experiment_id');
    const epId = params.get('episode_id');
    const jobId = params.get('experiment_job_id');

    void loadMetadata(true);
    fetch('/api/v1/episodes/resumable')
      .then((res) => readApi(res, resumableIdsSchema))
      .then((ids: string[]) => setResumableEpisodeIds(ids))
      .catch(() => { setResumableEpisodeIds([]); setRecoveryListError(true); });
    fetch('/api/v1/experiments/resumable')
      .then((res) => readApi(res, resumableIdsSchema))
      .then((ids: string[]) => setResumableExpIds(ids))
      .catch(() => { setResumableExpIds([]); setRecoveryListError(true); });
    fetch('/api/v1/experiments/jobs/resumable')
      .then((res) => readApi(res, resumableIdsSchema))
      .then((ids: string[]) => setResumableJobIds(ids))
      .catch(() => { setResumableJobIds([]); setRecoveryListError(true); });
    refreshExperimentDashboard();

    // Load recent history from localStorage
    try {
      const readList = (key: string): string[] => {
        const value: unknown = JSON.parse(localStorage.getItem(key) ?? '[]');
        return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
      };
      setRecentEpisodeIds(readList('al_recent_episodes').slice(0, 5));
      setRecentExpIds(readList('al_recent_experiments').slice(0, 5));
    } catch {
      // ignore storage error
    }

    if (jobId) {
      setActiveTab('experiment');
      setActiveJobId(jobId);
    } else if (expId) {
      setActiveTab('experiment');
      loadExperimentById(expId, false);
    } else if (epId) {
      setActiveTab('single');
      loadEpisodeById(epId, false);
    } else if (params.get('mode') === 'single') {
      setActiveTab('single');
    }

    const handlePopState = () => {
      const next = new URLSearchParams(window.location.search);
      const nextExpId = next.get('experiment_id');
      const nextEpId = next.get('episode_id');
      const nextJobId = next.get('experiment_job_id');
      if (nextJobId) {
        pageRequests.current.begin();
        setActiveTab('experiment');
        setActiveJobId(nextJobId);
        setExperiment(null);
        setJobWatchToken((value) => value + 1);
      } else if (nextExpId) {
        setActiveJobId(null);
        setActiveTab('experiment');
        loadExperimentById(nextExpId, false);
      } else if (nextEpId) {
        setActiveJobId(null);
        setActiveTab('single');
        loadEpisodeById(nextEpId, false);
      } else {
        setActiveJobId(null);
        setActiveTab(next.get('mode') === 'single' ? 'single' : 'experiment');
        pageRequests.current.begin();
        setExperiment(null);
        setArtifact(null);
        setLiveRun(null);
        setErrorMsg(null);
        finishLoading();
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    setReplayPlaying(false);
    setEventTypeFilter('ALL');
    setReplayIndex(0);
    setExpandedEvents({});
  }, [artifact?.episode.episode_id]);

  useEffect(() => {
    let cancelled = false;
    setEpisodeHistorySummaries(Object.fromEntries(
      recentEpisodeIds.map((id) => [id, { status: 'loading' } satisfies EpisodeHistorySummary]),
    ));

    const loadSummaries = async () => {
      const entries = await Promise.all(recentEpisodeIds.map(async (id) => {
        if (artifact?.episode.episode_id === id) {
          return [id, summarizeEpisode(artifact)] as const;
        }
        try {
          const response = await fetch(`/api/v1/episodes/${encodeURIComponent(id)}`);
          const data = await readEpisode(response, id);
          return [id, summarizeEpisode(data.artifact)] as const;
        } catch {
          return [id, { status: 'error' } satisfies EpisodeHistorySummary] as const;
        }
      }));
      if (!cancelled) setEpisodeHistorySummaries(Object.fromEntries(entries));
    };

    void loadSummaries();
    return () => { cancelled = true; };
  }, [recentEpisodeIds, artifact]);

  useEffect(() => {
    setReplayPlaying(false);
  }, [activeTab]);

  const addRecentEpisodeId = (id: string) => {
    setRecentEpisodeIds((prev) => {
      const next = [id, ...prev.filter((item) => item !== id)].slice(0, 5);
      try {
        localStorage.setItem('al_recent_episodes', JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  const addRecentExpId = (id: string) => {
    setRecentExpIds((prev) => {
      const next = [id, ...prev.filter((item) => item !== id)].slice(0, 5);
      try {
        localStorage.setItem('al_recent_experiments', JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  // Load an existing episode by ID
  const loadEpisodeById = async (id: string, updateUrl = true) => {
    if (!id || id.trim().length === 0) return;
    setActiveJobId(null);
    const requestId = pageRequests.current.begin();
    setLiveRun(null);
    beginLoading('正在读取历史 Episode。', 'history');
    setErrorMsg(null);
    setArtifact(null);
    if (updateUrl) {
      const url = new URL(window.location.href);
      url.searchParams.set('episode_id', id.trim());
      url.searchParams.delete('mode');
      url.searchParams.delete('experiment_id');
      url.searchParams.delete('experiment_job_id');
      window.history.pushState({}, '', url.toString());
    }
    try {
      const res = await fetch(`/api/v1/episodes/${encodeURIComponent(id.trim())}`);
      const data = await readEpisode(res, id);
      if (!pageRequests.current.isCurrent(requestId)) return;
      setArtifact(data.artifact);
      addRecentEpisodeId(id.trim());

    } catch (err: unknown) {
      if (!pageRequests.current.isCurrent(requestId)) return;
      const message = err instanceof Error ? err.message : '加载失败';
      setErrorMsg(message);
    } finally {
      if (pageRequests.current.isCurrent(requestId)) finishLoading();
    }
  };

  // Load an existing experiment by ID
  const loadExperimentById = async (id: string, updateUrl = true) => {
    if (!id || id.trim().length === 0) return;
    setActiveJobId(null);
    const requestId = pageRequests.current.begin();
    setLiveRun(null);
    beginLoading('正在读取历史对照实验。', 'history');
    setErrorMsg(null);
    setExperiment(null);
    if (updateUrl) {
      const url = new URL(window.location.href);
      url.searchParams.set('experiment_id', id.trim());
      url.searchParams.delete('mode');
      url.searchParams.delete('episode_id');
      url.searchParams.delete('experiment_job_id');
      window.history.pushState({}, '', url.toString());
    }
    try {
      const res = await fetch(`/api/v1/experiments/${encodeURIComponent(id.trim())}`);
      const data = await readExperiment(res, id);
      if (!pageRequests.current.isCurrent(requestId)) return;
      setExperiment(data.experiment);
      addRecentExpId(id.trim());

    } catch (err: unknown) {
      if (!pageRequests.current.isCurrent(requestId)) return;
      const message = err instanceof Error ? err.message : '加载实验失败';
      setErrorMsg(message);
    } finally {
      if (pageRequests.current.isCurrent(requestId)) finishLoading();
    }
  };

  // Execute single episode
  const handleRunEpisode = async () => {
    const requestId = pageRequests.current.begin();
    beginLoading('正在运行，Trace 节点会随事件出现。');
    setErrorMsg(null);
    setArtifact(null);
    const runningUrl = new URL(window.location.href);
    runningUrl.searchParams.delete('episode_id');
    runningUrl.searchParams.delete('experiment_id');
    window.history.pushState({}, '', runningUrl.toString());
    setLiveRun({ events: [], episodeId: null, model: selectedModel,
      environmentVersion: selectedSuite !== 'tool_lab_core' ? 'bfcl-adapted-single-call-v1'
        : selectedSingleTaskMeta?.supports_mcp && singleToolTransport === 'mcp' ? 'tool-lab-mcp-v1' : 'tool-lab-m0-v1',
      status: 'running' });
    requestAnimationFrame(() => {
      if (!pageRequests.current.isCurrent(requestId)) return;
      tracePanelRef.current?.focus({ preventScroll: true });
      tracePanelRef.current?.scrollIntoView({ block: 'start' });
    });
    try {
      const currentModelObj = meta?.models.find((m) => m.id === selectedModel);
      const isFake = selectedModel === 'fake' || currentModelObj?.provider === 'fake';

      const payload = {
        schema_version: singleRuntimeBackend === 'pydantic_ai'
          ? '1.7'
          : singlePlanning && selectedSingleTaskMeta?.supports_planning ? '1.6' : '1.5',
        ...(singlePlanning && selectedSingleTaskMeta?.supports_planning
          ? { planning: { schema_version: '1.0', algorithm_version: 'plan-update-v1' } } : {}),
        tool_call_mode: selectedSuite === 'tool_lab_core' ? singleCallMode : 'single',
        ...(singleContextChoice !== 'full' ? { context_policy: contextInput(singleContextChoice, singleContextWindow, singleMemoryBytes) } : {}),
        provider: isFake ? 'fake' : 'aihubmix',
        model: isFake ? 'fake-model' : selectedModel,
        scenario: isFake ? selectedScenario : null,
        task_id: selectedSingleTask,
        suite: selectedSuite,
        max_steps: maxSteps,
        max_execution_time_ms: executionSeconds * 1000,
        token_budget: isFake ? null : singleTokenBudget,
        runtime_backend: singleRuntimeBackend,
        runtime_strategy: singleRuntimeStrategy,
        tool_transport: selectedSingleTaskMeta?.supports_mcp
          ? singleToolTransport : 'local',
        fault_profile: isFake && selectedSuite === 'tool_lab_core'
          ? singleToolTransport === 'mcp'
            ? singleFaultProfile === 'mcp_disconnect' ? 'mcp_disconnect' : 'none'
            : singleFaultProfile === 'mcp_disconnect' ? 'none' : singleFaultProfile
          : 'none',
      };

      const res = await fetch('/api/v1/episodes/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      await requireOk(res);
      const data = await readEpisodeStream(res, (event) => {
        if (!pageRequests.current.isCurrent(requestId)) return;
        setLiveRun((current) => current ? { ...current, episodeId: event.episode_id,
          events: [...current.events, event] } : current);
      });
      if (!pageRequests.current.isCurrent(requestId)) return;
      const newArtifact = data.artifact;
      setArtifact(newArtifact);
      setLiveRun((current) => current ? { ...current, events: newArtifact.events,
        model: newArtifact.agent.model.model,
        environmentVersion: newArtifact.run_config.environment_version ?? current.environmentVersion,
        episodeId: newArtifact.episode.episode_id, status: 'completed' } : current);
      addRecentEpisodeId(newArtifact.episode.episode_id);

      const url = new URL(window.location.href);
      url.searchParams.set('episode_id', newArtifact.episode.episode_id);
      url.searchParams.delete('mode');
      url.searchParams.delete('experiment_id');
      window.history.replaceState({}, '', url.toString());
    } catch (err: unknown) {
      if (!pageRequests.current.isCurrent(requestId)) return;
      const message = err instanceof Error ? err.message : '运行失败';
      setErrorMsg(message);
      setLiveRun((current) => current ? { ...current, status: 'interrupted' } : current);
      fetch('/api/v1/episodes/resumable')
        .then((res) => readApi(res, resumableIdsSchema))
        .then((ids: string[]) => setResumableEpisodeIds(ids))
        .catch(() => setRecoveryListError(true));
    } finally {
      if (pageRequests.current.isCurrent(requestId)) finishLoading();
    }
  };

  const handleResumeEpisode = async (id: string) => {
    const requestId = pageRequests.current.begin();
    setLiveRun(null);
    beginLoading('正在从最近存档恢复 Episode。');
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/v1/episodes/${encodeURIComponent(id)}/resume`, {
        method: 'POST',
      });
      const data = await readEpisode(res, id);
      if (!pageRequests.current.isCurrent(requestId)) return;
      setArtifact(data.artifact);
      setResumableEpisodeIds((previous) => previous.filter((item) => item !== id));
      addRecentEpisodeId(id);
      const url = new URL(window.location.href);
      url.searchParams.set('episode_id', id);
      url.searchParams.delete('mode');
      url.searchParams.delete('experiment_id');
      window.history.pushState({}, '', url.toString());
    } catch (err: unknown) {
      if (!pageRequests.current.isCurrent(requestId)) return;
      setErrorMsg(err instanceof Error ? err.message : '恢复失败');
    } finally {
      if (pageRequests.current.isCurrent(requestId)) finishLoading();
    }
  };

  // Execute paired experiment
  const handleResumeExperiment = async (id: string) => {
    const requestId = pageRequests.current.begin();
    beginLoading('正在恢复原实验，已完成的 Episode 会直接复用。');
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/v1/experiments/${encodeURIComponent(id)}/resume`, {
        method: 'POST',
      });
      const data = await readExperiment(res, id);
      if (!pageRequests.current.isCurrent(requestId)) return;
      setExperiment(data.experiment);
      refreshExperimentDashboard();
      setResumableExpIds((previous) => previous.filter((item) => item !== id));
      addRecentExpId(id);
      const url = new URL(window.location.href);
      url.searchParams.set('experiment_id', id);
      url.searchParams.delete('mode');
      url.searchParams.delete('episode_id');
      window.history.pushState({}, '', url.toString());
    } catch (err: unknown) {
      if (!pageRequests.current.isCurrent(requestId)) return;
      setErrorMsg(err instanceof Error ? err.message : '实验恢复失败');
    } finally {
      if (pageRequests.current.isCurrent(requestId)) finishLoading();
    }
  };

  const handleRerunFailedEpisode = async () => {
    if (!artifact || artifact.evaluation.success) return;
    const requestId = pageRequests.current.begin();
    const sourceId = artifact.episode.episode_id;
    beginLoading('正在按原始配置单独重跑失败 Episode。');
    setErrorMsg(null);
    try {
      const response = await fetch(`/api/v1/episodes/${encodeURIComponent(sourceId)}/rerun`, {
        method: 'POST',
      });
      const data = await readEpisode(response);
      if (!pageRequests.current.isCurrent(requestId)) return;
      const rerun = data.artifact;
      setArtifact(rerun);
      addRecentEpisodeId(rerun.episode.episode_id);
      const url = new URL(window.location.href);
      url.searchParams.set('episode_id', rerun.episode.episode_id);
      url.searchParams.delete('mode');
      url.searchParams.delete('experiment_id');
      url.searchParams.delete('experiment_job_id');
      window.history.pushState({}, '', url.toString());
    } catch (error) {
      if (!pageRequests.current.isCurrent(requestId)) return;
      setErrorMsg(error instanceof Error ? error.message : '失败 Episode 重跑失败');
    } finally {
      if (pageRequests.current.isCurrent(requestId)) finishLoading();
    }
  };

  const handleRunExperiment = async () => {
    if (expTasks.length === 0) {
      setErrorMsg('请至少选择一个评测任务');
      return;
    }
    const seeds = parseSeedList(expSeedsText);
    if (!seeds) {
      setErrorMsg('Seed 必须是 1–10 个不重复整数，用英文逗号分隔');
      return;
    }
    if (expReferenceBudget !== '' && (!/^\d+(?:\.\d+)?$/.test(expReferenceBudget) || Number(expReferenceBudget) <= 0)) {
      setErrorMsg('原厂标价参考预算必须是正数 USD，或留空');
      return;
    }
    if (expGlobalTokenBudget !== '' && (!/^\d+$/.test(expGlobalTokenBudget)
      || Number(expGlobalTokenBudget) < 1 || Number(expGlobalTokenBudget) > 1_000_000_000)) {
      setErrorMsg('整场实验 Token 预算须为 1–1,000,000,000 的整数，或留空');
      return;
    }
    const episodeCount = expTasks.length * seeds.length * expRepeatCount * 2;
    const requestId = pageRequests.current.begin();
    setActiveJobId(null);
    setExperimentJob(null);
    setExperiment(null);
    beginLoading(`正在串行执行${comparisonAxis === 'context_policy' ? '上下文' : comparisonAxis === 'memory_ablation' ? '工具记忆' : comparisonAxis === 'runtime_backend' ? 'Runtime' : comparisonAxis === 'planning' ? '规划' : '恢复策略'}对照，预计 ${episodeCount} 个 Episode。`);
    setErrorMsg(null);
    let started = false;
    try {
      if (comparisonAxis === 'context_policy' && (!Number.isInteger(contextWindow) || contextWindow < 1 || contextWindow > 100)) {
        throw new Error('上下文窗口须为 1–100 的整数');
      }
      if (comparisonAxis === 'memory_ablation' && (!Number.isInteger(memoryAxisWindow) || memoryAxisWindow < 1 || memoryAxisWindow > 100)) {
        throw new Error('相同窗口轮次须为 1–100 的整数');
      }
      if (comparisonAxis === 'memory_ablation' && (!Number.isInteger(memoryAxisBytes) || memoryAxisBytes < 256 || memoryAxisBytes > 32768)) {
        throw new Error('记忆大小须为 256–32768 的整数字节');
      }
      const currentModelObj = meta?.models.find((m) => m.id === expModel);
      const isFake = expModel === 'fake' || currentModelObj?.provider === 'fake';

      const payload = {
        provider: isFake ? 'fake' : 'aihubmix',
        model: isFake ? 'fake-model' : expModel,
        scenario: isFake ? expScenario : null,
        task_ids: expTasks,
        seeds,
        repeat_count: expRepeatCount,
        token_budget: isFake ? null : expTokenBudget,
        max_total_tokens: expGlobalTokenBudget === '' ? null : Number(expGlobalTokenBudget),
        max_execution_time_ms: expExecutionSeconds * 1000,
        max_reference_cost_usd: isFake || expReferenceBudget === '' ? null : expReferenceBudget,
        comparison_axis: comparisonAxis,
        ...(comparisonAxis === 'context_policy' ? { context_policy: contextInput(contextChoice, contextWindow, memoryBytes) } : {}),
        ...(comparisonAxis === 'memory_ablation' ? { context_policy: contextInput('memory', memoryAxisWindow, memoryAxisBytes) } : {}),
        schema_version: comparisonAxis === 'runtime_backend'
          ? '1.10' : comparisonAxis === 'planning' ? '1.9' : '1.8',
        tool_call_mode: expCallMode,
        runtime_backend: comparisonAxis === 'runtime_backend' ? 'handwritten' : expRuntimeBackend,
        ...(comparisonAxis === 'runtime_backend' ? { runtime_target: expRuntimeTarget } : {}),
        runtime_strategy: expRuntimeStrategy,
        fault_profile: isFake ? expFaultProfile : 'none',
      };

      const res = await fetch('/api/v1/experiments/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const job = await readJob(res);
      if (!pageRequests.current.isCurrent(requestId)) return;
      started = true;
      setExperiment(null);
      setExperimentJob(job);
      setActiveJobId(job.experiment_id);
      setJobWatchToken((value) => value + 1);

      const url = new URL(window.location.href);
      url.searchParams.set('experiment_job_id', job.experiment_id);
      url.searchParams.delete('mode');
      url.searchParams.delete('experiment_id');
      url.searchParams.delete('episode_id');
      window.history.pushState({}, '', url.toString());
    } catch (err: unknown) {
      if (!pageRequests.current.isCurrent(requestId)) return;
      const message = err instanceof Error ? err.message : '对照实验运行失败';
      setErrorMsg(message);
      fetch('/api/v1/experiments/resumable')
        .then((res) => readApi(res, resumableIdsSchema))
        .then((ids: string[]) => setResumableExpIds(ids))
        .catch(() => setRecoveryListError(true));
    } finally {
      if (!started && pageRequests.current.isCurrent(requestId)) finishLoading();
    }
  };

  const handleControlExperimentJob = async (
    action: 'pause' | 'cancel' | 'resume', targetId = activeJobId,
  ) => {
    if (!targetId) return;
    const requestId = action === 'resume'
      ? pageRequests.current.begin() : pageRequests.current.capture();
    const controlId = jobControlRequests.current.begin();
    const ownsPage = () => pageRequests.current.isCurrent(requestId)
      && jobControlRequests.current.isCurrent(controlId);
    let resumed = false;
    if (action === 'resume') {
      setActiveJobId(null);
      setExperimentJob(null);
      beginLoading('正在恢复实验 Job。');
    }
    setErrorMsg(null);
    try {
      const response = await fetch(
        `/api/v1/experiments/jobs/${encodeURIComponent(targetId)}/${action}`,
        { method: 'POST' },
      );
      const data = await readJob(response, targetId);
      if (!ownsPage()) return;
      setExperimentJob(data);
      if (action === 'resume') {
        resumed = true;
        setExperiment(null);
        setActiveJobId(targetId);
        setJobWatchToken((value) => value + 1);
        setResumableJobIds((ids) => ids.filter((id) => id !== targetId));
        const url = new URL(window.location.href);
        url.searchParams.set('experiment_job_id', targetId);
        url.searchParams.delete('mode');
        url.searchParams.delete('experiment_id');
        url.searchParams.delete('episode_id');
        window.history.pushState({}, '', url.toString());
      } else if (data.status === 'cancelled') {
        setResumableJobIds((ids) => ids.filter((id) => id !== targetId));
      }
    } catch (error) {
      if (!ownsPage()) return;
      setErrorMsg(error instanceof Error ? error.message : '实验控制失败');
    } finally {
      if (action === 'resume' && !resumed && ownsPage()) finishLoading();
    }
  };

  const toggleEventExpand = (eventId: string) => {
    setExpandedEvents((prev) => ({ ...prev, [eventId]: !prev[eventId] }));
  };

  const toggleTaskSelection = (taskId: string) => {
    const task = meta?.tasks.find((item) => item.id === taskId);
    if (!expTasks.includes(taskId) && task?.category === 'evidence_chain' && expTokenBudget === 8000) setExpTokenBudget(task.token_budget);
    setExpTasks((prev) =>
      prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId]
    );
  };

  const configureClassroomScenario = (task: TaskOption, target: 'single' | 'experiment') => {
    if (isLoading || metadataLoading || !meta?.tasks.some((item) => item.id === task.id)) return;
    const model = activeTab === 'single' ? selectedModel : expModel;
    if (!meta.models.some((item) => item.id === model)) {
      setErrorMsg('请先选择当前目录中的模型，再配置演示场景');
      return;
    }
    if (target === 'single') {
      setSelectedModel(model);
      setSelectedSuite('tool_lab_core');
      setSelectedSingleTask(task.id);
      setSingleTaskQuery('');
      setMaxSteps(task.max_steps);
      setSingleTokenBudget(task.token_budget);
      setExecutionSeconds(300);
      setSingleRuntimeBackend('langgraph');
      setSingleRuntimeStrategy('handwritten');
      setSingleToolTransport('local');
      setSingleFaultProfile('none');
      setSelectedScenario('success');
      setSingleContextChoice('full');
    } else {
      setExpModel(model);
      setExpTasks([task.id]);
      setComparisonAxis('context_policy');
      setContextWindow(1);
      setContextChoice('window');
      setExpRuntimeBackend('langgraph');
      setExpRuntimeStrategy('handwritten');
      setExpScenario('clean');
      setExpFaultProfile('none');
      setExpSeedsText('1');
      setExpRepeatCount(1);
      setExpTokenBudget(task.token_budget);
      setExpExecutionSeconds(300);
      setExpGlobalTokenBudget(String(task.token_budget * 2));
      setExpReferenceBudget('');
    }
    switchTab(target);
    const launcher = document.querySelector<HTMLDetailsElement>('.classroom-scenarios');
    if (launcher) launcher.open = false;
    requestAnimationFrame(() => {
      const panel = document.getElementById(target === 'single' ? 'config-panel' : 'exp-config-panel');
      const details = panel instanceof HTMLDetailsElement ? panel : panel?.querySelector('details');
      if (details) details.open = true;
      const summary = details?.querySelector('summary');
      summary?.focus({ preventScroll: true });
      summary?.scrollIntoView({ block: 'start' });
    });
  };

  const currentSingleModelMeta = meta?.models.find((m) => m.id === selectedModel);
  const currentExpModelMeta = meta?.models.find((m) => m.id === expModel);
  const experimentTasks = meta?.tasks.filter((task) => task.suite === 'tool_lab_core') ?? [];
  const singleTasks = meta?.tasks.filter((task) => task.suite === selectedSuite) ?? [];
  const filteredSingleTasks = singleTasks.filter((task) => {
    const query = singleTaskQuery.trim().toLocaleLowerCase();
    return !query || `${task.name} ${task.id} ${task.category} ${taskCategoryLabels[task.category] ?? ''} ${task.description} ${taskDescription(task)}`
      .toLocaleLowerCase().includes(query);
  });
  const bfclTaskCount = meta?.tasks.filter((task) => task.suite === 'bfcl_adapted').length ?? 0;
  const selectedSingleTaskMeta = filteredSingleTasks.find((task) => task.id === selectedSingleTask);
  const defaultSingleMaxSteps = selectedSingleTaskMeta?.max_steps ?? (selectedSuite !== 'tool_lab_core' ? 1 : 6);
  const defaultSingleTokenBudget = selectedSingleTaskMeta?.category === 'evidence_chain' ? selectedSingleTaskMeta.token_budget : 8000;
  const singleAdvancedChangeCount = [
    singleRuntimeStrategy !== 'handwritten',
    singleContextChoice !== 'full',
    singlePlanning && Boolean(selectedSingleTaskMeta?.supports_planning),
    singleToolTransport === 'mcp' && Boolean(selectedSingleTaskMeta?.supports_mcp),
    maxSteps !== defaultSingleMaxSteps,
    executionSeconds !== 300,
    selectedModel === 'fake' && selectedScenario !== 'success',
    selectedModel === 'fake' && singleFaultProfile !== 'none',
    selectedModel !== 'fake' && singleTokenBudget !== defaultSingleTokenBudget,
  ].filter(Boolean).length;
  const eventTypes = Array.from(new Set(artifact?.events.map((event) => event.event_type) ?? []));
  const traceSteps = groupTraceByStep(artifact?.events ?? []);
  const visibleEvents = replayView === 'story'
    ? traceSteps.map((group) => group.events[group.events.length - 1])
    : artifact?.events.filter(
        (event) => eventTypeFilter === 'ALL' || event.event_type === eventTypeFilter,
      ) ?? [];
  // One saved event anchors all views; grouped steps never overwrite that position.
  const replayAnchor = artifact?.events[replayIndex];
  const safeReplayIndex = Math.max(0, replayView === 'story'
    ? traceSteps.findIndex((group) => group.events.some((event) => event.event_id === replayAnchor?.event_id))
    : visibleEvents.findIndex((event) => event.event_id === replayAnchor?.event_id));
  const selectReplayIndex = (index: number) => {
    const target = visibleEvents[index];
    if (target && artifact) setReplayIndex(artifact.events.findIndex((event) => event.event_id === target.event_id));
  };
  const activeReplayEvent = visibleEvents[safeReplayIndex];
  const activeStep = replayView === 'story' ? traceSteps[safeReplayIndex] : undefined;
  const proposedCalls = activeStep?.events.filter((event) => event.event_type === 'TOOL_CALL_PROPOSED') ?? [];
  const proposedCall = proposedCalls[0];
  const validation = activeStep?.events.find((event) => event.event_type === 'TOOL_CALL_VALIDATED');
  const toolResult = activeStep?.events.find((event) =>
    event.event_type === 'TOOL_SUCCEEDED' || event.event_type === 'TOOL_FAILED');
  const replaySnapshot = artifact
    ? snapshotAt(artifact, activeReplayEvent?.event_id)
    : { state: null, source: '尚无环境快照' };
  const previousSnapshot = artifact && safeReplayIndex > 0 && replayView === 'story'
    ? snapshotAt(artifact, traceSteps[safeReplayIndex - 1].events[traceSteps[safeReplayIndex - 1].events.length - 1]?.event_id).state
    : null;
  const hasStepSnapshot = activeStep?.events.some((event) =>
    event.event_type === 'ENVIRONMENT_UPDATED' && isRecord(event.payload.state)) ?? false;
  const stateChanges = hasStepSnapshot
    ? changedStateFields(previousSnapshot, replaySnapshot.state)
    : [];
  const initialObservation = activeStep?.events.find((event) => event.event_type === 'OBSERVATION_CREATED');
  const finishedEvent = activeStep?.events.find((event) => event.event_type === 'EPISODE_FINISHED');
  const validationError = typeof validation?.payload.error_code === 'string'
    ? validation.payload.error_code : null;
  const validationRejected = Boolean(validationError || validation?.payload.arguments_valid === false
    || validation?.payload.permitted === false);
  const stepFailed = Boolean(activeStep?.events.some(event => event.event_type === 'TOOL_FAILED'
    || event.event_type === 'TOOL_CALL_VALIDATED' && Boolean(event.payload.error_code || event.payload.permitted === false || event.payload.arguments_valid === false))
    || toolResult?.event_type === 'TOOL_FAILED'
    || validationRejected || finishedEvent?.payload.success === false);
  const visibleFeedback = toolFeedbackFields(toolResult, String(proposedCall?.payload.name ?? ''));
  const visibleStateChanges: [string, unknown][] = keyFields(Object.fromEntries(stateChanges),
    ['acquired_evidence', 'submission', 'done', 'proposed_call']).map(([key, value]) => [key,
      key === 'submission' && isRecord(value) ? value.answer
        : key === 'proposed_call' && isRecord(value) ? value.name : value]);
  const observationFields = isRecord(initialObservation?.payload.observation)
    ? keyFields(initialObservation.payload.observation, ['description', 'question', 'target_order_id', 'document_query'])
    : keyFields(finishedEvent?.payload ?? {}, ['termination_reason', 'detail']);
  const replaySteps = Array.from(new Set(visibleEvents.map((event) => event.step_index)));
  useContentMotion(storyStageRef,
    activeTab === 'single' && replayView === 'story'
      ? `${artifact?.episode.episode_id ?? ''}:${activeReplayEvent?.event_id ?? ''}` : '',
    safeReplayIndex);
  useEffect(() => {
    if (!replayPlaying || visibleEvents.length < 2) return;
    const timer = window.setTimeout(
      () => selectReplayIndex(Math.min(safeReplayIndex + 1, visibleEvents.length - 1)),
      replaySpeedMs,
    );
    return () => window.clearTimeout(timer);
  }, [replayPlaying, replaySpeedMs, safeReplayIndex, artifact, replayView, eventTypeFilter]);

  useEffect(() => {
    if (replayPlaying && safeReplayIndex >= visibleEvents.length - 1) {
      setReplayPlaying(false);
    }
  }, [replayPlaying, safeReplayIndex, visibleEvents.length]);
  const parsedExpSeeds = parseSeedList(expSeedsText);
  const activeComparisonAxis = experiment?.config.comparison_axis === 'context_policy'
    ? 'context_policy'
    : experiment?.config.comparison_axis === 'memory_ablation'
    ? 'memory_ablation'
    : experiment?.config.comparison_axis === 'planning'
    ? 'planning'
    : experiment?.config.comparison_axis === 'runtime_backend'
    ? 'runtime_backend'
    : experiment?.config.comparison_axis === 'recovery_policy'
      ? 'recovery_policy'
      : experiment ? 'recovery_policy' : comparisonAxis;
  const armLeftLabel = activeComparisonAxis === 'context_policy' ? '完整历史'
    : activeComparisonAxis === 'memory_ablation' ? '近期窗口（无记忆）'
    : activeComparisonAxis === 'planning' ? '无声明计划'
    : activeComparisonAxis === 'runtime_backend' ? 'Reference Runtime' : 'Baseline Policy';
  const armRightLabel = activeComparisonAxis === 'context_policy'
    ? experiment?.config.recovery_agent?.context_policy?.memory_max_bytes !== undefined ? '近期窗口 + 工具记忆' : '最近完整工具轮次'
    : activeComparisonAxis === 'memory_ablation' ? '近期窗口 + 工具记忆'
    : activeComparisonAxis === 'planning' ? '声明计划'
    : activeComparisonAxis === 'runtime_backend'
      ? `${experiment?.config.recovery_agent?.runtime_backend === 'pydantic_ai' ? 'PydanticAI' : 'LangGraph'} Runtime`
      : 'Recovery Policy';
  const expEpisodeCount =
    expTasks.length * (parsedExpSeeds?.length ?? 0) * expRepeatCount * 2;
  const isExperimentRunReady = Boolean(meta) && Boolean(expModel) && expTasks.length > 0 &&
    parsedExpSeeds !== null && expRepeatCount >= 1 && expRepeatCount <= 10 && !isLoading;
  const isSingleRunReady = Boolean(meta) && Boolean(selectedModel) && Boolean(selectedSingleTaskMeta) && !isLoading;
  const singleRunHint = !meta ? '正在读取任务与模型目录，完成后即可配置运行。'
    : !selectedModel ? '请先选择评测模型。' : !selectedSingleTaskMeta ? '请先选择一个任务。'
      : isLoading ? loadingMessage : null;
  const experimentRunHint = !meta ? '正在读取任务与模型目录，完成后即可配置运行。'
    : !expModel ? '请先选择评测模型。' : expTasks.length === 0 ? '至少选择一个任务后才能运行。'
      : parsedExpSeeds === null ? '请展开种子与预算设置，输入 1–10 个不重复整数 Seed。'
        : expRepeatCount < 1 || expRepeatCount > 10 ? '请展开种子与预算设置，将重复次数设为 1–10。'
          : isLoading ? loadingMessage : null;

  const hasExperimentResult = Boolean(experiment) || experimentJob?.status === 'failed';
  const experimentConfigPanel = (
    <section className="card" id="exp-config-panel">
      <details className="experiment-draft" open={!experiment}>
        <summary>{experiment ? '配置下一次对照实验' : '配置对照实验'}<span>草稿 · 不修改已保存结果</span></summary>
      <div className="card-title">
        <span>{experiment ? '下次运行配置' : '配置对照实验'}</span>
        <span className="badge badge-purple">受控变量对照</span>
      </div>
      <div className="card-desc">
        严格固定模型、任务、工具集、种子与预算，每次只比较一种策略变量。
      </div>

      <div className="experiment-setup-grid">
      <div className="experiment-controls">
      <div className="form-group">
        <label htmlFor="experiment-call-mode" className="form-label">两组共同的工具调用方式</label>
        <select id="experiment-call-mode" className="form-select" value={expCallMode}
          onChange={e => setExpCallMode(e.target.value as 'single' | 'serial')} disabled={isLoading}>
          <option value="serial">多工具：同轮只读调用，按顺序执行</option>
          <option value="single">单工具：每轮只接受一个调用</option>
        </select>
        <p className="form-hint">每批最多8个；每个工具独立校验与计数，提交答案单独调用。</p>
      </div>
      <div className="form-group">
        <label htmlFor="comparison-axis" className="form-label">对照变量</label>
        <select
          id="comparison-axis"
          className="form-select"
          value={comparisonAxis}
          onChange={(e) => setComparisonAxis(e.target.value as 'recovery_policy' | 'runtime_backend' | 'context_policy' | 'memory_ablation' | 'planning')}
          disabled={isLoading}
        >
          <option value="recovery_policy">恢复策略：关闭 vs 一次参数纠错</option>
          <option value="runtime_backend">执行框架：Reference vs LangGraph/PydanticAI</option>
          <option value="context_policy">上下文：完整历史 vs 最近完整工具轮次</option>
          <option value="memory_ablation">工具记忆：相同近期窗口 vs 相同窗口+记忆</option>
          <option value="planning">规划：无声明 vs 声明计划</option>
        </select>
      </div>

      {comparisonAxis === 'runtime_backend' ? (
        <>
          <div className="form-group">
            <label htmlFor="runtime-recovery-policy" className="form-label">两组相同的恢复策略</label>
            <select id="runtime-recovery-policy" className="form-select" value={expRuntimeStrategy}
              onChange={(e) => setExpRuntimeStrategy(e.target.value as 'handwritten' | 'handwritten_recovery')} disabled={isLoading}>
              <option value="handwritten">关闭参数纠错</option>
              <option value="handwritten_recovery">启用一次参数纠错</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="runtime-target" className="form-label">右侧执行框架</label>
            <select id="runtime-target" className="form-select" value={expRuntimeTarget}
              onChange={(e) => setExpRuntimeTarget(e.target.value as 'langgraph' | 'pydantic_ai')} disabled={isLoading}>
              <option value="langgraph">LangGraph</option>
              <option value="pydantic_ai">PydanticAI</option>
            </select>
          </div>
          <div className="strategy-summary" aria-label="Runtime 对照">
            <div><strong>Reference</strong><span>Python 手写调度循环</span></div>
            <div>
              <strong>{expRuntimeTarget === 'pydantic_ai' ? 'PydanticAI' : 'LangGraph'}</strong>
              <span>{expRuntimeTarget === 'pydantic_ai'
                ? '框架驱动单步节点，步间由适配器推进'
                : 'StateGraph 独立节点调度'}</span>
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="form-group">
            <label htmlFor="policy-runtime" className="form-label">两组共同使用的 Runtime</label>
            <select id="policy-runtime" className="form-select" value={expRuntimeBackend}
              onChange={(e) => setExpRuntimeBackend(e.target.value as 'handwritten' | 'langgraph')} disabled={isLoading}>
              <option value="handwritten">Reference：Python 手写循环</option>
              <option value="langgraph">LangGraph</option>
            </select>
          </div>
          {comparisonAxis === 'context_policy' ? <>
            <ContextSettings prefix="context" choice={contextChoice} rounds={contextWindow} bytes={memoryBytes} disabled={isLoading} comparison
              onChoice={setContextChoice} onRounds={setContextWindow} onBytes={setMemoryBytes} />
            <div className="form-group">
              <label htmlFor="context-recovery" className="form-label">两组相同的恢复策略</label>
              <select id="context-recovery" className="form-select" value={expRuntimeStrategy}
                onChange={(e) => setExpRuntimeStrategy(e.target.value as 'handwritten' | 'handwritten_recovery')} disabled={isLoading}>
                <option value="handwritten">关闭参数纠错</option><option value="handwritten_recovery">启用一次参数纠错</option>
              </select>
            </div>
            <p className="form-help">左侧完整历史；右侧最近 {contextWindow} 轮{contextChoice === 'memory' ? '加工具记忆' : ''}。此处比较整体上下文策略，单独验证记忆需固定相同窗口；Fake 只验证机制。</p>
          </> : comparisonAxis === 'memory_ablation' ? <>
            <div className="context-settings">
              <div className="context-settings-values">
                <div className="form-group">
                  <label htmlFor="memory-axis-window" className="form-label">相同窗口轮次 N（两侧共用）</label>
                  <input id="memory-axis-window" className="form-input" type="number" min="1" max="100" step="1" value={memoryAxisWindow}
                    disabled={isLoading} onChange={event => setMemoryAxisWindow(Number(event.target.value))} />
                </div>
                <div className="form-group">
                  <label htmlFor="memory-axis-bytes" className="form-label">右侧记忆上限 M（字节）</label>
                  <input id="memory-axis-bytes" className="form-input" type="number" min="256" max="32768" step="1" value={memoryAxisBytes}
                    disabled={isLoading} onChange={event => setMemoryAxisBytes(Number(event.target.value))} />
                </div>
              </div>
              <p className="form-help">左右窗口相同，仅记忆配置变化：左侧最近 {memoryAxisWindow} 轮无记忆，右侧同一窗口 + {memoryAxisBytes} 字节工具记忆。</p>
              <details className="context-help"><summary>策略说明与限制</summary>
                <p>两侧仅记忆子算法不同，其余变量全部固定。字节上限不是 Token 预算；记忆可能增加输入量，不保证效果。</p>
              </details>
            </div>
            <div className="form-group">
              <label htmlFor="memory-axis-recovery" className="form-label">两组相同的恢复策略</label>
              <select id="memory-axis-recovery" className="form-select" value={expRuntimeStrategy}
                onChange={(e) => setExpRuntimeStrategy(e.target.value as 'handwritten' | 'handwritten_recovery')} disabled={isLoading}>
                <option value="handwritten">关闭参数纠错</option><option value="handwritten_recovery">启用一次参数纠错</option>
              </select>
            </div>
            <p className="form-help">只比较记忆开关本身，窗口轮次由两侧共享；Fake 只验证机制，单对探索不证明因果收益。</p>
          </> : comparisonAxis === 'planning' ? <>
            <div className="form-group">
              <label htmlFor="planning-recovery" className="form-label">两组相同的恢复策略</label>
              <select id="planning-recovery" className="form-select" value={expRuntimeStrategy}
                onChange={(e) => setExpRuntimeStrategy(e.target.value as 'handwritten' | 'handwritten_recovery')} disabled={isLoading}>
                <option value="handwritten">关闭参数纠错</option><option value="handwritten_recovery">启用一次参数纠错</option>
              </select>
            </div>
            <p className="form-help">两侧固定完整上下文，仅规划组件变化：左侧无 <code>update_plan</code> 工具、不注入计划；右侧可用 <code>update_plan</code> 声明计划并每轮注入。计划是声明的子目标，不计为已执行。</p>
            <details className="context-help"><summary>策略说明与限制</summary>
              <p>计划声明仅记录与回填，真实完成仍由 <code>submit_answer</code> 与环境核验；额外调用与 Token 全部计入右侧自身预算，不另送免费调用。</p>
            </details>
          </> : <div className="strategy-summary" aria-label="恢复策略对照">
            <div><strong>Baseline</strong><span>参数错误后终止</span></div>
            <div><strong>Recovery</strong><span>INVALID_ARGUMENTS 最多纠错一次</span></div>
          </div>}
        </>
      )}

      {/* Model Selector */}
      <div className="form-group">
        <label htmlFor="exp-model-select" className="form-label">评测模型</label>
        <select
          id="exp-model-select"
          className="form-select"
          value={expModel}
          onChange={(e) => setExpModel(e.target.value)}
          disabled={isLoading}
        >
          {!expModel && <option value="" disabled>请选择评测模型</option>}
          {meta?.models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} {m.is_default ? '· 目录默认' : ''} {m.is_experimental ? '· 实验性' : ''}
            </option>
          ))}
        </select>
      </div>

      {/* Model Notes Box */}
      <details className="model-note-disclosure experiment-model-note">
        <summary>模型可用性与实测说明</summary>
        <div className="model-note-box">
          <strong>说明：</strong>{' '}
          {currentExpModelMeta
            ? currentExpModelMeta.notes
            : '模型元数据未就绪；请刷新目录后选择已列出的模型。'}
        </div>
      </details>

      {/* Scenario selector if Fake model */}
      {expModel === 'fake' && (
        <>
        <div className="form-group">
          <label htmlFor="exp-scenario-select" className="form-label">
            Fake 模拟场景
          </label>
          <select
            id="exp-scenario-select"
            className="form-select"
            value={expScenario}
            onChange={(e) => setExpScenario(e.target.value)}
            disabled={isLoading}
          >
            <option value="invalid-then-success">
              invalid-then-success (核心因果场景：Baseline 失败 / Recovery 挽救成功)
            </option>
            <option value="clean">clean / success (基准全通对照)</option>
            <option value="invalid-arguments">invalid-arguments (参数错误且无法纠正)</option>
            <option value="wrong-answer">wrong-answer (提交错误答案)</option>
            <option value="max-steps">max-steps (步数超限)</option>
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="exp-fault-profile" className="form-label">受控故障</label>
          <select id="exp-fault-profile" className="form-select" value={expFaultProfile}
            onChange={(e) => setExpFaultProfile(e.target.value)} disabled={isLoading}>
            <option value="none">无注入</option>
            <option value="tool_timeout">工具超时</option>
            <option value="empty_result">查询空结果</option>
          </select>
          <p className="metric-sub">两侧使用同一故障任务；结果只用于工程对照。</p>
        </div>
        </>
      )}

      </div>
      {/* Task Checkbox List */}
      <div className="form-group experiment-task-picker" role="group" aria-labelledby="exp-task-label">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span id="exp-task-label" className="form-label">评测任务 (多选)</span>
          <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.75rem' }}>
            <button
              type="button"
              className="btn-secondary"
              style={{ padding: '0.15rem 0.4rem', fontSize: '0.7rem' }}
              onClick={() => {
                setExpTasks(experimentTasks.map((t) => t.id));
                if (expTokenBudget === 8000 && experimentTasks.some((task) => task.category === 'evidence_chain')) setExpTokenBudget(20000);
              }}
            >
              全选
            </button>
            <button
              type="button"
              className="btn-secondary"
              style={{ padding: '0.15rem 0.4rem', fontSize: '0.7rem' }}
              onClick={() => setExpTasks([])}
            >
              清空
            </button>
          </div>
        </div>

        <div className="checkbox-list" id="task-checkbox-list">
          {experimentTasks.map((task) => (
            <label key={task.id} className="checkbox-item">
              <input
                type="checkbox"
                checked={expTasks.includes(task.id)}
                onChange={() => toggleTaskSelection(task.id)}
                disabled={isLoading}
              />
              <div>
                <div className="task-name">{task.name}</div>
                <div className="task-meta">
                  {task.description}
                </div>
              </div>
            </label>
          ))}
        </div>
      </div>
      </div>

      <details className="advanced-settings experiment-settings">
        <summary><span>种子与预算设置</span><small>Seed {expSeedsText} · 重复 {expRepeatCount} 次 · {expExecutionSeconds} 秒
          {expModel !== 'fake' && ` · Token ${expTokenBudget ?? '任务原预算'}${expReferenceBudget ? ` · 原厂参考上限 $${expReferenceBudget}` : ''}`}
          {expGlobalTokenBudget && ` · 全局 Token ${expGlobalTokenBudget}`}
        </small></summary>
      <div className="form-group">
        <label htmlFor="exp-seed-input" className="form-label">随机种子集合 (Seeds)</label>
        <input
          id="exp-seed-input"
          type="text"
          className="form-input"
          value={expSeedsText}
          onChange={(e) => setExpSeedsText(e.target.value)}
          placeholder="例如：1, 7, 42"
          disabled={isLoading}
        />
        <p className="metric-sub">使用英文逗号分隔 1–10 个不重复整数。</p>
      </div>

      <div className="form-group">
        <label htmlFor="exp-repeat-input" className="form-label">每个 Seed 重复次数</label>
        <input
          id="exp-repeat-input"
          type="number"
          min={1}
          max={10}
          className="form-input"
          value={expRepeatCount}
          onChange={(e) => setExpRepeatCount(Number(e.target.value))}
          disabled={isLoading}
        />
        <p className="metric-sub">Fake 通常无需重复；真实模型可用于观察非确定性。</p>
      </div>

      {expModel !== 'fake' && (
        <div className="form-group">
          <label htmlFor="exp-token-budget">每次运行 Token 预算（输入 + 输出）</label>
          <input id="exp-token-budget" type="number" min={100} max={20000}
            value={expTokenBudget ?? ''} placeholder="留空使用任务原预算"
            onChange={(e) => setExpTokenBudget(e.target.value === '' ? null : Number(e.target.value))}
            disabled={isLoading} />
          <p className="metric-sub">普通任务建议 8000，跨文档证据链建议 20000；两侧预算相同，免费通道按约 13 秒间隔请求，仍可能遇到账户限额。</p>
        </div>
      )}

      <div className="form-group">
        <label htmlFor="exp-time-limit">每次运行时限（秒）</label>
        <input id="exp-time-limit" className="form-input" type="number" min={1} max={3600}
          value={expExecutionSeconds} disabled={isLoading}
          onChange={(event) => setExpExecutionSeconds(Math.max(1, Math.min(3600, Math.floor(Number(event.target.value)) || 1)))} />
        <p className="metric-sub">两侧使用相同时限；恢复继承已用时间，已开始的工具先保存结果再停止。</p>
      </div>
      <div className="form-group">
        <label htmlFor="exp-global-token-budget">整场实验 Token 预算（可选）</label>
        <input id="exp-global-token-budget" className="form-input" type="text" inputMode="numeric"
          value={expGlobalTokenBudget} placeholder="留空不限制，例如 10000"
          onChange={(event) => setExpGlobalTokenBudget(event.target.value.trim())} disabled={isLoading} />
        <p className="metric-sub">累计所有任务、两侧、Seed 与重复的输入和输出；达到阈值后不启动或恢复下一运行，在途可能超额。Fake 使用模拟 Token。</p>
      </div>
      {expModel !== 'fake' && (
        <div className="form-group">
          <label htmlFor="exp-reference-budget">原厂标价参考预算（USD，可选）</label>
          <input id="exp-reference-budget" type="text" inputMode="decimal"
            value={expReferenceBudget} placeholder="留空不限制，例如 0.05"
            onChange={(e) => setExpReferenceBudget(e.target.value.trim())}
            disabled={isLoading} />
          <p className="metric-sub">按原厂官网未命中缓存价估算，达到阈值后不启动下一 Episode；这不是 AIHubMix 实付费用上限，也不能保证在途 Episode 不超额。</p>
        </div>
      )}

      </details>

      <div className="experiment-launch-bar">
      <div className="experiment-launch-summary"><strong>{expTasks.length} 个任务 · {parsedExpSeeds?.length ?? 0} 个 Seed · 每个重复 {expRepeatCount} 次</strong>
        <span>两侧共 {expEpisodeCount} 次执行 · {expModel === 'fake' ? '离线模拟，不代表模型能力' : '将调用当前选定模型'}</span></div>
      <button
        id="run-exp-button"
        className="btn-primary"
        onClick={handleRunExperiment}
        disabled={!isExperimentRunReady}
        aria-describedby={experimentRunHint ? 'experiment-run-hint' : undefined}
        title={
          !meta
            ? '任务元数据尚未就绪'
            : expTasks.length === 0
              ? '至少选择 1 个评测任务后才能运行'
              : parsedExpSeeds === null
                ? 'Seed 必须是 1–10 个不重复整数'
              : undefined
        }
      >
        {isLoading ? (
          <>
            <div className="spinner" />
            <span>{loadingActivity === 'history' ? '正在读取历史记录…' : '正在执行实验…'}</span>
          </>
        ) : (
          <>
            <span>开始运行对照实验 ({expEpisodeCount} 次执行)</span>
          </>
        )}
      </button>
      {experimentRunHint && <p id="experiment-run-hint" className="inline-note" role="status">{experimentRunHint}</p>}
      {isLoading && (
        <p className="loading-note" role="status" aria-live="polite">
          {loadingMessage} <span aria-hidden="true">已等待 {elapsedSeconds} 秒。</span>
        </p>
      )}
      </div>

      </details>

      {activeJobId && experimentJob?.experiment_id === activeJobId && (
        <div className="resumable-panel" role="status" aria-live="polite">
          <div className="card-title">实验任务：{experimentJobLabels[experimentJob.status]}</div>
          <p className="card-desc"><code>{activeJobId}</code> · 控制请求在当前 Episode 结束后生效。</p>
          <div className="resumable-list">
            {['queued', 'running'].includes(experimentJob.status) && !experimentJob.requested_action && (
              <>
                <button className="btn-secondary" onClick={() => handleControlExperimentJob('pause')}>暂停</button>
                <button className="btn-secondary" onClick={() => handleControlExperimentJob('cancel')}>取消</button>
              </>
            )}
            {experimentJob.requested_action && <span>已请求{experimentJob.requested_action === 'pause' ? '暂停' : '取消'}，等待安全点。</span>}
            {['paused', 'interrupted'].includes(experimentJob.status) && (
              <>
                <button className="btn-secondary" onClick={() => handleControlExperimentJob('resume')}>从安全点恢复</button>
                <button className="btn-secondary" onClick={() => handleControlExperimentJob('cancel')}>取消实验</button>
              </>
            )}
          </div>
        </div>
      )}

      {resumableJobIds.some((id) => id !== activeJobId) && (
        <section className="resumable-panel" aria-labelledby="resumable-job-title">
          <div className="card-title" id="resumable-job-title">可恢复的实验任务</div>
          <p className="card-desc">原计划和已完成 Episode 均保留；继续运行可能重新发送中断中的模型请求。</p>
          <div className="resumable-list">
            {resumableJobIds.filter((id) => id !== activeJobId).map((id) => (
              <button key={id} className="btn-secondary" disabled={isLoading}
                onClick={() => handleControlExperimentJob('resume', id)}>
                恢复 Job <code>{id}</code>
              </button>
            ))}
          </div>
        </section>
      )}

      {resumableExpIds.length > 0 && (
        <section className="resumable-panel" aria-labelledby="resumable-exp-title">
          <div className="card-title" id="resumable-exp-title">待恢复的对照实验</div>
          <p className="card-desc">继续原实验并复用已完成结果；中断中的模型请求可能重新发送。</p>
          <div className="resumable-list">
            {resumableExpIds.map((id) => (
              <button key={id} className="btn-secondary" disabled={isLoading}
                onClick={() => handleResumeExperiment(id)}>
                恢复 Experiment <code>{id}</code>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Recent Experiments History */}
      {recentExpIds.length > 0 && (
        <div className="history-panel">
          <div className="history-panel-title">
            最近实验历史：
          </div>
          <div className="history-list">
            {recentExpIds.map((rid) => (
              <button
                key={rid}
                className="btn-secondary history-button"
                onClick={() => loadExperimentById(rid)}
              >
                {rid}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );

  return (
    <div>
      <a className="skip-link" href="#main-content" onClick={(event) => {
        if (!mainMotionRef.current) return;
        event.preventDefault();
        mainMotionRef.current.focus({ preventScroll: true });
        mainMotionRef.current.scrollIntoView({ block: 'start' });
      }}>跳至工作区</a>
      {/* Header */}
      <header className="app-header">
        <div className="header-container">
          <a className="brand" href="/brand/fox-preview.html" target="_blank" rel="noopener noreferrer"
            aria-label="AgentLabyrinth · 查看标志动态展示">
            <span className="brand-mark" aria-hidden="true">
              <img src="/brand/fox-motion.svg" width="36" height="36" alt=""
                onError={(event) => {
                  if (event.currentTarget.src.includes('fox-motion.svg')) {
                    event.currentTarget.src = '/brand/fox-mark.svg';
                  }
                }} />
            </span>
            <div>
              <div className="brand-title">AgentLabyrinth</div>
              <div className="brand-subtitle">可复现 Agent 实验平台</div>
            </div>
          </a>

          <div className="header-actions">
            <nav className="nav-tabs" data-active={activeTab} aria-label="工作区模式">
              <button
                id="tab-experiment"
                className={`nav-tab ${activeTab === 'experiment' ? 'active' : ''}`}
                aria-pressed={activeTab === 'experiment'}
                onClick={() => switchTab('experiment')}
                disabled={isLoading && loadingActivity === 'run' && !activeJobId}
              >
                对照实验 <span className="nav-english">Agent Comparison</span>
              </button>
              <button
                id="tab-single"
                className={`nav-tab ${activeTab === 'single' ? 'active' : ''}`}
                aria-pressed={activeTab === 'single'}
                onClick={() => switchTab('single')}
                disabled={isLoading && loadingActivity === 'run' && !activeJobId}
              >
                单次运行 <span className="nav-english">Single Episode</span>
              </button>
            </nav>

          </div>
        </div>
      </header>

      {/* Main Content */}
      <main id="main-content" tabIndex={-1}
        className={`main-container ${activeTab === 'single' && artifact ? 'viewing-episode' : ''}`} ref={mainMotionRef}>
        <section className="page-intro" aria-labelledby="page-title">
          <div>
            <div className="page-eyebrow">Agent 评测工作台</div>
            <h1 id="page-title">
              {activeTab === 'experiment' ? '比较策略差异' : '审查一次完整运行'}
            </h1>
            <p>
              {activeTab === 'experiment'
                ? '固定任务、模型、种子与预算，每次比较上下文、恢复策略或 Runtime 中的一项。'
                : '运行一个任务，核查评测结论、环境状态与完整 Trace。'}
            </p>
          </div>
          <span className="workspace-status">
            {meta ? `${meta.tasks.length} 个可用任务` : '正在读取任务目录'}
          </span>
        </section>

        {/* Error Alert Box */}
        {recoveryListError && (
          <p className="inline-note" role="status">待恢复记录读取失败，列表可能不完整。请刷新页面重新读取。</p>
        )}
        {errorMsg && (
          <div id="error-alert" className="alert-box alert-error" role="alert">
            <span className="alert-label">错误</span>
            <div>{errorMsg}</div>
          </div>
        )}
        {(metadataError || meta?.model_catalog_status === 'unavailable') && (
          <div className="alert-box alert-error" role="status">
            <span className="alert-label">模型目录暂不可用</span>
            <div>
              <p>{metadataError ? `目录读取失败：${metadataError}` : '此前未能读取 AIHubMix 模型目录，普通候选暂时隐藏；带日期实测的目录例外可能仍可选，不表示已确认当前可用。'}</p>
              <p>可先用 Fake，或查看候选说明后尝试；上游失败状态最多缓存 30 秒，连接恢复后请重新读取。</p>
              <button type="button" className="btn-secondary" disabled={metadataLoading || isLoading}
                onClick={() => void loadMetadata()}>{metadataLoading ? '正在重新读取…' : '重新读取模型目录'}</button>
            </div>
          </div>
        )}
        {meta?.model_catalog_status === 'live' && meta.models.some((model) => model.provider === 'aihubmix') && (
          <div className="model-catalog-caution" role="note">
            网关目录仅表示模型 ID 可见，不能验证当前 Key 的调用权限、额度或通道。真实可用性以实际运行结果为准。
          </div>
        )}

        <ClassroomScenarios tasks={meta?.tasks ?? []} disabled={isLoading || metadataLoading || !meta}
          hasSavedResult={Boolean(artifact || experiment || activeJobId)} onConfigure={configureClassroomScenario} />

        {/* TAB 1: EXPERIMENT MODE */}
        {activeTab === 'experiment' && (
          <div>
            {/* Persistent ID Bar */}
            <div className="persistence-bar persistence-bar-spaced">
              <div className="persistence-cluster">
                <span className="persistence-label">当前 Experiment:</span>
                <span className="persistence-value">
                  {experiment ? experiment.experiment_id : '尚未运行'}
                </span>
                {experiment && (
                  <>
                    <button
                      id="btn-copy-exp-id"
                      className="btn-secondary"
                      onClick={async () => setCopyNotice(await copyTextToClipboard(experiment.experiment_id, 'Experiment ID'))}
                    >
                      复制 ID
                    </button>
                    <span className="persistence-export-actions">
                      <button
                        id="btn-export-experiment"
                        className="btn-secondary"
                        onClick={() =>
                          downloadJson(
                            `agentlabyrinth-experiment-${experiment.experiment_id}.json`,
                            experiment,
                          )
                        }
                      >
                        导出 JSON
                      </button>
                      <button
                        id="btn-export-experiment-csv"
                        className="btn-secondary"
                        onClick={() => downloadFile(
                          `agentlabyrinth-experiment-${experiment.experiment_id}.csv`,
                          experimentCsv(experiment),
                          'text/csv;charset=utf-8',
                        )}
                      >
                        导出 CSV
                      </button>
                    </span>
                  </>
                )}
              </div>
              <HistoryReader kind="exp" value={inputExpId} busy={isLoading}
                onChange={setInputExpId} onRead={loadExperimentById} />
            </div>
            {copyNotice && (
              <div className="copy-feedback" role="status" aria-live="polite">
                {copyNotice}
              </div>
            )}

            <details className="history-disclosure">
              <summary>实验历史与趋势 <span>{dashboardLoading ? '读取中' : `${dashboardItems.length} 条记录`}</span></summary>
            <ExperimentDashboard items={dashboardItems} loading={dashboardLoading} error={dashboardError}
              skipped={dashboardSkipped} activeId={experiment?.experiment_id}
              onRefresh={refreshExperimentDashboard} onOpen={loadExperimentById} />
            </details>

            <div className={`dashboard-grid experiment-workspace ${hasExperimentResult ? 'saved-experiment-grid' : ''}`}>
              {!hasExperimentResult && experimentConfigPanel}

              {/* Right Panel: Aggregate Metrics + Comparison Table */}
              <div className="single-result-stack">
                {/* Aggregate Summary Cards */}
                <section className="card" id="exp-metrics-panel">
                  <div className="card-title">
                    <span>聚合对照指标</span>
                    {experiment && (
                      <span className="badge badge-purple">
                        {experiment.pairs.length} 组任务对比
                      </span>
                    )}
                  </div>
                  <div className="card-desc">
                    {activeComparisonAxis === 'context_policy'
                      ? '只改变模型可见上下文，比较成功率、工具调用、已报告 Token 与耗时；不计算纠错挽救率。'
                      : activeComparisonAxis === 'memory_ablation'
                      ? '左右窗口相同，只切换单任务工具记忆；比较成功率、工具调用、已报告 Token 与耗时，不计算纠错挽救率。'
                      : activeComparisonAxis === 'planning'
                      ? '两侧固定完整上下文，只切换规划组件（是否可声明并注入计划）；比较成功率、工具调用、已报告 Token 与耗时，不计算纠错挽救率。'
                      : activeComparisonAxis === 'runtime_backend'
                      ? '比较两个 Runtime 在相同模型、任务、预算和恢复策略下的成功率、用量与耗时。'
                      : '比较恢复策略的成功率、参数错误挽救转化率与额外用量。'}
                  </div>

                  {experiment ? (
                    <div>
                      {activeComparisonAxis === 'context_policy' && <p className="model-note-box" aria-label="已保存上下文对照">完整历史 vs {contextLabel(experiment.config.recovery_agent?.context_policy)} · 保存结果，不随草稿改变</p>}
                      {activeComparisonAxis === 'memory_ablation' && <p className="model-note-box" aria-label="已保存工具记忆对照">相同窗口：{contextLabel(experiment.config.baseline_agent?.context_policy)} vs {contextLabel(experiment.config.recovery_agent?.context_policy)} · 保存结果，不随草稿改变</p>}
                      {activeComparisonAxis === 'planning' && <p className="model-note-box" aria-label="已保存规划对照">两侧完整上下文：{contextLabel(experiment.config.baseline_agent?.context_policy)} · 左侧无声明，右侧 {experiment.config.recovery_agent?.planning?.algorithm_version ?? '声明计划'} · 保存结果，不随草稿改变</p>}
                      <div className="episode-provenance" aria-label="已保存实验来源">
                        <span>工具调用：{typeof experiment.config.model === 'object' && experiment.config.model?.tool_call_mode === 'serial' ? '多工具 · 顺序执行' : '单工具'}（两侧相同）</span>
                        <strong>{typeof experiment.config.model === 'string'
                          ? experiment.config.model : experiment.config.model?.model || '历史模型未提供'}</strong>
                        <span>{armLeftLabel} ↔ {armRightLabel}</span>
                      </div>
                      <p className="experiment-reading-note">{experiment.config.provider === 'fake'
                        ? '离线模拟对照 · 用于展示运行与恢复机制，不代表真实模型能力。'
                        : '真实 API 小样本对照 · 当前结果只描述本次实验，不代表稳定排名。'}</p>
                      {activeComparisonAxis === 'context_policy' && (
                        <div className="classroom-result-reading" aria-label="上下文实验解读">
                          <strong>这一场实验说明什么</strong>
                          <p>同一模型、任务和预算，仅改变上下文策略。完整历史通过 {experiment.metrics.baseline_success_count} / {experiment.metrics.total_pairs}，
                            {armRightLabel}通过 {experiment.metrics.recovery_success_count} / {experiment.metrics.total_pairs}。</p>
                          {experiment.config.recovery_agent?.context_policy?.memory_max_bytes !== undefined && <p>右侧同时包含窗口与工具记忆；此对照不能单独证明记忆的收益，需与相同窗口的无记忆配置比较。</p>}
                          <p>先查看成对结果和失败 Trace，再结合已报告 Token 与耗时判断差异；窗口缩短不保证省 Token 或提高成功率。
                            {experiment.config.provider === 'fake' ? ' Fake 结果只验证机制。' : ' 单次小样本不足以证明策略稳定优胜。'}</p>
                        </div>
                      )}
                      {activeComparisonAxis === 'memory_ablation' && (
                        <div className="classroom-result-reading" aria-label="工具记忆实验解读">
                          <strong>这一场实验说明什么</strong>
                          <p>同一模型、任务、预算与 {experiment.config.baseline_agent?.context_policy?.max_tool_rounds} 轮窗口，仅切换右侧工具记忆。无记忆窗口通过 {experiment.metrics.baseline_success_count} / {experiment.metrics.total_pairs}，
                            带记忆窗口通过 {experiment.metrics.recovery_success_count} / {experiment.metrics.total_pairs}。</p>
                          <p>左右窗口相同，仅记忆配置变化；真实输出仍有随机性，单对不是因果收益证明。字节不是 Token，记忆可能增加输入量，不保证效果。
                            {experiment.config.provider === 'fake' ? ' Fake 结果只验证机制。' : ' 单次小样本不足以证明稳定优胜。'}</p>
                        </div>
                      )}
                      {activeComparisonAxis === 'planning' && (
                        <div className="classroom-result-reading" aria-label="规划实验解读">
                          <strong>这一场实验说明什么</strong>
                          <p>同一模型、任务、预算与完整上下文，仅切换右侧规划声明。无声明计划通过 {experiment.metrics.baseline_success_count} / {experiment.metrics.total_pairs}，
                            声明计划通过 {experiment.metrics.recovery_success_count} / {experiment.metrics.total_pairs}。</p>
                          <p>计划是模型声明的子目标，不等于已执行；真实完成仍以 <code>submit_answer</code> 与环境核验为准。额外声明调用与 Token 全部计入右侧自身预算。
                            {experiment.config.provider === 'fake' ? ' Fake 结果只验证机制。' : ' 单次小样本不足以证明稳定优胜。'}</p>
                        </div>
                      )}
                      {experiment.config.max_total_tokens != null && (
                        <p className="experiment-reading-note" aria-label="已保存全局 Token 预算">
                          全局 Token 边界预算：{experiment.config.max_total_tokens} · 已报告累计：
                          {experiment.metrics.baseline_total_tokens + experiment.metrics.recovery_total_tokens}
                          {experiment.metrics.baseline_total_tokens + experiment.metrics.recovery_total_tokens > experiment.config.max_total_tokens
                            ? ' · 最后一轮在途执行已超额' : ''}。此值来自保存结果，非当前草稿。
                        </p>
                      )}
                      <ExperimentCharts labels={[armLeftLabel, armRightLabel]}
                        rates={[experiment.metrics.baseline_success_rate, experiment.metrics.recovery_success_rate]}
                        tokens={[experiment.metrics.baseline_total_tokens, experiment.metrics.recovery_total_tokens]}
                        durations={[experiment.metrics.baseline_avg_duration_ms, experiment.metrics.recovery_avg_duration_ms]}
                        total={experiment.metrics.total_pairs}
                        counts={[experiment.metrics.baseline_success_count, experiment.metrics.recovery_success_count]} />
                      <ExperimentReviewSummary experiment={experiment} />
                      {activeComparisonAxis === 'memory_ablation' && <MemoryPairReview key={experiment.experiment_id}
                        pairs={experiment.pairs} labels={[armLeftLabel, armRightLabel]} />}
                      {activeComparisonAxis === 'planning' && <PlanningPairReview key={experiment.experiment_id}
                        pairs={experiment.pairs} labels={[armLeftLabel, armRightLabel]} />}
                      <div>
                        {/* Retry Recovery Count & Rate */}
                        {activeComparisonAxis === 'recovery_policy' && <div
                          className="metric-box"
                          style={{
                            border: '1px solid var(--accent-primary)',
                            background: 'var(--brand-soft)',
                          }}
                        >
                          <div className="metric-label" style={{ color: 'var(--brand-action)' }}>
                            挽救转化 (Recovery)
                          </div>
                          <div className="metric-value" style={{ color: 'var(--brand-action)' }}>
                            {experiment.metrics.retry_recovery_count} 例
                          </div>
                          <div className="metric-sub">
                            {experiment.metrics.retry_eligible_count === 0
                              ? '本次没有可恢复的参数错误样本'
                              : experiment.metrics.retry_eligible_count !== null && experiment.metrics.retry_eligible_count !== undefined
                              ? `转化率: ${((experiment.metrics.retry_recovery_rate ?? 0) * 100).toFixed(1)}% (${experiment.metrics.retry_recovery_count} / ${experiment.metrics.retry_eligible_count} 可恢复样本)`
                              : `转化率: ${((experiment.metrics.retry_recovery_rate ?? 0) * 100).toFixed(1)}% (${experiment.metrics.retry_recovery_count} 例，历史版本未统计可恢复基数)`}
                          </div>
                        </div>}

                      </div>
                      <details className="episode-details experiment-usage">
                        <summary>查看用量与质量指标<span>Token、步数、耗时、费用与工具调用</span></summary>
                        <div className="metrics-grid">
                        {/* Total Tokens & Delta */}
                        <div className="metric-box">
                          <div className="metric-label">已报告 Token ({armLeftLabel} / {armRightLabel})</div>
                          <div className="metric-value" style={{ fontSize: '1.05rem' }}>
                            {experiment.metrics.baseline_total_tokens} / {experiment.metrics.recovery_total_tokens}
                          </div>
                          <div className="metric-sub">
                            已报告差值: {formatSigned(experiment.metrics.recovery_total_tokens - experiment.metrics.baseline_total_tokens)} tokens
                          </div>
                          <div className="metric-sub">汇总值不能确认总用量完整；请结合各次运行的保存轨迹核查，不能直接当作完整节省量。</div>
                        </div>

                        {/* Average Steps */}
                        <div className="metric-box">
                          <div className="metric-label">平均步数 ({armLeftLabel} / {armRightLabel})</div>
                          <div className="metric-value" style={{ fontSize: '1.1rem' }}>
                            {experiment.metrics.baseline_avg_steps} / {experiment.metrics.recovery_avg_steps}
                          </div>
                          <div className="metric-sub">单任务平均步数</div>
                        </div>

                        {/* Average Duration */}
                        <div className="metric-box">
                          <div className="metric-label">平均耗时 ({armLeftLabel} / {armRightLabel})</div>
                          <div className="metric-value" style={{ fontSize: '1.05rem' }}>
                            {experiment.metrics.baseline_avg_duration_ms} / {experiment.metrics.recovery_avg_duration_ms} ms
                          </div>
                          <div className="metric-sub">
                            {experiment.config.provider === 'fake' ? '模拟费用' : '网关估算费用'}: {experiment.metrics.baseline_total_cost != null &&
                              experiment.metrics.recovery_total_cost != null
                              ? `$${experiment.metrics.baseline_total_cost} / $${experiment.metrics.recovery_total_cost}`
                              : experiment.metrics.is_cost_known
                                ? '历史产物未统计'
                                : '未知 (未验证)'}
                          </div>
                        </div>

                        <div className="metric-box">
                          <div className="metric-label">原厂标价参考成本 ({armLeftLabel} / {armRightLabel})</div>
                          <div className="metric-value" style={{ fontSize: '1.05rem' }}>
                            {experiment.metrics.baseline_total_reference_cost != null && experiment.metrics.recovery_total_reference_cost != null
                              ? `$${experiment.metrics.baseline_total_reference_cost} / $${experiment.metrics.recovery_total_reference_cost}`
                              : '未知'}
                          </div>
                          <div className="metric-sub">USD · 按全部输入未命中缓存估算，非实际扣费</div>
                        </div>

                        {/* Tool Selection & Argument Validity Rates */}
                        <div className="metric-box">
                          <div className="metric-label">允许工具命中比例 ({armLeftLabel} / {armRightLabel})</div>
                          <div className="metric-sub">所提议工具属于任务预期且非禁止集合的比例；不表示当前步骤最优或任务正确率。</div>
                          <div className="metric-value" style={{ fontSize: '1.05rem' }}>
                            {experiment.metrics.baseline_tool_selection_accuracy !== null && experiment.metrics.baseline_tool_selection_accuracy !== undefined
                              ? (experiment.metrics.baseline_tool_selection_accuracy * 100).toFixed(0) + '%'
                              : '未提供'} / {experiment.metrics.recovery_tool_selection_accuracy !== null && experiment.metrics.recovery_tool_selection_accuracy !== undefined
                              ? (experiment.metrics.recovery_tool_selection_accuracy * 100).toFixed(0) + '%'
                              : '未提供'}
                          </div>
                          <div className="metric-sub">
                            参数合法: {experiment.metrics.baseline_tool_argument_validity_rate !== null && experiment.metrics.baseline_tool_argument_validity_rate !== undefined
                              ? (experiment.metrics.baseline_tool_argument_validity_rate * 100).toFixed(0) + '%'
                              : '未提供'} / {experiment.metrics.recovery_tool_argument_validity_rate !== null && experiment.metrics.recovery_tool_argument_validity_rate !== undefined
                              ? (experiment.metrics.recovery_tool_argument_validity_rate * 100).toFixed(0) + '%'
                              : '未提供'}
                          </div>
                        </div>

                        {/* Model & Tool Call Counts */}
                        <div className="metric-box">
                          <div className="metric-label">平均模型 / 工具调用 ({armLeftLabel} / {armRightLabel})</div>
                          <div className="metric-value" style={{ fontSize: '1.05rem' }}>
                            {experiment.metrics.baseline_avg_model_calls !== null && experiment.metrics.baseline_avg_model_calls !== undefined
                              ? experiment.metrics.baseline_avg_model_calls
                              : '未提供'} / {experiment.metrics.recovery_avg_model_calls !== null && experiment.metrics.recovery_avg_model_calls !== undefined
                              ? experiment.metrics.recovery_avg_model_calls
                              : '未提供'}
                          </div>
                          <div className="metric-sub">
                            工具调用: {experiment.metrics.baseline_avg_tool_calls !== null && experiment.metrics.baseline_avg_tool_calls !== undefined
                              ? experiment.metrics.baseline_avg_tool_calls
                              : '未提供'} / {experiment.metrics.recovery_avg_tool_calls !== null && experiment.metrics.recovery_avg_tool_calls !== undefined
                              ? experiment.metrics.recovery_avg_tool_calls
                              : '未提供'}
                          </div>
                        </div>
                      </div>

                      </details>

                      <details className="record-summary experiment-record">
                        <summary>已保存实验配置 · 固定变量与哈希</summary>
                        <div className="summary-header">
                          <strong className="summary-title">
                            已保存实验配置（固定变量与哈希）
                          </strong>
                          <span className="hash-pill">
                            Hash: {experiment.config_hash ? experiment.config_hash.slice(0, 16) + '...' : 'N/A'}
                          </span>
                        </div>
                        <div className="summary-grid">
                          <div>
                            <strong>模型：</strong>{' '}
                            {typeof experiment.config.model === 'string'
                              ? experiment.config.model
                              : experiment.config.model?.model || 'N/A'}
                          </div>
                          <div>
                            <strong>场景：</strong>{' '}
                            {experiment.config.scenario || 'N/A (真实模型)'}
                          </div>
                          <div>
                            <strong>种子 (Seeds)：</strong>{' '}
                            {Array.isArray(experiment.config.seeds)
                              ? experiment.config.seeds.join(', ')
                              : String(experiment.config.seed ?? 1)}
                          </div>
                          <div>
                            <strong>每个 Seed 重复：</strong>{' '}
                            {String(experiment.config.repeat_count ?? 1)} 次
                          </div>
                          <div>
                            <strong>每次运行时限：</strong>{' '}
                            {isRecord(experiment.config.budget) && typeof experiment.config.budget.max_execution_time_ms === 'number'
                              ? `${experiment.config.budget.max_execution_time_ms / 1000} 秒` : '历史配置未设置'}
                          </div>
                          <div>
                            <strong>数据来源：</strong>{' '}
                            {experiment.config.provider === 'fake' ? '离线模拟' : '真实 API（探索性）'}
                          </div>
                          <div>
                            <strong>运行时间：</strong>{' '}
                            {new Date(experiment.created_at).toLocaleString()}
                          </div>
                          <div>
                            <strong>任务数量：</strong>{' '}
                            {Array.isArray(experiment.config.task_ids)
                              ? experiment.config.task_ids.length
                              : experiment.pairs.length}
                          </div>
                          <div>
                            <strong>评测器：</strong>{' '}
                            {experiment.config.evaluator || 'order_status_v1'}
                          </div>
                          <div>
                            <strong>{armLeftLabel}：</strong>{' '}
                            {experiment.config.baseline_agent?.runtime_backend || 'handwritten'}
                            {' / '}
                            {experiment.config.baseline_agent?.runtime_strategy || 'handwritten'}
                          </div>
                          <div>
                            <strong>{armRightLabel}：</strong>{' '}
                            {experiment.config.recovery_agent?.runtime_backend || 'handwritten'}
                            {' / '}
                            {experiment.config.recovery_agent?.runtime_strategy || 'handwritten_recovery'}
                          </div>
                        </div>
                      </details>

                      {/* Paired Comparison Table */}
                      <div className="card-title paired-table-title">
                        <span>成对任务明细对比 (Paired Comparison Table)</span>
                      </div>
                      <div className="table-container">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>评测任务</th>
                              <th>{armLeftLabel}</th>
                              <th>{armRightLabel}</th>
                              <th>判定效果</th>
                              <th>步数、调用与 Tokens</th>
                              <th>Trace 审查</th>
                            </tr>
                          </thead>
                          <tbody>
                            {experiment.pairs.map((pair) => (
                              <tr key={`${pair.task_id}-${pair.seed}-${pair.repeat_index ?? 1}`}>
                                        <td className="task-name">
                                          {pair.task_name}
                                          <div className="task-meta inline-note">
                                            Seed {pair.seed} · 第 {pair.repeat_index ?? 1} 次
                                          </div>
                                        </td>
                                        <td>
                                          <span className={`badge ${pair.baseline_success ? 'badge-green' : 'badge-red'}`}>
                                            {pair.baseline_success ? 'SUCCESS' : 'FAILED'}
                                          </span>
                                          <div className="task-meta inline-note">
                                            {pair.baseline_termination_reason}
                                          </div>
                                        </td>
                                        <td>
                                          <span className={`badge ${pair.recovery_success ? 'badge-green' : 'badge-red'}`}>
                                            {pair.recovery_success ? 'SUCCESS' : 'FAILED'}
                                          </span>
                                          <div className="task-meta inline-note">
                                            {pair.recovery_termination_reason}
                                          </div>
                                        </td>
                                        <td>
                                          <span className={`badge ${pair.recovered ? 'badge-cyan' : ''}`}>
                                            {comparisonLabel(pair, activeComparisonAxis)}
                                          </span>
                                          {activeComparisonAxis === 'recovery_policy' && pair.retry_eligible === true && (
                                            <div className="inline-note">
                                              <span className="badge badge-purple pill-small">
                                                可恢复样本
                                              </span>
                                            </div>
                                          )}
                                          {activeComparisonAxis === 'recovery_policy' && pair.retry_eligible === null && (
                                            <div className="inline-note">
                                              <span className="badge pill-small" style={{ opacity: 0.7 }}>
                                                基数未统计
                                              </span>
                                            </div>
                                          )}
                                        </td>
                                        <td className="mono-metrics">
                                          <div>步数: {pair.baseline_steps} → {pair.recovery_steps}</div>
                                          <div>Tokens: {pair.baseline_tokens} → {pair.recovery_tokens}</div>
                                          <div className="meta-muted">
                                            模型调用: {pair.baseline_model_calls !== null && pair.baseline_model_calls !== undefined ? pair.baseline_model_calls : '未提供'} → {pair.recovery_model_calls !== null && pair.recovery_model_calls !== undefined ? pair.recovery_model_calls : '未提供'}
                                          </div>
                                        </td>
                                        <td>
                                          <div className="trace-actions">
                                            <button
                                              className="btn-secondary trace-button"
                                              aria-label={`查看 ${pair.task_name} 的 ${armLeftLabel} Trace`}
                                              onClick={() => {
                                                setActiveTab('single');
                                                loadEpisodeById(pair.baseline_episode_id);
                                              }}
                                            >
                                              {armLeftLabel} Trace
                                            </button>
                                            <button
                                              className="btn-secondary trace-button"
                                              aria-label={`查看 ${pair.task_name} 的 ${armRightLabel} Trace`}
                                              onClick={() => {
                                                setActiveTab('single');
                                                loadEpisodeById(pair.recovery_episode_id);
                                              }}
                                            >
                                              {armRightLabel} Trace
                                            </button>
                                          </div>
                                        </td>
                                      </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : (
                    <div className="empty-state" aria-label={experimentJob?.status === 'failed' ? '已停止实验说明' : undefined}>
                      <div className="empty-icon">{experimentJob?.status === 'failed' ? '实验已停止' : '尚无实验结果'}</div>
                      {experimentJob?.status === 'failed' ? <>
                        <p>{errorMsg ?? '实验运行失败，已保存记录保留。'}</p>
                        <p>本次未形成完整成对结果，不显示成功率。原计划与已完成记录保留，可用于审查。</p>
                      </> : <div>选择模型和任务，运行一次对照；也可以读取已保存的实验结果。</div>}
                    </div>
                  )}
                </section>
              </div>
              {hasExperimentResult && experimentConfigPanel}
            </div>
          </div>
        )}

        {/* TAB 2: SINGLE EPISODE MODE */}
        {activeTab === 'single' && (
          <div>
            {/* Persistent ID Bar */}
            <div className="persistence-bar persistence-bar-spaced">
              <div className="persistence-cluster">
                <span className="persistence-label">当前 Episode:</span>
                <span className="persistence-value">
                  {artifact ? artifact.episode.episode_id : liveRun?.episodeId
                    ?? (liveRun ? liveRun.status === 'running' ? '运行中，等待运行 ID' : '连接中断，尚未收到运行 ID' : '尚未运行')}
                </span>
                {artifact && (
                  <>
                    <button
                      id="btn-copy-id"
                      className="btn-secondary"
                      onClick={async () => setCopyNotice(await copyTextToClipboard(artifact.episode.episode_id, 'Episode ID'))}
                    >
                      复制 ID
                    </button>
                    <button
                      id="btn-export-episode"
                      className="btn-secondary"
                      onClick={() =>
                        downloadJson(
                          `agentlabyrinth-episode-${artifact.episode.episode_id}.json`,
                          artifact,
                        )
                      }
                    >
                      导出 JSON
                    </button>
                    {!artifact.evaluation.success && (
                      <button className="btn-secondary" disabled={isLoading}
                        onClick={handleRerunFailedEpisode}>
                        单独重跑失败 Episode
                      </button>
                    )}
                  </>
                )}
              </div>
              <HistoryReader kind="episode" value={inputEpisodeId} busy={isLoading}
                onChange={setInputEpisodeId} onRead={loadEpisodeById} />
            </div>
            {copyNotice && (
              <div className="copy-feedback" role="status" aria-live="polite">
                {copyNotice}
              </div>
            )}

            <div className={`dashboard-grid single-dashboard ${artifact ? 'has-artifact' : liveRun ? 'streaming' : 'configuring'}`}>
              <details className="card config-panel" id="config-panel" open={!artifact}>
                <summary className="card-title config-panel-summary">
                  <span>{artifact ? '下次运行配置' : '配置单次运行'}</span>
                  <span className="config-summary-meta">
                    {artifact
                      ? `${selectedSingleTaskMeta?.name ?? '选择任务'} · ${currentSingleModelMeta?.name ?? (selectedModel || '选择模型')}`
                      : `${singleTasks.length} 个可用任务`}
                  </span>
                </summary>
                <div className="config-panel-content">
                  <div className="single-setup-grid">
                    <section className="task-picker" aria-labelledby="task-picker-title">
                      <div className="task-picker-heading">
                        <div>
                          <h2 id="task-picker-title">先选一个任务</h2>
                          <p>查看任务目标，再决定使用哪种执行方式。</p>
                        </div>
                        <span className="task-picker-count">{filteredSingleTasks.length} 个</span>
                      </div>

                      <fieldset className="suite-choice" disabled={isLoading || !meta}>
                        <legend className="form-label">任务集</legend>
                        <div className="suite-choice-options">
                          <label className={selectedSuite === 'tool_lab_core' ? 'selected' : ''}>
                            <input type="radio" name="single-suite" value="tool_lab_core"
                              checked={selectedSuite === 'tool_lab_core'}
                              onChange={() => {
                                setSelectedSuite('tool_lab_core');
                                setSingleTaskQuery('');
                                const first = meta?.tasks.find((task) => task.id === meta.default_task)
                                  ?? meta?.tasks.find((task) => task.suite === 'tool_lab_core');
                                if (first) setSelectedSingleTask(first.id);
                                setMaxSteps(first?.max_steps ?? 6);
                                setSingleTokenBudget(8000);
                                setSingleToolTransport('local');
                                setSingleFaultProfile('none');
                              }} />
                            <span>ToolLab</span>
                            <small>原生任务</small>
                          </label>
                          <label className={selectedSuite === 'bfcl_adapted' ? 'selected' : ''}
                            aria-disabled={bfclTaskCount === 0}>
                            <input type="radio" name="single-suite" value="bfcl_adapted"
                              checked={selectedSuite === 'bfcl_adapted'}
                              disabled={bfclTaskCount === 0}
                              onChange={() => {
                                setSelectedSuite('bfcl_adapted');
                                setSingleTaskQuery('');
                                const first = meta?.tasks.find((task) => task.suite === 'bfcl_adapted');
                                if (first) setSelectedSingleTask(first.id);
                                setMaxSteps(1);
                                setSingleTokenBudget(8000);
                                setSingleToolTransport('local');
                                setSingleFaultProfile('none');
                              }} />
                            <span>BFCL</span>
                            <small>{bfclTaskCount > 0 ? `${bfclTaskCount} 道改编题` : '尚未导入'}</small>
                          </label>
                          <label className={selectedSuite === 'bfcl_java_adapted' ? 'selected' : ''}
                            aria-disabled={!meta?.tasks.some((task) => task.suite === 'bfcl_java_adapted')}>
                            <input type="radio" name="single-suite" value="bfcl_java_adapted"
                              checked={selectedSuite === 'bfcl_java_adapted'}
                              disabled={!meta?.tasks.some((task) => task.suite === 'bfcl_java_adapted')}
                              onChange={() => {
                                setSelectedSuite('bfcl_java_adapted');
                                setSingleTaskQuery('');
                                const first = meta?.tasks.find((task) => task.suite === 'bfcl_java_adapted');
                                if (first) setSelectedSingleTask(first.id);
                                setMaxSteps(1);
                                setSingleTokenBudget(8000);
                                setSingleToolTransport('local');
                                setSingleFaultProfile('none');
                              }} />
                            <span>BFCL Java</span>
                            <small>固定改编题</small>
                          </label>
                        </div>
                      </fieldset>
                      {selectedSuite !== 'tool_lab_core' && (
                        <p className="suite-provenance">
                          BFCL V4 固定上游提交的 AgentLabyrinth 改编子集；任务卡为中文说明，模型接收英文原题。仅本地精确匹配函数调用提议，非官方分数。
                        </p>
                      )}

                      <label htmlFor="single-task-search" className="form-label task-search-label">搜索任务</label>
                      <input id="single-task-search" className="form-input task-search" type="search"
                        value={singleTaskQuery} placeholder="名称、类别或目标"
                        onChange={(event) => setSingleTaskQuery(event.target.value)}
                        disabled={isLoading || !meta} />

                      <div className="task-option-list" role="group" aria-label="评测任务">
                        {!meta && <p className="task-list-message">正在读取可用任务…</p>}
                        {meta && filteredSingleTasks.length === 0 && (
                          <p className="task-list-message">没有匹配的任务，请调整搜索条件。</p>
                        )}
                        {filteredSingleTasks.map((task) => (
                          <button key={task.id} type="button"
                            className={`task-option ${selectedSingleTask === task.id ? 'selected' : ''}`}
                            aria-pressed={selectedSingleTask === task.id}
                            onClick={() => {
                              if (maxSteps === defaultSingleMaxSteps) setMaxSteps(task.max_steps);
                              if (singleTokenBudget === defaultSingleTokenBudget) setSingleTokenBudget(task.category === 'evidence_chain' ? task.token_budget : 8000);
                              setSelectedSingleTask(task.id);
                              setSingleToolTransport('local');
                              setSingleFaultProfile('none');
                            }}
                            disabled={isLoading}>
                            <span className="task-option-topline">
                              <strong>{task.name}</strong>
                              <span>{taskCategoryLabels[task.category] ?? task.category.replace(/_/g, ' ')}</span>
                            </span>
                            <span className="task-option-description">{taskDescription(task)}</span>
                            <span className="task-option-foot">
                              {task.split === 'development' ? '开发集' : task.split === 'evaluation' ? '评测集' : task.split} · 最多 {task.max_steps} 步 · {
                                task.suite === 'tool_lab_core'
                                  ? task.supports_mcp ? '支持 MCP' : '本地工具'
                                  : '本地函数调用提议评测'
                              }
                            </span>
                          </button>
                        ))}
                      </div>
                    </section>

                    <section className="single-run-options" aria-labelledby="execution-heading">
                      <div className="task-picker-heading execution-heading">
                        <div>
                          <h2 id="execution-heading">配置执行方式</h2>
                          <p>选择模型与 Runtime；其他参数按需展开。</p>
                        </div>
                      </div>

                <div className="form-group">
                    <label htmlFor="model-select" className="form-label">评测模型</label>

                  <select
                    id="model-select"
                    className="form-select"
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    disabled={isLoading}
                  >
                    {!selectedModel && <option value="" disabled>请选择评测模型</option>}
                    {meta?.models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} {m.is_default ? '· 目录默认' : ''} {m.is_experimental ? '· 实验性' : ''}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Model Notes Box */}
                <div className="form-group">
                  <details className="model-note-disclosure">
                    <summary>模型目录说明</summary>
                    <div className="model-note-box" tabIndex={0} aria-label="模型目录说明详情">
                      <strong>说明：</strong>{' '}
                      {currentSingleModelMeta
                        ? currentSingleModelMeta.notes
                        : '模型元数据未就绪；请刷新目录后选择已列出的模型。'}
                    </div>
                  </details>
                </div>

                <fieldset className="execution-choice" disabled={isLoading}>
                  <legend className="form-label">执行 Runtime</legend>
                  <div className="execution-choice-grid">
                    {([
                      ['handwritten', 'Reference', 'Python 手写控制循环'],
                      ['langgraph', 'LangGraph', '独立图节点调度'],
                      ['pydantic_ai', 'PydanticAI', '框架节点驱动单步，步间由适配器推进'],
                    ] as const).map(([backend, name, description]) => (
                      <label className="execution-option" key={backend}>
                        <input type="radio" name="single-runtime-backend" value={backend}
                          checked={singleRuntimeBackend === backend}
                          onChange={() => setSingleRuntimeBackend(backend)} />
                        <span><strong>{name}</strong><small>{description}</small></span>
                      </label>
                    ))}
                  </div>
                  <p className="metric-sub">三种调度方式使用相同工具与评测规则；PydanticAI 的步间推进仍由适配器完成。</p>
                </fieldset>


                  <div className="single-launch-bar">
                    <div className="single-launch-summary" aria-live="polite">
                      <strong>{selectedSingleTaskMeta?.name ?? '请选择任务'}</strong>
                      <span>
                        {currentSingleModelMeta?.name || selectedModel || '请选择模型'}
                        {' · '}{singleRuntimeBackend === 'langgraph' ? 'LangGraph' : singleRuntimeBackend === 'pydantic_ai' ? 'PydanticAI' : 'Reference'}
                        {' · '}
                        {singleToolTransport === 'mcp' && selectedSingleTaskMeta?.supports_mcp
                          ? 'MCP HTTP'
                          : selectedSuite === 'tool_lab_core' ? '本地工具' : '本地函数调用提议评测'}
                      </span>
                      <small>{!meta || !selectedModel ? '目录就绪后可开始运行'
                        : selectedModel === 'fake' ? 'Fake 离线模拟' : '将发起真实模型请求'}</small>
                      <span className="single-parameter-summary">{singleContextChoice === 'full' ? '完整历史' : `近期 ${singleContextWindow} 轮${singleContextChoice === 'memory' ? ` · 记忆 ${singleMemoryBytes} 字节` : ''}`} · 最多 {maxSteps} 步 · {executionSeconds} 秒</span>
                    </div>
                    <div className="single-launch-action">
                      <button id="run-button" className="btn-primary"
                        onClick={handleRunEpisode} disabled={!isSingleRunReady}
                        aria-describedby={singleRunHint ? 'single-run-hint' : undefined}
                        title={!meta ? '元数据尚未就绪' : !selectedSingleTaskMeta ? '请选择一个可见任务后再运行' : undefined}>
                        {isLoading ? <><div className="spinner" /><span>{loadingActivity === 'history' ? '正在读取历史记录…' : '正在运行 Episode…'}</span></>
                          : <span>开始运行 Episode</span>}
                      </button>
                      {singleRunHint && !isLoading && <p id="single-run-hint" className="inline-note" role="status">{singleRunHint}</p>}
                      {isLoading && (
                        <p id="single-run-hint" className="loading-note" role="status" aria-live="polite">
                          {loadingMessage} <span aria-hidden="true">已等待 {elapsedSeconds} 秒。</span>
                        </p>
                      )}
                    </div>
                  </div>
                    </section>
                <details className="advanced-settings single-advanced-settings">
                  <summary>
                    <span>更多设置</span>
                    <span>
                      {singleAdvancedChangeCount > 0
                        ? `${singleAdvancedChangeCount} 项非默认 · 最多 ${maxSteps} 步`
                        : '保持默认值'}
                    </span>
                  </summary>
                  <div className="single-advanced-grid">
                    <section className="settings-group" aria-labelledby="single-tools-heading">
                      <h3 id="single-tools-heading">工具与容错</h3>
                  {selectedSingleTaskMeta?.supports_mcp && (
                    <div className="form-group">
                      <label htmlFor="single-tool-transport" className="form-label">文档工具传输</label>
                      <select id="single-tool-transport" className="form-select" value={singleToolTransport}
                        onChange={(e) => {
                          setSingleToolTransport(e.target.value as 'local' | 'mcp');
                          setSingleFaultProfile('none');
                        }} disabled={isLoading}>
                        <option value="local">本地 ToolLab</option>
                        <option value="mcp">MCP HTTP（需启动独立 localhost 服务）</option>
                      </select>
                    </div>
                  )}
                  <div className="form-group">
                    <label htmlFor="single-call-mode" className="form-label">工具调用方式</label>
                    <select id="single-call-mode" className="form-select" value={selectedSuite === 'tool_lab_core' ? singleCallMode : 'single'}
                      onChange={e => setSingleCallMode(e.target.value as 'single' | 'serial')}
                      disabled={isLoading || selectedSuite !== 'tool_lab_core'}>
                      <option value="serial">多工具：同轮只读调用，按顺序执行</option>
                      <option value="single">单工具：每轮只接受一个调用</option>
                    </select>
                    <p className="form-hint">{selectedSuite === 'tool_lab_core' ? '每批最多8个，提交答案单独调用；窗口按完整模型轮次保留。' : '当前BFCL任务按单函数调用评分，使用单工具方式。'}</p>
                    <label htmlFor="single-runtime-policy" className="form-label">参数纠错策略</label>
                    <select id="single-runtime-policy" className="form-select" value={singleRuntimeStrategy}
                      onChange={(e) => setSingleRuntimeStrategy(e.target.value as 'handwritten' | 'handwritten_recovery')} disabled={isLoading}>
                      <option value="handwritten">关闭：参数错误后终止</option>
                      <option value="handwritten_recovery">开启：INVALID_ARGUMENTS 最多纠错一次</option>
                    </select>
                  </div>

                  {selectedModel === 'fake' && (
                    <>
                    <div className="form-group">
                      <label htmlFor="scenario-select" className="form-label">Fake 模拟场景</label>
                      <select id="scenario-select" className="form-select"
                        value={selectedScenario}
                        onChange={(e) => setSelectedScenario(e.target.value)}
                        disabled={isLoading}>
                        <option value="success">success (完整通过，答案匹配)</option>
                        <option value="invalid-then-success">invalid-then-success (一次重试后通过)</option>
                        <option value="wrong-answer">wrong-answer (提交错误答案)</option>
                        <option value="invalid-arguments">invalid-arguments (工具参数校验失败)</option>
                        <option value="max-steps">max-steps (步数超限终止)</option>
                      </select>
                    </div>
                    {selectedSuite === 'tool_lab_core' && (
                      <div className="form-group">
                        <label htmlFor="single-fault-profile" className="form-label">受控故障</label>
                        <select id="single-fault-profile" className="form-select" value={
                          singleToolTransport === 'mcp'
                            ? singleFaultProfile === 'mcp_disconnect' ? 'mcp_disconnect' : 'none'
                            : singleFaultProfile === 'mcp_disconnect' ? 'none' : singleFaultProfile
                        } onChange={(e) => setSingleFaultProfile(e.target.value)} disabled={isLoading}>
                          <option value="none">无注入</option>
                          {singleToolTransport === 'mcp'
                            ? <option value="mcp_disconnect">MCP 连接中断</option>
                            : <>
                              <option value="tool_timeout">工具超时</option>
                              <option value="empty_result">查询空结果</option>
                            </>}
                        </select>
                        <p className="metric-sub">仅 Fake 工程演示；产物记录故障配置。</p>
                      </div>
                    )}
                    </>
                  )}
                    </section>
                    <section className="settings-group" aria-labelledby="single-context-heading">
                      <h3 id="single-context-heading">上下文与记忆</h3>
                      {selectedSingleTaskMeta?.supports_planning && <div className="form-group">
                        <label className="form-label" htmlFor="single-planning">
                          <input id="single-planning" type="checkbox" checked={singlePlanning} disabled={isLoading}
                            onChange={event => setSinglePlanning(event.target.checked)} /> 启用声明计划
                        </label>
                        <p className="form-hint">模型可声明、更新子目标；额外调用计入相同预算，声明不代表已执行。</p>
                      </div>}
                  <ContextSettings prefix="single-context" choice={singleContextChoice} rounds={singleContextWindow} bytes={singleMemoryBytes} disabled={isLoading}
                    onChoice={setSingleContextChoice} onRounds={setSingleContextWindow} onBytes={setSingleMemoryBytes} />
                    </section>
                    <section className="settings-group" aria-labelledby="single-budget-heading">
                      <h3 id="single-budget-heading">运行预算</h3>
                  <div className="form-group">
                    <label htmlFor="steps-input" className="form-label">步数上限 (Max Steps)</label>
                    <input id="steps-input" type="number" className="form-input" min={1} max={20}
                      value={maxSteps}
                      onChange={(e) => setMaxSteps(parseInt(e.target.value, 10) || 6)}
                      disabled={isLoading} />
                  </div>
                  {selectedModel !== 'fake' && (
                    <div className="form-group">
                      <label htmlFor="single-token-budget" className="form-label">本次运行 Token 预算（输入 + 输出）</label>
                      <input id="single-token-budget" className="form-input" type="number" min={100} max={20000}
                        value={singleTokenBudget ?? ''} placeholder="留空使用任务原预算"
                        onChange={(e) => setSingleTokenBudget(e.target.value === '' ? null : Number(e.target.value))}
                        disabled={isLoading} />
                      <p className="metric-sub">当前任务建议 {defaultSingleTokenBudget}；累计输入与输出计入预算，免费通道仍可能遇到账户限额。</p>
                    </div>
                  )}
                  <div className="form-group">
                    <label htmlFor="single-time-limit" className="form-label">本次运行时限（秒）</label>
                    <input id="single-time-limit" className="form-input" type="number" min={1} max={3600}
                      value={executionSeconds} disabled={isLoading}
                      onChange={(event) => setExecutionSeconds(Math.max(1, Math.min(3600, Math.floor(Number(event.target.value)) || 1)))} />
                    <p className="metric-sub">恢复继承已用时间；已开始的工具先保存结果再停止。</p>
                  </div>
                    </section>
                  </div>
                </details>
                  </div>
                </div>
              </details>

              {/* Right Column: Single Episode Result + Trace View */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {/* Result Summary */}
                <section className="card" id="results-panel" aria-labelledby="episode-results-title">
                  <div className="card-title">
                    <h2 id="episode-results-title" className="section-heading">运行结果指标</h2>
                    {artifact && (
                      <div className="result-heading-actions">
                      <a className="result-jump" href="#trace-panel" onClick={(event) => {
                        if (!tracePanelRef.current) return;
                        event.preventDefault();
                        tracePanelRef.current.focus({ preventScroll: true });
                        tracePanelRef.current.scrollIntoView({ block: 'start' });
                      }}>查看调用过程</a>
                      <span
                        id="eval-badge"
                        className={`badge ${artifact.evaluation.success ? 'badge-green' : 'badge-red'}`}
                      >
                        {artifact.evaluation.success ? '评测通过 (SUCCESS)' : '评测未通过 (FAILED)'}
                      </span>
                      </div>
                    )}
                  </div>
                  {artifact ? (
                    <EpisodeSummary artifact={artifact}
                      explanation={explainFailure(artifact.episode.detail || artifact.evaluation.reason)} />
                  ) : (
                    <div className="empty-state compact-empty">
                      <div>运行完成后，评测指标与只读 Trace 会显示在这里。</div>
                    </div>
                  )}
                </section>

                {artifact && <EpisodeReviewPanel key={artifact.episode.episode_id} artifact={artifact} models={meta?.models ?? []} />}

                {/* Trace Timeline */}
                <section className="card" id="trace-panel" ref={tracePanelRef} tabIndex={-1} aria-labelledby="trace-title">
                  <div className="card-title">
                    <h2 id="trace-title" className="section-heading">{liveRun ? liveRun.status === 'completed' ? '本次执行过程' : '实时执行过程' : 'Trace Replay'}</h2>
                    {artifact && (
                      <span className="badge" style={{ fontFamily: 'var(--font-mono)' }}>
                        {artifact.events.length} 个事件
                      </span>
                    )}
                  </div>
                  <div className="card-desc">
                    {liveRun ? liveRun.status === 'completed' ? '执行已完成，停留在最终输出；仅主动查看时进入历史回放。' : '节点随实际事件即时出现；结束后停留在最终输出，不自动重播。'
                      : '仅回放已保存的事件和环境快照，不重新请求模型或执行工具。'}
                  </div>

                  {liveRun ? (
                    <>
                      <p className="loading-note" role="status">
                        {liveRun.status === 'running' ? '正在接收真实 Trace 事件。' : liveRun.status === 'completed' ? '本次运行已结束，结果已保存。' : '实时连接已中断，后端运行状态未知。'}
                        {liveRun.episodeId && ` Episode ID：${liveRun.episodeId}`}
                      </p>
                      {liveRun.events.length > 0 && <McpFlowReplay displayMode={liveRun.status === 'completed' ? 'completed' : 'live'} events={liveRun.events}
                        environmentVersion={liveRun.environmentVersion} model={liveRun.model}
                        finalState={artifact?.episode.final_state ?? {}} evaluation={artifact?.evaluation}
                        termination={artifact?.episode.termination_reason ?? (liveRun.status === 'running' ? '运行中' : '连接中断')}
                        detail={artifact?.episode.detail ?? ''} />}
                      {liveRun.status === 'completed' && <button type="button" className="btn-secondary"
                        onClick={() => { setReplayPlaying(false); setReplayIndex(0); setReplayView('flow'); setLiveRun(null); }}>
                        查看保存详情与回放
                      </button>}
                    </>
                  ) : artifact && artifact.events.length > 0 ? (
                    <>
                      <div className="view-switch flow-switch" data-active={replayView} aria-label="Replay 视图">
                        <button type="button" className={replayView === 'flow' ? 'active' : ''}
                          aria-pressed={replayView === 'flow'}
                          onClick={() => { setReplayPlaying(false); setReplayView('flow'); }}>
                          流程动画
                        </button>
                        <button type="button" className={replayView === 'story' ? 'active' : ''}
                          aria-pressed={replayView === 'story'}
                          onClick={() => { setReplayPlaying(false); setReplayView('story'); }}>
                          过程概览
                        </button>
                        <button type="button" className={replayView === 'events' ? 'active' : ''}
                          aria-pressed={replayView === 'events'}
                          onClick={() => { setReplayPlaying(false); setEventTypeFilter('ALL'); setReplayView('events'); }}>
                          技术 Trace
                        </button>
                      </div>
                      <div ref={replayMotionRef} className="replay-content" data-view={replayView}>
                      {replayView === 'flow' && <McpFlowReplay key={artifact.episode.episode_id}
                        events={artifact.events} environmentVersion={artifact.run_config.environment_version ?? ''}
                        model={artifact.agent.model.model} finalState={artifact.episode.final_state}
                        evaluation={artifact.evaluation}
                        termination={artifact.episode.termination_reason} detail={artifact.episode.detail}
                        eventIndex={replayIndex} onSelectEvent={setReplayIndex} />}
                      <div hidden={replayView === 'flow'}>
                      {replayView === 'story' && <div className="step-rail" role="group" aria-label="执行步骤（方向键切换）"
                        onKeyDown={(event) => {
                          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
                          const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('.step-card'));
                          const current = buttons.indexOf(event.target as HTMLButtonElement);
                          if (current < 0) return;
                          event.preventDefault();
                          const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
                            : Math.max(0, Math.min(buttons.length - 1, current + (event.key === 'ArrowRight' ? 1 : -1)));
                          setReplayPlaying(false);
                          selectReplayIndex(next);
                          buttons[next]?.focus();
                        }}>
                        {traceSteps.map((group, index) => <button key={`${group.step}-${index}`} type="button"
                          className={`step-card ${safeReplayIndex === index ? 'active' : ''}`}
                          aria-current={safeReplayIndex === index ? 'step' : undefined}
                          onClick={() => { setReplayPlaying(false); selectReplayIndex(index); }}>
                          <span className="step-card-number">{group.step === 0 ? '开始' : `Step ${group.step}`}</span>
                          <strong>{stepTitle(group.events)}</strong>
                          <small>{stepOutcome(group.events)}</small>
                        </button>)}
                      </div>}
                      <div className={`replay-toolbar ${replayView === 'story' ? 'story-toolbar' : ''}`} aria-label="Replay controls">
                        {replayView === 'events' && <label>
                          <span>事件类型</span>
                          <select
                            id="trace-event-filter"
                            className="form-select"
                            value={eventTypeFilter}
                            onChange={(event) => {
                              setReplayPlaying(false);
                              setEventTypeFilter(event.target.value);
                              const first = artifact.events.findIndex((candidate) => event.target.value === 'ALL' || candidate.event_type === event.target.value);
                              setReplayIndex(Math.max(first, 0));
                            }}
                          >
                            <option value="ALL">全部事件</option>
                            {eventTypes.map((eventType) => (
                              <option key={eventType} value={eventType}>
                                {formatEventTypeLabel(eventType)}
                              </option>
                            ))}
                          </select>
                        </label>}
                        <label>
                          <span>跳转 Step</span>
                          <select
                            id="trace-step-jump"
                            className="form-select"
                            value={activeReplayEvent?.step_index ?? ''}
                            disabled={visibleEvents.length === 0}
                            onChange={(event) => {
                              setReplayPlaying(false);
                              const step = Number(event.target.value);
                              const index = visibleEvents.findIndex(
                                (candidate) => candidate.step_index === step,
                              );
                              selectReplayIndex(Math.max(index, 0));
                            }}
                          >
                            {replaySteps.map((step) => (
                              <option key={step} value={step}>
                                Step {step}
                              </option>
                            ))}
                          </select>
                        </label>
                        <div className="replay-buttons">
                          <button
                            id="trace-previous"
                            className="btn-secondary"
                            disabled={safeReplayIndex <= 0 || visibleEvents.length === 0}
                            onClick={() => {
                              setReplayPlaying(false);
                              selectReplayIndex(Math.max(safeReplayIndex - 1, 0));
                            }}
                          >
                            ← 上一步
                          </button>
                          <span className="replay-position">
                            {visibleEvents.length === 0
                              ? '0 / 0'
                              : `${safeReplayIndex + 1} / ${visibleEvents.length}`}
                          </span>
                          <button
                            id="trace-next"
                            className="btn-secondary"
                            disabled={
                              visibleEvents.length === 0 ||
                              safeReplayIndex >= visibleEvents.length - 1
                            }
                            onClick={() => {
                              setReplayPlaying(false);
                              selectReplayIndex(Math.min(safeReplayIndex + 1, visibleEvents.length - 1));
                            }}
                          >
                            下一步 →
                          </button>
                          <button
                            id="trace-play-pause"
                            className="btn-secondary"
                            disabled={visibleEvents.length < 2}
                            aria-label={replayPlaying ? '暂停回放' : '自动播放回放'}
                            onClick={() => {
                              if (!replayPlaying && safeReplayIndex >= visibleEvents.length - 1) {
                                selectReplayIndex(0);
                              }
                              setReplayPlaying(!replayPlaying);
                            }}
                          >
                            {replayPlaying ? '暂停' : '播放'}
                          </button>
                          <label htmlFor="trace-playback-speed">
                            <span>速度</span>
                            <select
                              id="trace-playback-speed"
                              className="form-select"
                              value={replaySpeedMs}
                              onChange={(event) => setReplaySpeedMs(Number(event.target.value))}
                            >
                              <option value={2000}>0.5×</option>
                              <option value={1000}>1×</option>
                              <option value={500}>2×</option>
                            </select>
                          </label>
                        </div>
                      </div>

                      {activeReplayEvent && replayView === 'story' && activeStep ? (
                        <div className="story-stage" ref={storyStageRef}>
                          <div className="story-stage-header" aria-live="polite">
                            <div>
                              <span className="story-eyebrow">{activeStep.step === 0 ? '开始' : `Step ${activeStep.step}`} · {activeStep.events.length} 条已保存事件</span>
                              <h3>{stepTitle(activeStep.events)}</h3>
                            </div>
                            <div className="story-status-group">
                              {artifact.run_config.environment_version === 'tool-lab-mcp-v1' && <span className="story-transport">MCP HTTP</span>}
                              <span className={`story-outcome ${stepFailed ? 'failed' : ''}`}>
                                {stepOutcome(activeStep.events)}
                              </span>
                            </div>
                          </div>
                          <div className="story-stage-grid">
                            <section className="story-sheet">
                              <span className="story-section-label">{proposedCall ? '01 · 模型行动' : initialObservation ? '01 · 任务观察' : '01 · 运行结果'}</span>
                              <h4>{proposedCall ? '选择工具并提交参数' : initialObservation ? '接收任务观察' : '运行结束'}</h4>
                              {proposedCalls.length > 1 ? <div className="story-batch-list" aria-label="本轮工具列表">
                                <p>本轮 {proposedCalls.length} 个调用，按顺序执行；以下仅展示已记录的事件。</p>
                                {proposedCalls.map((call, i) => {
                                  const related = activeStep.events.filter(event => event.payload.call_id === call.payload.call_id);
                                  const returned = related.find(event => ['TOOL_SUCCEEDED', 'TOOL_FAILED'].includes(event.event_type));
                                  const checked = related.find(event => event.event_type === 'TOOL_CALL_VALIDATED');
                                  const rejected = checked?.payload.error_code || checked?.payload.permitted === false || checked?.payload.arguments_valid === false;
                                  return <section className="story-batch-call" key={String(call.payload.call_id)}>
                                    <h4>{i + 1}. {String(call.payload.name)}</h4>
                                    <p className="story-muted">{String(call.payload.call_id)} · {returned ? returned.event_type === 'TOOL_SUCCEEDED' ? '执行成功' : '执行失败'
                                      : rejected ? `校验拒绝：${String(checked?.payload.error_code ?? '未通过')}`
                                      : related.some(event => event.event_type === 'TOOL_STARTED') ? '调用已开始，结果待确认' : '未执行'}</p>
                                    {isRecord(call.payload.arguments) && <ReadableFields entries={Object.entries(call.payload.arguments)} />}
                                    {returned && <ReadableFields entries={toolFeedbackFields(returned, String(call.payload.name))} />}
                                  </section>;
                                })}
                              </div> : proposedCall ? <>
                                <div className="story-tool-name">{String(proposedCall.payload.name ?? '未知工具')}</div>
                                {isRecord(proposedCall.payload.arguments) && Object.keys(proposedCall.payload.arguments).length > 0
                                  ? <ReadableFields entries={Object.entries(proposedCall.payload.arguments)} />
                                  : <p className="story-muted">未记录工具参数</p>}
                              </> : <ReadableFields entries={observationFields} />}
                            </section>
                            <section className="story-sheet">
                              <span className="story-section-label">02 · 校验与反馈</span>
                              <h4>{toolResult?.event_type === 'TOOL_FAILED' || validationRejected
                                ? '行动未通过' : toolResult ? '工具返回' : '尚无工具反馈'}</h4>
                              {proposedCalls.length > 1 ? <p>{activeStep.events.filter(e => e.event_type === 'TOOL_SUCCEEDED').length} 个成功返回，{activeStep.events.filter(e => e.event_type === 'TOOL_FAILED').length} 个执行失败；各调用的校验、参数与结果见本轮工具列表。</p> : <>
                              {validation && <p className={`story-validation ${validationRejected ? 'failed' : ''}`}>
                                工具校验：{validationRejected ? validationError ?? '未通过'
                                  : validation.payload.arguments_valid === true ? '通过' : '未记录结果'}
                              </p>}
                              {visibleFeedback.length > 0
                                ? <ReadableFields entries={visibleFeedback} />
                                : <p className="story-muted">{validationRejected
                                  ? '工具没有执行。' : initialObservation ? '等待模型选择行动。' : '本步没有工具返回。'}</p>}
                              </>}
                              {finishedEvent && proposedCall && <p className="story-finish">
                                终止：{String(finishedEvent.payload.termination_reason ?? '已结束')}
                              </p>}
                            </section>
                            <section className="story-sheet story-state-sheet">
                              <span className="story-section-label">03 · 环境变化</span>
                              <div className="story-state-heading"><h4>与上一步相比</h4><span>{replaySnapshot.source}</span></div>
                              {activeStep.step === 0 && replaySnapshot.state ? <div className="story-initial-state">
                                <span>初始环境已记录</span>
                                {['orders', 'documents', 'acquired_evidence'].filter((key) => Array.isArray(replaySnapshot.state?.[key])).map((key) =>
                                  <span key={key}>{fieldLabels[key]} {(replaySnapshot.state?.[key] as unknown[]).length}</span>)}
                              </div> : hasStepSnapshot && stateChanges.length > 0
                                ? <ReadableFields entries={visibleStateChanges} />
                                : <p className="story-muted">{!replaySnapshot.state ? '此时还没有已保存的环境快照。'
                                  : !hasStepSnapshot ? '本步没有新的环境快照，无法确认字段变化。'
                                    : !previousSnapshot ? '缺少上一步快照，无法计算字段变化。'
                                    : '状态快照与上一步一致。'}</p>}
                            </section>
                          </div>
                          <button type="button" className="story-raw-link" onClick={() => {
                            setReplayPlaying(false);
                            setEventTypeFilter('ALL');
                            setReplayIndex(artifact?.events.findIndex((event) => event.event_id === activeStep.events[0]?.event_id) ?? 0);
                            setReplayView('events');
                          }}>查看本步原始事件 →</button>
                        </div>
                      ) : activeReplayEvent ? (
                        <div className="replay-grid">
                          <aside className="replay-state-panel" aria-label="Environment snapshot">
                            <div className="replay-panel-heading">
                              <span>Environment State</span>
                              <span className="badge badge-cyan">{replaySnapshot.source}</span>
                            </div>
                            {replaySnapshot.state ? (
                              <pre>{JSON.stringify(replaySnapshot.state, null, 2)}</pre>
                            ) : (
                              <div className="replay-unavailable">
                                当前事件之前没有已保存快照。历史产物仍可继续浏览事件。
                              </div>
                            )}
                          </aside>

                          <div className="replay-event-panel" key={activeReplayEvent.event_id}>
                            <div className="replay-panel-heading">
                              <span>当前事件</span>
                              <span className="event-step-pill">
                                Step {activeReplayEvent.step_index}
                              </span>
                            </div>
                            <>
                              <div className="active-event-name">{formatEventTypeLabel(activeReplayEvent.event_type)}</div>
                              <div className="event-raw-name">原始事件名：{activeReplayEvent.event_type}</div>
                              <div className="event-meta">
                                {new Date(activeReplayEvent.timestamp).toLocaleString()}
                                {typeof activeReplayEvent.duration_ms === 'number' && activeReplayEvent.duration_ms > 0
                                  ? ` · ${activeReplayEvent.duration_ms} ms` : ' · 时长未知'}
                              </div>
                              <pre>{JSON.stringify(activeReplayEvent.payload, null, 2)}</pre>
                            </>
                          </div>
                        </div>
                      ) : (
                        <div className="empty-state compact-empty">
                          当前筛选没有匹配事件，请选择其他事件类型。
                        </div>
                      )}

                      {replayView === 'events' && visibleEvents.length > 0 && (
                        <div className="timeline-container" id="timeline-list">
                          {visibleEvents.map((ev, index) => {
                            const isExpanded = !!expandedEvents[ev.event_id];
                            const isActive = ev.event_id === activeReplayEvent?.event_id;
                            return (
                              <div
                                key={ev.event_id}
                                className={`timeline-event ${isActive ? 'active' : ''}`}
                              >
                                <button
                                  type="button"
                                  className="event-header"
                                  aria-expanded={isExpanded}
                                  onClick={() => {
                                    selectReplayIndex(index);
                                    toggleEventExpand(ev.event_id);
                                  }}
                                >
                                  <div className="event-info">
                                    <span className="event-step-pill">Step {ev.step_index}</span>
                                    <span className="event-name-stack">
                                      <span className="event-name">{formatEventTypeLabel(ev.event_type)}</span>
                                      <span className="event-raw-name">{ev.event_type}</span>
                                    </span>
                                  </div>
                                  <div className="event-meta">
                                    <span>{new Date(ev.timestamp).toLocaleTimeString()}</span>
                                    <span>{isExpanded ? '▲ 收起' : '▼ 展开'}</span>
                                  </div>
                                </button>
                                {isExpanded && (
                                  <div className="event-body">
                                    <pre>{JSON.stringify(ev.payload, null, 2)}</pre>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                      </div>
                      </div>
                    </>
                  ) : (
                    <div className="empty-state">
                      <div className="empty-icon">暂无 Trace</div>
                      <div>Trace 数据将在 Episode 执行完成后呈现在此。</div>
                    </div>
                  )}
                </section>
              </div>
            </div>
            {resumableEpisodeIds.length > 0 && (
              <section className="card resumable-panel" aria-labelledby="resumable-title">
                <div className="card-title" id="resumable-title">待恢复的单次运行</div>
                <p className="card-desc">
                  仅列出上次后端进程留下的运行。恢复可能重新发送中断中的模型请求并产生额外用量。
                </p>
                <div className="resumable-list">
                  {resumableEpisodeIds.map((id) => (
                    <button key={id} className="btn-secondary" disabled={isLoading}
                      onClick={() => handleResumeEpisode(id)}>
                      恢复 Episode <code>{id}</code>
                    </button>
                  ))}
                </div>
              </section>
            )}
            {recentEpisodeIds.length > 0 && (
              <section className="card recent-episodes" aria-labelledby="recent-episodes-title">
                <div className="card-title" id="recent-episodes-title">最近运行</div>
                <p className="card-desc">历史条目仅通过 GET 回读；切换历史产物不会发起新运行。</p>
                <div className="recent-episode-list">
                  {recentEpisodeIds.map((id) => {
                    const summary = episodeHistorySummaries[id];
                    const status = summary?.status === 'ready'
                      ? summary.success === undefined ? '结果未记录' : summary.success ? '评测通过' : '评测未通过'
                      : summary?.status === 'error' ? '摘要暂不可用' : '读取摘要中';
                    const statusClass = summary?.status === 'ready'
                      ? summary.success === undefined ? 'badge' : summary.success ? 'badge-green' : 'badge-red'
                      : 'badge';
                    const parsedTime = summary?.timestamp ? new Date(summary.timestamp) : null;
                    const time = parsedTime && !Number.isNaN(parsedTime.getTime())
                      ? parsedTime.toLocaleString() : '时间未记录';
                    return (
                      <article className="recent-episode-row" key={id}>
                        <button type="button" className="recent-episode-open"
                          onClick={() => loadEpisodeById(id)} disabled={isLoading}>
                          <span className="recent-episode-main">
                            <strong>{summary?.taskName ?? '读取历史 Episode'}</strong>
                            <span>{summary?.modelId ?? (summary?.status === 'error' ? '无法读取摘要' : '模型信息读取中')} · {time}</span>
                          </span>
                          <span className={`badge ${statusClass}`}>{status}</span>
                        </button>
                        <button type="button" className="btn-secondary recent-episode-copy"
                          aria-label={`复制 Episode ID ${id}`}
                          onClick={async () => setCopyNotice(await copyTextToClipboard(id, 'Episode ID'))}>
                          复制 ID
                        </button>
                      </article>
                    );
                  })}
                </div>
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
