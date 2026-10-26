import { useEffect, useRef, useState } from 'react';
import type { EpisodeArtifact, PairComparison } from './apiContracts';
import { readEpisode } from './apiClient';
import { savedDocumentReads } from './flowFrames';

/** Inspect two saved episodes on demand; never start or modify an experiment. */
export function MemoryPairReview({ pairs, labels }: { pairs: PairComparison[]; labels: [string, string] }) {
  const [selected, setSelected] = useState('0');
  const pair = pairs[Number(selected)] ?? pairs[0];
  if (!pair) return null;
  return <section className="memory-pair-review chart-panel" aria-label="工具记忆执行差异">
    <div className="chart-heading"><div><span className="story-section-label">从实际执行判断差异</span><h3>记忆有没有减少重复工作？</h3></div></div>
    <p className="chart-note">按一对保存记录查看，不重新运行模型。重复阅读不一定无效，需结合任务通过情况与实际内容判断。</p>
    <label className="form-label" htmlFor="memory-review-pair">选择要审查的任务对</label>
    <select className="form-select" id="memory-review-pair" value={selected} onChange={event => setSelected(event.target.value)}>
      {pairs.map((item, index) => <option key={`${item.baseline_episode_id}:${item.recovery_episode_id}`} value={index}>
        {item.task_name} · Seed {item.seed} · 第 {item.repeat_index ?? 1} 次
      </option>)}
    </select>
    <SavedPairDetails key={`${pair.baseline_episode_id}:${pair.recovery_episode_id}`} pair={pair} labels={labels} />
  </section>;
}

function SavedPairDetails({ pair, labels }: { pair: PairComparison; labels: [string, string] }) {
  const [results, setResults] = useState<PromiseSettledResult<EpisodeArtifact>[] | null>(null);
  const [loading, setLoading] = useState(false);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);
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
    if (controller.signal.aborted) return;
    setResults(arms);
    setLoading(false);
  }
  return <>
    <div className="memory-review-actions">
      <button type="button" className="btn-secondary" disabled={loading} onClick={load}>
        {loading ? '正在读取两侧记录…' : results ? '重新读取两侧执行记录' : '读取两侧执行记录'}
      </button>
      <span role="status">{loading ? '只读取已保存的 Episode，未发起模型请求。' : results
        ? `已读取 ${results.filter(result => result.status === 'fulfilled').length} / 2 侧，来源为下方 Episode ID。`
        : '按需读取两条记录，不批量加载全部 Trace。'}</span>
    </div>
    {results && <div className="memory-review-arms">{results.map((result, index) => {
      const id = index === 0 ? pair.baseline_episode_id : pair.recovery_episode_id;
      const artifact = result.status === 'fulfilled' ? result.value : null;
      const reads = artifact ? savedDocumentReads(artifact.events) : null;
      return <section key={id} className="memory-review-arm" aria-label={`${labels[index]}执行记录`}>
        <h4><i className={`chart-key arm-${index}`} />{labels[index]}</h4>
        <p className="memory-review-id">Episode：{id}</p>
        {artifact ? <>
          <p><span className={`badge ${artifact.evaluation.success ? 'badge-green' : 'badge-red'}`}>
            {artifact.evaluation.success ? '评测通过' : '评测未通过'}</span> · {artifact.episode.termination_reason}</p>
          <dl className="memory-review-counts">
            <div><dt>工具调用</dt><dd>{artifact.episode.tool_call_count}<small> 次</small></dd></div>
            <div><dt>成功阅读</dt><dd>{reads?.total ?? '未知'}<small>{reads ? ' 次' : ''}</small></dd></div>
            <div><dt>重复阅读</dt><dd>{reads?.repeated ?? '未知'}<small>{reads ? ' 次' : ''}</small></dd></div>
          </dl>
          {reads ? reads.documents.length ? <details className="chart-data">
            <summary>查看实际阅读的文档</summary>
            <ul className="memory-read-documents">{reads.documents.map(doc => <li key={doc.id}>
              <span>{doc.title}<small>{doc.id}</small></span><strong>{doc.readCount} 次</strong>
            </li>)}</ul>
          </details> : <p className="chart-note">完整 Trace 中没有成功读取文档的记录；工具记忆也可能保存其他工具结果。</p>
            : <p className="chart-note">未保存完整起止 Trace，无法确认阅读次数，不按零处理。</p>}
        </> : <p className="memory-review-error" role="alert">此侧记录读取失败：{result.status === 'rejected' && result.reason instanceof Error
          ? result.reason.message : '记录不可用'}。可重新读取；不会自动运行任务。</p>}
      </section>;
    })}</div>}
    <p className="chart-note">阅读统计复用资料工作台：仅实际成功返回匹配文档计数，同一文档首次之后的成功读取计为重复；失败、空返回与页面预览不计。当前一对不代表稳定收益。</p>
  </>;
}
