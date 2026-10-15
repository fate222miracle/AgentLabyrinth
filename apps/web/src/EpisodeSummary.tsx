import type { EpisodeArtifact } from './apiContracts';
import { contextLabel } from './ContextSettings';

interface Props { artifact: EpisodeArtifact; explanation: string }

/** Present saved facts first; secondary details never alter or recompute the artifact. */
export function EpisodeSummary({ artifact, explanation }: Props) {
  const { episode, agent, task, run_config: config } = artifact;
  const simulated = agent.model.provider === 'fake';
  const suite = String(task.evaluator_config.suite ?? '');
  const cost = episode.estimated_cost;
  const costLabel = simulated ? '模拟费用' : '网关估算费用';
  const costValue = cost.is_known ? `$${cost.amount} USD` : '未知 (未验证)';
  return (
    <div className="episode-summary">
      <div className="episode-provenance" aria-label="已保存运行来源">
        <span className={`badge ${simulated ? 'badge-blue' : 'badge-yellow'}`}>
          {simulated ? 'Fake 离线模拟' : agent.model.provider === 'aihubmix' ? '真实 API · 探索性结果' : `来源：${agent.model.provider}`}
        </span>
        <strong id="metric-model">{agent.model.model}</strong>
        <span>{suite.startsWith('bfcl_')
          ? `BFCL ${suite === 'bfcl_java_adapted' ? 'Java ' : ''}改编子集` : '原生 ToolLab'} · {task.name}</span>
      </div>
      <div className="episode-runtime">
        <span>{agent.runtime_backend ?? 'handwritten'} Runtime</span>
        <span>{agent.runtime_strategy === 'handwritten_recovery' ? '一次参数纠错' : '无参数纠错'}</span>
        <span>工具传输：{config.environment_version === 'tool-lab-mcp-v1' ? 'MCP HTTP' : '本地'}</span>
        {agent.context_policy && <span>上下文：{contextLabel(agent.context_policy)}</span>}
      </div>
      <div className="metrics-grid episode-metrics">
        <div className="metric-box">
          <div className="metric-label">终止状态</div>
          <div className="metric-value" id="metric-status">{episode.termination_reason}</div>
          <div className="metric-sub">{explanation}</div>
        </div>
        <div className="metric-box">
          <div className="metric-label">步数 / 工具调用</div>
          <div className="metric-value" id="metric-steps">{episode.step_count} 步 / {episode.tool_call_count} 次工具</div>
          <div className="metric-sub">模型调用: {episode.model_call_count} 次</div>
        </div>
        <div className="metric-box">
          <div className="metric-label">{episode.token_usage.simulated ? 'Token 消耗 · 模拟' : 'Token 消耗'}</div>
          <div className="metric-value" id="metric-tokens">{episode.token_usage.prompt_tokens + episode.token_usage.completion_tokens}</div>
          <div className="metric-sub">输入 {episode.token_usage.prompt_tokens} / 输出 {episode.token_usage.completion_tokens}</div>
        </div>
        <div className="metric-box">
          <div className="metric-label">耗时</div>
          <div className="metric-value" id="metric-duration">{episode.duration_ms} ms</div>
          <div className="metric-sub">保存的时限：{agent.budget?.max_execution_time_ms
            ? `${agent.budget.max_execution_time_ms / 1000} 秒` : '历史配置未设置'}</div>
        </div>
      </div>
      <details className="episode-details" key={episode.episode_id}>
        <summary>费用与配置详情 <span>{costLabel}：{costValue} · 原厂参考：{artifact.reference_cost ? `$${artifact.reference_cost.amount} USD` : '未知'}</span></summary>
        <dl className="episode-detail-grid">
          <div><dt>{costLabel}</dt><dd id="metric-cost">{costValue}</dd><dd>价格版本：{cost.price_table_version}</dd></div>
          <div><dt>原厂标价参考成本</dt><dd>{artifact.reference_cost ? `$${artifact.reference_cost.amount} USD` : '未知'}</dd><dd>未命中缓存价 · 非实付费用{artifact.reference_cost ? ` · ${artifact.reference_cost.price_table_version}` : ''}</dd></div>
          <div><dt>Runtime 版本</dt><dd>{config.runtime_version ?? '历史产物未记录'}</dd></div>
          <div><dt>评分协议</dt><dd>{suite.startsWith('bfcl_')
            ? `AgentLabyrinth-adapted subset · ${String(task.evaluator_config.source_case_id ?? task.name)}` : task.name}</dd></div>
        </dl>
      </details>
    </div>
  );
}
