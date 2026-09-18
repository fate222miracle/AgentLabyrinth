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
  };
  evaluation: {
    success: boolean;
    reason: string;
    metrics: Record<string, unknown>;
  };
  agent: {
    model: {
      provider: string;
      model: string;
    };
  };
  events: TraceEvent[];
}

export default function App() {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('gemini-3.7-flash-free');
  const [selectedScenario, setSelectedScenario] = useState<string>('success');
  const [maxSteps, setMaxSteps] = useState<number>(6);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [artifact, setArtifact] = useState<EpisodeArtifact | null>(null);
  const [expandedEvents, setExpandedEvents] = useState<Record<string, boolean>>({});
  const [recentIds, setRecentIds] = useState<string[]>([]);
  const [inputEpisodeId, setInputEpisodeId] = useState<string>('');

  // 1. Fetch Metadata on initial mount
  useEffect(() => {
    fetch('/api/v1/meta')
      .then((res) => {
        if (!res.ok) throw new Error('无法连接后端配置元数据');
        return res.json();
      })
      .then((data: MetaResponse) => {
        setMeta(data);
        if (data.default_model) setSelectedModel(data.default_model);
      })
      .catch((err) => {
        setErrorMsg(`API 连通性错误: ${err.message}`);
      });

    // Load recent IDs from localStorage
    try {
      const saved = localStorage.getItem('al_recent_episodes');
      if (saved) setRecentIds(JSON.parse(saved));
    } catch {
      // ignore storage error
    }

    // Check URL param ?episode_id=xxx
    const params = new URLSearchParams(window.location.search);
    const urlEpisodeId = params.get('episode_id');
    if (urlEpisodeId) {
      loadEpisodeById(urlEpisodeId);
    }
  }, []);

  // Save to recent IDs list
  const addRecentId = (id: string) => {
    setRecentIds((prev) => {
      const next = [id, ...prev.filter((item) => item !== id)].slice(0, 5);
      try {
        localStorage.setItem('al_recent_episodes', JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  // Load an existing episode by ID
  const loadEpisodeById = async (id: string) => {
    if (!id || id.trim().length === 0) return;
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/v1/episodes/${encodeURIComponent(id.trim())}`);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.message || `未能找到 Episode (${res.status})`);
      }
      const data = await res.json();
      setArtifact(data.artifact);
      addRecentId(id.trim());

      // Update URL without full reload
      const url = new URL(window.location.href);
      url.searchParams.set('episode_id', id.trim());
      window.history.pushState({}, '', url.toString());
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '加载失败';
      setErrorMsg(message);
    } finally {
      setIsLoading(false);
    }
  };

  // Trigger execution of a new episode
  const handleRun = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const currentModelObj = meta?.models.find((m) => m.id === selectedModel);
      const isFake = selectedModel === 'fake' || currentModelObj?.provider === 'fake';

      const payload = {
        provider: isFake ? 'fake' : 'aihubmix',
        model: isFake ? 'fake-model' : selectedModel,
        scenario: isFake ? selectedScenario : null,
        task_id: 'order-status-001',
        max_steps: maxSteps,
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
      addRecentId(newArtifact.episode.episode_id);

      // Update URL query string
      const url = new URL(window.location.href);
      url.searchParams.set('episode_id', newArtifact.episode.episode_id);
      window.history.pushState({}, '', url.toString());
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '运行失败';
      setErrorMsg(message);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleEventExpand = (eventId: string) => {
    setExpandedEvents((prev) => ({ ...prev, [eventId]: !prev[eventId] }));
  };

  const currentModelMeta = meta?.models.find((m) => m.id === selectedModel);

  return (
    <div>
      {/* Header */}
      <header className="app-header">
        <div className="header-container">
          <div className="brand">
            <span className="brand-icon">🧭</span>
            <div>
              <div className="brand-title">AgentLabyrinth</div>
              <div className="brand-subtitle">M1 ToolLab Web 演示闭环 (切片 B)</div>
            </div>
          </div>
          <div className="header-badges">
            <span className="badge badge-blue">单用户本地演示</span>
            <span className="badge badge-green">ADR-003 Accepted</span>
            <span className="badge">SSOT V0.5</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-container">
        {/* Persistent ID Bar */}
        <div className="persistence-bar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <span style={{ color: 'var(--text-muted)' }}>当前 Episode:</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
              {artifact ? artifact.episode.episode_id : '尚未运行'}
            </span>
            {artifact && (
              <button
                id="btn-copy-id"
                className="btn-secondary"
                onClick={() => {
                  navigator.clipboard.writeText(artifact.episode.episode_id);
                  alert('Episode ID 已复制到剪贴板！');
                }}
              >
                复制 ID
              </button>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <input
              id="input-episode-id"
              className="form-input"
              style={{ width: '220px', padding: '0.35rem 0.6rem', fontSize: '0.75rem' }}
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

        {/* Error Alert Box */}
        {errorMsg && (
          <div id="error-alert" className="alert-box alert-error">
            <span>⚠️</span>
            <div>{errorMsg}</div>
          </div>
        )}

        <div className="dashboard-grid">
          {/* Panel 1: Configuration */}
          <section className="card" id="config-panel">
            <div className="card-title">
              <span>实验配置</span>
              <span className="badge badge-blue">ToolLab</span>
            </div>
            <div className="card-desc">选择模型模式与限制，发起单次受控评测。</div>

            <div className="form-group">
              <label htmlFor="model-select" className="form-label">评测模型</label>
              <select
                id="model-select"
                className="form-select"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                disabled={isLoading}
              >
                {meta?.models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} {m.is_default ? '★ 默认推荐' : ''} {m.is_experimental ? '⚠️ 实验性' : ''}
                  </option>
                ))}
              </select>
            </div>

            {/* Model Notes Box */}
            {currentModelMeta && (
              <div className="form-group">
                <div className="model-note-box">
                  <strong>说明：</strong> {currentModelMeta.notes}
                </div>
              </div>
            )}

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
                  <option value="wrong-answer">wrong-answer (提交错误答案，评测失败)</option>
                  <option value="invalid-arguments">invalid-arguments (工具参数校验失败)</option>
                  <option value="max-steps">max-steps (步数超限终止)</option>
                </select>
              </div>
            )}

            {/* Task Info */}
            <div className="form-group">
              <label className="form-label">评测任务</label>
              <div
                style={{
                  padding: '0.65rem 0.85rem',
                  background: 'rgba(15, 23, 42, 0.4)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.8125rem',
                }}
              >
                <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                  order-status-001 (查询订单状态并提交证据)
                </div>
                <div style={{ color: 'var(--text-muted)', marginTop: '0.2rem', fontSize: '0.75rem' }}>
                  严格预算: 1000 Tokens, 最大 6 步
                </div>
              </div>
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

            <button
              id="run-button"
              className="btn-primary"
              onClick={handleRun}
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <div className="spinner" />
                  <span>正在运行 Episode...</span>
                </>
              ) : (
                <>
                  <span>🚀</span>
                  <span>开始运行 Episode</span>
                </>
              )}
            </button>

            {/* Recent Runs */}
            {recentIds.length > 0 && (
              <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                  最近运行历史：
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                  {recentIds.map((rid) => (
                    <button
                      key={rid}
                      className="btn-secondary"
                      style={{ textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      onClick={() => loadEpisodeById(rid)}
                    >
                      🕒 {rid}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </section>

          {/* Right Column: Result Summary + Trace View */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Panel 2: Result Summary */}
            <section className="card" id="results-panel">
              <div className="card-title">
                <span>运行结果指标</span>
                {artifact && (
                  <span
                    id="eval-badge"
                    className={`badge ${artifact.evaluation.success ? 'badge-green' : 'badge-red'}`}
                  >
                    {artifact.evaluation.success ? '✓ 评测通过 (SUCCESS)' : '✕ 评测未通过 (FAILED)'}
                  </span>
                )}
              </div>
              <div className="card-desc">展示当前 Episode 的终态判定、用量与真实性审计指标。</div>

              {artifact ? (
                <div>
                  <div className="metrics-grid">
                    {/* Model Info */}
                    <div className="metric-box">
                      <div className="metric-label">执行模型</div>
                      <div className="metric-value" style={{ fontSize: '1rem' }} id="metric-model">
                        {artifact.agent.model.model}
                      </div>
                      <div className="metric-sub">
                        {artifact.episode.token_usage.simulated ? (
                          <span className="badge badge-yellow">离线模拟 (Fake)</span>
                        ) : (
                          <span className="badge badge-green">真实网络模型</span>
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
                        {artifact.episode.detail || artifact.evaluation.reason}
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
                  <div className="empty-icon">📊</div>
                  <div>请在左侧选择模型并点击“开始运行 Episode”，或输入已有 ID 查看历史结果。</div>
                </div>
              )}
            </section>

            {/* Panel 3: Trace Timeline */}
            <section className="card" id="trace-panel">
              <div className="card-title">
                <span>事件级 Trace 时间线</span>
                {artifact && (
                  <span className="badge" style={{ fontFamily: 'var(--font-mono)' }}>
                    {artifact.events.length} 个事件
                  </span>
                )}
              </div>
              <div className="card-desc">
                按事件时间戳严格呈现模型提议、工具格式校验、执行反馈及环境状态。
              </div>

              {artifact && artifact.events.length > 0 ? (
                <div className="timeline-container" id="timeline-list">
                  {artifact.events.map((ev) => {
                    const isExpanded = !!expandedEvents[ev.event_id];
                    return (
                      <div key={ev.event_id} className="timeline-event">
                        <div
                          className="event-header"
                          onClick={() => toggleEventExpand(ev.event_id)}
                        >
                          <div className="event-info">
                            <span className="event-step-pill">Step {ev.step_index}</span>
                            <span className="event-name">{ev.event_type}</span>
                          </div>
                          <div className="event-meta">
                            <span>{new Date(ev.timestamp).toLocaleTimeString()}</span>
                            <span>{isExpanded ? '▲ 收起' : '▼ 展开'}</span>
                          </div>
                        </div>
                        {isExpanded && (
                          <div className="event-body">
                            <pre>{JSON.stringify(ev.payload, null, 2)}</pre>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-icon">📜</div>
                  <div>Trace 数据将在 Episode 执行完成后呈现在此。</div>
                </div>
              )}
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
