import { useEffect, useState } from 'react';
import { readApi, readEpisode } from './apiClient';
import { gridWorldComparisonSchema, type EpisodeArtifact, type GridWorldBatch, type GridWorldComparisonRow as Row, type ModelOption } from './apiContracts';
import { publicStates } from './GridWorldMap';
import { GridWorldPairReview } from './GridWorldPairReview';
import { GridWorldBatches } from './GridWorldBatches';
import { explainFailure } from './traceSteps';
import './gridworld-comparison.css';

const number = new Intl.NumberFormat('zh-CN');
const dateTime = new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
const format = (value: number | null) => value === null ? '未知' : number.format(value);
const replayUrl = (id: string) => `/gridworld/${id}`;
const taskLabel = (name: string) => name === 'key-door-002-v1' ? '回廊档案室' : '钥匙与门';
const totals = (row: Row) => row.input_tokens === null || row.output_tokens === null
  ? null : row.input_tokens + row.output_tokens;

function Route({ artifact, side }: { artifact: EpisodeArtifact; side: string }) {
  const { states, invalid } = publicStates(artifact.events);
  const first = states[0];
  const last = states[states.length - 1];
  if (!first || !last) return <p>该局没有可用地图轨迹。</p>;
  const [width, height] = last.size;
  const pickup = states.find(state => state.lastAction?.accepted && state.lastAction.action === 'pickup');
  const open = states.find(state => state.lastAction?.accepted && state.lastAction.action === 'use');
  return <figure className="comparison-route">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${side} 局已探索路线`}>
      {last.knownCells.map(cell => <rect key={`${cell.x},${cell.y}`} x={cell.x + .025} y={cell.y + .025}
        width=".95" height=".95" rx=".06" className={`route-cell route-${cell.kind}`} />)}
      <polyline className="route-line" points={states.map(({ position: [x, y] }) => `${x + .5},${y + .5}`).join(' ')} />
      <circle className="route-start" cx={first.position[0] + .5} cy={first.position[1] + .5} r=".16" />
      {pickup && <circle className="route-milestone" cx={pickup.position[0] + .5} cy={pickup.position[1] + .5} r=".13" />}
      {open && <circle className="route-milestone" cx={open.position[0] + .5} cy={open.position[1] + .5} r=".13" />}
      <circle className="route-stop" cx={last.position[0] + .5} cy={last.position[1] + .5} r=".19" />
    </svg>
    <figcaption>
      <span>起点 {first.position.join(', ')} · 停止点 {last.position.join(', ')}</span>
      <span>{pickup ? `第 ${pickup.actionCount} 步拾钥匙` : '未拾取钥匙'} · {open ? `第 ${open.actionCount} 步开门` : '未开门'}</span>
      {invalid && <span>后续地图数据无效，路线绘制到最后有效状态。</span>}
    </figcaption>
  </figure>;
}

function Pair({ rows: [a, b], models }: { rows: [Row, Row]; models: ModelOption[] }) {
  const [artifacts, setArtifacts] = useState<[EpisodeArtifact, EpisodeArtifact] | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const read = async (id: string) => (await readEpisode(
      await fetch(`/api/v1/episodes/${encodeURIComponent(id)}`, { signal: controller.signal }), id,
    )).artifact;
    void Promise.all([read(a.episode_id), read(b.episode_id)])
      .then(pair => { if (!controller.signal.aborted) setArtifacts(pair); })
      .catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, [a.episode_id, b.episode_id, attempt]);
  const metrics: Array<{ label: string; values: [number | null, number | null]; unit: string }> = [
    { label: '动作数', values: [a.actions, b.actions], unit: '' },
    { label: '总 Token', values: [a.usage_complete ? totals(a) : null, b.usage_complete ? totals(b) : null], unit: '' },
    { label: '耗时', values: [a.duration_ms / 1000, b.duration_ms / 1000], unit: ' 秒' },
  ];
  return <section className="comparison-panel" aria-label="两局并排对比">
    <h2>两局并排对比</h2>
    <div className="comparison-charts">{metrics.map(metric => {
      const max = Math.max(1, ...metric.values.map(value => value ?? 0));
      return <div className="comparison-metric" key={metric.label}>
        <h3>{metric.label}</h3>
        {metric.values.map((value, i) => <div className="comparison-bar-row" key={i}>
          <span>{i === 0 ? 'A' : 'B'}</span>
          <span className="comparison-track" aria-hidden="true"><span style={{ width: `${(value ?? 0) / max * 100}%` }} /></span>
          <strong>{format(value)}{value === null ? '' : metric.unit}</strong>
        </div>)}
      </div>;
    })}</div>
    <div className="comparison-routes">{[a, b].map((row, i) => <article key={row.episode_id}>
      <h3>{i === 0 ? 'A' : 'B'} · {row.model_id}</h3>
      <p>{row.success ? '通关' : explainFailure(row.detail) || row.termination}</p>
      {artifacts && <Route artifact={artifacts[i]} side={i === 0 ? 'A' : 'B'} />}
      <a href={replayUrl(row.episode_id)}>查看 3D 回放 →</a>
    </article>)}</div>
    {!artifacts && (failed
      ? <p role="alert">路线读取失败。 <button className="btn-secondary" onClick={() => { setFailed(false); setAttempt(value => value + 1); }}>重新读取路线</button></p>
      : <p role="status">正在读取两局的轨迹…</p>)}
    {a.provider === 'aihubmix' && b.provider === 'aihubmix'
      && <GridWorldPairReview rows={[a, b]} artifacts={artifacts} models={models} />}
  </section>;
}

export function GridWorldComparison({ models }: { models: ModelOption[] }) {
  const [items, setItems] = useState<Row[] | null>(null);
  const [error, setError] = useState(false);
  const [skipped, setSkipped] = useState(0);
  const [revision, setRevision] = useState(0);
  const [group, setGroup] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [batch, setBatch] = useState<GridWorldBatch | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void fetch('/api/v1/episodes/gridworld-comparison', { signal: controller.signal })
      .then(response => readApi(response, gridWorldComparisonSchema))
      .then(data => {
        if (controller.signal.aborted) return;
        setItems(data.items);
        setSkipped(data.skipped_count);
      })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [revision]);
  const groups = new Map<string, Row[]>();
  for (const row of batch ? batch.runs.flatMap(run => run.row ? [run.row] : []) : items ?? []) {
    const groupRows = groups.get(row.comparison_key) ?? [];
    if (!groupRows.some(item => item.model_id === row.model_id)) groupRows.push(row);
    groups.set(row.comparison_key, groupRows);
  }
  const defaultGroup = [...groups].find(([, rows]) => rows[0].provider === 'aihubmix' && rows.length >= 2)?.[0]
    ?? [...groups].find(([, rows]) => rows[0].provider === 'aihubmix')?.[0]
    ?? groups.keys().next().value ?? '';
  const key = groups.has(group) ? group : defaultGroup;
  const rows = groups.get(key) ?? [];
  const a = rows.find(row => row.episode_id === selected[0]);
  const b = rows.find(row => row.episode_id === selected[1]);
  const pair: [Row, Row] | null = a && b ? (a.episode_id < b.episode_id ? [a, b] : [b, a]) : null;
  return <>
    <GridWorldBatches models={models} selected={batch} onSelect={setBatch} />
    <section className="comparison-panel" aria-label="模型运行总览">
      <div className="comparison-toolbar">
        <div><h2>模型运行总览</h2><p>{batch
          ? `当前查看 ${new Date(batch.created_at).toLocaleString('zh-CN')} 批次的已保存结果。`
          : '读取最近 100 条已保存的 GridWorld 运行。每组每个模型显示最新一局。'}</p></div>
        {batch ? <button className="btn-secondary" onClick={() => setBatch(null)}>返回全部历史</button> :
        <button className="btn-secondary" disabled={items === null && !error}
          onClick={() => { setError(false); setItems(null); setRevision(value => value + 1); }}>刷新记录</button>}
      </div>
      {!batch && error ? <p role="alert">暂时无法读取模型运行记录。</p>
        : !batch && items === null ? <p role="status">正在读取已保存记录…</p>
          : !rows.length ? <p>暂无可比较记录。<a href="/gridworld">前往 GridWorld 运行 →</a></p> : <>
            {!batch && <label className="comparison-group">运行配置
              <select className="form-select" value={key} onChange={event => { setGroup(event.target.value); setSelected([]); }}>
                {[...groups].map(([id, [row, ...others]], i) => <option key={id} value={id}>
                  {taskLabel(row.task_name)} · {row.provider === 'fake' ? 'Fake' : '真实模型'} · {row.context_rounds ? `最近 ${row.context_rounds} 轮` : '完整历史'} · {row.max_steps} 步 · {others.length + 1} 个模型 · 配置 {i + 1}
                </option>)}
              </select>
            </label>}
            <p className="comparison-scope">Seed {rows[0].seed} · {format(rows[0].token_budget)} Token · {rows[0].max_execution_time_ms === null ? '时限未知' : `${rows[0].max_execution_time_ms / 1000} 秒`}</p>
            <p role="status">{rows.length < 2 ? '这组需要再保存一个不同模型的运行才能并排对比。' : `请选择两局。已选 ${Number(Boolean(a)) + Number(Boolean(b))} / 2。`}</p>
            <div className="comparison-table-wrap" role="region" aria-label="模型结果表" tabIndex={0}>
              <table className="comparison-table">
                <thead><tr><th scope="col">模型</th><th scope="col">结果</th><th scope="col">动作 / 拒绝</th><th scope="col">输入 / 输出 Token</th><th scope="col">耗时</th><th scope="col">回放</th></tr></thead>
                <tbody>{rows.map(row => {
                  const checked = selected.includes(row.episode_id);
                  return <tr key={row.episode_id}>
                    <th scope="row"><label><input type="checkbox" checked={checked} disabled={rows.length < 2 || (!checked && Boolean(a && b))}
                      aria-label={`选择 ${row.model_id}`} onChange={() => {
                        setSelected(current => checked ? current.filter(id => id !== row.episode_id)
                          : [...current.filter(id => rows.some(item => item.episode_id === id)), row.episode_id].slice(0, 2));
                      }} /> {row.model_id}</label><time dateTime={row.started_at}>{dateTime.format(new Date(row.started_at))}</time></th>
                    <td className={row.success ? 'record-success' : 'record-failed'}>{row.success ? '通关' : explainFailure(row.detail) || row.termination}</td>
                    <td>{format(row.actions)} / {format(row.illegal_actions)}</td>
                    <td>{row.input_tokens === null ? '未知' : `${format(row.input_tokens)} / ${format(row.output_tokens)}${row.usage_complete ? '' : '（部分报告）'}`}</td>
                    <td>{format(row.duration_ms / 1000)} 秒</td><td><a href={replayUrl(row.episode_id)} aria-label={`回放 ${row.model_id}`}>查看</a></td>
                  </tr>;
                })}</tbody>
              </table>
            </div>
          </>}
      {skipped > 0 && <p role="status">{skipped} 条保存记录校验失败，已跳过。</p>}
    </section>
    {pair && <Pair key={`${pair[0].episode_id}:${pair[1].episode_id}`} rows={pair} models={models} />}
  </>;
}
