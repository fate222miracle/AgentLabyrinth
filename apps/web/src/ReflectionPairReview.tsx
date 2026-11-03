import { useEffect, useRef, useState } from 'react';
import type { EpisodeArtifact, PairComparison, TraceEvent } from './apiContracts';
import { readEpisode } from './apiClient';
import { explainFailure } from './traceSteps';
import { savedUsage } from './historySummary';

type ReflectionView = {
  status: 'produced' | 'rejected' | 'none' | 'unknown';
  diagnosis?: string;
  revisedGoal?: string;
  sourceIds: string[];
  detail?: string;
};

function savedReflection(events: TraceEvent[]): ReflectionView {
  if (events[0]?.event_type !== 'EPISODE_STARTED' || events.at(-1)?.event_type !== 'EPISODE_FINISHED') {
    return { status: 'unknown', sourceIds: [] };
  }
  const event = events.find(item => item.event_type === 'REFLECTION_PRODUCED'
    || item.event_type === 'REFLECTION_REJECTED');
  if (!event) return { status: 'none', sourceIds: [] };
  const sources = Array.isArray(event.payload.source_event_ids)
    ? event.payload.source_event_ids.filter((id): id is string => typeof id === 'string') : [];
  return event.event_type === 'REFLECTION_PRODUCED'
    ? { status: 'produced', diagnosis: String(event.payload.diagnosis ?? ''),
        revisedGoal: String(event.payload.revised_goal ?? ''), sourceIds: sources }
    : { status: 'rejected', detail: String(event.payload.detail ?? '未知原因'), sourceIds: sources };
}

export function ReflectionPairReview({ pairs, labels }: { pairs: PairComparison[]; labels: [string, string] }) {
  const [selected, setSelected] = useState('0');
  const [results, setResults] = useState<PromiseSettledResult<EpisodeArtifact>[] | null>(null);
  const [loading, setLoading] = useState(false);
  const pending = useRef<AbortController | null>(null);
  const pair = pairs[Number(selected)] ?? pairs[0];
  useEffect(() => () => pending.current?.abort(), []);
  if (!pair) return null;

  async function load() {
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setResults(null);
    setLoading(true);
    const arms = await Promise.allSettled([pair.baseline_episode_id, pair.recovery_episode_id].map(async id => {
      const response = await fetch(`/api/v1/episodes/${encodeURIComponent(id)}`, { signal: controller.signal });
      return (await readEpisode(response, id)).artifact;
    }));
    if (!controller.signal.aborted) {
      setResults(arms);
      setLoading(false);
    }
  }

  return <section className="memory-pair-review chart-panel" aria-label="停滞反思差异">
    <div className="chart-heading"><div><span className="story-section-label">从已保存 Trace 判断差异</span><h3>反思有没有真正改变后续行为？</h3></div></div>
    <p className="chart-note">只读两侧 Episode，展示触发依据、诊断和修正目标；声明不等于执行，最终仍以后续工具 Trace 和评分为准。</p>
    <label className="form-label" htmlFor="reflection-review-pair">选择要审查的任务对</label>
    <select className="form-select" id="reflection-review-pair" value={selected} onChange={event => {
      setSelected(event.target.value); setResults(null);
    }}>
      {pairs.map((item, index) => <option key={`${item.baseline_episode_id}:${item.recovery_episode_id}`} value={index}>
        {item.task_name} · Seed {item.seed} · 第 {item.repeat_index ?? 1} 次
      </option>)}
    </select>
    <div className="memory-review-actions">
      <button type="button" className="btn-secondary" disabled={loading} onClick={load}>
        {loading ? '正在读取两侧记录…' : results ? '重新读取两侧记录' : '读取两侧执行记录'}
      </button>
      <span role="status">{loading ? '只读取已保存 Episode，未发起模型请求。' : results
        ? `已读取 ${results.filter(result => result.status === 'fulfilled').length} / 2 侧。`
        : '按需读取，不自动重跑。'}</span>
    </div>
    {results && <div className="memory-review-arms">{results.map((result, index) => {
      const id = index === 0 ? pair.baseline_episode_id : pair.recovery_episode_id;
      const artifact = result.status === 'fulfilled' ? result.value : null;
      const reflection = artifact ? savedReflection(artifact.events) : null;
      const usage = artifact ? savedUsage(artifact) : null;
      return <section key={id} className="memory-review-arm" aria-label={`${labels[index]}执行记录`}>
        <h4><i className={`chart-key arm-${index}`} />{labels[index]}</h4>
        <p className="memory-review-id">Episode：{id}</p>
        {artifact && reflection ? <>
          <p><span className={`badge ${artifact.evaluation.success ? 'badge-green' : 'badge-red'}`}>
            {artifact.evaluation.success ? '评测通过' : '评测未通过'}</span> · {artifact.episode.termination_reason}</p>
          {artifact.episode.detail && <p className="chart-note">终止说明：{explainFailure(artifact.episode.detail)}</p>}
          <dl className="memory-review-counts">
            <div><dt>模型请求</dt><dd>{artifact.episode.model_call_count}<small> 次</small></dd></div>
            <div><dt>工具调用</dt><dd>{artifact.episode.tool_call_count}<small> 次</small></dd></div>
            <div><dt>已报告 Token</dt><dd>{usage?.reportedTotal ?? '未知'}</dd></div>
          </dl>
          {reflection.status === 'produced' && <div className="model-note-box">
            <strong>已生成一次行动修正</strong>
            <p>停滞诊断：{reflection.diagnosis}</p><p>修正目标：{reflection.revisedGoal}</p>
            <small>触发事件：{reflection.sourceIds.join(' → ') || '未记录'}</small>
          </div>}
          {reflection.status === 'rejected' && <p className="memory-review-error">反思被拒绝：{reflection.detail}；未自动重试。</p>}
          {reflection.status === 'none' && <p className="chart-note">完整 Trace 中没有反思事件。{artifact.agent.reflection ? '本次未触发。' : '本侧未启用。'}</p>}
          {reflection.status === 'unknown' && <p className="chart-note">起止 Trace 不完整，反思状态未知，不按零处理。</p>}
        </> : <p className="memory-review-error" role="alert">此侧记录读取失败：{result.status === 'rejected' && result.reason instanceof Error
          ? result.reason.message : '记录不可用'}。</p>}
      </section>;
    })}</div>}
  </section>;
}
