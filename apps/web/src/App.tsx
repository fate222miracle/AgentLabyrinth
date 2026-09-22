import { useState, useEffect } from 'react';

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
  suite: 'tool_lab_core' | 'bfcl_adapted';
  split: string;
}

interface MetaResponse {
  schema_version: string;
  request_id: string;
  models: ModelOption[];
  tasks: TaskOption[];
  default_model: string;
  default_task: string;
}

interface TraceEvent {
  event_id: string;
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
  agent: {
    name?: string;
    runtime_strategy?: string;
    model: {
      provider: string;
      model: string;
    };
  };
  events: TraceEvent[];
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
  retry_recovery_count: number;
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

function downloadJson(filename: string, value: unknown): void {
  const blob = new Blob([`${JSON.stringify(value, null, 2)}\n`], {
    type: 'application/json;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
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

function comparisonLabel(pair: PairComparison): string {
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
  const [selectedSingleTask, setSelectedSingleTask] = useState<string>('');
  const [selectedSuite, setSelectedSuite] = useState<'tool_lab_core' | 'bfcl_adapted'>('tool_lab_core');
  const [maxSteps, setMaxSteps] = useState<number>(6);
  const [artifact, setArtifact] = useState<EpisodeArtifact | null>(null);
  const [recentEpisodeIds, setRecentEpisodeIds] = useState<string[]>([]);
  const [inputEpisodeId, setInputEpisodeId] = useState<string>('');
  const [expandedEvents, setExpandedEvents] = useState<Record<string, boolean>>({});
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('ALL');
  const [replayIndex, setReplayIndex] = useState<number>(0);

  // Experiment states
  const [expModel, setExpModel] = useState<string>('');
  const [expScenario, setExpScenario] = useState<string>('invalid-then-success');
  const [expTasks, setExpTasks] = useState<string[]>([]);
  const [expSeedsText, setExpSeedsText] = useState<string>('1');
  const [expRepeatCount, setExpRepeatCount] = useState<number>(1);
  const [expTokenBudget, setExpTokenBudget] = useState<number | null>(8000);
  const [singleTokenBudget, setSingleTokenBudget] = useState<number | null>(8000);
  const [experiment, setExperiment] = useState<ExperimentArtifact | null>(null);
  const [recentExpIds, setRecentExpIds] = useState<string[]>([]);
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
          setSelectedSingleTask(data.tasks[0].id);
          setExpTasks(data.tasks.filter((t) => t.suite === 'tool_lab_core').map((t) => t.id));
        }
      })
      .catch((err) => {
        setErrorMsg(`API 连通性错误: ${err.message}`);
      });

    // Load recent history from localStorage
    try {
      const savedEpisodes = localStorage.getItem('al_recent_episodes');
      if (savedEpisodes) setRecentEpisodeIds(JSON.parse(savedEpisodes));
      const savedExps = localStorage.getItem('al_recent_experiments');
      if (savedExps) setRecentExpIds(JSON.parse(savedExps));
      const savedCustom = localStorage.getItem('al_custom_models');
      if (savedCustom) setCustomModels(JSON.parse(savedCustom));
    } catch {
      // ignore storage error
    }

    if (expId) {
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
      if (nextExpId) {
        setActiveTab('experiment');
        loadExperimentById(nextExpId, false);
      } else if (nextEpId) {
        setActiveTab('single');
        loadEpisodeById(nextEpId, false);
      } else {
        setExperiment(null);
        setArtifact(null);
        setErrorMsg(null);
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    setEventTypeFilter('ALL');
    setReplayIndex(Math.max((artifact?.events.length ?? 1) - 1, 0));
    setExpandedEvents({});
  }, [artifact?.episode.episode_id]);

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
    beginLoading('正在读取历史 Episode。');
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/v1/episodes/${encodeURIComponent(id.trim())}`);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.message || `未能找到 Episode (${res.status})`);
      }
      const data = await res.json();
      setArtifact(data.artifact);
      addRecentEpisodeId(id.trim());

      if (updateUrl) {
        const url = new URL(window.location.href);
        url.searchParams.set('episode_id', id.trim());
        url.searchParams.delete('experiment_id');
        window.history.pushState({}, '', url.toString());
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '加载失败';
      setErrorMsg(message);
    } finally {
      finishLoading();
    }
  };

  // Load an existing experiment by ID
  const loadExperimentById = async (id: string, updateUrl = true) => {
    if (!id || id.trim().length === 0) return;
    beginLoading('正在读取历史对照实验。');
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/v1/experiments/${encodeURIComponent(id.trim())}`);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.message || `未能找到 Experiment (${res.status})`);
      }
      const data = await res.json();
      setExperiment(data.experiment);
      addRecentExpId(id.trim());

      if (updateUrl) {
        const url = new URL(window.location.href);
        url.searchParams.set('experiment_id', id.trim());
        url.searchParams.delete('episode_id');
        window.history.pushState({}, '', url.toString());
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '加载实验失败';
      setErrorMsg(message);
    } finally {
      finishLoading();
    }
  };

  // Execute single episode
  const handleRunEpisode = async () => {
    beginLoading('正在执行单次运行，完成后展示详细轨迹。');
    setErrorMsg(null);
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
      };

      const res = await fetch('/api/v1/episodes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.message || `执行失败 (${res.status})`);
      }

      const data = await res.json();
      const newArtifact = data.artifact as EpisodeArtifact;
      setArtifact(newArtifact);
      addRecentEpisodeId(newArtifact.episode.episode_id);

      const url = new URL(window.location.href);
      url.searchParams.set('episode_id', newArtifact.episode.episode_id);
      url.searchParams.delete('experiment_id');
      window.history.pushState({}, '', url.toString());
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '运行失败';
      setErrorMsg(message);
    } finally {
      finishLoading();
    }
  };

  // Execute paired experiment
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
    const episodeCount = expTasks.length * seeds.length * expRepeatCount * 2;
    beginLoading(`正在串行执行对照实验，完成后展示详细轨迹。预计 ${episodeCount} 个 Episode。`);
    setErrorMsg(null);
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
      };

      const res = await fetch('/api/v1/experiments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.message || `对照实验执行失败 (${res.status})`);
      }

      const data = await res.json();
      const expArt = data.experiment as ExperimentArtifact;
      setExperiment(expArt);
      addRecentExpId(expArt.experiment_id);

      const url = new URL(window.location.href);
      url.searchParams.set('experiment_id', expArt.experiment_id);
      url.searchParams.delete('episode_id');
      window.history.pushState({}, '', url.toString());
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '对照实验运行失败';
      setErrorMsg(message);
    } finally {
      finishLoading();
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
  const bfclTaskCount = meta?.tasks.filter((task) => task.suite === 'bfcl_adapted').length ?? 0;
  const eventTypes = Array.from(new Set(artifact?.events.map((event) => event.event_type) ?? []));
  const visibleEvents =
    artifact?.events.filter(
      (event) => eventTypeFilter === 'ALL' || event.event_type === eventTypeFilter,
    ) ?? [];
  const safeReplayIndex = Math.min(replayIndex, Math.max(visibleEvents.length - 1, 0));
  const activeReplayEvent = visibleEvents[safeReplayIndex];
  const replaySnapshot = artifact
    ? snapshotAt(artifact, activeReplayEvent?.event_id)
    : { state: null, source: '尚无环境快照' };
  const replaySteps = Array.from(new Set(visibleEvents.map((event) => event.step_index)));
  const parsedExpSeeds = parseSeedList(expSeedsText);
  const expEpisodeCount =
    expTasks.length * (parsedExpSeeds?.length ?? 0) * expRepeatCount * 2;
  const isExperimentRunReady = Boolean(meta) && Boolean(expModel) && expTasks.length > 0 &&
    parsedExpSeeds !== null && expRepeatCount >= 1 && expRepeatCount <= 10 && !isLoading;
  const isSingleRunReady = Boolean(meta) && Boolean(selectedModel) && Boolean(selectedSingleTask) && !isLoading;

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
            <div className="nav-tabs">
              <button
                id="tab-experiment"
                className={`nav-tab ${activeTab === 'experiment' ? 'active' : ''}`}
                onClick={() => setActiveTab('experiment')}
              >
                对照实验 <span className="nav-english">Baseline vs Recovery</span>
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
                ? '在相同模型、任务、种子与预算下，对照 Baseline 与 Recovery。'
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

            <div className="dashboard-grid">
              {/* Left Panel: Experiment Config */}
              <section className="card" id="exp-config-panel">
                <div className="card-title">
                  <span>下次运行配置</span>
                  <span className="badge badge-purple">Baseline vs Recovery</span>
                </div>
                <div className="card-desc">
                  严格在相同模型、任务、工具集、种子与预算下，对比单次容错恢复机制的有效性与开销。
                </div>

                <div className="strategy-summary" aria-label="Agent 策略">
                  <div><strong>Baseline</strong><span>基础 Tool Calling 循环</span></div>
                  <div><strong>Recovery</strong><span>仅对 INVALID_ARGUMENTS 增加一次受控纠错</span></div>
                </div>

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
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
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
                    衡量容错恢复策略相较基线的成功率提升、挽救转化率与代价比（Tokens / 耗时）。
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
                            <strong>基准策略：</strong>{' '}
                            {(experiment.config.baseline_strategy as string) ||
                              ((experiment.config.baseline_agent as Record<string, unknown>)?.runtime_strategy as string) ||
                              'handwritten'}
                          </div>
                          <div>
                            <strong>容错策略：</strong>{' '}
                            {(experiment.config.recovery_strategy as string) ||
                              ((experiment.config.recovery_agent as Record<string, unknown>)?.runtime_strategy as string) ||
                              'handwritten_recovery'}
                          </div>
                        </div>
                      </div>

                      <div className="metrics-grid">
                        {/* Baseline Success */}
                        <div className="metric-box">
                          <div className="metric-label">Baseline 成功率</div>
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
                          <div className="metric-label">Recovery 成功率</div>
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
                        <div
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
                            {experiment.metrics.retry_eligible_count !== null && experiment.metrics.retry_eligible_count !== undefined
                              ? `转化率: ${((experiment.metrics.retry_recovery_rate ?? 0) * 100).toFixed(1)}% (${experiment.metrics.retry_recovery_count} / ${experiment.metrics.retry_eligible_count} 可恢复样本)`
                              : `转化率: ${((experiment.metrics.retry_recovery_rate ?? 0) * 100).toFixed(1)}% (${experiment.metrics.retry_recovery_count} 例，历史版本未统计可恢复基数)`}
                          </div>
                        </div>

                        {/* Total Tokens & Delta */}
                        <div className="metric-box">
                          <div className="metric-label">Token 总消耗 (Base / Rec)</div>
                          <div className="metric-value" style={{ fontSize: '1.05rem' }}>
                            {experiment.metrics.baseline_total_tokens} / {experiment.metrics.recovery_total_tokens}
                          </div>
                          <div className="metric-sub">
                            增量 Delta: {formatSigned(experiment.metrics.recovery_total_tokens - experiment.metrics.baseline_total_tokens)} tokens
                          </div>
                        </div>

                        {/* Average Steps */}
                        <div className="metric-box">
                          <div className="metric-label">平均步数 (Base / Rec)</div>
                          <div className="metric-value" style={{ fontSize: '1.1rem' }}>
                            {experiment.metrics.baseline_avg_steps} / {experiment.metrics.recovery_avg_steps}
                          </div>
                          <div className="metric-sub">单任务平均步数</div>
                        </div>

                        {/* Average Duration */}
                        <div className="metric-box">
                          <div className="metric-label">平均耗时 (Base / Rec)</div>
                          <div className="metric-value" style={{ fontSize: '1.05rem' }}>
                            {experiment.metrics.baseline_avg_duration_ms} / {experiment.metrics.recovery_avg_duration_ms} ms
                          </div>
                          <div className="metric-sub">
                            费用: {experiment.metrics.baseline_total_cost != null &&
                              experiment.metrics.recovery_total_cost != null
                              ? `$${experiment.metrics.baseline_total_cost} / $${experiment.metrics.recovery_total_cost}`
                              : experiment.metrics.is_cost_known
                                ? '历史产物未统计'
                                : '未知 (未验证)'}
                          </div>
                        </div>

                        {/* Tool Selection & Argument Validity Rates */}
                        <div className="metric-box">
                          <div className="metric-label">工具选择 / 参数合法率 (Base / Rec)</div>
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
                          <div className="metric-label">平均模型 / 工具调用 (Base / Rec)</div>
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
                              <th>Baseline (基准)</th>
                              <th>Recovery (容错)</th>
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
                                            {comparisonLabel(pair)}
                                          </span>
                                          {pair.retry_eligible === true && (
                                            <div className="inline-note">
                                              <span className="badge badge-purple pill-small">
                                                可恢复样本
                                              </span>
                                            </div>
                                          )}
                                          {pair.retry_eligible === null && (
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
                                              aria-label={`查看 ${pair.task_name} 的基线 Trace`}
                                              onClick={() => {
                                                setActiveTab('single');
                                                loadEpisodeById(pair.baseline_episode_id);
                                              }}
                                            >
                                              基线 Trace
                                            </button>
                                            <button
                                              className="btn-secondary trace-button"
                                              aria-label={`查看 ${pair.task_name} 的恢复 Trace`}
                                              onClick={() => {
                                                setActiveTab('single');
                                                loadEpisodeById(pair.recovery_episode_id);
                                              }}
                                            >
                                              恢复 Trace
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

            <div className="dashboard-grid">
              {/* Left Panel: Single Episode Config */}
              <section className="card" id="config-panel">
                <div className="card-title">
                  <span>单次运行配置</span>
                  <span className="badge badge-blue">ToolLab</span>
                </div>
                <div className="card-desc">选择模型模式与限制，发起单次受控评测。</div>

                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <label htmlFor="model-select" className="form-label">评测模型</label>
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ padding: '0.15rem 0.4rem', fontSize: '0.7rem' }}
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
                  <div className="model-note-box">
                    <strong>说明：</strong>{' '}
                    {currentSingleModelMeta
                      ? currentSingleModelMeta.notes
                      : `自定义免费模型 (${selectedModel})，将使用 AIHubMix 接口发起真实测试。`}
                  </div>
                </div>

                {/* Scenario selector if Fake model */}
                {selectedModel === 'fake' && (
                  <div className="form-group">
                    <label htmlFor="scenario-select" className="form-label">Fake 模拟场景</label>
                    <select
                      id="scenario-select"
                      className="form-select"
                      value={selectedScenario}
                      onChange={(e) => setSelectedScenario(e.target.value)}
                      disabled={isLoading}
                    >
                      <option value="success">success (完整通过，答案匹配)</option>
                      <option value="invalid-then-success">invalid-then-success (一次重试后通过)</option>
                      <option value="wrong-answer">wrong-answer (提交错误答案)</option>
                      <option value="invalid-arguments">invalid-arguments (工具参数校验失败)</option>
                      <option value="max-steps">max-steps (步数超限终止)</option>
                    </select>
                  </div>
                )}

                {/* Task Selection */}
                <div className="form-group">
                  <label htmlFor="suite-select" className="form-label">数据集</label>
                  <select
                    id="suite-select"
                    className="form-select"
                    value={selectedSuite}
                    onChange={(e) => {
                      const suite = e.target.value as 'tool_lab_core' | 'bfcl_adapted';
                      setSelectedSuite(suite);
                      const first = meta?.tasks.find((task) => task.suite === suite);
                      if (first) setSelectedSingleTask(first.id);
                      setMaxSteps(suite === 'bfcl_adapted' ? 1 : 6);
                    }}
                    disabled={isLoading}
                  >
                    <option value="tool_lab_core">原生 ToolLab</option>
                    <option value="bfcl_adapted" disabled={bfclTaskCount === 0}>
                      BFCL 改编子集（{bfclTaskCount === 0 ? '请先运行导入脚本' : `${bfclTaskCount} 道真实固定题`}）
                    </option>
                  </select>
                  {selectedSuite === 'bfcl_adapted' && (
                    <p className="metric-sub">
                      来源：BFCL V4 固定上游提交；AgentLabyrinth-adapted subset；本地精确匹配，不是官方 BFCL 分数。
                    </p>
                  )}
                </div>
                <div className="form-group">
                  <label htmlFor="task-select" className="form-label">评测任务</label>
                  <select
                    id="task-select"
                    className="form-select"
                    value={selectedSingleTask}
                    onChange={(e) => setSelectedSingleTask(e.target.value)}
                    disabled={isLoading}
                  >
                    {singleTasks.map((task) => (
                      <option key={task.id} value={task.id}>
                        {task.name} · {task.split}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Max Steps Override */}
                <div className="form-group">
                  <label htmlFor="steps-input" className="form-label">步数上限 (Max Steps)</label>
                  <input
                    id="steps-input"
                    type="number"
                    className="form-input"
                    min={1}
                    max={20}
                    value={maxSteps}
                    onChange={(e) => setMaxSteps(parseInt(e.target.value) || 6)}
                    disabled={isLoading}
                  />
                </div>

                {selectedModel !== 'fake' && (
                  <div className="form-group">
                    <label htmlFor="single-token-budget">总 Token 预算（输入 + 输出）</label>
                    <input id="single-token-budget" type="number" min={100} max={20000}
                      value={singleTokenBudget ?? ''} placeholder="留空使用任务原预算"
                      onChange={(e) => setSingleTokenBudget(e.target.value === '' ? null : Number(e.target.value))}
                      disabled={isLoading} />
                    <p className="metric-sub">真实多轮建议 8000；两种策略使用相同预算。免费通道按约 13 秒间隔发起请求，仍可能遇到账户限额。</p>
                  </div>
                )}

                <button
                  id="run-button"
                  className="btn-primary"
                  onClick={handleRunEpisode}
                  disabled={!isSingleRunReady}
                  title={!meta ? '元数据尚未就绪' : !selectedSingleTask ? '请选择一个任务后再运行' : undefined}
                >
                  {isLoading ? (
                    <>
                      <div className="spinner" />
                      <span>正在运行 Episode...</span>
                    </>
                  ) : (
                    <>
                      <span>开始运行 Episode</span>
                    </>
                  )}
                </button>
                {isLoading && (
                  <p className="loading-note" role="status" aria-live="polite">
                    {loadingMessage} <span aria-hidden="true">已等待 {elapsedSeconds} 秒。</span>
                  </p>
                )}

                {/* Recent Runs */}
                {recentEpisodeIds.length > 0 && (
                  <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                      最近运行历史：
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                      {recentEpisodeIds.map((rid) => (
                        <button
                          key={rid}
                          className="btn-secondary"
                          style={{ textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                          onClick={() => loadEpisodeById(rid)}
                        >
                          {rid}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </section>

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
                            {artifact.task.evaluator_config.suite === 'bfcl_adapted'
                              ? 'BFCL 改编子集'
                              : '原生 ToolLab'}
                          </div>
                          <div className="metric-sub">
                            {artifact.task.evaluator_config.suite === 'bfcl_adapted'
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
                            {artifact.agent.runtime_strategy === 'handwritten_recovery' ? (
                              <span className="badge badge-purple">Recovery 容错策略</span>
                            ) : (
                              <span className="badge badge-blue">Baseline 策略</span>
                            )}
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
                          <div className="metric-label">预估费用</div>
                          <div className="metric-value" id="metric-cost" style={{ color: artifact.episode.estimated_cost.is_known ? 'var(--text-primary)' : 'var(--warn-text)' }}>
                            {artifact.episode.estimated_cost.is_known
                              ? `$${artifact.episode.estimated_cost.amount} USD`
                              : '未知 (未验证)'}
                          </div>
                          <div className="metric-sub">
                            版本: {artifact.episode.estimated_cost.price_table_version}
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="empty-state">
                      <div className="empty-icon">尚无运行结果</div>
                      <div>请在左侧选择模型并点击“开始运行 Episode”，或输入已有 ID 查看历史结果。</div>
                    </div>
                  )}
                </section>

                {/* Trace Timeline */}
                <section className="card" id="trace-panel">
                  <div className="card-title">
                    <span>Trace Replay</span>
                    {artifact && (
                      <span className="badge" style={{ fontFamily: 'var(--font-mono)' }}>
                        {artifact.events.length} 个事件
                      </span>
                    )}
                  </div>
                  <div className="card-desc">
                    仅回放已保存的事件和环境快照，不重新请求模型或执行工具。
                  </div>

                  {artifact && artifact.events.length > 0 ? (
                    <>
                      <div className="replay-toolbar" aria-label="Replay controls">
                        <label>
                          <span>事件类型</span>
                          <select
                            id="trace-event-filter"
                            className="form-select"
                            value={eventTypeFilter}
                            onChange={(event) => {
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
                        </label>
                        <label>
                          <span>跳转 Step</span>
                          <select
                            id="trace-step-jump"
                            className="form-select"
                            value={activeReplayEvent?.step_index ?? ''}
                            disabled={visibleEvents.length === 0}
                            onChange={(event) => {
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
                            onClick={() => setReplayIndex((index) => Math.max(index - 1, 0))}
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
                            onClick={() =>
                              setReplayIndex((index) =>
                                Math.min(index + 1, visibleEvents.length - 1),
                              )
                            }
                          >
                            下一步 →
                          </button>
                        </div>
                      </div>

                      {activeReplayEvent ? (
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

                          <div className="replay-event-panel">
                            <div className="replay-panel-heading">
                              <span>当前事件</span>
                              <span className="event-step-pill">
                                Step {activeReplayEvent.step_index}
                              </span>
                            </div>
                            <div className="active-event-name">
                              {formatEventTypeLabel(activeReplayEvent.event_type)}
                            </div>
                            <div className="event-raw-name">原始事件名：{activeReplayEvent.event_type}</div>
                            <div className="event-meta">
                              {new Date(activeReplayEvent.timestamp).toLocaleString()}
                              {typeof activeReplayEvent.duration_ms === 'number' && activeReplayEvent.duration_ms > 0
                                ? ` · ${activeReplayEvent.duration_ms} ms`
                                : ' · 时长未知'}
                            </div>
                            <pre>{JSON.stringify(activeReplayEvent.payload, null, 2)}</pre>
                          </div>
                        </div>
                      ) : (
                        <div className="empty-state compact-empty">
                          当前筛选没有匹配事件，请选择其他事件类型。
                        </div>
                      )}

                      {visibleEvents.length > 0 && (
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
          </div>
        )}
      </main>
    </div>
  );
}
