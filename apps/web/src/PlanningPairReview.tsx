import { useEffect, useRef, useState } from 'react';
import type { EpisodeArtifact, PairComparison, TraceEvent } from './apiContracts';
import { readEpisode } from './apiClient';
import { savedDocumentReads } from './flowFrames';
import { ReadableFields } from './ReadableFields';
import { explainFailure } from './traceSteps';
import { savedUsage } from './historySummary';

type PlanItemView = { id: string; goal: string; status: string; depends_on: unknown };

const PLAN_STATUS_LABELS: Record<string, string> = {
  pending: '声明待办', active: '声明进行中', done: '声明完成', cancelled: '声明取消',
};

/** The declared plan comes from PLAN_UPDATED events; it is a claim, not executed work. */
function declaredPlan(events: TraceEvent[]) {
  const updates = events.filter((event) => event.event_type === 'PLAN_UPDATED');
  const last = updates.at(-1);
  const raw = last && Array.isArray((last.payload as { items?: unknown }).items)
    ? (last.payload as { items: unknown[] }).items : [];
  const items = raw.filter((entry): entry is PlanItemView => Boolean(entry) && typeof entry === 'object'
    && typeof (entry as PlanItemView).id === 'string' && typeof (entry as PlanItemView).goal === 'string');
  return { declarations: updates.length, items };
}

/** Executed tools come from reached TOOL_STARTED events; only real arrivals count. */
function executedTools(events: TraceEvent[]) {
  const counts = new Map<string, number>();
  for (const event of events) {
    if (event.event_type !== 'TOOL_STARTED') continue;
    const name = (event.payload as { name?: unknown }).name;
    if (typeof name !== 'string') continue;
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  return [...counts].map(([name, count]) => ({ name, count }));
}

function hasCompleteTrace(events: TraceEvent[]): boolean {
  return events[0]?.event_type === 'EPISODE_STARTED' && events.at(-1)?.event_type === 'EPISODE_FINISHED';
}

/** Inspect two saved episodes on demand; the plan is shown separately from executed tools. */
export function PlanningPairReview({ pairs, labels }: { pairs: PairComparison[]; labels: [string, string] }) {
  const [selected, setSelected] = useState('0');
  const pair = pairs[Number(selected)] ?? pairs[0];
  if (!pair) return null;
  return <section className="memory-pair-review chart-panel" aria-label="规划执行差异">
    <div className="chart-heading"><div><span className="story-section-label">从实际执行判断差异</span><h3>声明的计划有没有对应到实际执行？</h3></div></div>
    <p className="chart-note">按一对保存记录查看，不重新运行模型。分别展示子目标声明和已开始的工具；仅凭工具次数不能认定子目标是否完成，需结合具体参数、返回和评测核对。</p>
    <label className="form-label" htmlFor="planning-review-pair">选择要审查的任务对</label>
    <select className="form-select" id="planning-review-pair" value={selected} onChange={event => setSelected(event.target.value)}>
      {pairs.map((item, index) => <option key={`${item.baseline_episode_id}:${item.recovery_episode_id}`} value={index}>
        {item.task_name} · Seed {item.seed} · 第 {item.repeat_index ?? 1} 次
      </option>)}
    </select>
    <SavedPlanningDetails key={`${pair.baseline_episode_id}:${pair.recovery_episode_id}`} pair={pair} labels={labels} />
  </section>;
}

function SavedPlanningDetails({ pair, labels }: { pair: PairComparison; labels: [string, string] }) {
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
      const usage = artifact ? savedUsage(artifact) : null;
      const complete = artifact ? hasCompleteTrace(artifact.events) : false;
      const plan = artifact && complete ? declaredPlan(artifact.events) : null;
      const tools = artifact && complete ? executedTools(artifact.events) : null;
      const reads = artifact ? savedDocumentReads(artifact.events) : null;
      const submission = artifact?.episode.final_state.submission;
      const submitted = typeof submission === 'object' && submission !== null && !Array.isArray(submission)
        ? submission as Record<string, unknown> : null;
      return <section key={id} className="memory-review-arm" aria-label={`${labels[index]}执行记录`}>
        <h4><i className={`chart-key arm-${index}`} />{labels[index]}</h4>
        <p className="memory-review-id">Episode：{id}</p>
        {artifact ? <>
          <p className="chart-note">规划组件：{artifact.agent.planning ? '已启用' : '未启用'}。
            {artifact.agent.planning && plan && plan.declarations === 0
              ? '本次未声明计划，不能按实际使用规划解读。' : ''}</p>
          <p><span className={`badge ${artifact.evaluation.success ? 'badge-green' : 'badge-red'}`}>
            {artifact.evaluation.success ? '评测通过' : '评测未通过'}</span> · {artifact.episode.termination_reason}</p>
          {artifact.episode.detail && <p className="chart-note">终止说明：{explainFailure(artifact.episode.detail)}</p>}
          <dl className="memory-review-counts">
            <div><dt>模型请求</dt><dd>{artifact.episode.model_call_count}<small> 次</small></dd></div>
            <div><dt>工具调用</dt><dd>{artifact.episode.tool_call_count}<small> 次</small></dd></div>
            <div><dt>成功阅读 / 重复</dt><dd>{reads ? `${reads.total} / ${reads.repeated}` : '未知'}<small>{reads ? ' 次' : ''}</small></dd></div>
          </dl>
          <p className="chart-note">已报告 Token{artifact.episode.token_usage.simulated ? '（模拟）' : ''}：{usage?.reportedTotal === null
            ? '未知（未报告）' : `输入 ${artifact.episode.token_usage.prompt_tokens} / 输出 ${artifact.episode.token_usage.completion_tokens}`}；保存耗时 {artifact.episode.duration_ms} ms。规划声明的开销计入本侧；未报告用量不据此补齐。</p>
          {!usage?.complete && <p className="chart-note">总用量未知，不能据已报告值计算完整节省比例。</p>}
          <h5>实际提交</h5>
          {submitted && typeof submitted.answer === 'string' ? <ReadableFields entries={['answer', 'evidence'].filter(key => key in submitted)
            .map(key => [key, submitted[key]])} /> : <p className="chart-note">此侧未保存已提交的答案；计划自称完成不代表实际提交。</p>}
          {reads && reads.documents.length > 0 && <details className="chart-data">
            <summary>成功读取的资料与提交引用</summary>
            <ul className="memory-read-documents">{reads.documents.map(doc => <li key={doc.id}>
              <span>{doc.title}<small>{doc.id}{doc.evidenceId ? ` · ${doc.evidenceId}` : ''}</small></span>
              <strong>{doc.readCount} 次{doc.cited ? ' · 提交引用' : ''}</strong>
            </li>)}</ul>
            <p className="chart-note">引用标记来自成功提交事件，不表示证据适用或答案正确；结论仍以原评测为准。</p>
          </details>}
          {complete && plan ? <>
            <p className="chart-note">计划声明：{plan.declarations} 次{plan.items.length ? '' : '（本侧未声明计划）'}</p>
            {plan.items.length > 0 && <ul className="memory-read-documents">{plan.items.map(item => <li key={item.id}>
              <span>{item.goal}<small>{item.id}</small></span>
              <strong>{PLAN_STATUS_LABELS[item.status] ?? item.status}</strong>
            </li>)}</ul>}
          </> : <p className="chart-note">未保存完整起止 Trace，计划声明未知，不按零处理。</p>}
          {complete && tools ? <details className="chart-data">
            <summary>已实际执行的工具</summary>
            <p className="chart-note">统计已到达的调用开始事件，包含后续失败或结果未知的调用，不代表执行成功。</p>
            <ul className="memory-read-documents">{tools.length ? tools.map(tool => <li key={tool.name}>
              <span>{tool.name}</span><strong>{tool.count} 次</strong>
            </li>) : <li><span>本侧没有已到达的工具执行事件。</span></li>}</ul>
          </details> : <p className="chart-note">未保存完整起止 Trace，已执行工具未知，不按零处理。</p>}
        </> : <p className="memory-review-error" role="alert">此侧记录读取失败：{result.status === 'rejected' && result.reason instanceof Error
          ? result.reason.message : '记录不可用'}。可重新读取；不会自动运行任务。</p>}
      </section>;
    })}</div>}
    <p className="chart-note">计划为模型声明的子目标，核验完成以 <code>submit_answer</code> 与环境返回为准；页面只展示已到达事件，不补写未发生的执行。当前一对不代表稳定收益。</p>
  </>;
}
