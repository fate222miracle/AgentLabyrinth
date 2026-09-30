import { useState, useEffect, useLayoutEffect, useRef } from 'react';
import { changedStateFields, groupTraceByStep, keyFields, stepOutcome, stepTitle } from './traceSteps';
import { McpFlowReplay } from './McpFlowReplay';
import { summarizeEpisode, type EpisodeHistorySummary, type ExperimentDashboardItem } from './historySummary';
import { ExperimentDashboard } from './ExperimentDashboard';
import { readEpisodeStream } from './streamEpisode';

interface ModelOption {
  id: string;
  name: string;
  provider: 'fake' | 'aihubmix';
  is_default: boolean;
  is_experimental: boolean;
  notes: string;
  scenarios: string[];
}

interface TaskOption {
  id: string;
  name: string;
  category: string;
  description: string;
  max_steps: number;
  token_budget: number;
  suite: 'tool_lab_core' | 'bfcl_adapted' | 'bfcl_java_adapted';
  split: string;
  supports_mcp: boolean;
}

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
  error_recovery: '错误恢复',
  bfcl_single_call: '单次函数调用',
};

function taskDescription(task: TaskOption): string {
  return task.suite !== 'tool_lab_core' ? bfclDescriptions[task.id] ?? task.description : task.description;
}

interface MetaResponse {
  schema_version: string;
  request_id: string;
  models: ModelOption[];
  tasks: TaskOption[];
  default_model: string;
  default_task: string;
  model_catalog_status: 'live' | 'unavailable' | 'static';
}

interface TraceEvent {
  event_id: string;
  episode_id: string;
  step_index: number;
  event_type: string;
  timestamp: string;
  duration_ms: number;
  payload: Record<string, unknown>;
  token_usage: {
    prompt_tokens: number;
    completion_tokens: number;
    simulated: boolean;
  };
  estimated_cost: {
    amount: string;
    currency: string;
    price_table_version: string;
    is_known: boolean;
  };
}

interface EpisodeArtifact {
  schema_version: string;
  task: {
    name: string;
    max_steps: number;
    evaluator_config: Record<string, unknown>;
  };
  episode: {
    episode_id: string;
    termination_reason: string;
    detail: string;
    step_count: number;
    model_call_count: number;
    tool_call_count: number;
    duration_ms: number;
    token_usage: {
      prompt_tokens: number;
      completion_tokens: number;
      simulated: boolean;
    };
    estimated_cost: {
      amount: string;
      currency: string;
      price_table_version: string;
      is_known: boolean;
    };
    final_state: Record<string, unknown>;
  };
  evaluation: {
    success: boolean;
    reason: string;
    metrics: Record<string, unknown>;
  };
  run_config: { runtime_version?: string | null; environment_version?: string };
  agent: {
    name?: string;
    runtime_strategy?: string;
    runtime_backend?: string;
    model: {
      provider: string;
      model: string;
    };
  };
  events: TraceEvent[];
  reference_cost?: {
    amount: string;
    currency: string;
    price_table_version: string;
    is_known: boolean;
  } | null;
}

interface PairComparison {
  task_id: string;
  task_name: string;
  seed: number;
  repeat_index?: number;
  baseline_episode_id: string;
  baseline_success: boolean;
  baseline_termination_reason: string;
  baseline_steps: number;
  baseline_tokens: number;
  baseline_duration_ms: number;
  baseline_cost?: string | null;
  baseline_reference_cost?: string | null;
  baseline_model_calls?: number | null;
  baseline_tool_calls?: number | null;
  baseline_tool_selection_accuracy?: number | null;
  baseline_tool_argument_validity_rate?: number | null;
  recovery_episode_id: string;
  recovery_success: boolean;
  recovery_termination_reason: string;
  recovery_steps: number;
  recovery_tokens: number;
  recovery_duration_ms: number;
  recovery_cost?: string | null;
  recovery_reference_cost?: string | null;
  recovery_model_calls?: number | null;
  recovery_tool_calls?: number | null;
  recovery_tool_selection_accuracy?: number | null;
  recovery_tool_argument_validity_rate?: number | null;
  retry_eligible?: boolean | null;
  recovered: boolean;
}

interface ExperimentAggregateMetrics {
  total_pairs: number;
  baseline_success_count: number;
  recovery_success_count: number;
  baseline_success_rate: number;
  recovery_success_rate: number;
  retry_eligible_count?: number | null;
  retry_recovery_count: number | null;
  retry_recovery_rate?: number | null;
  baseline_total_tokens: number;
  recovery_total_tokens: number;
  baseline_avg_steps: number;
  recovery_avg_steps: number;
  baseline_avg_model_calls?: number | null;
  recovery_avg_model_calls?: number | null;
  baseline_avg_tool_calls?: number | null;
  recovery_avg_tool_calls?: number | null;
  baseline_tool_selection_accuracy?: number | null;
  recovery_tool_selection_accuracy?: number | null;
  baseline_tool_argument_validity_rate?: number | null;
  recovery_tool_argument_validity_rate?: number | null;
  baseline_avg_duration_ms: number;
  recovery_avg_duration_ms: number;
  baseline_total_cost?: string | null;
  recovery_total_cost?: string | null;
  is_cost_known: boolean;
  baseline_total_reference_cost?: string | null;
  recovery_total_reference_cost?: string | null;
  is_reference_cost_known?: boolean;
}

interface ExperimentArtifact {
  schema_version: string;
  experiment_id: string;
  created_at: string;
  config: Record<string, unknown>;
  config_hash: string;
  episode_ids: string[];
  pairs: PairComparison[];
  metrics: ExperimentAggregateMetrics;
}

interface ExperimentJobState {
  experiment_id: string;
  status: 'queued' | 'running' | 'paused' | 'cancelled' | 'completed' | 'failed' | 'interrupted';
  requested_action: 'pause' | 'cancel' | null;
  error_code: string | null;
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

const fieldLabels: Record<string, string> = {
  answer: '答案', evidence: '引用证据', acquired_evidence: '已获取证据',
  records: '查询记录', documents: '文档', document: '文档内容',
  document_id: '文档 ID', order_id: '订单 ID', status: '状态',
  evidence_id: '证据 ID', target_order_id: '目标订单', task_kind: '任务类型',
  document_query: '文档检索目标', code: '错误码', message: '错误说明', retryable: '可重试',
  title: '标题', content: '内容', feedback: '反馈',
  submission: '提交内容', accepted: '已接受', proposed_call: '已提交调用',
  table: '数据表', filters: '筛选条件', query: '检索词', top_k: '返回上限',
  description: '任务说明', question: '任务问题', done: '任务结束',
  termination_reason: '终止原因', detail: '详情', success: '成功',
};

function ReadableValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="story-muted">无</span>;
  if (typeof value === 'boolean') return <span>{value ? '是' : '否'}</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="story-muted">空</span>;
    return <div className="story-value-list">{value.map((item, index) =>
      <div className="story-value-item" key={index}><ReadableValue value={item} /></div>)}</div>;
  }
  if (isRecord(value)) return Object.keys(value).length > 0
    ? <ReadableFields entries={Object.entries(value)} /> : <span className="story-muted">空</span>;
  return <span className="story-value-text">{String(value)}</span>;
}

function ReadableFields({ entries }: { entries: [string, unknown][] }) {
  return <dl className="story-fields">{entries.map(([key, value]) =>
    <div className="story-field" key={key}>
      <dt title={key}>{fieldLabels[key] ?? key.replace(/_/g, ' ')}</dt>
      <dd><ReadableValue value={value} /></dd>
    </div>)}</dl>;
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
    'tool_argument_validity_rate', 'pair_retry_eligible', 'pair_recovered',
  ];
  const axis = typeof experiment.config.comparison_axis === 'string'
    ? experiment.config.comparison_axis : 'recovery_policy';
  const rows = experiment.pairs.flatMap((pair) => [
    [experiment.experiment_id, experiment.config_hash, axis, pair.task_id, pair.seed,
      pair.repeat_index ?? 1, axis === 'runtime_backend' ? 'reference' : 'baseline',
      pair.baseline_episode_id, pair.baseline_success,
      pair.baseline_termination_reason, pair.baseline_steps, pair.baseline_model_calls,
      pair.baseline_tool_calls, pair.baseline_tokens, pair.baseline_duration_ms,
      pair.baseline_cost, pair.baseline_reference_cost, pair.baseline_tool_selection_accuracy,
      pair.baseline_tool_argument_validity_rate,
      axis === 'runtime_backend' ? null : pair.retry_eligible,
      axis === 'runtime_backend' ? null : pair.recovered],
    [experiment.experiment_id, experiment.config_hash, axis, pair.task_id, pair.seed,
      pair.repeat_index ?? 1, axis === 'runtime_backend' ? 'langgraph' : 'recovery',
      pair.recovery_episode_id, pair.recovery_success,
      pair.recovery_termination_reason, pair.recovery_steps, pair.recovery_model_calls,
      pair.recovery_tool_calls, pair.recovery_tokens, pair.recovery_duration_ms,
      pair.recovery_cost, pair.recovery_reference_cost, pair.recovery_tool_selection_accuracy,
      pair.recovery_tool_argument_validity_rate,
      axis === 'runtime_backend' ? null : pair.retry_eligible,
      axis === 'runtime_backend' ? null : pair.recovered],
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

function comparisonLabel(pair: PairComparison, axis: 'recovery_policy' | 'runtime_backend'): string {
  if (axis === 'runtime_backend') {
    if (pair.baseline_success && pair.recovery_success) return '两种 Runtime 均通过';
    if (!pair.baseline_success && !pair.recovery_success) return '两种 Runtime 均未通过';
    return pair.baseline_success ? 'Reference 通过' : 'LangGraph 通过';
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
    environmentVersion: string; status: 'running' | 'interrupted';
  } | null>(null);
  const [recentEpisodeIds, setRecentEpisodeIds] = useState<string[]>([]);
  const [episodeHistorySummaries, setEpisodeHistorySummaries] = useState<
    Record<string, EpisodeHistorySummary>
  >({});
  const [resumableEpisodeIds, setResumableEpisodeIds] = useState<string[]>([]);
  const [inputEpisodeId, setInputEpisodeId] = useState<string>('');
  const [expandedEvents, setExpandedEvents] = useState<Record<string, boolean>>({});
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('ALL');
  const [replayIndex, setReplayIndex] = useState<number>(0);
  const [replayPlaying, setReplayPlaying] = useState<boolean>(false);
  const [replaySpeedMs, setReplaySpeedMs] = useState<number>(1000);
  const [replayView, setReplayView] = useState<'flow' | 'story' | 'events'>('flow');
  const storyStageRef = useRef<HTMLDivElement>(null);
  const previousStoryIndex = useRef(0);

  // Experiment states
  const [expModel, setExpModel] = useState<string>('');
  const [expScenario, setExpScenario] = useState<string>('invalid-then-success');
  const [expFaultProfile, setExpFaultProfile] = useState<string>('none');
  const [comparisonAxis, setComparisonAxis] = useState<'recovery_policy' | 'runtime_backend'>('recovery_policy');
  const [expRuntimeBackend, setExpRuntimeBackend] = useState<'handwritten' | 'langgraph'>('handwritten');
  const [expRuntimeStrategy, setExpRuntimeStrategy] = useState<'handwritten' | 'handwritten_recovery'>('handwritten_recovery');
  const [singleRuntimeBackend, setSingleRuntimeBackend] = useState<'handwritten' | 'langgraph'>('handwritten');
  const [singleToolTransport, setSingleToolTransport] = useState<'local' | 'mcp'>('local');
  const [singleRuntimeStrategy, setSingleRuntimeStrategy] = useState<'handwritten' | 'handwritten_recovery'>('handwritten');
  const [expTasks, setExpTasks] = useState<string[]>([]);
  const [expSeedsText, setExpSeedsText] = useState<string>('1');
  const [expRepeatCount, setExpRepeatCount] = useState<number>(1);
  const [expTokenBudget, setExpTokenBudget] = useState<number | null>(8000);
  const [expReferenceBudget, setExpReferenceBudget] = useState<string>('');
  const [singleTokenBudget, setSingleTokenBudget] = useState<number | null>(8000);
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

  // Custom Model states
  const [customModels, setCustomModels] = useState<string[]>([]);
  const [showCustomModelInputExp, setShowCustomModelInputExp] = useState<boolean>(false);
  const [customModelTextExp, setCustomModelTextExp] = useState<string>('');
  const [showCustomModelInputSingle, setShowCustomModelInputSingle] = useState<boolean>(false);
  const [customModelTextSingle, setCustomModelTextSingle] = useState<string>('');

  // Global loading & error
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [loadingMessage, setLoadingMessage] = useState<string>('');
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copyNotice, setCopyNotice] = useState<string | null>(null);
  const historyRequestId = useRef(0);

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

  const beginLoading = (message: string) => {
    setLoadingMessage(message);
    setIsLoading(true);
  };

  const finishLoading = () => {
    setIsLoading(false);
    setLoadingMessage('');
  };

  useEffect(() => {
    if (!activeJobId) return;
    let cancelled = false;
    let timer = 0;
    beginLoading('实验运行中；暂停与取消将在当前 Episode 结束后生效。');
    const poll = async () => {
      try {
        const response = await fetch(`/api/v1/experiments/jobs/${encodeURIComponent(activeJobId)}`);
        if (!response.ok) throw new Error(`实验状态读取失败 (${response.status})`);
        const job = await response.json() as ExperimentJobState;
        if (cancelled) return;
        setExperimentJob(job);
        if (job.status === 'completed') {
          const result = await fetch(`/api/v1/experiments/${encodeURIComponent(activeJobId)}`);
          if (!result.ok) throw new Error('实验已完成，但结果读取失败');
          const data = await result.json() as { experiment: ExperimentArtifact };
          if (cancelled) return;
          setExperiment(data.experiment);
          addRecentExpId(activeJobId);
          setResumableJobIds((ids) => ids.filter((id) => id !== activeJobId));
          refreshExperimentDashboard();
          const url = new URL(window.location.href);
          if (url.searchParams.get('experiment_job_id') === activeJobId) {
            url.searchParams.set('experiment_id', activeJobId);
            url.searchParams.delete('experiment_job_id');
            window.history.replaceState({}, '', url.toString());
          }
          setActiveJobId(null);
          finishLoading();
        } else if (['paused', 'cancelled', 'failed', 'interrupted'].includes(job.status)) {
          finishLoading();
          if (job.status === 'paused' || job.status === 'interrupted' || job.status === 'failed') {
            setResumableJobIds((ids) => ids.includes(activeJobId) ? ids : [activeJobId, ...ids]);
          } else {
            setResumableJobIds((ids) => ids.filter((id) => id !== activeJobId));
          }
          if (job.status === 'failed') setErrorMsg(job.error_code === 'REFERENCE_COST_BUDGET_EXCEEDED'
            ? '已达到原厂标价参考预算；已完成的 Episode 已保存。若要提高预算，请创建新实验。'
            : '实验执行失败，已完成的 Episode 仍保留；可检查后恢复。');
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
        if (!res.ok) throw new Error('dashboard unavailable');
        return res.json();
      })
      .then((data: { items: ExperimentDashboardItem[]; skipped_count: number }) => {
        if (controller.signal.aborted) return;
        setDashboardItems(Array.isArray(data.items) ? data.items : []);
        setDashboardSkipped(data.skipped_count ?? 0);
        setDashboardError(false);
      })
      .catch(() => { if (!controller.signal.aborted) setDashboardError(true); })
      .finally(() => { if (!controller.signal.aborted) setDashboardLoading(false); });
  };

  const addCustomModel = (modelId: string, target: 'exp' | 'single') => {
    const cleanId = modelId.trim();
    if (!cleanId) return;
    setCustomModels((prev) => {
      const next = prev.includes(cleanId) ? prev : [...prev, cleanId];
      try {
        localStorage.setItem('al_custom_models', JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
    if (target === 'exp') {
      setExpModel(cleanId);
      setShowCustomModelInputExp(false);
      setCustomModelTextExp('');
    } else {
      setSelectedModel(cleanId);
      setShowCustomModelInputSingle(false);
      setCustomModelTextSingle('');
    }
  };

  // 1. Fetch Metadata and parse initial query parameters
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const expId = params.get('experiment_id');
    const epId = params.get('episode_id');
    const jobId = params.get('experiment_job_id');

    fetch('/api/v1/meta')
      .then((res) => {
        if (!res.ok) throw new Error('无法连接后端配置元数据');
        return res.json();
      })
      .then((data: MetaResponse) => {
        setMeta(data);
        if (data.default_model) {
          setSelectedModel(data.default_model);
          setExpModel(data.default_model);
        }
        if (data.tasks && data.tasks.length > 0) {
          const initialTask = data.tasks.find((task) => task.suite === 'tool_lab_core') ?? data.tasks[0];
          setSelectedSuite(initialTask.suite);
          setSelectedSingleTask(initialTask.id);
          setExpTasks(data.tasks.filter((t) => t.suite === 'tool_lab_core').map((t) => t.id));
        }
      })
      .catch((err) => {
        setErrorMsg(`API 连通性错误: ${err.message}`);
      });
    fetch('/api/v1/episodes/resumable')
      .then((res) => res.ok ? res.json() : [])
      .then((ids: string[]) => setResumableEpisodeIds(ids))
      .catch(() => setResumableEpisodeIds([]));
    fetch('/api/v1/experiments/resumable')
      .then((res) => res.ok ? res.json() : [])
      .then((ids: string[]) => setResumableExpIds(ids))
      .catch(() => setResumableExpIds([]));
    fetch('/api/v1/experiments/jobs/resumable')
      .then((res) => res.ok ? res.json() : [])
      .then((ids: string[]) => setResumableJobIds(ids))
      .catch(() => setResumableJobIds([]));
    refreshExperimentDashboard();

    // Load recent history from localStorage
    try {
      const readList = (key: string): string[] => {
        const value: unknown = JSON.parse(localStorage.getItem(key) ?? '[]');
        return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
      };
      setRecentEpisodeIds(readList('al_recent_episodes').slice(0, 5));
      setRecentExpIds(readList('al_recent_experiments').slice(0, 5));
      setCustomModels(readList('al_custom_models'));
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
    }

    const handlePopState = () => {
      const next = new URLSearchParams(window.location.search);
      const nextExpId = next.get('experiment_id');
      const nextEpId = next.get('episode_id');
      const nextJobId = next.get('experiment_job_id');
      if (nextJobId) {
        setActiveTab('experiment');
        setActiveJobId(nextJobId);
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
        historyRequestId.current += 1;
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
    setReplayIndex(Math.max((artifact?.events.length ?? 1) - 1, 0));
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
          if (!response.ok) return [id, { status: 'error' } satisfies EpisodeHistorySummary] as const;
          const data = await response.json() as { artifact?: Partial<EpisodeArtifact> };
          return [id, data.artifact ? summarizeEpisode(data.artifact)
            : { status: 'error' } satisfies EpisodeHistorySummary] as const;
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
    const requestId = ++historyRequestId.current;
    setLiveRun(null);
    beginLoading('正在读取历史 Episode。');
    setErrorMsg(null);
    if (!updateUrl) setArtifact(null);
    try {
      const res = await fetch(`/api/v1/episodes/${encodeURIComponent(id.trim())}`);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(res.status === 404
          ? `未能找到 Episode ${id.trim()}` : errData.message || `读取 Episode 失败 (${res.status})`);
      }
      const data = await res.json();
      if (requestId !== historyRequestId.current) return;
      setArtifact(data.artifact);
      addRecentEpisodeId(id.trim());

      if (updateUrl) {
        const url = new URL(window.location.href);
        url.searchParams.set('episode_id', id.trim());
        url.searchParams.delete('experiment_id');
        url.searchParams.delete('experiment_job_id');
        window.history.pushState({}, '', url.toString());
      }
    } catch (err: unknown) {
      if (requestId !== historyRequestId.current) return;
      const message = err instanceof Error ? err.message : '加载失败';
      setErrorMsg(message);
    } finally {
      if (requestId === historyRequestId.current) finishLoading();
    }
  };

  // Load an existing experiment by ID
  const loadExperimentById = async (id: string, updateUrl = true) => {
    if (!id || id.trim().length === 0) return;
    setActiveJobId(null);
    const requestId = ++historyRequestId.current;
    setLiveRun(null);
    beginLoading('正在读取历史对照实验。');
    setErrorMsg(null);
    if (!updateUrl) setExperiment(null);
    try {
      const res = await fetch(`/api/v1/experiments/${encodeURIComponent(id.trim())}`);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(res.status === 404
          ? `未能找到 Experiment ${id.trim()}` : errData.message || `读取 Experiment 失败 (${res.status})`);
      }
      const data = await res.json();
      if (requestId !== historyRequestId.current) return;
      setExperiment(data.experiment);
      addRecentExpId(id.trim());

      if (updateUrl) {
        const url = new URL(window.location.href);
        url.searchParams.set('experiment_id', id.trim());
        url.searchParams.delete('episode_id');
        url.searchParams.delete('experiment_job_id');
        window.history.pushState({}, '', url.toString());
      }
    } catch (err: unknown) {
      if (requestId !== historyRequestId.current) return;
      const message = err instanceof Error ? err.message : '加载实验失败';
      setErrorMsg(message);
    } finally {
      if (requestId === historyRequestId.current) finishLoading();
    }
  };

  // Execute single episode
  const handleRunEpisode = async () => {
    const requestId = ++historyRequestId.current;
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
    try {
      const currentModelObj = meta?.models.find((m) => m.id === selectedModel);
      const isFake = selectedModel === 'fake' || currentModelObj?.provider === 'fake';

      const payload = {
        provider: isFake ? 'fake' : 'aihubmix',
        model: isFake ? 'fake-model' : selectedModel,
        scenario: isFake ? selectedScenario : null,
        task_id: selectedSingleTask,
        suite: selectedSuite,
        max_steps: maxSteps,
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

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.message || `执行失败 (${res.status})`);
      }

      const data = await readEpisodeStream(res, (value) => {
        if (requestId !== historyRequestId.current) return;
        if (!value || typeof value !== 'object' || !('event_id' in value)
          || typeof value.event_id !== 'string' || !('episode_id' in value)
          || typeof value.episode_id !== 'string' || !('event_type' in value)
          || typeof value.event_type !== 'string' || !('payload' in value)
          || !value.payload || typeof value.payload !== 'object') {
          throw new Error('实时 Trace 格式无效。');
        }
        const event = value as TraceEvent;
        setLiveRun((current) => current ? { ...current, episodeId: event.episode_id,
          events: [...current.events, event] } : current);
      }) as { artifact?: EpisodeArtifact };
      if (requestId !== historyRequestId.current) return;
      if (!data?.artifact?.episode?.episode_id) throw new Error('完成事件缺少 Episode 产物。');
      const newArtifact = data.artifact as EpisodeArtifact;
      setArtifact(newArtifact);
      setLiveRun(null);
      addRecentEpisodeId(newArtifact.episode.episode_id);

      const url = new URL(window.location.href);
      url.searchParams.set('episode_id', newArtifact.episode.episode_id);
      url.searchParams.delete('experiment_id');
      window.history.replaceState({}, '', url.toString());
    } catch (err: unknown) {
      if (requestId !== historyRequestId.current) return;
      const message = err instanceof Error ? err.message : '运行失败';
      setErrorMsg(message);
      setLiveRun((current) => current ? { ...current, status: 'interrupted' } : current);
      fetch('/api/v1/episodes/resumable')
        .then((res) => res.ok ? res.json() : [])
        .then((ids: string[]) => setResumableEpisodeIds(ids))
        .catch(() => {});
    } finally {
      if (requestId === historyRequestId.current) finishLoading();
    }
  };

  const handleResumeEpisode = async (id: string) => {
    setLiveRun(null);
    beginLoading('正在从最近存档恢复 Episode。');
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/v1/episodes/${encodeURIComponent(id)}/resume`, {
        method: 'POST',
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.message || `恢复失败 (${res.status})`);
      }
      const data = await res.json();
      setArtifact(data.artifact as EpisodeArtifact);
      setResumableEpisodeIds((previous) => previous.filter((item) => item !== id));
      addRecentEpisodeId(id);
      const url = new URL(window.location.href);
      url.searchParams.set('episode_id', id);
      url.searchParams.delete('experiment_id');
      window.history.pushState({}, '', url.toString());
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : '恢复失败');
    } finally {
      finishLoading();
    }
  };

  // Execute paired experiment
  const handleResumeExperiment = async (id: string) => {
    beginLoading('正在恢复原实验，已完成的 Episode 会直接复用。');
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/v1/experiments/${encodeURIComponent(id)}/resume`, {
        method: 'POST',
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.message || `实验恢复失败 (${res.status})`);
      }
      const data = await res.json();
      setExperiment(data.experiment as ExperimentArtifact);
      refreshExperimentDashboard();
      setResumableExpIds((previous) => previous.filter((item) => item !== id));
      addRecentExpId(id);
      const url = new URL(window.location.href);
      url.searchParams.set('experiment_id', id);
      url.searchParams.delete('episode_id');
      window.history.pushState({}, '', url.toString());
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : '实验恢复失败');
    } finally {
      finishLoading();
    }
  };

  const handleRerunFailedEpisode = async () => {
    if (!artifact || artifact.evaluation.success) return;
    const sourceId = artifact.episode.episode_id;
    beginLoading('正在按原始配置单独重跑失败 Episode。');
    setErrorMsg(null);
    try {
      const response = await fetch(`/api/v1/episodes/${encodeURIComponent(sourceId)}/rerun`, {
        method: 'POST',
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || `失败 Episode 重跑被拒绝 (${response.status})`);
      const rerun = data.artifact as EpisodeArtifact;
      setArtifact(rerun);
      addRecentEpisodeId(rerun.episode.episode_id);
      const url = new URL(window.location.href);
      url.searchParams.set('episode_id', rerun.episode.episode_id);
      url.searchParams.delete('experiment_id');
      url.searchParams.delete('experiment_job_id');
      window.history.pushState({}, '', url.toString());
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : '失败 Episode 重跑失败');
    } finally {
      finishLoading();
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
    const episodeCount = expTasks.length * seeds.length * expRepeatCount * 2;
    beginLoading(`正在串行执行${comparisonAxis === 'runtime_backend' ? 'Runtime' : '恢复策略'}对照，预计 ${episodeCount} 个 Episode。`);
    setErrorMsg(null);
    let started = false;
    try {
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
        max_reference_cost_usd: isFake || expReferenceBudget === '' ? null : expReferenceBudget,
        comparison_axis: comparisonAxis,
        runtime_backend: expRuntimeBackend,
        runtime_strategy: expRuntimeStrategy,
        fault_profile: isFake ? expFaultProfile : 'none',
      };

      const res = await fetch('/api/v1/experiments/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.message || `对照实验执行失败 (${res.status})`);
      }

      const job = await res.json() as ExperimentJobState;
      started = true;
      setExperiment(null);
      setExperimentJob(job);
      setActiveJobId(job.experiment_id);
      setJobWatchToken((value) => value + 1);

      const url = new URL(window.location.href);
      url.searchParams.set('experiment_job_id', job.experiment_id);
      url.searchParams.delete('experiment_id');
      url.searchParams.delete('episode_id');
      window.history.pushState({}, '', url.toString());
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '对照实验运行失败';
      setErrorMsg(message);
      fetch('/api/v1/experiments/resumable')
        .then((res) => res.ok ? res.json() : [])
        .then((ids: string[]) => setResumableExpIds(ids))
        .catch(() => {});
    } finally {
      if (!started) finishLoading();
    }
  };

  const handleControlExperimentJob = async (
    action: 'pause' | 'cancel' | 'resume', targetId = activeJobId,
  ) => {
    if (!targetId) return;
    setErrorMsg(null);
    try {
      const response = await fetch(
        `/api/v1/experiments/jobs/${encodeURIComponent(targetId)}/${action}`,
        { method: 'POST' },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || `实验控制失败 (${response.status})`);
      setExperimentJob(data as ExperimentJobState);
      if (action === 'resume') {
        setActiveJobId(targetId);
        setJobWatchToken((value) => value + 1);
        setResumableJobIds((ids) => ids.filter((id) => id !== targetId));
        const url = new URL(window.location.href);
        url.searchParams.set('experiment_job_id', targetId);
        url.searchParams.delete('experiment_id');
        url.searchParams.delete('episode_id');
        window.history.pushState({}, '', url.toString());
      } else if (data.status === 'cancelled') {
        setResumableJobIds((ids) => ids.filter((id) => id !== targetId));
      }
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : '实验控制失败');
    }
  };

  const toggleEventExpand = (eventId: string) => {
    setExpandedEvents((prev) => ({ ...prev, [eventId]: !prev[eventId] }));
  };

  const toggleTaskSelection = (taskId: string) => {
    setExpTasks((prev) =>
      prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId]
    );
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
  const defaultSingleMaxSteps = selectedSuite !== 'tool_lab_core' ? 1 : 6;
  const singleAdvancedChangeCount = [
    singleRuntimeStrategy !== 'handwritten',
    singleToolTransport === 'mcp' && Boolean(selectedSingleTaskMeta?.supports_mcp),
    maxSteps !== defaultSingleMaxSteps,
    selectedModel === 'fake' && selectedScenario !== 'success',
    selectedModel === 'fake' && singleFaultProfile !== 'none',
    selectedModel !== 'fake' && singleTokenBudget !== 8000,
  ].filter(Boolean).length;
  const eventTypes = Array.from(new Set(artifact?.events.map((event) => event.event_type) ?? []));
  const traceSteps = groupTraceByStep(artifact?.events ?? []);
  const visibleEvents = replayView === 'story'
    ? traceSteps.map((group) => group.events[group.events.length - 1])
    : artifact?.events.filter(
        (event) => eventTypeFilter === 'ALL' || event.event_type === eventTypeFilter,
      ) ?? [];
  const safeReplayIndex = Math.min(replayIndex, Math.max(visibleEvents.length - 1, 0));
  const activeReplayEvent = visibleEvents[safeReplayIndex];
  const activeStep = replayView === 'story' ? traceSteps[safeReplayIndex] : undefined;
  const proposedCall = activeStep?.events.find((event) => event.event_type === 'TOOL_CALL_PROPOSED');
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
  const stepFailed = Boolean(toolResult?.event_type === 'TOOL_FAILED'
    || validationRejected || finishedEvent?.payload.success === false);
  const toolFeedback = toolResult && isRecord(toolResult.payload.observation)
    ? toolResult.payload.observation : toolResult?.payload;
  const feedbackFields = isRecord(toolFeedback?.result) ? toolFeedback.result : toolFeedback;
  const feedbackDetail = isRecord(feedbackFields?.error) ? feedbackFields.error : feedbackFields;
  const toolName = String(proposedCall?.payload.name ?? '');
  const preferredFeedbackKeys = toolResult?.event_type === 'TOOL_FAILED'
    ? ['code', 'message', 'retryable']
    : toolName === 'search_documents' ? ['documents']
      : toolName === 'read_document' ? ['document']
        : toolName === 'query_records' ? ['records']
          : toolName === 'submit_answer' ? ['feedback']
            : ['accepted', 'feedback'];
  const visibleFeedback = isRecord(feedbackDetail)
    ? keyFields(feedbackDetail, preferredFeedbackKeys) : [];
  const visibleStateChanges: [string, unknown][] = keyFields(Object.fromEntries(stateChanges),
    ['acquired_evidence', 'submission', 'done', 'proposed_call']).map(([key, value]) => [key,
      key === 'submission' && isRecord(value) ? value.answer
        : key === 'proposed_call' && isRecord(value) ? value.name : value]);
  const observationFields = isRecord(initialObservation?.payload.observation)
    ? keyFields(initialObservation.payload.observation, ['description', 'question', 'target_order_id', 'document_query'])
    : keyFields(finishedEvent?.payload ?? {}, ['termination_reason', 'detail']);
  const replaySteps = Array.from(new Set(visibleEvents.map((event) => event.step_index)));
  useLayoutEffect(() => {
    if (replayView !== 'story' || !activeStep) return;
    const node = storyStageRef.current;
    if (!node || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const direction = safeReplayIndex < previousStoryIndex.current ? -1 : 1;
    previousStoryIndex.current = safeReplayIndex;
    const animation = node.animate([
      { opacity: 0.5, transform: `translateY(${direction * 8}px)` },
      { opacity: 1, transform: 'translateY(0)' },
    ], { duration: 240, easing: 'cubic-bezier(.2,.8,.2,1)' });
    return () => animation.cancel();
  }, [replayView, activeReplayEvent?.event_id, artifact?.episode.episode_id]);
  useEffect(() => {
    if (!replayPlaying || visibleEvents.length < 2) return;
    const timer = window.setInterval(
      () => setReplayIndex((index) => Math.min(index + 1, visibleEvents.length - 1)),
      replaySpeedMs,
    );
    return () => window.clearInterval(timer);
  }, [replayPlaying, replaySpeedMs, visibleEvents.length]);

  useEffect(() => {
    if (replayPlaying && safeReplayIndex >= visibleEvents.length - 1) {
      setReplayPlaying(false);
    }
  }, [replayPlaying, safeReplayIndex, visibleEvents.length]);
  const parsedExpSeeds = parseSeedList(expSeedsText);
  const activeComparisonAxis = experiment?.config.comparison_axis === 'runtime_backend'
    ? 'runtime_backend'
    : experiment?.config.comparison_axis === 'recovery_policy'
      ? 'recovery_policy'
      : experiment ? 'recovery_policy' : comparisonAxis;
  const armLeftLabel = activeComparisonAxis === 'runtime_backend' ? 'Reference Runtime' : 'Baseline Policy';
  const armRightLabel = activeComparisonAxis === 'runtime_backend' ? 'LangGraph Runtime' : 'Recovery Policy';
  const expEpisodeCount =
    expTasks.length * (parsedExpSeeds?.length ?? 0) * expRepeatCount * 2;
  const isExperimentRunReady = Boolean(meta) && Boolean(expModel) && expTasks.length > 0 &&
    parsedExpSeeds !== null && expRepeatCount >= 1 && expRepeatCount <= 10 && !isLoading;
  const isSingleRunReady = Boolean(meta) && Boolean(selectedModel) && Boolean(selectedSingleTaskMeta) && !isLoading;

  return (
    <div>
      {/* Header */}
      <header className="app-header">
        <div className="header-container">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">AL</span>
            <div>
              <div className="brand-title">AgentLabyrinth</div>
              <div className="brand-subtitle">可复现 Agent 实验平台</div>
            </div>
          </div>

          <div className="header-actions">
            <div className="nav-tabs" data-active={activeTab}>
              <button
                id="tab-experiment"
                className={`nav-tab ${activeTab === 'experiment' ? 'active' : ''}`}
                onClick={() => setActiveTab('experiment')}
              >
                对照实验 <span className="nav-english">Agent Comparison</span>
              </button>
              <button
                id="tab-single"
                className={`nav-tab ${activeTab === 'single' ? 'active' : ''}`}
                onClick={() => setActiveTab('single')}
              >
                单次运行 <span className="nav-english">Single Episode</span>
              </button>
            </div>

          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-container">
        <section className="page-intro" aria-labelledby="page-title">
          <div>
            <div className="page-eyebrow">Agent 评测工作台</div>
            <h1 id="page-title">
              {activeTab === 'experiment' ? '比较策略差异' : '审查一次完整运行'}
            </h1>
            <p>
              {activeTab === 'experiment'
                ? '固定任务、模型、种子与预算，分别比较恢复策略或 Runtime 执行框架。'
                : '运行一个任务，核查评测结论、环境状态与完整 Trace。'}
            </p>
          </div>
          <span className="workspace-status">
            {meta ? `${meta.tasks.length} 个可用任务` : '正在读取任务目录'}
          </span>
        </section>

        {/* Error Alert Box */}
        {errorMsg && (
          <div id="error-alert" className="alert-box alert-error" role="alert">
            <span className="alert-label">错误</span>
            <div>{errorMsg}</div>
          </div>
        )}
        {meta?.model_catalog_status === 'unavailable' && (
          <div className="alert-box alert-error" role="status">
            <span className="alert-label">模型目录暂不可用</span>
            <div>无法确认 AIHubMix 当前 Key 可访问的模型，已暂时隐藏真实模型；可先用 Fake 离线场景。</div>
          </div>
        )}

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
              <div className="persistence-input-row">
                <input
                  id="input-exp-id"
                  className="form-input persistence-input"
                  placeholder="输入实验 UUID 快速读取"
                  value={inputExpId}
                  onChange={(e) => setInputExpId(e.target.value)}
                />
                <button
                  id="btn-load-exp-id"
                  className="btn-secondary"
                  onClick={() => loadExperimentById(inputExpId)}
                  disabled={isLoading || !inputExpId.trim()}
                >
                  重读实验
                </button>
              </div>
            </div>
            {copyNotice && (
              <div className="copy-feedback" role="status" aria-live="polite">
                {copyNotice}
              </div>
            )}

            <ExperimentDashboard items={dashboardItems} loading={dashboardLoading} error={dashboardError}
              skipped={dashboardSkipped} activeId={experiment?.experiment_id}
              onRefresh={refreshExperimentDashboard} onOpen={loadExperimentById} />

            <div className="dashboard-grid">
              {/* Left Panel: Experiment Config */}
              <section className="card" id="exp-config-panel">
                <div className="card-title">
                  <span>下次运行配置</span>
                  <span className="badge badge-purple">受控变量对照</span>
                </div>
                <div className="card-desc">
                  严格固定模型、任务、工具集、种子与预算，每次只比较一种策略变量。
                </div>

                <div className="form-group">
                  <label htmlFor="comparison-axis" className="form-label">对照变量</label>
                  <select
                    id="comparison-axis"
                    className="form-select"
                    value={comparisonAxis}
                    onChange={(e) => setComparisonAxis(e.target.value as 'recovery_policy' | 'runtime_backend')}
                    disabled={isLoading}
                  >
                    <option value="recovery_policy">恢复策略：关闭 vs 一次参数纠错</option>
                    <option value="runtime_backend">执行框架：手写循环 vs LangGraph</option>
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
                    <div className="strategy-summary" aria-label="Runtime 对照">
                      <div><strong>Reference</strong><span>Python 手写调度循环</span></div>
                      <div><strong>LangGraph</strong><span>StateGraph 独立节点调度</span></div>
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
                    <div className="strategy-summary" aria-label="恢复策略对照">
                      <div><strong>Baseline</strong><span>参数错误后终止</span></div>
                      <div><strong>Recovery</strong><span>INVALID_ARGUMENTS 最多纠错一次</span></div>
                    </div>
                  </>
                )}

                {/* Model Selector */}
                <div className="form-group">
                  <div className="inline-header">
                  <label htmlFor="exp-model-select" className="form-label">评测模型</label>
                  <button
                    type="button"
                    className="btn-secondary btn-xs"
                    onClick={() => setShowCustomModelInputExp(!showCustomModelInputExp)}
                  >
                    {showCustomModelInputExp ? '取消' : '+ 自定义模型'}
                  </button>
                  </div>

                  {showCustomModelInputExp && (
                  <div className="compact-inline">
                    <input
                      className="form-input compact-input"
                      placeholder="输入新免费模型 ID (例如: coding-glm-5.2-free)"
                      value={customModelTextExp}
                      onChange={(e) => setCustomModelTextExp(e.target.value)}
                    />
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => addCustomModel(customModelTextExp, 'exp')}
                        disabled={!customModelTextExp.trim()}
                      >
                        确定
                      </button>
                    </div>
                  )}

                  <select
                    id="exp-model-select"
                    className="form-select"
                    value={expModel}
                    onChange={(e) => setExpModel(e.target.value)}
                    disabled={isLoading}
                  >
                    {meta?.models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} {m.is_default ? '· 默认推荐' : ''} {m.is_experimental ? '· 实验性' : ''}
                      </option>
                    ))}
                    {customModels
                      .filter((cid) => !meta?.models.some((m) => m.id === cid))
                      .map((cid) => (
                        <option key={cid} value={cid}>
                          {cid} (自定义免费模型)
                        </option>
                      ))}
                  </select>
                </div>

                {/* Model Notes Box */}
                <div className="form-group">
                  <div className="model-note-box">
                    <strong>说明：</strong>{' '}
                    {currentExpModelMeta
                      ? currentExpModelMeta.notes
                      : `自定义免费模型 (${expModel})，将使用 AIHubMix 接口发起真实测试。`}
                  </div>
                </div>

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

                {/* Task Checkbox List */}
                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <label className="form-label">评测任务 (多选)</label>
                    <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.75rem' }}>
                      <button
                        type="button"
                        className="btn-secondary"
                        style={{ padding: '0.15rem 0.4rem', fontSize: '0.7rem' }}
                        onClick={() => setExpTasks(experimentTasks.map((t) => t.id))}
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
                            {task.description.slice(0, 32)}...
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

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
                    <label htmlFor="exp-token-budget">总 Token 预算（输入 + 输出）</label>
                    <input id="exp-token-budget" type="number" min={100} max={20000}
                      value={expTokenBudget ?? ''} placeholder="留空使用任务原预算"
                      onChange={(e) => setExpTokenBudget(e.target.value === '' ? null : Number(e.target.value))}
                      disabled={isLoading} />
                    <p className="metric-sub">真实多轮建议 8000；两种策略使用相同预算。免费通道按约 13 秒间隔发起请求，仍可能遇到账户限额。</p>
                  </div>
                )}

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

                <button
                  id="run-exp-button"
                  className="btn-primary"
                  onClick={handleRunExperiment}
                  disabled={!isExperimentRunReady}
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
                      <span>正在串行执行成对评测...</span>
                    </>
                  ) : (
                    <>
                      <span>开始运行对照实验 ({expEpisodeCount} 次执行)</span>
                    </>
                  )}
                </button>
                {isLoading && (
                  <p className="loading-note" role="status" aria-live="polite">
                    {loadingMessage} <span aria-hidden="true">已等待 {elapsedSeconds} 秒。</span>
                  </p>
                )}

                {activeJobId && experimentJob && (
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
                    {activeComparisonAxis === 'runtime_backend'
                      ? '比较两个 Runtime 在相同模型、任务、预算和恢复策略下的成功率、用量与耗时。'
                      : '比较恢复策略的成功率、参数错误挽救转化率与额外用量。'}
                  </div>

                  {experiment ? (
                    <div>
                      {/* Preserved Experiment Configuration Panel */}
                      <div className="record-summary">
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
                              : (experiment.config.model as Record<string, unknown>)?.model as string || 'N/A'}
                          </div>
                          <div>
                            <strong>场景：</strong>{' '}
                            {(experiment.config.scenario as string) || 'N/A (真实模型)'}
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
                            {(experiment.config.evaluator as string) || 'order_status_v1'}
                          </div>
                          <div>
                            <strong>{armLeftLabel}：</strong>{' '}
                            {((experiment.config.baseline_agent as Record<string, unknown>)?.runtime_backend as string) || 'handwritten'}
                            {' / '}
                            {((experiment.config.baseline_agent as Record<string, unknown>)?.runtime_strategy as string) || 'handwritten'}
                          </div>
                          <div>
                            <strong>{armRightLabel}：</strong>{' '}
                            {((experiment.config.recovery_agent as Record<string, unknown>)?.runtime_backend as string) || 'handwritten'}
                            {' / '}
                            {((experiment.config.recovery_agent as Record<string, unknown>)?.runtime_strategy as string) || 'handwritten_recovery'}
                          </div>
                        </div>
                      </div>

                      <div className="metrics-grid">
                        {/* Baseline Success */}
                        <div className="metric-box">
                          <div className="metric-label">{armLeftLabel} 成功率</div>
                          <div
                            className="metric-value"
                            style={{
                              color:
                                experiment.metrics.baseline_success_rate > 0
                                  ? 'var(--success-text)'
                                  : 'var(--fail-text)',
                            }}
                          >
                            {(experiment.metrics.baseline_success_rate * 100).toFixed(1)}%
                          </div>
                          <div className="metric-sub">
                            {experiment.metrics.baseline_success_count} / {experiment.metrics.total_pairs} 通过
                          </div>
                        </div>

                        {/* Recovery Success */}
                        <div className="metric-box">
                          <div className="metric-label">{armRightLabel} 成功率</div>
                          <div
                            className="metric-value"
                            style={{
                              color:
                                experiment.metrics.recovery_success_rate > 0
                                  ? 'var(--success-text)'
                                  : 'var(--fail-text)',
                            }}
                          >
                            {(experiment.metrics.recovery_success_rate * 100).toFixed(1)}%
                          </div>
                          <div className="metric-sub">
                            {experiment.metrics.recovery_success_count} / {experiment.metrics.total_pairs} 通过
                          </div>
                        </div>

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

                        {/* Total Tokens & Delta */}
                        <div className="metric-box">
                          <div className="metric-label">Token 总消耗 ({armLeftLabel} / {armRightLabel})</div>
                          <div className="metric-value" style={{ fontSize: '1.05rem' }}>
                            {experiment.metrics.baseline_total_tokens} / {experiment.metrics.recovery_total_tokens}
                          </div>
                          <div className="metric-sub">
                            增量 Delta: {formatSigned(experiment.metrics.recovery_total_tokens - experiment.metrics.baseline_total_tokens)} tokens
                          </div>
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
                          <div className="metric-label">工具选择 / 参数合法率 ({armLeftLabel} / {armRightLabel})</div>
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
                    <div className="empty-state">
                      <div className="empty-icon">尚无实验结果</div>
                      <div>请在左侧选择模型与任务，点击“开始运行对照实验”，或输入历史实验 UUID 进行复核。</div>
                    </div>
                  )}
                </section>
              </div>
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
                  {artifact ? artifact.episode.episode_id : '尚未运行'}
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
              <div className="persistence-input-row">
                <input
                  id="input-episode-id"
                  className="form-input persistence-input"
                  placeholder="输入 UUID 快速读取"
                  value={inputEpisodeId}
                  onChange={(e) => setInputEpisodeId(e.target.value)}
                />
                <button
                  id="btn-load-id"
                  className="btn-secondary"
                  onClick={() => loadEpisodeById(inputEpisodeId)}
                  disabled={isLoading || !inputEpisodeId.trim()}
                >
                  重读
                </button>
              </div>
            </div>
            {copyNotice && (
              <div className="copy-feedback" role="status" aria-live="polite">
                {copyNotice}
              </div>
            )}

            <div className={`dashboard-grid single-dashboard ${artifact ? 'has-artifact' : 'configuring'}`}>
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
                  <div className="single-launch-bar">
                    <div className="single-launch-summary" aria-live="polite">
                      <strong>{selectedSingleTaskMeta?.name ?? '请选择任务'}</strong>
                      <span>
                        {currentSingleModelMeta?.name || selectedModel || '请选择模型'}
                        {' · '}{singleRuntimeBackend === 'langgraph' ? 'LangGraph' : 'Reference'}
                        {' · '}
                        {singleToolTransport === 'mcp' && selectedSingleTaskMeta?.supports_mcp
                          ? 'MCP HTTP'
                          : selectedSuite === 'tool_lab_core' ? '本地工具' : '本地函数调用提议评测'}
                      </span>
                      <small>{selectedModel === 'fake' ? 'Fake 离线模拟' : '将发起真实模型请求'}</small>
                    </div>
                    <div className="single-launch-action">
                      <button id="run-button" className="btn-primary"
                        onClick={handleRunEpisode} disabled={!isSingleRunReady}
                        title={!meta ? '元数据尚未就绪' : !selectedSingleTaskMeta ? '请选择一个可见任务后再运行' : undefined}>
                        {isLoading ? <><div className="spinner" /><span>正在运行 Episode...</span></>
                          : <span>开始运行 Episode</span>}
                      </button>
                      {isLoading && (
                        <p className="loading-note" role="status" aria-live="polite">
                          {loadingMessage} <span aria-hidden="true">已等待 {elapsedSeconds} 秒。</span>
                        </p>
                      )}
                    </div>
                  </div>
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
                                const first = meta?.tasks.find((task) => task.suite === 'tool_lab_core');
                                if (first) setSelectedSingleTask(first.id);
                                setMaxSteps(6);
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
                  <div className="model-select-heading">
                    <label htmlFor="model-select" className="form-label">评测模型</label>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => setShowCustomModelInputSingle(!showCustomModelInputSingle)}
                    >
                      {showCustomModelInputSingle ? '取消' : '+ 自定义模型'}
                    </button>
                  </div>

                  {showCustomModelInputSingle && (
                    <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                      <input
                        className="form-input"
                        style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}
                        placeholder="输入新免费模型 ID (例如: coding-glm-5.2-free)"
                        value={customModelTextSingle}
                        onChange={(e) => setCustomModelTextSingle(e.target.value)}
                      />
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => addCustomModel(customModelTextSingle, 'single')}
                        disabled={!customModelTextSingle.trim()}
                      >
                        确定
                      </button>
                    </div>
                  )}

                  <select
                    id="model-select"
                    className="form-select"
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    disabled={isLoading}
                  >
                    {meta?.models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} {m.is_default ? '· 默认推荐' : ''} {m.is_experimental ? '· 实验性' : ''}
                      </option>
                    ))}
                    {customModels
                      .filter((cid) => !meta?.models.some((m) => m.id === cid))
                      .map((cid) => (
                        <option key={cid} value={cid}>
                          {cid} (自定义免费模型)
                        </option>
                      ))}
                  </select>
                </div>

                {/* Model Notes Box */}
                <div className="form-group">
                  <details className="model-note-disclosure">
                    <summary>模型目录说明</summary>
                    <div className="model-note-box">
                      <strong>说明：</strong>{' '}
                      {currentSingleModelMeta
                        ? currentSingleModelMeta.notes
                        : `自定义免费模型 (${selectedModel})，将使用 AIHubMix 接口发起真实测试。`}
                    </div>
                  </details>
                </div>

                <fieldset className="execution-choice" disabled={isLoading}>
                  <legend className="form-label">执行 Runtime</legend>
                  <div className="execution-choice-grid">
                    {([
                      ['handwritten', 'Reference', 'Python 手写控制循环'],
                      ['langgraph', 'LangGraph', '独立图节点调度'],
                    ] as const).map(([backend, name, description]) => (
                      <label className="execution-option" key={backend}>
                        <input type="radio" name="single-runtime-backend" value={backend}
                          checked={singleRuntimeBackend === backend}
                          onChange={() => setSingleRuntimeBackend(backend)} />
                        <span><strong>{name}</strong><small>{description}</small></span>
                      </label>
                    ))}
                  </div>
                  <p className="metric-sub">两种调度方式使用相同工具与评测规则。</p>
                </fieldset>
                <details className="advanced-settings">
                  <summary>
                    <span>更多设置</span>
                    <span>
                      {singleAdvancedChangeCount > 0
                        ? `${singleAdvancedChangeCount} 项非默认 · 最多 ${maxSteps} 步`
                        : '保持默认值'}
                    </span>
                  </summary>
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
                  <div className="form-group">
                    <label htmlFor="steps-input" className="form-label">步数上限 (Max Steps)</label>
                    <input id="steps-input" type="number" className="form-input" min={1} max={20}
                      value={maxSteps}
                      onChange={(e) => setMaxSteps(parseInt(e.target.value, 10) || 6)}
                      disabled={isLoading} />
                  </div>
                  {selectedModel !== 'fake' && (
                    <div className="form-group">
                      <label htmlFor="single-token-budget" className="form-label">总 Token 预算（输入 + 输出）</label>
                      <input id="single-token-budget" className="form-input" type="number" min={100} max={20000}
                        value={singleTokenBudget ?? ''} placeholder="留空使用任务原预算"
                        onChange={(e) => setSingleTokenBudget(e.target.value === '' ? null : Number(e.target.value))}
                        disabled={isLoading} />
                      <p className="metric-sub">真实多轮建议 8000；两种策略使用相同预算。免费通道仍可能遇到账户限额。</p>
                    </div>
                  )}
                </details>

                    </section>
                  </div>
                </div>
              </details>

              {/* Right Column: Single Episode Result + Trace View */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {/* Result Summary */}
                <section className="card" id="results-panel">
                  <div className="card-title">
                    <span>运行结果指标</span>
                    {artifact && (
                      <span
                        id="eval-badge"
                        className={`badge ${artifact.evaluation.success ? 'badge-green' : 'badge-red'}`}
                      >
                        {artifact.evaluation.success ? '评测通过 (SUCCESS)' : '评测未通过 (FAILED)'}
                      </span>
                    )}
                  </div>
                  <div className="card-desc">展示当前 Episode 的终态判定、用量与真实性审计指标。</div>

                  {artifact ? (
                    <div>
                      <div className="metrics-grid">
                        <div className="metric-box">
                          <div className="metric-label">数据集 / 评分协议</div>
                          <div className="metric-value" style={{ fontSize: '0.95rem' }}>
                            {String(artifact.task.evaluator_config.suite ?? '').startsWith('bfcl_')
                              ? `BFCL ${artifact.task.evaluator_config.suite === 'bfcl_java_adapted' ? 'Java ' : ''}改编子集`
                              : '原生 ToolLab'}
                          </div>
                          <div className="metric-sub">
                            {String(artifact.task.evaluator_config.suite ?? '').startsWith('bfcl_')
                              ? `AgentLabyrinth-adapted subset · ${String(artifact.task.evaluator_config.source_case_id ?? artifact.task.name)}`
                              : artifact.task.name}
                          </div>
                        </div>
                        {/* Model Info */}
                        <div className="metric-box">
                          <div className="metric-label">执行模型 / 策略</div>
                          <div className="metric-value" style={{ fontSize: '0.95rem' }} id="metric-model">
                            {artifact.agent.model.model}
                          </div>
                          <div className="metric-sub">
                            <span className="badge badge-blue">{artifact.agent.runtime_backend ?? 'handwritten'} Runtime</span>{' '}
                            <span className={`badge ${artifact.agent.runtime_strategy === 'handwritten_recovery' ? 'badge-purple' : 'badge-blue'}`}>
                              {artifact.agent.runtime_strategy === 'handwritten_recovery' ? '一次参数纠错' : '无参数纠错'}
                            </span>
                            <div>Runtime 版本：{artifact.run_config.runtime_version ?? '历史产物未记录'}</div>
                            <div>工具传输：{artifact.run_config.environment_version === 'tool-lab-mcp-v1' ? 'MCP HTTP' : '本地'}</div>
                          </div>
                        </div>

                        {/* Termination */}
                        <div className="metric-box">
                          <div className="metric-label">终止状态</div>
                          <div className="metric-value" id="metric-status" style={{ fontSize: '1.1rem' }}>
                            {artifact.episode.termination_reason}
                          </div>
                          <div className="metric-sub" style={{ color: 'var(--text-muted)' }}>
                            {explainFailure(artifact.episode.detail || artifact.evaluation.reason)}
                          </div>
                        </div>

                        {/* Steps & Tool Calls */}
                        <div className="metric-box">
                          <div className="metric-label">步数 / 工具调用</div>
                          <div className="metric-value" id="metric-steps">
                            {artifact.episode.step_count} 步 / {artifact.episode.tool_call_count} 次工具
                          </div>
                          <div className="metric-sub">模型调用: {artifact.episode.model_call_count} 次</div>
                        </div>

                        {/* Token Usage */}
                        <div className="metric-box">
                          <div className="metric-label">Token 消耗</div>
                          <div className="metric-value" id="metric-tokens">
                            {artifact.episode.token_usage.prompt_tokens + artifact.episode.token_usage.completion_tokens}
                          </div>
                          <div className="metric-sub">
                            P: {artifact.episode.token_usage.prompt_tokens} / C: {artifact.episode.token_usage.completion_tokens}
                          </div>
                        </div>

                        {/* Latency */}
                        <div className="metric-box">
                          <div className="metric-label">耗时</div>
                          <div className="metric-value" id="metric-duration">
                            {artifact.episode.duration_ms} ms
                          </div>
                          <div className="metric-sub">运行耗时</div>
                        </div>

                        {/* Cost: Strictly "未知" when is_known is False */}
                        <div className="metric-box">
                          <div className="metric-label">{artifact.agent.model.provider === 'fake' ? '模拟费用' : '网关估算费用'}</div>
                          <div className="metric-value" id="metric-cost" style={{ color: artifact.episode.estimated_cost.is_known ? 'var(--text-primary)' : 'var(--warn-text)' }}>
                            {artifact.episode.estimated_cost.is_known
                              ? `$${artifact.episode.estimated_cost.amount} USD`
                              : '未知 (未验证)'}
                          </div>
                          <div className="metric-sub">
                            版本: {artifact.episode.estimated_cost.price_table_version}
                          </div>
                        </div>
                        <div className="metric-box">
                          <div className="metric-label">原厂标价参考成本</div>
                          <div className="metric-value">{artifact.reference_cost ? `$${artifact.reference_cost.amount} USD` : '未知'}</div>
                          <div className="metric-sub">未命中缓存价 · 非实付费用{artifact.reference_cost ? ` · ${artifact.reference_cost.price_table_version}` : ''}</div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="empty-state compact-empty">
                      <div>运行完成后，评测指标与只读 Trace 会显示在这里。</div>
                    </div>
                  )}
                </section>

                {/* Trace Timeline */}
                <section className="card" id="trace-panel">
                  <div className="card-title">
                    <span>{liveRun ? '实时 Trace' : 'Trace Replay'}</span>
                    {artifact && (
                      <span className="badge" style={{ fontFamily: 'var(--font-mono)' }}>
                        {artifact.events.length} 个事件
                      </span>
                    )}
                  </div>
                  <div className="card-desc">
                    {liveRun ? '节点只随已记录的事件出现；结束后保存完整产物供只读回放。'
                      : '仅回放已保存的事件和环境快照，不重新请求模型或执行工具。'}
                  </div>

                  {liveRun ? (
                    <>
                      <p className="loading-note" role="status">
                        {liveRun.status === 'running' ? '正在接收真实 Trace 事件。' : '实时连接已中断，后端运行状态未知。'}
                        {liveRun.episodeId && ` Episode ID：${liveRun.episodeId}`}
                      </p>
                      {liveRun.events.length > 0 && <McpFlowReplay live events={liveRun.events}
                        environmentVersion={liveRun.environmentVersion} model={liveRun.model}
                        finalState={{}} termination={liveRun.status === 'running' ? '运行中' : '连接中断'} detail="" />}
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
                          onClick={() => { setReplayPlaying(false); setReplayIndex(0); setReplayView('story'); }}>
                          过程概览
                        </button>
                        <button type="button" className={replayView === 'events' ? 'active' : ''}
                          aria-pressed={replayView === 'events'}
                          onClick={() => { setReplayPlaying(false); setReplayIndex(0); setReplayView('events'); }}>
                          技术 Trace
                        </button>
                      </div>
                      {replayView === 'flow' && <McpFlowReplay key={artifact.episode.episode_id}
                        events={artifact.events} environmentVersion={artifact.run_config.environment_version ?? ''}
                        model={artifact.agent.model.model} finalState={artifact.episode.final_state}
                        termination={artifact.episode.termination_reason} detail={artifact.episode.detail} />}
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
                          setReplayIndex(next);
                          buttons[next]?.focus();
                        }}>
                        {traceSteps.map((group, index) => <button key={`${group.step}-${index}`} type="button"
                          className={`step-card ${safeReplayIndex === index ? 'active' : ''}`}
                          aria-current={safeReplayIndex === index ? 'step' : undefined}
                          onClick={() => { setReplayPlaying(false); setReplayIndex(index); }}>
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
                              setReplayIndex(0);
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
                              setReplayIndex(Math.max(index, 0));
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
                              setReplayIndex((index) => Math.max(index - 1, 0));
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
                              setReplayIndex((index) =>
                                Math.min(index + 1, visibleEvents.length - 1),
                              );
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
                                setReplayIndex(0);
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
                              {proposedCall ? <>
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
                              {validation && <p className={`story-validation ${validationRejected ? 'failed' : ''}`}>
                                工具校验：{validationRejected ? validationError ?? '未通过'
                                  : validation.payload.arguments_valid === true ? '通过' : '未记录结果'}
                              </p>}
                              {visibleFeedback.length > 0
                                ? <ReadableFields entries={visibleFeedback} />
                                : <p className="story-muted">{validationRejected
                                  ? '工具没有执行。' : initialObservation ? '等待模型选择行动。' : '本步没有工具返回。'}</p>}
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
                                    setReplayIndex(index);
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
