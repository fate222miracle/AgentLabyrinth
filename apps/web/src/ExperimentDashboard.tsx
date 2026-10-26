import { useState } from 'react';
import { comparableHistory, type ExperimentDashboardItem } from './historySummary';
import { comparisonLabels, ExperimentCharts, HistoryTrendChart } from './ExperimentCharts';

interface Props {
  items: ExperimentDashboardItem[];
  loading: boolean;
  error: boolean;
  skipped: number;
  activeId?: string;
  onRefresh: () => void;
  onOpen: (id: string) => void;
}

const axisLabel = (item: ExperimentDashboardItem) => item.comparison_axis === 'context_policy' ? '上下文对照'
  : item.comparison_axis === 'memory_ablation' ? '工具记忆对照'
  : item.comparison_axis === 'planning' ? '规划对照'
  : item.comparison_axis === 'runtime_backend' ? 'Runtime 对照' : item.comparison_axis === 'recovery_policy' ? '恢复策略对照' : '对照类型未记录';
const signed = (value: number) => `${value > 0 ? '+' : ''}${Number(value.toFixed(2))}`;
const cost = (value: string | null | undefined) => value == null ? '未知' : `$${value}`;
const faultLabels: Record<string, string> = { none: '无故障', tool_timeout: '工具超时', empty_result: '查询空结果', mcp_disconnect: 'MCP 断线' };
const scenarioLabels: Record<string, string> = { success: '正常场景', 'invalid-then-success': '首次参数错误' };
const faultLabel = (value: string | null | undefined) => faultLabels[value ?? ''] ?? value ?? '未记录';
const scenarioLabel = (item: ExperimentDashboardItem) => item.provider === 'aihubmix' ? '真实请求' : scenarioLabels[item.scenario ?? ''] ?? item.scenario ?? '未记录';

export function ExperimentDashboard({ items, loading, error, skipped, activeId, onRefresh, onOpen }: Props) {
  const [selectedKey, setSelectedKey] = useState('');
  const [limit, setLimit] = useState(8);
  const groups = [...new Map(items.filter((item) => item.comparison_key).map((item) => [item.comparison_key!, item])).values()];
  const key = groups.some((item) => item.comparison_key === selectedKey) ? selectedKey : '';
  const visible = key ? comparableHistory(items, key) : items;
  const [latest, previous] = key ? visible.filter(item => item.total_pairs > 0) : [];
  const spotlight = visible.find(item => item.experiment_id === activeId) ?? visible[0];
  return (
    <section className="card experiment-dashboard" aria-labelledby="experiment-dashboard-title" aria-busy={loading}>
      <div className="dashboard-toolbar">
        <div>
          <div className="card-title" id="experiment-dashboard-title">实验指标看板</div>
          <p className="card-desc">最近 100 次已保存实验。选择同配置组查看变化，保留模型、任务、预算和评分条件一致。</p>
        </div>
        <button className="btn-secondary" type="button" disabled={loading} onClick={onRefresh}>刷新记录</button>
      </div>
      <label className="dashboard-filter">实验历史范围
        <select value={key} onChange={(event) => { setSelectedKey(event.target.value); setLimit(8); }}>
          <option value="">全部历史 · 不汇总排名</option>
          {groups.map((item, index) => (
            <option key={item.comparison_key} value={item.comparison_key!}>
              配置组 {index + 1} · {item.model_id ?? '模型未记录'} · {axisLabel(item)} · {item.task_ids?.length ?? 0} 题 · Seed {item.seeds?.join('/') || '未记录'} · 重复 {item.repeat_count ?? '未记录'} · {scenarioLabel(item)} · {faultLabel(item.fault_profile)} · {item.comparison_key?.slice(0, 6)}
            </option>
          ))}
        </select>
      </label>
      {loading && <p role="status">正在读取已保存的指标…</p>}
      {error && <p role="alert">历史指标读取失败。请刷新记录重试；已有结果仍可打开。</p>}
      {skipped > 0 && <p role="status">有 {skipped} 份损坏或不匹配的历史文件未计入。</p>}
      {!loading && !error && visible.length === 0 && <p className="metric-sub">暂无已完成实验。</p>}
      {spotlight && <div className="dashboard-spotlight">
        <div className="chart-heading"><div><span className="story-section-label">单场结果 · 不汇总不同配置</span>
          <h3>{spotlight.model_id ?? '模型未记录'} · {axisLabel(spotlight)}</h3></div>
          <button type="button" className="btn-secondary" onClick={() => onOpen(spotlight.experiment_id)}>读取这场实验</button></div>
        <p className="chart-note">{spotlight.provider === 'fake' ? '离线模拟' : spotlight.provider === 'aihubmix' ? '真实模型记录' : '来源未记录'} · {new Date(spotlight.created_at).toLocaleString()} · {spotlight.total_pairs} 对任务</p>
        <ExperimentCharts labels={comparisonLabels(spotlight.comparison_axis, spotlight.recovery_backend)} total={spotlight.total_pairs}
          rates={[spotlight.baseline_success_rate, spotlight.recovery_success_rate]}
          tokens={[spotlight.baseline_total_tokens, spotlight.recovery_total_tokens]}
          durations={[spotlight.baseline_avg_duration_ms, spotlight.recovery_avg_duration_ms]} />
      </div>}
      <HistoryTrendChart items={key ? visible : []} onOpen={onOpen} />
      {latest && previous && (
        <div className="dashboard-trend" aria-label="最近两次同配置实验变化">
          <p><strong>最近一次相对上一次</strong> · {new Date(previous.created_at).toLocaleString()} → {new Date(latest.created_at).toLocaleString()}</p>
          <dl>
            <div><dt>成功率变化（百分点）</dt><dd>{signed((latest.baseline_success_rate - previous.baseline_success_rate) * 100)} / {signed((latest.recovery_success_rate - previous.recovery_success_rate) * 100)}</dd></div>
            <div><dt>Token 变化</dt><dd>{signed(latest.baseline_total_tokens - previous.baseline_total_tokens)} / {signed(latest.recovery_total_tokens - previous.recovery_total_tokens)}</dd></div>
            <div><dt>平均耗时变化（ms）</dt><dd>{signed(latest.baseline_avg_duration_ms - previous.baseline_avg_duration_ms)} / {signed(latest.recovery_avg_duration_ms - previous.recovery_avg_duration_ms)}</dd></div>
          </dl>
          <p className="metric-sub">数值依次为两侧；单次变化仅供观察，不能据此判断统计显著性。</p>
        </div>
      )}
      {key && visible.length === 1 && <p className="metric-sub">当前配置只有一次完整运行，尚无历史差值。</p>}
      <div className="experiment-dashboard-list">
        {visible.slice(0, limit).map((item) => {
          const labels = comparisonLabels(item.comparison_axis, item.recovery_backend);
          return (
            <article className="experiment-dashboard-item" key={item.experiment_id}>
              <button className="dashboard-open" type="button" aria-current={activeId === item.experiment_id ? 'true' : undefined} onClick={() => onOpen(item.experiment_id)}>
                <strong>{axisLabel(item)} · {item.model_id ?? '模型未记录'}</strong>
                <span>{item.provider === 'fake' ? '离线模拟' : item.provider === 'aihubmix' ? '真实模型' : '来源未记录'} · {item.total_pairs} 对 · {new Date(item.created_at).toLocaleString()}</span>
              </button>
              <div className="dashboard-bars" aria-label="两侧成功率">
                {[item.baseline_success_rate, item.recovery_success_rate].map((rate, index) => (
                  <label key={labels[index]}>{labels[index]} {item.total_pairs ? `${Math.round(rate * 100)}%` : '无样本'}
                    {item.total_pairs > 0 && <progress max="100" value={rate * 100} />}
                  </label>
                ))}
              </div>
              <p className="metric-sub">Token {item.baseline_total_tokens} / {item.recovery_total_tokens} · 平均耗时 {Math.round(item.baseline_avg_duration_ms)} / {Math.round(item.recovery_avg_duration_ms)} ms</p>
              <p className="metric-sub">{item.provider === 'fake' ? '模拟费用' : '网关估算费用'} {cost(item.baseline_total_cost)} / {cost(item.recovery_total_cost)} · 原厂参考成本 {cost(item.baseline_reference_cost)} / {cost(item.recovery_reference_cost)} USD</p>
              <details><summary>查看实验范围与来源</summary>
                <p className="metric-sub">{item.environment_version} · {item.task_ids?.join('、') || '任务未记录'}</p>
                <p className="metric-sub">Seed {item.seeds?.join('、') || '未记录'} · 重复 {item.repeat_count ?? '未记录'} · 场景 {scenarioLabel(item)} · 故障 {faultLabel(item.fault_profile)}</p>
                <p className="metric-sub">{item.comparison_key ? '具有完整比较配置' : '旧记录协议来源不足，仅展示单次结果'} · 参考价格版本 {item.reference_price_version ?? '未记录'}</p>
                <p className="metric-sub">实验 ID：{item.experiment_id}</p>
              </details>
            </article>
          );
        })}
      </div>
      {visible.length > limit && <button className="btn-secondary" type="button" onClick={() => setLimit(limit + 8)}>再显示 8 条记录（已显示 {limit} / {visible.length}）</button>}
    </section>
  );
}
