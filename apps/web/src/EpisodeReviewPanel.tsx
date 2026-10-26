import { useEffect, useState } from 'react';

import { readApi } from './apiClient';
import {
  episodeReviewListResponseSchema,
  episodeReviewResponseSchema,
  requireIdentity,
  type EpisodeArtifact,
  type EpisodeReview,
  type ModelOption,
} from './apiContracts';

type Verdict = 'pass' | 'fail' | 'uncertain';
type Rating = 'pass' | 'fail' | 'unknown';

const verdictLabels: Record<Verdict, string> = { pass: '通过', fail: '不通过', uncertain: '暂无法判断' };
const ratingLabels: Record<Rating, string> = { pass: '符合要求', fail: '存在问题', unknown: '暂无法判断' };

function renderReview(review: EpisodeReview, artifact: EpisodeArtifact) {
  return <article key={review.review_id} className="review-item">
    <div><span className="badge badge-yellow">
      模型复核 · {review.provider} · {review.model}
    </span><time dateTime={review.created_at}>{new Date(review.created_at).toLocaleString('zh-CN')}</time></div>
    {review.status === 'completed' ? <>
      <strong>{review.verdict ? verdictLabels[review.verdict] : '未知（未记录）'}</strong>
      <span className="review-agreement">{review.verdict === 'uncertain' ? '暂无法与规则评分比较'
        : (review.verdict === 'pass') === artifact.evaluation.success ? '与规则评分一致' : '与规则评分存在分歧，请检查下方理由'}</span>
      <p>{review.rationale}</p>
      <dl><div><dt>答案是否正确</dt><dd>{review.answer_correctness ? ratingLabels[review.answer_correctness] : '未知（未记录）'}</dd></div>
        <div><dt>依据是否充分</dt><dd>{review.evidence_support ? ratingLabels[review.evidence_support] : '未知（未记录）'}</dd></div>
        <div><dt>工具使用是否合规</dt><dd>{review.process_safety ? ratingLabels[review.process_safety] : '未知（未记录）'}</dd></div></dl>
    </> : <>
      <p className="review-failure">复核失败：{review.failure_code}</p>
      <p>{review.failure_code === 'INVALID_JUDGE_OUTPUT' ? '模型回复不符合约定的评审格式，未产生有效判断。'
        : review.failure_code === 'INVALID_EVENT_REFERENCE' ? '模型引用了本次运行以外的事件，评审未被接受。'
          : '评审服务请求失败，没有获得模型判断。'}规则评分保持不变。</p>
    </>}
    {review.status === 'completed' && (review.event_ids.length > 0 ? <details className="review-citations">
      <summary>查看判断依据（{review.event_ids.length} 条执行记录）</summary>
      <ul>{review.event_ids.map((id) => {
        const event = artifact.events.find((item) => item.event_id === id);
        return <li key={id}>{event ? `第 ${event.step_index} 步 · ${event.event_type}` : '引用记录未找到'} · {id}</li>;
      })}</ul>
    </details> : <p>本次判断未引用执行事件。</p>)}
    <details className="review-technical">
      <summary>技术详情 <span>版本、评审用量与来源</span></summary>
      <dl className="review-provenance" aria-label="已保存评审来源与用量">
        <div><dt>评分量表</dt><dd>{review.rubric_version}</dd></div>
        {review.method === 'llm_judge' && <>
          <div><dt>提示版本</dt><dd>{review.prompt_version}</dd></div>
          <div><dt>评审模型</dt><dd>{review.provider} / {review.model}</dd></div>
          <div><dt>评审 Token{review.token_usage?.simulated ? ' · 模拟' : ''}</dt>
            <dd>{review.token_usage ? `输入 ${review.token_usage.prompt_tokens} / 输出 ${review.token_usage.completion_tokens}` : '未知（未报告）'}</dd></div>
          <div><dt>评审估算费用</dt>
            <dd>{review.estimated_cost?.is_known ? `$${review.estimated_cost.amount} USD` : '未知（未验证）'}</dd></div>
          <div><dt>价格表版本</dt><dd>{review.estimated_cost?.price_table_version ?? '未记录'}</dd></div>
        </>}
      </dl>
    </details>
  </article>;
}

function csvCell(value: unknown): string {
  const text = String(value ?? '');
  const safe = /^[=+\-@]/.test(text) ? `'${text}` : text;
  return `"${safe.replace(/"/g, '""')}"`;
}

function downloadReviews(episodeId: string, reviews: EpisodeReview[]): void {
  const rows = reviews.map((review) => [
    review.review_id, review.episode_id, review.created_at, review.method, review.status,
    review.verdict, review.answer_correctness, review.evidence_support, review.process_safety,
    review.rationale, review.reviewer_label, review.provider, review.model, review.failure_code,
    review.event_ids.join('|'), review.episode_content_hash, review.review_input_hash,
    review.prompt_version, review.rubric_version,
    review.token_usage?.prompt_tokens, review.token_usage?.completion_tokens, review.token_usage?.simulated,
    review.estimated_cost?.is_known,
    review.estimated_cost?.is_known ? review.estimated_cost.amount : null,
    review.estimated_cost?.currency, review.estimated_cost?.price_table_version,
  ].map(csvCell).join(','));
  const header = [
    'review_id', 'episode_id', 'created_at', 'method', 'status', 'verdict',
    'answer_correctness', 'evidence_support', 'process_safety', 'rationale',
    'reviewer_label', 'provider', 'model', 'failure_code', 'event_ids',
    'episode_content_hash', 'review_input_hash',
    'prompt_version', 'rubric_version', 'prompt_tokens', 'completion_tokens', 'simulated',
    'cost_is_known', 'estimated_cost', 'currency', 'price_table_version',
  ].join(',');
  const blob = new Blob([`\ufeff${header}\n${rows.join('\n')}\n`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `episode-${episodeId}-reviews.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revoking on the same tick cancels the blob download; mirror the App helper.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

interface Props { artifact: EpisodeArtifact; models: ModelOption[] }

/** Read saved real Judge results; demo and manual creation are not product actions. */
export function EpisodeReviewPanel({ artifact, models }: Props) {
  const episodeId = artifact.episode.episode_id;
  const [reviews, setReviews] = useState<EpisodeReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [judgeModel, setJudgeModel] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const judgeModels = models.filter((model) => model.provider === 'aihubmix');
  const hasSubmission = typeof artifact.episode.final_state.submission === 'object'
    && artifact.episode.final_state.submission !== null;
  const modelAvailable = judgeModels.some((model) => model.id === judgeModel);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    setReviews([]);
    void (async () => {
      try {
        const response = await fetch(
          `/api/v1/episodes/${encodeURIComponent(episodeId)}/reviews`,
          { signal: controller.signal },
        );
        const data = await readApi(response, episodeReviewListResponseSchema);
        requireIdentity(data.episode_id, episodeId);
        if (controller.signal.aborted) return;
        setReviews(data.reviews);
      } catch (reason) {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '评审记录读取失败。');
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [episodeId]);

  const modelReviews = reviews.filter((review) => review.method === 'llm_judge' && review.provider !== 'fake')
    .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at));

  async function runJudge(): Promise<void> {
    if (saving || !hasSubmission || !modelAvailable) return;
    const requestedModel = judgeModel;
    setSaving(true);
    setSaveError('');
    try {
      const response = await fetch('/api/v1/episode-reviews', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ schema_version: '1.1', episode_id: episodeId,
          method: 'llm_judge', judge_provider: 'aihubmix', judge_model: requestedModel }),
      });
      const data = await readApi(response, episodeReviewResponseSchema);
      requireIdentity(data.review.episode_id, episodeId);
      if (data.review.method !== 'llm_judge' || data.review.provider !== 'aihubmix'
        || data.review.model !== requestedModel) throw new Error('评审返回的模型与本次选择不一致。');
      setReviews((current) => [...current, data.review]);
    } catch (reason) {
      setSaveError(reason instanceof Error ? reason.message : '评审请求失败。');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card episode-review-card" aria-labelledby="episode-review-title">
      <div className="card-title review-heading">
        <div>
          <h2 id="episode-review-title" className="section-heading">大模型评审</h2>
          <p className="card-desc">让模型检查答案、依据和工具使用，并给出理由。它可能误判，原规则评分保持不变。</p>
        </div>
        {reviews.length > 0 && <button className="btn-secondary" type="button"
          onClick={() => downloadReviews(episodeId, reviews)}>导出全部记录 CSV</button>}
      </div>
      <div className="review-judge-controls">
        <label className="form-label">评审模型
          <select className="form-select" value={judgeModel} disabled={saving}
            onChange={(event) => setJudgeModel(event.target.value)}>
            <option value="">请选择真实模型</option>
            {judgeModels.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}
          </select>
        </label>
        <button className="btn-primary" type="button" disabled={loading || saving || !hasSubmission || !modelAvailable}
          onClick={runJudge}>{saving ? '正在评审…' : '评审本次结果'}</button>
      </div>
      <p className="metric-sub">点击后发起一次真实模型请求，评审用量单独记录；不自动重试，不改变 Agent 的执行结果。</p>
      {!hasSubmission && <p className="metric-sub">本次没有已保存的最终提交，暂不能进行模型评审。</p>}
      {judgeModels.length === 0 && <p className="metric-sub">暂无可选的真实模型，请先恢复模型目录。</p>}
      {(loading || saving) && <p role="status">{saving ? '正在等待模型评审结果，不会额外重试…' : '正在读取已保存的模型评审…'}</p>}
      {(error || saveError) && <p role="alert" className="review-failure">{saveError || `模型评审记录读取失败：${error}`}</p>}
      <div className="review-baseline" aria-label="确定性评分">
        <strong>规则评分：{artifact.evaluation.success ? '通过' : '未通过'}</strong>
        <span>与下方模型判断分别保留，不互相覆盖</span>
      </div>
      <div className="review-list">{modelReviews.map((review) => renderReview(review, artifact))}</div>
      {!loading && !error && modelReviews.length === 0 && <p className="metric-sub">尚无大模型评审。选择模型后点击上方按钮，才会生成判断与理由。</p>}
      {reviews.length > modelReviews.length && <details className="review-archive">
        <summary>旧人工／模拟记录（{reviews.length - modelReviews.length} 条，仅归档）</summary>
        <p>这些记录不作为大模型评审结论。完整字段保留在上方 CSV 导出与历史 API 中。</p>
      </details>}
    </section>
  );
}
