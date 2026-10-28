import { useState } from 'react';
import type { ExperimentDashboardItem } from './historySummary';

export function comparisonLabels(axis: string, runtimeRight?: string | null): [string, string] {
  return axis === 'context_policy' ? ['完整历史', '近期窗口'] : axis === 'memory_ablation'
    ? ['窗口（无记忆）', '窗口 + 记忆'] : axis === 'planning'
    ? ['无声明计划', '声明计划'] : axis === 'runtime_backend'
    ? ['Reference', runtimeRight === 'pydantic_ai' ? 'PydanticAI' : 'LangGraph']
    : axis === 'recovery_policy' ? ['Baseline', 'Recovery'] : ['左侧', '右侧'];
}

export function ExperimentCharts({ labels, rates, tokens, durations, total, counts }: {
  labels: [string, string]; rates: [number, number]; tokens: [number, number]; durations: [number, number]; total: number;
  counts?: [number, number];
}) {
  return <div className="experiment-charts" aria-label="实验图形指标">
    <section className="chart-panel success-chart"><div className="chart-heading"><h3>任务通过比例</h3><span>每侧 {total} 次执行</span></div>
      <div className="success-rings">{rates.map((rate, index) => <figure key={labels[index]}>
        <svg viewBox="0 0 140 140" role="img" aria-label={total ? `${labels[index]}：通过 ${(rate * 100).toFixed(1)}%，未通过 ${((1 - rate) * 100).toFixed(1)}%` : `${labels[index]}：没有样本`}>
          <circle cx="70" cy="70" r="52" className="ring-track" />
          {total > 0 && <circle cx="70" cy="70" r="52" pathLength="100" className={`ring-arm arm-${index}`}
            strokeDasharray={`${rate * 100} 100`} transform="rotate(-90 70 70)" />}
          <text x="70" y="68" textAnchor="middle" className="ring-value">{total ? `${(rate * 100).toFixed(1)}%` : '—'}</text>
          <text x="70" y="88" textAnchor="middle" className="ring-label">{total ? '通过' : '没有样本'}</text>
        </svg><figcaption><i className={`chart-key arm-${index}`} />{labels[index]}
          {counts && <span className="chart-count">{counts[index]} / {total} 通过</span>}</figcaption>
      </figure>)}</div><p className="chart-note">着色为通过，灰色为未通过；按独立评测结论统计。</p>
    </section>
    <div className="usage-charts">{[{ title: '已报告 Token', values: tokens, unit: 'tokens' },
      { title: '平均执行耗时', values: durations, unit: 'ms' }].map(({ title, values, unit }) => {
        const ceiling = Math.max(...values, 1);
        return <section className="chart-panel" key={title} aria-label={title}>
          <div className="chart-heading"><h3>{title}</h3><span>{unit}</span></div>
          <div className="arm-bars">{values.map((value, index) => <div className="arm-bar-row" key={labels[index]}>
            <div><span><i className={`chart-key arm-${index}`} />{labels[index]}</span><strong>{Number(value.toFixed(2)).toLocaleString()} <small>{unit}</small></strong></div>
            <div className="arm-bar-track" aria-hidden="true"><span className={`arm-${index}`} style={{ width: `${value / ceiling * 100}%` }} /></div>
          </div>)}</div>
          {unit === 'tokens' && <p className="chart-note">仅汇总已报告用量；请求中断可能漏报，不能据此确认完整消耗或节省量。</p>}
        </section>;
      })}</div>
  </div>;
}

/** Graph only the already filtered, compatible saved runs; run spacing is ordinal, not elapsed time. */
export function HistoryTrendChart({ items, onOpen }: { items: ExperimentDashboardItem[]; onOpen: (id: string) => void }) {
  const [metric, setMetric] = useState('success');
  const history = items.filter(item => item.total_pairs > 0).slice().reverse().slice(-30);
  const labels = comparisonLabels(history[0]?.comparison_axis ?? '', history[0]?.recovery_backend);
  const unit = metric === 'success' ? '%' : metric === 'tokens' ? 'tokens' : 'ms';
  const title = metric === 'success' ? '成功率' : metric === 'tokens' ? '已报告 Token' : '平均耗时';
  const values = history.map(item => metric === 'success' ? [item.baseline_success_rate * 100, item.recovery_success_rate * 100]
    : metric === 'tokens' ? [item.baseline_total_tokens, item.recovery_total_tokens]
      : [item.baseline_avg_duration_ms, item.recovery_avg_duration_ms]);
  const ceiling = metric === 'success' ? 100 : Math.max(1, ...values.flat());
  const x = (i: number) => 56 + i / Math.max(history.length - 1, 1) * 544;
  const y = (value: number) => 208 - value / ceiling * 168;
  return <section className="chart-panel history-trend-chart" aria-label="同配置历史折线图">
    <div className="chart-heading"><div><span className="story-section-label">同条件 · 历史趋势</span><h3>{title}变化</h3></div>
      <label><span className="sr-only">历史趋势指标</span><select aria-label="历史趋势指标" value={metric} onChange={event => setMetric(event.target.value)}>
        <option value="success">成功率</option><option value="tokens">已报告 Token</option><option value="duration">平均耗时</option>
      </select></label></div>
    <div className="chart-legend">{labels.map((label, i) => <span key={label}><i className={`chart-key arm-${i}`} />{label} · {i === 0 ? '实线' : '虚线'}</span>)}<span>单位：{unit}</span>
      {history.length >= 2 && values.every(value => value[0] === value[1]) && <span>两侧数值相同，曲线重合</span>}</div>
    {metric === 'tokens' && <p className="chart-note">曲线只表示已报告用量，未报告部分未知；请核查保存的运行，不能直接当作完整节省趋势。</p>}
    {history.length >= 2 ? <>
      <svg viewBox="0 0 640 250" role="img" aria-label={`${title}：${history.length} 次同配置实验，按保存时间排序的运行序号`}>
        {[0, 0.5, 1].map(fraction => <g key={fraction}>
          <line x1="56" x2="600" y1={y(fraction * ceiling)} y2={y(fraction * ceiling)} className="chart-gridline" />
          <text x="46" y={y(fraction * ceiling) + 4} textAnchor="end">{new Intl.NumberFormat('zh-CN', { notation: 'compact', maximumFractionDigits: 1 }).format(fraction * ceiling)}</text>
        </g>)}
        {[0, 1].map(arm => <g key={arm}>
          <polyline className={`chart-line arm-${arm}`} points={values.map((value, i) => `${x(i)},${y(value[arm])}`).join(' ')} />
          {history.map((item, i) => <a key={item.experiment_id} href={`?experiment_id=${item.experiment_id}`} tabIndex={0}
            aria-label={`读取第 ${i + 1} 次实验的 ${labels[arm]}：${values[i][arm].toFixed(1)} ${unit}`}
            onClick={event => { event.preventDefault(); onOpen(item.experiment_id); }}>
            <title>{new Date(item.created_at).toLocaleString()} · {labels[arm]} {values[i][arm].toFixed(1)} {unit}</title>
            <circle cx={x(i)} cy={y(values[i][arm])} r={arm === 0 ? 5 : 3} className={`chart-point arm-${arm}`} />
          </a>)}
        </g>)}
        <text x="56" y="235">第 1 次</text><text x="600" y="235" textAnchor="end">第 {history.length} 次</text>
      </svg>
      <p className="chart-note">{new Date(history[0].created_at).toLocaleString()} → {new Date(history.at(-1)!.created_at).toLocaleString()}。最近最多 30 次，横轴为等间距运行序号；点击点只读取保存结果。</p>
      <details className="chart-data"><summary>查看趋势原始数值</summary><div className="table-scroll"><table><thead><tr><th>保存时间</th><th>{labels[0]} ({unit})</th><th>{labels[1]} ({unit})</th></tr></thead>
        <tbody>{history.map((item, i) => <tr key={item.experiment_id}><td>{new Date(item.created_at).toLocaleString()}</td><td>{values[i][0]}</td><td>{values[i][1]}</td></tr>)}</tbody></table></div></details>
    </> : <div className="chart-empty">{history.length === 1 ? '当前配置只有一次完整运行，尚无历史趋势。' : items.length ? '当前配置没有可用的成对样本。' : '选择同配置组后显示历史折线。'}<p>模型、任务、预算和评分协议保持一致，才有比较意义。</p></div>}
  </section>;
}
